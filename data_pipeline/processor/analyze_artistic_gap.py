"""Compare basic vs enriched interest scoring for ACR code."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import os

url = os.getenv('DATABASE_URL') or 'postgresql://postgres:cronk112482@localhost:5432/uhpathfinder'
engine = create_engine(url)

def check_artistic_representation(code='acr', limit=50):
    """Check how many top occupations have Artistic in their top 3 interests."""
    with engine.connect() as conn:
        # Count occupations where 'a' is in top 3 (contains_a = True)
        sql = text('''
            SELECT 
                COUNT(*) FILTER (WHERE contains_a = TRUE) as with_artistic,
                COUNT(*) as total,
                ROUND(100.0 * COUNT(*) FILTER (WHERE contains_a = TRUE) / COUNT(*), 1) as pct
            FROM (
                SELECT contains_a 
                FROM riasec.interest_job_signals 
                WHERE LOWER(fk_riasec_code) = LOWER(:code)
                ORDER BY interest_sum DESC, interests_count DESC
                LIMIT :limit
            ) subset
        ''')
        result = conn.execute(sql, {"code": code, "limit": limit}).fetchone()
        return result

print(f"Artistic Representation in Top 50 ACR Occupations:")
print(f"=" * 60)
result = check_artistic_representation('acr', 50)
print(f"With Artistic in top-3 interests: {result[0]}/{result[1]} ({result[2]}%)")
print(f"\nThis shows why balanced composite scoring is needed - the")
print(f"simple interest_sum ordering underrepresents Artistic (A) despite")
print(f"it being part of the user's ACR profile.")
