"""Backfill confidence values for existing program-occupation links.

Usage:
    python src/scripts/backfill_confidence.py --baseline 0.0 --only-null

By default, only NULL confidences are updated. You can override this with
`--include-non-null` to force-write the baseline to every row.
"""
from __future__ import annotations

import os
import argparse
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session
from src.models.public_schema.associations import program_occupation_association as prog_occ


def get_db_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("TEST_DATABASE_URL")
    )


def backfill_confidence(baseline: float, only_null: bool, include_non_null: bool, dry_run: bool) -> int:
    if only_null and include_non_null:
        raise ValueError("Cannot use --only-null and --include-non-null together.")

    url = get_db_url()
    engine = create_engine(url)
    updated = 0
    with Session(engine) as session:
        stmt = update(prog_occ)
        if only_null:
            stmt = stmt.where(prog_occ.c.confidence.is_(None))
        elif not include_non_null:
            # Default behavior same as only-null
            stmt = stmt.where(prog_occ.c.confidence.is_(None))
        stmt = stmt.values(confidence=baseline)

        if dry_run:
            # Count rows that WOULD be updated
            preview_q = session.query(prog_occ).filter(prog_occ.c.confidence.is_(None)) if (only_null or not include_non_null) else session.query(prog_occ)
            updated = preview_q.count()
            print(f"[DRY RUN] Would update {updated} rows to confidence={baseline}")
            return updated

        result = session.execute(stmt)
        session.commit()
        updated = result.rowcount or 0
        print(f"Updated {updated} rows to confidence={baseline}")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill confidence values for program-occupation links.")
    parser.add_argument("--baseline", type=float, default=0.0, help="Confidence value to apply.")
    parser.add_argument("--only-null", action="store_true", help="Update only rows where confidence IS NULL.")
    parser.add_argument("--include-non-null", action="store_true", help="Force update even existing confidence values.")
    parser.add_argument("--dry-run", action="store_true", help="Preview count without writing.")
    args = parser.parse_args()

    backfill_confidence(
        baseline=args.baseline,
        only_null=args.only_null,
        include_non_null=args.include_non_null,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
