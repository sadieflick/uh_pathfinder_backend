import json
from typing import List
from sqlalchemy.orm import Session, joinedload
import datetime
from src.db.session import get_session_factory
from src.models.public_schema.occupation import Occupation
from src.models.public_schema.program import Program
from src.models.public_schema.associations import program_occupation_association as prog_occ
from src.core.llm import call_ollama_json, extract_program_matches, DEFAULT_OLLAMA_MODEL

def prune_matches_batch(batch_limit: int | None = None, dry_run: bool = False):
    # Initialize session factory lazily (SessionLocal may be None until engine init)
    SessionFactory = get_session_factory()
    db: Session = SessionFactory()
    
    # 1. Fetch all Occupations that have ANY linked programs
    # We use joinedload to fetch the programs in the same query (efficient)
    occupations = db.query(Occupation).options(
        joinedload(Occupation.programs),
        joinedload(Occupation.onet_occupation)
    ).filter(
        Occupation.programs.any()  # Only get occs with links
    ).all()
    
    print(f"Found {len(occupations)} occupations with linked programs to validate.")

    try:
        for idx, occupation in enumerate(occupations):
            if batch_limit is not None and idx >= batch_limit:
                print(f"Reached batch limit {batch_limit}, stopping early.")
                break
            # 2. Prepare the Batch Data
            candidates = []
            for program in occupation.programs:
                candidates.append({
                    "id": program.id,
                    "name": program.name,
                    "description": (program.description or "")[:120]  # Shorter truncate for local model speed
                })
            print(f"\n--- Validating {len(candidates)} programs for: {occupation.onet_occupation.title if occupation.onet_occupation else occupation.onet_code} ---")
            candidatenames = [c['name'] for c in candidates]
            for name in candidatenames:
                print(f" - {name}")
            if not candidates:
                continue

            occ_title = occupation.onet_occupation.title if occupation.onet_occupation else occupation.onet_code

            # 3. The Batch LLM Call
            valid_program_ids = generate_batch_mapping(occupation, candidates, model=DEFAULT_OLLAMA_MODEL)

            print(f"Model returned {len(valid_program_ids)} valid matches.")

            # Fallback heuristic: if model call fails (empty list) keep ALL for now in dry-run
            if dry_run and not valid_program_ids:
                print("[DRY RUN] Model returned no matches (timeout or parse). Leaving all links unchanged for this occupation.")
                valid_program_ids = [p['id'] for p in candidates]

            # 4. Bulk Update the Database
            # A. Update Valid Links (High Confidence)
            if valid_program_ids:
                if dry_run:
                    print(f"[DRY RUN] Would set confidence=0.95 for {len(valid_program_ids)} rows")
                else:
                    db.query(prog_occ).filter(
                        prog_occ.c.occupation_onet_code == occupation.onet_code,
                        prog_occ.c.program_id.in_(valid_program_ids)
                    ).update({"confidence": 0.95}, synchronize_session=False)

                print(f"✅ Validated {len(valid_program_ids)} matches.")

            # B. Delete Invalid Links
            # (Any candidate that is NOT in the valid_ids list)
            invalid_ids = [p['id'] for p in candidates if p['id'] not in valid_program_ids]

            #print invalid program names for clarity
            print(f"Invalid programs: {[p['name'] for p in candidates if p['id'] in invalid_ids]}")

            if invalid_ids:
                if dry_run:
                    print(f"[DRY RUN] Would delete {len(invalid_ids)} rows")
                else:
                    db.query(prog_occ).filter(
                        prog_occ.c.occupation_onet_code == occupation.onet_code,
                        prog_occ.c.program_id.in_(invalid_ids)
                    ).delete(synchronize_session=False)

                print(f"❌ Removed {len(invalid_ids)} bad matches.")

            if not dry_run:
                db.commit()
    finally:
        db.close()

def generate_batch_mapping(
    occupation: Occupation,
    candidates: List[dict[str, str]],
    model: str = DEFAULT_OLLAMA_MODEL
) -> List[str]:
    """
    Stub method for your 'Option C' Hybrid Mapper.
    
    Takes a program description and a list of candidate O*NET codes (from Vector search).
    Returns a validated list of the top 10 matching codes.
    """
    # Local Ollama model call (no remote credits required)
    # Provide system-style instruction embedded in prompt for models lacking system role support.
    # print timestamp

    print(f"Calling Ollama at {datetime.datetime.now().isoformat()}")
    
    system_prompt = (
        "You are an expert career counselor and data taxonomist. Return ONLY a JSON list of program IDs that are related training programs. If none valid return []."
    )
    
    occ_title = occupation.onet_occupation.title if occupation.onet_occupation else occupation.onet_code
    occ_desc = occupation.onet_occupation.description if occupation.onet_occupation else "Description unavailable"
    user_message = f"""
    You are a Career Counselor.

    TARGET OCCUPATION: {occ_title}
    DESCRIPTION: {occ_desc}

    Below is a JSON list of Education Programs. 
    Identify which programs provide related training for this occupation.

    CRITERIA:
    - KEEP programs relevant to the occupational career path, or to a VERY related entry-level occupation (e.g. "Nursing Assistance Program" for "Nurse Practitioner").
    - REJECT very loose matches e.g. reject "Culinary Arts Program" for "Art Teacher" or "Early Childhood Education Program" for "Archeology Teachers, Postsecondary".
    - REJECT matches that are in a different field or sector.
    - IF IN DOUBT, KEEP the program.

    CANDIDATE PROGRAMS:
    {json.dumps(candidates, indent=2)}

    RESPONSE FORMAT:
    Return ONLY a JSON list of the 'id' strings for the valid programs. 
    If none are valid, return [].
    Example: ["prog-1", "prog-3"]
    """
    
    try:
        raw_content = call_ollama_json(
            prompt=f"{system_prompt}\n\n{user_message}",
            model=model,
            system=None,
        )
        matches = extract_program_matches(raw_content)
        return matches
    except Exception as e:
        print(f"Error generating mapping for occupation {occ_title}: {e}")
        return []
    

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Validate occupation-program matches with LLM confidence scoring.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of occupations to process")
    parser.add_argument("--dry-run", action="store_true", help="Do not modify the database")
    args = parser.parse_args()
    print(f"Time at start: {datetime.datetime.now().isoformat()}")
    prune_matches_batch(batch_limit=args.limit, dry_run=args.dry_run)
    print(f"Time after last call: {datetime.datetime.now().isoformat()}")