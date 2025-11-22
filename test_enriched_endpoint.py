"""Test enriched RIASEC endpoint with balanced scoring."""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.services.assessment_service import AssessmentService
from src.api.v1.schemas.assessment import RiasecCodeRequest

def test_enriched_riasec():
    url = os.getenv('DATABASE_URL') or 'postgresql://postgres:cronk112482@localhost:5432/uhpathfinder'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        db = Session(bind=conn)
        service = AssessmentService()
        
        # Test ACR code with enriched scoring
        request = RiasecCodeRequest(riasec_code="ACR", limit=20)
        result = service.process_riasec_code(request, db)
        
        print(f"RIASEC Code: {result.riasec_code}")
        print(f"Occupation pool size: {len(result.occupation_pool)}")
        print(f"Top jobs returned: {len(result.top10_jobs)}")
        print(f"Skills panel size: {len(result.skills_panel)}")
        print(f"\nTop 10 Occupations (with balanced scoring metadata):")
        print(f"{'#':<4} {'O*NET Code':<15} {'Title':<40} {'Comp_Score':<11} {'I_Sum':<6} {'I_Cnt':<5}")
        print("-" * 95)
        
        for idx, job in enumerate(result.top10_jobs[:10], 1):
            title_trunc = job.title[:37] + "..." if len(job.title) > 40 else job.title
            comp_score = f"{job.composite_score:.5f}" if job.composite_score else "N/A"
            i_sum = f"{job.interest_sum:.2f}" if job.interest_sum else "N/A"
            i_cnt = str(job.interests_count) if job.interests_count else "N/A"
            print(f"{idx:<4} {job.onet_code:<15} {title_trunc:<40} {comp_score:<11} {i_sum:<6} {i_cnt:<5}")
        
        # Check for Artistic representation
        print(f"\n{'='*90}")
        print("Checking Artistic representation in results...")
        
        # We need to query the actual scores to see if A-heavy jobs ranked higher
        db_check = Session(bind=conn)
        from sqlalchemy import text
        check_sql = text("""
            SELECT occ_code, title, score_a, contains_a
            FROM riasec.interest_job_signals sig
            JOIN onet.occupation_data od ON sig.occ_code = od.onetsoc_code
            WHERE LOWER(sig.fk_riasec_code) = 'acr'
              AND sig.occ_code = ANY(:codes)
            ORDER BY score_a DESC
            LIMIT 5
        """)
        rows = db_check.execute(check_sql, {"codes": result.occupation_pool[:20]}).fetchall()
        
        print(f"\nTop 5 by Artistic score (from top 20 returned):")
        for r in rows:
            contains = "✓" if r.contains_a else "✗"
            print(f"  {r.occ_code:<15} A={float(r.score_a):<5.2f} Contains_A:{contains} - {r.title[:50]}")

if __name__ == "__main__":
    test_enriched_riasec()
