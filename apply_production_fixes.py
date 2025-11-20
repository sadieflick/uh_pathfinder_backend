"""
Apply all database fixes to PRODUCTION database
Run this script to fix encoding and program classifications on production
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import re

# Get production database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    print("\nTo set it, use the connection string from Render:")
    print("export DATABASE_URL='postgresql://uhpathfinderdb_user:PASSWORD@dpg-d4ed6m1r0fns73blnhu0-a.oregon-postgres.render.com:5432/uhpathfinderdb'")
    sys.exit(1)

print("=" * 70)
print("PRODUCTION DATABASE FIX SCRIPT")
print("=" * 70)
print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'Unknown'}")
print("\nThis script will:")
print("1. Fix encoding issues (Mānoa, Hawaiʻi)")
print("2. Fix program durations (2-year → 4-year where applicable)")
print("3. Fix degree types (Associate → Bachelor's where applicable)")
print("=" * 70)

response = input("\n⚠️  WARNING: This will modify PRODUCTION data. Continue? (yes/no): ")
if response.lower() != 'yes':
    print("Aborted.")
    sys.exit(0)

# Create engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("\n" + "=" * 70)
print("STEP 1: Fixing Encoding Issues")
print("=" * 70)

# Fix encoding in program names and descriptions
encoding_fixes = {
    'MÄ\x81noa': 'Mānoa',
    'Manoa': 'Mānoa',
    'Hawaiâi': 'Hawaiʻi',
    'HawaiÊ»i': 'Hawaiʻi',
    'Hawai?i': 'Hawaiʻi',
}

for old, new in encoding_fixes.items():
    # Fix in name field
    result = session.execute(
        text("UPDATE programs SET name = REPLACE(name, :old, :new) WHERE name LIKE :pattern"),
        {"old": old, "new": new, "pattern": f"%{old}%"}
    )
    if result.rowcount > 0:
        print(f"  ✓ Fixed {result.rowcount} records: '{old}' → '{new}' in name")
    
    # Fix in description field  
    result = session.execute(
        text("UPDATE programs SET description = REPLACE(description, :old, :new) WHERE description LIKE :pattern"),
        {"old": old, "new": new, "pattern": f"%{old}%"}
    )
    if result.rowcount > 0:
        print(f"  ✓ Fixed {result.rowcount} records: '{old}' → '{new}' in description")

session.commit()
print("\n✓ Encoding fixes applied")

print("\n" + "=" * 70)
print("STEP 2: Fixing Program Durations")
print("=" * 70)

# Import the duration fix function from the existing script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from fix_program_durations import infer_duration_from_text
    
    # Get programs that might be misclassified
    query = text("""
        SELECT id, name, description, duration_years, degree_type
        FROM programs
        WHERE (
            (description ILIKE '%bachelor%' OR description ILIKE '%B.S.%' OR description ILIKE '%B.A.%')
            AND duration_years < 4
        )
        OR (
            description ~* 'total (number of )?credits:?\\s*(12[0-9]|13[0-9]|14[0-9]|15[0-9])'
            AND duration_years < 4
        )
    """)
    
    programs = session.execute(query).fetchall()
    print(f"\nFound {len(programs)} potentially misclassified programs")
    
    updates = []
    for prog in programs:
        inferred = infer_duration_from_text(prog.description)
        if inferred and inferred != prog.duration_years:
            updates.append((prog.id, inferred, prog.duration_years))
    
    print(f"\nWill update {len(updates)} programs:")
    for prog_id, new_dur, old_dur in updates[:10]:
        print(f"  {prog_id}: {old_dur} years → {new_dur} years")
    if len(updates) > 10:
        print(f"  ... and {len(updates) - 10} more")
    
    if updates:
        response = input(f"\nApply these {len(updates)} duration updates? (yes/no): ")
        if response.lower() == 'yes':
            for prog_id, new_dur, _ in updates:
                session.execute(
                    text("UPDATE programs SET duration_years = :dur WHERE id = :id"),
                    {"dur": new_dur, "id": prog_id}
                )
            session.commit()
            print(f"✓ Updated {len(updates)} program durations")
        else:
            print("Skipped duration updates")
    
except ImportError:
    print("⚠ Could not import duration fix function, skipping this step")

print("\n" + "=" * 70)
print("STEP 3: Fixing Degree Types")
print("=" * 70)

# Fix degree types for 4-year programs still marked as Associate
result = session.execute(text("""
    SELECT COUNT(*) FROM programs 
    WHERE duration_years >= 4 
    AND degree_type ILIKE '%associate%'
"""))
count = result.scalar()

if count > 0:
    print(f"\nFound {count} 4-year programs with Associate degree type")
    response = input("Fix these by changing to appropriate Bachelor's degree? (yes/no): ")
    
    if response.lower() == 'yes':
        # Update to Bachelor of Science by default
        session.execute(text("""
            UPDATE programs 
            SET degree_type = CASE
                WHEN name ILIKE '%B.A.%' OR name ILIKE '%bachelor of arts%' THEN 'Bachelor of Arts'
                WHEN name ILIKE '%education%' OR description ILIKE '%teacher%' THEN 'Bachelor of Education'
                WHEN name ILIKE '%BBA%' OR name ILIKE '%business administration%' THEN 'Bachelor of Business Administration'
                ELSE 'Bachelor of Science'
            END
            WHERE duration_years >= 4
            AND degree_type ILIKE '%associate%'
        """))
        session.commit()
        print(f"✓ Updated {count} degree types")
else:
    print("✓ No degree type fixes needed")

print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

# Show final distribution
result = session.execute(text("""
    SELECT degree_type, COUNT(*) as count
    FROM programs
    GROUP BY degree_type
    ORDER BY count DESC
"""))

print("\nFinal degree type distribution:")
for row in result:
    print(f"  {row.degree_type}: {row.count}")

# Check for remaining issues
result = session.execute(text("""
    SELECT COUNT(*) FROM programs 
    WHERE duration_years >= 4 AND degree_type ILIKE '%associate%'
"""))
remaining = result.scalar()

if remaining > 0:
    print(f"\n⚠ Warning: {remaining} 4-year programs still have Associate degree")
else:
    print("\n✓ No 4-year programs with Associate degree")

session.close()

print("\n" + "=" * 70)
print("FIXES COMPLETE!")
print("=" * 70)
print("\nNext steps:")
print("1. Test the backend API again: python3 debug_500.py")
print("2. Check encoding in browser")
print("3. Verify 4-year programs show in University section")
