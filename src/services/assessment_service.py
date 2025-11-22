from typing import Dict, List, Iterable, Optional, Any
import json
import os
from pathlib import Path

from src.api.v1.schemas.assessment import (
    RiasecCodeRequest,
    RiasecResult,
    SkillDefinition,
    SkillRatingsSubmission,
    SkillWeightsResponse,
    SkillWeighted,
    InterestQuizRequest,
    InterestQuizResponse,
    SkillTriageResponse,
)
from src.repositories.assessment_repo import AssessmentRepository
from src.repositories.riasec_repo import RiasecRepository
from .static_references.riasec_combo_map import canonical_riasec
from sqlalchemy.orm import Session

STATIC_DIR = Path(__file__).parent / "static_references"
SKILLS_FILE = STATIC_DIR / "oneStop40Skills.json"


class AssessmentService:
    """Service layer for RIASEC interest and skill weighting workflows."""

    def __init__(self) -> None:
        self._skills_cache: List[SkillDefinition] | None = None

    # ---------------- Utility -----------------
    def _load_skill_definitions(self) -> List[SkillDefinition]:
        if self._skills_cache is not None:
            return self._skills_cache
        raw = json.loads(SKILLS_FILE.read_text())
        defs: List[SkillDefinition] = []
        for row in raw:
            defs.append(
                SkillDefinition(
                    element_id=row["ElementId"],
                    name=row["ElementName"],
                    question=row.get("Question", ""),
                    easy_read_description=row.get("EasyReadDescription", ""),
                    anchor_first=row.get("AnchorFirst", ""),
                    anchor_third=row.get("AnchorThrid", ""),
                    anchor_last=row.get("AnchorLast", ""),
                    data_point_20=row.get("DataPoint20", 0.0),
                    data_point_35=row.get("DataPoint35", 0.0),
                    data_point_50=row.get("DataPoint50", 0.0),
                    data_point_65=row.get("DataPoint65", 0.0),
                    data_point_80=row.get("DataPoint80", 0.0),
                )
            )
        self._skills_cache = defs
        return defs

    # ---------------- Interest (RIASEC) -----------------
    def process_riasec_code(self, payload: RiasecCodeRequest, db: Session) -> RiasecResult:
        """Return interest-filtered occupations with balanced composite scoring + baseline skill panel.

        Uses enriched interest_job_signals table when available for balanced scoring that properly
        represents all letters in the RIASEC code. Falls back to basic interest_matched_jobs ordering.
        
        Optionally integrates CareerOneStop SKA (Skills Matcher) ranking when include_ska=True.
        
        Scoring methodology:
        - Fetches enriched signals with per-letter scores, positions, and presence flags
        - Computes balanced composite interest score combining:
          * interest_sum normalization (35%)
          * balanced per-letter score - min of normalized letter scores (25%)
          * coverage ratio - fraction of code letters in occupation's top-3 (20%)
          * rarity bonus - inverse frequency weighting for underrepresented letters (20%)
        - Optionally blends with SKA ranking when available
        - Returns up to 150 occupations (configurable via limit param, default 50, max 150)
        """
        repo = RiasecRepository(db)
        canonical_code = canonical_riasec(payload.riasec_code)
        include_ska = getattr(payload, "include_ska", False)
        
        # Determine how many jobs to return (default 50, clamp 1..150 for enriched path)
        try:
            limit = int(getattr(payload, "limit", 50) or 50)
        except Exception:
            limit = 50
        if limit < 1:
            limit = 1
        elif limit > 150:
            limit = 150
        
        # Try enriched signals path first
        signals = repo.get_enriched_interest_signals(canonical_code, limit=limit)
        ska_available = False
        skill_frequencies: Optional[Dict[str, int]] = None
        
        if signals:
            # Use balanced composite scoring
            if include_ska:
                # Attempt SKA integration
                scored_jobs, ska_available = self._compute_ska_enhanced_scores(
                    signals, canonical_code, db
                )
            else:
                scored_jobs = self._compute_balanced_scores(signals, canonical_code)
            
            # Get skill frequencies for this RIASEC code
            skill_freq_rows = repo.get_interest_filtered_skills(canonical_code)
            skill_frequencies = {
                row["element_id"]: row["total_frequency"]
                for row in skill_freq_rows
            }
            
            top_jobs_data = scored_jobs[:limit]
            occupation_pool = [j["occ_code"] for j in top_jobs_data]
            top10_jobs = [
                {
                    "onet_code": j["occ_code"],
                    "title": j["title"],
                    "median_salary": j.get("median_salary"),
                    "growth_outlook": j.get("growth_outlook"),
                    "composite_score": j.get("composite_score"),
                    "interest_sum": j.get("interest_sum"),
                    "interests_count": j.get("interests_count"),
                    "ska_rank": j.get("ska_rank"),
                }
                for j in top_jobs_data
            ]
        else:
            # Fallback to basic ordering (legacy path)
            profile = repo.get_profile(canonical_code)
            if profile:
                top_jobs_data = repo.top_matched_jobs(profile, limit=min(limit, 50))
                occupation_pool = [j["occ_code"] for j in top_jobs_data]
                top10_jobs = [
                    {
                        "onet_code": j["occ_code"], 
                        "title": j["title"],
                        "median_salary": j.get("median_salary"),
                        "growth_outlook": j.get("growth_outlook")
                    }
                    for j in top_jobs_data
                ]
            else:
                occupation_pool = []
                top10_jobs = []
        
        skills_panel = self._load_skill_definitions()
        return RiasecResult(
            riasec_code=canonical_code,
            occupation_pool=occupation_pool,
            top10_jobs=top10_jobs,  # type: ignore[arg-type]
            skills_panel=skills_panel,
            skill_frequencies=skill_frequencies,
            ska_available=ska_available if include_ska else None,
        )
    
    def _compute_balanced_scores(self, signals: List[Dict], code: str) -> List[Dict]:
        """Compute balanced composite interest score for occupations.
        
        Uses enriched per-letter signals to create a balanced ranking that represents
        all letters in the user's RIASEC code, preventing underrepresentation of any dimension.
        
        Parameters
        ----------
        signals : list of dict
            Enriched signal rows from interest_job_signals table
        code : str
            RIASEC code (e.g., 'ACR')
            
        Returns
        -------
        list of dict
            Occupations sorted by composite_score DESC, each with occ_code, title, 
            median_salary, growth_outlook, composite_score fields
        """
        if not signals:
            return []
        
        code_letters = [c.lower() for c in code]
        max_interest_sum = float(max(s.get("interest_sum", 1) for s in signals) or 1)
        
        # Collect letter rarity (count how many occupations have each letter in top-3)
        letter_counts: Dict[str, int] = {l: 0 for l in ["r","i","a","s","e","c"]}
        for s in signals:
            for l in letter_counts:
                if s.get(f"contains_{l}"):
                    letter_counts[l] += 1
        max_possible_rarity = sum(1 / (letter_counts[l] or 1) for l in code_letters)
        
        # Precompute max scores per letter for normalization
        max_letter_score: Dict[str, float] = {l: 0.0 for l in ["r","i","a","s","e","c"]}
        for s in signals:
            for l in max_letter_score:
                val = float(s.get(f"score_{l}") or 0.0)
                if val > max_letter_score[l]:
                    max_letter_score[l] = val
        
        # Compute composite score for each occupation
        scored = []
        for s in signals:
            interest_sum_norm = float(s.get("interest_sum", 0) or 0) / max_interest_sum
            
            # Balanced score: minimum of normalized per-letter scores (penalizes missing letters)
            per_letter_norms = [
                float(s.get(f"score_{l}") or 0.0) / (max_letter_score[l] or 1) 
                for l in code_letters
            ]
            balanced_score = min(per_letter_norms) if per_letter_norms else 0.0
            
            # Coverage: fraction of code letters present in occupation's top-3
            present_count = sum(1 for l in code_letters if s.get(f"contains_{l}"))
            coverage_ratio = present_count / len(code_letters)
            
            # Rarity bonus: reward occupations with underrepresented letters
            rarity_bonus = sum(
                1 / (letter_counts[l] or 1) 
                for l in code_letters 
                if s.get(f"contains_{l}")
            )
            rarity_bonus_norm = (rarity_bonus / max_possible_rarity) if max_possible_rarity else 0.0
            
            # Composite: weighted blend
            composite = (
                0.35 * interest_sum_norm + 
                0.25 * balanced_score + 
                0.20 * coverage_ratio + 
                0.20 * rarity_bonus_norm
            )
            
            scored.append({
                "occ_code": s["occ_code"],
                "title": s.get("title"),
                "median_salary": s.get("median_annual_wage"),
                "growth_outlook": s.get("employment_outlook"),
                "composite_score": round(composite, 5),
                "interest_sum": s.get("interest_sum"),
                "interests_count": s.get("interests_count"),
            })
        
        # Sort by composite score descending
        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        return scored
    
    def _compute_ska_enhanced_scores(
        self, signals: List[Dict], code: str, db: Session
    ) -> tuple[List[Dict], bool]:
        """Compute SKA-enhanced composite scores by blending interest scores with CareerOneStop ranking.
        
        Parameters
        ----------
        signals : list of dict
            Enriched signal rows from interest_job_signals table
        code : str
            RIASEC code (e.g., 'ACR')
        db : Session
            Database session for skill frequency queries
            
        Returns
        -------
        tuple[list of dict, bool]
            (scored occupations sorted by composite_score DESC, ska_available flag)
        """
        # First compute interest-only scores
        interest_scored = self._compute_balanced_scores(signals, code)
        
        # Attempt to get SKA rankings
        ska_available = False
        ska_rank_map: Dict[str, int] = {}
        
        # Check if COS credentials are available
        from src.core.config import ONESTOP_USERID, ONESTOP_API_KEY
        if ONESTOP_USERID and ONESTOP_API_KEY:
            # Aggregate skill frequencies for SKA payload
            repo = RiasecRepository(db)
            skill_freq_rows = repo.get_interest_filtered_skills(code)
            freq_map = {row["element_id"]: row["total_frequency"] for row in skill_freq_rows}
            
            # Build SKA payload
            ska_payload = self._build_ska_payload(freq_map)
            
            # Call CareerOneStop API
            assessment_repo = AssessmentRepository()
            ska_results = assessment_repo.get_150_jobs_from_cos(ska_payload)
            
            if ska_results:
                ska_available = True
                # Build rank map (occ_code -> rank position)
                for idx, job in enumerate(ska_results, 1):
                    occ_code = job.get("OnetCode") or job.get("onet_code")
                    if occ_code:
                        ska_rank_map[occ_code] = idx
        
        # Merge SKA ranks into interest scores
        if ska_available and ska_rank_map:
            max_rank = len(ska_rank_map)
            for job in interest_scored:
                ska_rank = ska_rank_map.get(job["occ_code"])
                if ska_rank:
                    job["ska_rank"] = ska_rank
                    # Blend SKA into composite: 60% interest + 40% SKA component
                    interest_component = job["composite_score"]
                    ska_score_norm = (max_rank - ska_rank + 1) / max_rank
                    job["composite_score"] = round(
                        0.6 * interest_component + 0.4 * ska_score_norm, 5
                    )
            
            # Re-sort by updated composite score
            interest_scored.sort(key=lambda x: x["composite_score"], reverse=True)
        
        return interest_scored, ska_available
    
    def _build_ska_payload(self, freq_map: Dict[str, int]) -> Dict[str, Any]:
        """Build CareerOneStop SKA payload from skill frequency map.
        
        Parameters
        ----------
        freq_map : dict
            Mapping of element_id -> total_frequency
            
        Returns
        -------
        dict
            SKA payload with SKAValueList
        """
        skill_defs = self._load_skill_definitions()
        skill_def_map = {d.element_id: d for d in skill_defs}
        
        ska_values = []
        for element_id, frequency in freq_map.items():
            skill_def = skill_def_map.get(element_id)
            if skill_def:
                # Normalize frequency to 1-5 scale (simple approach)
                # Higher frequency = higher rating
                max_freq = max(freq_map.values()) if freq_map else 1
                normalized = (frequency / max_freq) * 4 + 1  # Scale to 1-5
                rating = min(5.0, max(1.0, normalized))
                
                ska_values.append({
                    "ElementId": element_id,
                    "ElementName": skill_def.name,
                    "SKARating": round(rating, 1)
                })
        
        return {"SKAValueList": ska_values}

    # ---------------- Skill Weighting -----------------
    def compute_skill_weights(
        self, submission: SkillRatingsSubmission
    ) -> SkillWeightsResponse:
        """Compute adjusted weights from user ratings and baseline definitions.

        Algorithm (initial draft):
        - normalized_score = (raw_rating - dp20) / (dp80 - dp20), clipped 0..1
        - adjusted_weight = normalized_score * (1 + mid_gap_factor)
          where mid_gap_factor = (dp80 - dp50) / (dp80) to slightly boost skills with long tail of mastery.
        - category_weights: aggregate adjusted_weight by skill 'name' token root (simple placeholder grouping)
        """
        defs = {d.element_id: d for d in self._load_skill_definitions()}
        weighted: List[SkillWeighted] = []
        category_acc: Dict[str, float] = {}

        for element_id, raw in submission.ratings.items():
            skill_def = defs.get(element_id)
            if not skill_def:
                continue
            span = max(skill_def.data_point_80 - skill_def.data_point_20, 1e-6)
            normalized = (raw - skill_def.data_point_20) / span
            if normalized < 0:
                normalized = 0.0
            elif normalized > 1:
                normalized = 1.0
            mid_gap_factor = (skill_def.data_point_80 - skill_def.data_point_50) / max(skill_def.data_point_80, 1e-6)
            adjusted = normalized * (1 + mid_gap_factor)
            weighted.append(
                SkillWeighted(
                    element_id=element_id,
                    raw_rating=raw,
                    normalized_score=round(normalized, 4),
                    adjusted_weight=round(adjusted, 4),
                )
            )
            # Simple category key: first word of name
            cat_key = skill_def.name.split()[0]
            category_acc[cat_key] = category_acc.get(cat_key, 0.0) + adjusted

        # Normalize category weights to sum=1
        total_cat = sum(category_acc.values()) or 1.0
        category_weights_norm = {k: round(v / total_cat, 4) for k, v in category_acc.items()}

        return SkillWeightsResponse(
            riasec_code=submission.riasec_code,
            weighted_skills=sorted(weighted, key=lambda w: w.adjusted_weight, reverse=True),
            category_weights=category_weights_norm,
        )

    # ---------------- Backward compatibility placeholders -----------------
    def process_interest_quiz(self, payload: InterestQuizRequest) -> InterestQuizResponse:
        scores: Dict[str, float] = {"R": 8.5, "I": 7.0, "A": 6.0, "S": 5.0, "E": 4.0, "C": 3.0}
        return InterestQuizResponse(
            session_id="demo-session",
            top_codes=["RIA"],
            scores=scores,
        )

    def triage_skills(self) -> SkillTriageResponse:
        skills: List[Dict[str, object]] = [
            {"skill_id": "2.A.1.a", "name": "Active Listening", "frequency": 95},
            {"skill_id": "2.A.1.b", "name": "Critical Thinking", "frequency": 90},
        ]
        return SkillTriageResponse(skills=skills)
