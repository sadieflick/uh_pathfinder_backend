"""
Fix degree_type for programs that have been reclassified to 4+ years but still have Associate degree type.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def fix_degree_types(dry_run: bool = True):
    """Fix degree types for 4+ year programs still marked as Associate."""
    
    with engine.connect() as conn:
        # Find Associate programs with 4+ year duration
        query = text("""
            SELECT id, name, degree_type, duration_years
            FROM public.programs
            WHERE degree_type LIKE 'Associate%'
            AND duration_years >= 4
            ORDER BY name
        """)
        
        results = conn.execute(query).fetchall()
        
        print(f"Found {len(results)} Associate programs with 4+ year duration")
        print("="*80)
        
        if not results:
            print("No corrections needed!")
            return
        
        corrections = []
        for row in results:
            # Determine new degree type based on program name
            name_lower = row.name.lower()
            
            if ' ba ' in name_lower or 'bachelor of arts' in name_lower:
                new_degree_type = "Bachelor of Arts"
            elif ' bs ' in name_lower or 'bachelor of science' in name_lower:
                new_degree_type = "Bachelor of Science"
            elif ' bba ' in name_lower:
                new_degree_type = "Bachelor of Business Administration"
            elif 'education' in name_lower and 'bachelor' not in name_lower:
                new_degree_type = "Bachelor of Education"
            else:
                # Default to Bachelor of Science for university programs
                new_degree_type = "Bachelor of Science"
            
            corrections.append({
                'id': row.id,
                'name': row.name,
                'old_type': row.degree_type,
                'new_type': new_degree_type,
                'duration': row.duration_years
            })
            
            print(f"\n{row.name}")
            print(f"  Duration: {row.duration_years} years")
            print(f"  Change: {row.degree_type} → {new_degree_type}")
    
    print("\n" + "="*80)
    
    if dry_run:
        print(f"DRY RUN - {len(corrections)} corrections identified")
        print("Run with --apply to apply changes")
        return
    
    # Apply corrections
    with Session(engine) as session:
        for corr in corrections:
            update_query = text("""
                UPDATE public.programs
                SET degree_type = :new_type
                WHERE id = :program_id
            """)
            session.execute(update_query, {
                'new_type': corr['new_type'],
                'program_id': corr['id']
            })
        
        session.commit()
        print(f"✓ Applied {len(corrections)} degree type corrections")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    fix_degree_types(dry_run=not args.apply)
