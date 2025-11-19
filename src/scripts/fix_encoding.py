"""
Script to fix character encoding in the database.

This permanently fixes mojibake (garbled text) in the database,
specifically Hawaiian characters like ā, ʻ, etc.

Run this script to clean up the data at the source so the service layer
doesn't need to fix it on every request.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

from src.utils.text import fix_encoding

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

print(f"Using database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
engine = create_engine(DATABASE_URL)


def fix_program_encoding(db: Session, dry_run: bool = True):
    """Fix encoding issues in program table."""
    print("\n" + "="*60)
    print("FIXING PROGRAM DATA ENCODING")
    print("="*60)
    
    # Get all programs with text fields
    query = text("""
        SELECT id, name, description, degree_type
        FROM public.program
        WHERE name LIKE '%Ä%' 
           OR name LIKE '%â%'
           OR description LIKE '%Ä%' 
           OR description LIKE '%â%'
           OR degree_type LIKE '%Ä%'
           OR degree_type LIKE '%â%'
    """)
    
    programs = db.execute(query).fetchall()
    print(f"\nFound {len(programs)} programs with encoding issues")
    
    if not programs:
        print("✓ No encoding issues found in programs!")
        return
    
    fixed_count = 0
    for program in programs[:10]:  # Show first 10 examples
        print(f"\n📝 Program: {program.id}")
        print(f"  BEFORE name: {program.name}")
        fixed_name = fix_encoding(program.name)
        print(f"  AFTER  name: {fixed_name}")
        
        if program.description:
            if len(program.description) > 100:
                print(f"  BEFORE desc: {program.description[:100]}...")
                fixed_desc = fix_encoding(program.description)
                print(f"  AFTER  desc: {fixed_desc[:100]}...")
            else:
                print(f"  BEFORE desc: {program.description}")
                fixed_desc = fix_encoding(program.description)
                print(f"  AFTER  desc: {fixed_desc}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would fix {len(programs)} programs")
        print("   Run with --apply to make changes")
        return
    
    # Apply fixes
    print(f"\n🔧 Applying fixes to {len(programs)} programs...")
    
    for program in programs:
        update_query = text("""
            UPDATE public.program
            SET name = :name,
                description = :description,
                degree_type = :degree_type
            WHERE id = :id
        """)
        
        db.execute(update_query, {
            "id": program.id,
            "name": fix_encoding(program.name),
            "description": fix_encoding(program.description) if program.description else None,
            "degree_type": fix_encoding(program.degree_type) if program.degree_type else None
        })
        fixed_count += 1
        
        if fixed_count % 100 == 0:
            print(f"  Fixed {fixed_count}/{len(programs)} programs...")
            db.commit()
    
    db.commit()
    print(f"\n✅ Fixed {fixed_count} programs!")


def fix_institution_encoding(db: Session, dry_run: bool = True):
    """Fix encoding issues in institution table."""
    print("\n" + "="*60)
    print("FIXING INSTITUTION DATA ENCODING")
    print("="*60)
    
    query = text("""
        SELECT id, name, location, campus
        FROM public.institutions
        WHERE name LIKE '%Ä%' 
           OR name LIKE '%â%'
           OR location LIKE '%Ä%' 
           OR location LIKE '%â%'
           OR campus LIKE '%Ä%'
           OR campus LIKE '%â%'
    """)
    
    institutions = db.execute(query).fetchall()
    print(f"\nFound {len(institutions)} institutions with encoding issues")
    
    if not institutions:
        print("✓ No encoding issues found in institutions!")
        return
    
    for inst in institutions:
        print(f"\n🏫 Institution: {inst.id}")
        print(f"  BEFORE name:     {inst.name}")
        print(f"  AFTER  name:     {fix_encoding(inst.name)}")
        if inst.location:
            print(f"  BEFORE location: {inst.location}")
            print(f"  AFTER  location: {fix_encoding(inst.location)}")
        if inst.campus:
            print(f"  BEFORE campus:   {inst.campus}")
            print(f"  AFTER  campus:   {fix_encoding(inst.campus)}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would fix {len(institutions)} institutions")
        print("   Run with --apply to make changes")
        return
    
    # Apply fixes
    print(f"\n🔧 Applying fixes to {len(institutions)} institutions...")
    
    for inst in institutions:
        update_query = text("""
            UPDATE public.institutions
            SET name = :name,
                location = :location,
                campus = :campus
            WHERE id = :id
        """)
        
        db.execute(update_query, {
            "id": inst.id,
            "name": fix_encoding(inst.name),
            "location": fix_encoding(inst.location) if inst.location else None,
            "campus": fix_encoding(inst.campus) if inst.campus else None
        })
    
    db.commit()
    print(f"\n✅ Fixed {len(institutions)} institutions!")


def main():
    """Main function to fix all encoding issues."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix character encoding in database')
    parser.add_argument('--apply', action='store_true', 
                       help='Apply fixes (default is dry-run)')
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    if dry_run:
        print("\n" + "🔍 DRY RUN MODE - No changes will be made".center(60))
    else:
        print("\n" + "⚠️  APPLYING CHANGES TO DATABASE".center(60))
    
    with Session(engine) as db:
        fix_institution_encoding(db, dry_run)
        fix_program_encoding(db, dry_run)
    
    print("\n" + "="*60)
    if dry_run:
        print("DRY RUN COMPLETE")
        print("Run with --apply to make permanent changes")
    else:
        print("ENCODING FIXES APPLIED SUCCESSFULLY")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
