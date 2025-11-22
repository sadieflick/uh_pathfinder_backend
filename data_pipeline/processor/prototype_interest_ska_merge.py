"""Prototype script: merge interest-matched occupations (up to 150) with CareerOneStop SKA-ranked jobs.

Flow (offline prototype before API endpoint integration):
1. Fetch top interest-matched jobs (ordered by interests_count DESC, interest_sum DESC).
2. Aggregate skill frequencies for the RIASEC code (riasec.interest_filtered_skills) -> frequency map.
3. Load baseline 40-skill panel definitions to get anchor distribution points.
4. Generate SKA payload (DataValue per skill) using blended formula:
      DataValue = 2.0 + 3.0 * freq_norm * mastery_factor
   where:
      freq_norm = frequency / max_frequency (0..1)
      mastery_factor = (dp80 - dp50) / max(dp80, 1e-6)  (amplifies skills with long mastery tail)
   Clamp to [1.0, 5.0] and round to 3 decimals.
5. Call CareerOneStop API (if credentials present) else fallback to empty SKA list.
6. Merge lists assigning scores:
      interest_score_norm = interest_sum / max_interest_sum
      interest_count_norm = interests_count / 3.0
      ska_score_norm      = (max_rank - rank + 1)/max_rank  (higher is better) if rank available.
   combined_score = 0.5*interest_score_norm + 0.2*interest_count_norm + 0.3*ska_score_norm
7. Output merged JSON (sorted by combined_score DESC) to stdout or optional file.

Usage:
    python prototype_interest_ska_merge.py --code ACR --limit 150 --output merged_ACR.json --dry-run

Flags:
    --dry-run : Skip CareerOneStop API call, simulate ska ranks as empty.

Notes:
    This is a prototype; formulas may evolve. Safe to iterate before wiring into endpoint.
"""
from __future__ import annotations

import os
import json
import argparse
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from src.repositories.riasec_repo import RiasecRepository
from src.services.static_references.example_ska_values import ska_values as example_ska
from src.services.assessment_service import AssessmentService  # for skill definitions
from src.repositories.assessment_repo import AssessmentRepository


@dataclass
class InterestJob:
    occ_code: str
    title: str
    interests_count: int
    interest_sum: int
    median_salary: float | None
    growth_outlook: str | None


def get_db_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("TEST_DATABASE_URL")
        or "postgresql://postgres:cronk112482@localhost:5432/uhpathfinder"
    )


def fetch_interest_jobs(db: Session, code: str, limit: int) -> List[InterestJob]:
    """Fallback interest jobs fetch (original basic ordering)."""
    repo = RiasecRepository(db)
    rows = repo.top_interest_matched_jobs(code, limit=limit)
    return [
        InterestJob(
            occ_code=r["occ_code"],
            title=r["title"],
            interests_count=int(r["interests_count"]),
            interest_sum=int(r["interest_sum"]),
            median_salary=r.get("median_salary"),
            growth_outlook=r.get("growth_outlook"),
        )
        for r in rows
    ]


def fetch_interest_signals(db: Session, code: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """Fetch enriched interest signals from riasec.interest_job_signals if table exists.

    Returns list of dict rows or None if table missing.
    """
    # Check existence
    exists_sql = text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema='riasec' AND table_name='interest_job_signals'
        ) AS ok
    """)
    if not db.execute(exists_sql).scalar():
        return None
    sql = text("""
        SELECT * FROM riasec.interest_job_signals
        WHERE UPPER(fk_riasec_code)=UPPER(:code)
        LIMIT :limit
    """)
    rows = db.execute(sql, {"code": code, "limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def aggregate_skill_frequency(db: Session, riasec_code: str) -> Dict[str, int]:
    repo = RiasecRepository(db)
    rows = repo.get_interest_filtered_skills(riasec_code)
    freq_map: Dict[str, int] = {}
    for row in rows:
        freq_map[row["element_id"]] = int(row["total_frequency"])
    return freq_map


def build_ska_payload(skill_defs, freq_map: Dict[str, int]) -> Dict[str, Any]:
    if not freq_map:
        return example_ska  # fallback example
    max_freq = max(freq_map.values()) or 1
    payload_list = []
    for d in skill_defs:
        freq = freq_map.get(d.element_id, 0)
        freq_norm = freq / max_freq  # 0..1
        mastery_factor = (d.data_point_80 - d.data_point_50) / max(d.data_point_80, 1e-6)
        data_value = 2.0 + 3.0 * freq_norm * mastery_factor
        if data_value < 1.0:
            data_value = 1.0
        if data_value > 5.0:
            data_value = 5.0
        payload_list.append({"ElementId": d.element_id, "DataValue": f"{data_value:.3f}"})
    return {"SKAValueList": payload_list}


def call_cos_api(payload: Dict[str, Any], dry_run: bool) -> List[Dict[str, Any]]:
    if dry_run:
        return []
    repo = AssessmentRepository()
    return repo.get_150_jobs_from_cos(payload)


def compute_balanced_interest_scores(signals: List[Dict[str, Any]], code: str) -> Dict[str, float]:
    """Compute balanced per-occ composite interest-only score using enriched signals.

    Formula components (per occupation):
      interest_sum_norm = interest_sum / max_interest_sum
      coverage_ratio    = (# code letters with contains_* true) / len(code)
      balanced_score    = min(normalized letter scores among code letters)
      rarity_bonus_norm = sum(1 / letter_total_count for each code letter present) / max_possible

    composite_interest = 0.35*interest_sum_norm + 0.25*balanced_score + 0.2*coverage_ratio + 0.2*rarity_bonus_norm
    """
    if not signals:
        return {}
    code_letters = [c.lower() for c in code]
    max_interest_sum = float(max(s.get("interest_sum", 1) for s in signals) or 1)

    # Collect total counts per letter for rarity (presence counts via contains_letter)
    letter_counts: Dict[str, int] = {l: 0 for l in ["r","i","a","s","e","c"]}
    for s in signals:
        for l in letter_counts:
            if s.get(f"contains_{l}"):
                letter_counts[l] += 1
    # Max possible rarity sum for normalization
    max_possible = sum(1 / (letter_counts[l] or 1) for l in code_letters)
    
    # Precompute max scores per letter
    max_letter_score: Dict[str, float] = {l:0.0 for l in ["r","i","a","s","e","c"]}
    for s in signals:
        for l in max_letter_score:
            val = float(s.get(f"score_{l}") or 0.0)
            if val > max_letter_score[l]:
                max_letter_score[l] = val
    
    # Compute per-occupation composite scores
    scores_out: Dict[str, float] = {}
    for s in signals:
        occ = s["occ_code"]
        interest_sum_norm = float(s.get("interest_sum", 0) or 0) / max_interest_sum
        per_letter_norms = [ float(s.get(f"score_{l}") or 0.0) / (max_letter_score[l] or 1) for l in code_letters]
        balanced_score = min(per_letter_norms) if per_letter_norms else 0.0
        present_count = sum(1 for l in code_letters if s.get(f"contains_{l}"))
        coverage_ratio = present_count / len(code_letters)
        rarity_bonus = sum(1 / (letter_counts[l] or 1) for l in code_letters if s.get(f"contains_{l}"))
        rarity_bonus_norm = (rarity_bonus / max_possible) if max_possible else 0.0
        composite = 0.35*interest_sum_norm + 0.25*balanced_score + 0.2*coverage_ratio + 0.2*rarity_bonus_norm
        scores_out[occ] = composite
    return scores_out


def merge_rankings(interest_jobs: List[InterestJob], ska_rank_list: List[Dict[str, Any]],
                   interest_balanced_scores: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    # Map SKA ranks by occupation code (case-insensitive match; SKA uses ONetCode or similar key)
    ska_map: Dict[str, Dict[str, Any]] = {}
    for idx, entry in enumerate(ska_rank_list, start=1):
        code = entry.get("ONetCode") or entry.get("OccupationCode") or entry.get("occ_code")
        if not code:
            continue
        ska_map[code] = {"rank": idx, "raw": entry}

    max_interest_sum = max((j.interest_sum for j in interest_jobs), default=1)
    max_rank = max((v["rank"] for v in ska_map.values()), default=1)

    merged: List[Dict[str, Any]] = []
    for job in interest_jobs:
        ska_entry = ska_map.get(job.occ_code)
        interest_score_norm = job.interest_sum / max_interest_sum
        interest_count_norm = job.interests_count / 3.0  # code length baseline
        ska_score_norm = (
            (max_rank - ska_entry["rank"] + 1) / max_rank if ska_entry else 0.0
        )
        # If we have balanced interest composite, blend it; otherwise fallback to original weights
        balanced_component = interest_balanced_scores.get(job.occ_code) if interest_balanced_scores else None
        if balanced_component is not None:
            # Blend: 0.6 balanced interest composite + 0.4 ska component (ska component uses existing split)
            ska_component = (0.5 * interest_score_norm + 0.2 * interest_count_norm + 0.3 * ska_score_norm)
            combined = 0.6 * balanced_component + 0.4 * ska_component
            interest_explainer = {
                "interest_sum_norm": round(interest_score_norm, 4),
                "interest_count_norm": round(interest_count_norm, 4),
                "ska_score_norm": round(ska_score_norm, 4),
                "balanced_interest": round(balanced_component, 4)
            }
        else:
            combined = 0.5 * interest_score_norm + 0.2 * interest_count_norm + 0.3 * ska_score_norm
            interest_explainer = {
                "interest_sum_norm": round(interest_score_norm, 4),
                "interest_count_norm": round(interest_count_norm, 4),
                "ska_score_norm": round(ska_score_norm, 4)
            }
        merged.append(
            {
                "occ_code": job.occ_code,
                "title": job.title,
                "interests_count": job.interests_count,
                "interest_sum": job.interest_sum,
                "median_salary": job.median_salary,
                "growth_outlook": job.growth_outlook,
                "ska_rank": ska_entry.get("rank") if ska_entry else None,
                "combined_score": round(combined, 5),
                "source": "interest+ska" if ska_entry else "interest_only",
                "score_components": interest_explainer,
            }
        )

    # Optionally append SKA-only occupations not in interest list (if we wanted reach expansion)
    # Skipped in prototype for simplicity.

    merged.sort(key=lambda x: x["combined_score"], reverse=True)
    return merged


def main():
    parser = argparse.ArgumentParser(description="Prototype merged interest/SKA ranking")
    parser.add_argument("--code", required=True, help="RIASEC 3-letter code (e.g., ACR)")
    parser.add_argument("--limit", type=int, default=150, help="Max interest-matched occupations")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Skip CareerOneStop API call")
    args = parser.parse_args()

    engine = create_engine(get_db_url())
    with engine.connect() as conn:
        session = Session(bind=conn)
        try:
            signals = fetch_interest_signals(session, args.code, args.limit)
            if signals is not None:
                print(f"Using enriched interest signals table for code {args.code}.")
                # Convert signals back to InterestJob (basic fields) for merge path
                interest_jobs = [
                    InterestJob(
                        occ_code=s["occ_code"],
                        title="(title unknown)" if False else s["occ_code"],  # title may not be stored, fallback occ_code
                        interests_count=int(s.get("interests_count", 0)),
                        interest_sum=int(s.get("interest_sum", 0)),
                        median_salary=None,
                        growth_outlook=None,
                    ) for s in signals
                ]
                interest_balanced_scores = compute_balanced_interest_scores(signals, args.code)
            else:
                interest_jobs = fetch_interest_jobs(session, args.code, args.limit)
                interest_balanced_scores = None
                print(f"Fetched {len(interest_jobs)} basic interest-matched jobs for code {args.code}.")
            freq_map = aggregate_skill_frequency(session, args.code)
            print(f"Aggregated {len(freq_map)} skill frequencies (subset of 40).")
            svc = AssessmentService()
            skill_defs = svc._load_skill_definitions()
            ska_payload = build_ska_payload(skill_defs, freq_map)
            print("Generated SKA payload with", len(ska_payload.get("SKAValueList", [])), "skills.")
            ska_rank_list = call_cos_api(ska_payload, args.dry_run)
            print(f"Retrieved {len(ska_rank_list)} SKA-ranked jobs from API.")
            merged = merge_rankings(interest_jobs, ska_rank_list, interest_balanced_scores=interest_balanced_scores)
            print(f"Merged list size: {len(merged)}")
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(merged, f, indent=2)
                print(f"Wrote merged ranking to {args.output}")
            else:
                # Print top 15 preview
                print(json.dumps(merged[:15], indent=2))
        finally:
            session.close()


if __name__ == "__main__":
    main()
