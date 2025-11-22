"""Build the riasec.interest_job_signals table.

This table enriches each (occ_code, fk_riasec_code) pair from
riasec.interest_matched_jobs with per-letter interest scores, boolean
presence flags, positional ranks, and existing aggregate metrics.

Rationale:
    Current ordering (interests_count DESC, interest_sum DESC) overweights
    occupations that share any two letters, starving representation of the
    third (e.g. Artistic 'A' in ACR). A richer signal layer enables balanced
    composite scoring (e.g. penalizing missing letters, rewarding balanced
    presence, rarity weighting, etc.).

Source tables assumed:
    - riasec.interest_matched_jobs (columns: occ_code, fk_riasec_code, interest_sum, interests_count, ...)
    - onet.interest (columns include onetsoc_code, element_id (R/I/A/S/E/C), data_value)

Table DDL (run manually in pgAdmin because Alembic ignores riasec schema):
    CREATE TABLE riasec.interest_job_signals (
        occ_code TEXT NOT NULL,
        fk_riasec_code TEXT NOT NULL,
        score_r NUMERIC,
        score_i NUMERIC,
        score_a NUMERIC,
        score_s NUMERIC,
        score_e NUMERIC,
        score_c NUMERIC,
        contains_r BOOLEAN,
        contains_i BOOLEAN,
        contains_a BOOLEAN,
        contains_s BOOLEAN,
        contains_e BOOLEAN,
        contains_c BOOLEAN,
        position_r SMALLINT,  -- 1=highest among RIASEC for occ, 6=lowest
        position_i SMALLINT,
        position_a SMALLINT,
        position_s SMALLINT,
        position_e SMALLINT,
        position_c SMALLINT,
        interest_sum NUMERIC,
        interests_count SMALLINT,
        PRIMARY KEY (occ_code, fk_riasec_code)
    );
    CREATE INDEX idx_interest_job_signals_code ON riasec.interest_job_signals(fk_riasec_code);
    CREATE INDEX idx_interest_job_signals_occ ON riasec.interest_job_signals(occ_code);

Population logic:
    1. Pivot onet.interest rows for each occupation into (score_r,...score_c).
    2. Rank per-letter scores (1..6) to derive position_* columns.
    3. Determine contains_* flags: a letter is considered "contained" for a given fk_riasec_code if that letter appears in the RIASEC code OR is in the occupation's top 3 scores (configurable; choose one).
       Current implementation: flag True if letter is in the occupation's top 3 scores AND appears in fk_riasec_code (stricter, focusing on user profile alignment).
    4. Join to interest_matched_jobs for interest_sum, interests_count.
    5. Upsert rows.

Usage:
    python build_interest_job_signals.py --commit
    python build_interest_job_signals.py --code ACR --commit

    Omit --commit for a dry-run preview.
"""
from __future__ import annotations

import os
import argparse
from typing import Dict, List, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def get_db_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("TEST_DATABASE_URL")
        or "postgresql://postgres:cronk112482@localhost:5432/uhpathfinder"
    )


def fetch_interest_base(session: Session, code_filter: str | None) -> List[Dict]:
    """Fetch base joined data (interest_matched_jobs + all per-letter scores)."""
    filt_sql = "" if not code_filter else "AND UPPER(imj.fk_riasec_code)=UPPER(:code)"
    sql = text(f"""
        SELECT imj.occ_code,
               imj.fk_riasec_code,
               imj.interest_sum,
               imj.interests_count,
               i.element_id,
               i.data_value
        FROM riasec.interest_matched_jobs imj
        JOIN onet.interests i ON i.onetsoc_code = imj.occ_code
        WHERE 1=1 {filt_sql}
        ORDER BY imj.occ_code
    """)
    params = {"code": code_filter} if code_filter else {}
    rows = session.execute(sql, params).mappings().all()
    return rows


def pivot_scores(rows: List[Dict]) -> Dict[Tuple[str, str], Dict]:
    """Pivot element_id (R/I/A/S/E/C) to per-letter scores per (occ_code, fk_code)."""
    # Map O*NET element_id to RIASEC letter
    element_to_letter = {
        "1.B.1.a": "r",
        "1.B.1.b": "i",
        "1.B.1.c": "a",
        "1.B.1.d": "s",
        "1.B.1.e": "e",
        "1.B.1.f": "c",
    }
    out: Dict[Tuple[str, str], Dict] = {}
    for r in rows:
        key = (r["occ_code"], r["fk_riasec_code"])
        bucket = out.setdefault(
            key,
            {
                "occ_code": r["occ_code"],
                "fk_riasec_code": r["fk_riasec_code"],
                "interest_sum": r["interest_sum"],
                "interests_count": r["interests_count"],
                "scores": {},
            },
        )
        element_id = r["element_id"]
        letter = element_to_letter.get(element_id)
        if letter:
            bucket["scores"][f"score_{letter}"] = float(r["data_value"]) if r["data_value"] is not None else None
    return out


def compute_positions_and_flags(pivot: Dict[Tuple[str, str], Dict]) -> None:
    for data in pivot.values():
        scores = data["scores"]
        # Ensure all letters present (may be None if missing)
        for l in "ria sec".replace(" ", ""):
            scores.setdefault(f"score_{l}", 0.0)
        ordered = sorted(
            [(l, scores[f"score_{l}"]) for l in ["r", "i", "a", "s", "e", "c"]],
            key=lambda x: x[1],
            reverse=True,
        )
        # Assign position (1..6) based on descending score
        position_map = {letter: idx + 1 for idx, (letter, _) in enumerate(ordered)}
        # Top 3 set for occupation
        top3_letters = {letter for letter, _ in ordered[:3]}
        profile_letters = set(data["fk_riasec_code"].lower())
        for l in ["r", "i", "a", "s", "e", "c"]:
            data[f"position_{l}"] = position_map[l]
            data[f"contains_{l}"] = l in top3_letters and l in profile_letters


def generate_rows(pivot: Dict[Tuple[str, str], Dict]) -> List[Dict]:
    out = []
    for p in pivot.values():
        row = {
            "occ_code": p["occ_code"],
            "fk_riasec_code": p["fk_riasec_code"],
            "interest_sum": p["interest_sum"],
            "interests_count": p["interests_count"],
        }
        row.update(p["scores"])  # score_r ... score_c
        for l in ["r", "i", "a", "s", "e", "c"]:
            row[f"position_{l}"] = p[f"position_{l}"]
            row[f"contains_{l}"] = p[f"contains_{l}"]
        out.append(row)
    return out


def upsert_rows(session: Session, rows: List[Dict], commit: bool) -> int:
    if not rows:
        return 0
    # Build parameterized upsert using ON CONFLICT
    insert_sql = text(
        """
        INSERT INTO riasec.interest_job_signals (
            occ_code, fk_riasec_code,
            score_r, score_i, score_a, score_s, score_e, score_c,
            contains_r, contains_i, contains_a, contains_s, contains_e, contains_c,
            position_r, position_i, position_a, position_s, position_e, position_c,
            interest_sum, interests_count
        ) VALUES (
            :occ_code, :fk_riasec_code,
            :score_r, :score_i, :score_a, :score_s, :score_e, :score_c,
            :contains_r, :contains_i, :contains_a, :contains_s, :contains_e, :contains_c,
            :position_r, :position_i, :position_a, :position_s, :position_e, :position_c,
            :interest_sum, :interests_count
        )
        ON CONFLICT (occ_code, fk_riasec_code) DO UPDATE SET
            score_r = EXCLUDED.score_r,
            score_i = EXCLUDED.score_i,
            score_a = EXCLUDED.score_a,
            score_s = EXCLUDED.score_s,
            score_e = EXCLUDED.score_e,
            score_c = EXCLUDED.score_c,
            contains_r = EXCLUDED.contains_r,
            contains_i = EXCLUDED.contains_i,
            contains_a = EXCLUDED.contains_a,
            contains_s = EXCLUDED.contains_s,
            contains_e = EXCLUDED.contains_e,
            contains_c = EXCLUDED.contains_c,
            position_r = EXCLUDED.position_r,
            position_i = EXCLUDED.position_i,
            position_a = EXCLUDED.position_a,
            position_s = EXCLUDED.position_s,
            position_e = EXCLUDED.position_e,
            position_c = EXCLUDED.position_c,
            interest_sum = EXCLUDED.interest_sum,
            interests_count = EXCLUDED.interests_count
        """
    )
    for chunk_start in range(0, len(rows), 500):
        chunk = rows[chunk_start:chunk_start + 500]
        session.execute(insert_sql, chunk)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Populate riasec.interest_job_signals table")
    parser.add_argument("--code", help="Optional 3-letter RIASEC code filter", default=None)
    parser.add_argument("--commit", action="store_true", help="Persist changes (otherwise dry-run)")
    args = parser.parse_args()

    engine = create_engine(get_db_url())
    with engine.connect() as conn:
        session = Session(bind=conn)
        try:
            base_rows = fetch_interest_base(session, args.code)
            pivot = pivot_scores(base_rows)
            compute_positions_and_flags(pivot)
            rows = generate_rows(pivot)
            count = upsert_rows(session, rows, commit=args.commit)
            if args.commit:
                conn.commit()  # Commit at connection level
            action = "UPSERTED" if args.commit else "WOULD upsert"
            print(f"{action} {count} rows into riasec.interest_job_signals")
        except Exception as e:
            if args.commit:
                conn.rollback()
            raise
        finally:
            session.close()


if __name__ == "__main__":
    main()
