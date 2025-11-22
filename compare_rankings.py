"""Compare old vs new RIASEC ranking for ACR code."""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

def compare_rankings():
    url = os.getenv('DATABASE_URL') or 'postgresql://postgres:cronk112482@localhost:5432/uhpathfinder'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        db = Session(bind=conn)
        
        print("="*90)
        print("COMPARISON: Old (interest_sum DESC) vs New (Balanced Composite) for ACR")
        print("="*90)
        
        # Old method: simple interest_sum ordering
        old_sql = text("""
            SELECT occ_code, title, interest_sum, interests_count,
                   score_a, contains_a
            FROM riasec.interest_job_signals sig
            JOIN onet.occupation_data od ON sig.occ_code = od.onetsoc_code
            WHERE LOWER(fk_riasec_code) = 'acr'
            ORDER BY interest_sum DESC, interests_count DESC
            LIMIT 10
        """)
        old_rows = db.execute(old_sql).fetchall()
        
        print("\n🔴 OLD METHOD (interest_sum DESC):")
        print(f"{'Rank':<6} {'O*NET':<15} {'Title':<40} {'I_Sum':<7} {'A_Score':<8} {'Has_A'}")
        print("-" * 90)
        for idx, r in enumerate(old_rows, 1):
            has_a = "✓" if r.contains_a else "✗"
            title_trunc = r.title[:37] + "..." if len(r.title) > 40 else r.title
            print(f"{idx:<6} {r.occ_code:<15} {title_trunc:<40} {r.interest_sum:<7} {float(r.score_a):<8.2f} {has_a}")
        
        artistic_old = sum(1 for r in old_rows if r.contains_a)
        print(f"\nOccupations with Artistic in top-3: {artistic_old}/10 ({artistic_old*10}%)")
        
        # New method: balanced composite via service
        from src.services.assessment_service import AssessmentService
        from src.api.v1.schemas.assessment import RiasecCodeRequest
        
        service = AssessmentService()
        request = RiasecCodeRequest(riasec_code="ACR", limit=10)
        result = service.process_riasec_code(request, db)
        
        # Query enriched data for the returned codes
        new_codes = [j.onet_code for j in result.top10_jobs]
        new_sql = text("""
            SELECT occ_code, title, interest_sum, interests_count,
                   score_a, contains_a
            FROM riasec.interest_job_signals sig
            JOIN onet.occupation_data od ON sig.occ_code = od.onetsoc_code
            WHERE occ_code = ANY(:codes)
        """)
        new_data = {r.occ_code: r for r in db.execute(new_sql, {"codes": new_codes}).fetchall()}
        
        print("\n\n🟢 NEW METHOD (Balanced Composite Scoring):")
        print(f"{'Rank':<6} {'O*NET':<15} {'Title':<40} {'I_Sum':<7} {'A_Score':<8} {'Has_A'}")
        print("-" * 90)
        for idx, job in enumerate(result.top10_jobs, 1):
            row = new_data.get(job.onet_code)
            if row:
                has_a = "✓" if row.contains_a else "✗"
                title_trunc = job.title[:37] + "..." if len(job.title) > 40 else job.title
                print(f"{idx:<6} {job.onet_code:<15} {title_trunc:<40} {row.interest_sum:<7} {float(row.score_a):<8.2f} {has_a}")
        
        artistic_new = sum(1 for j in result.top10_jobs if new_data.get(j.onet_code) and new_data[j.onet_code].contains_a)
        print(f"\nOccupations with Artistic in top-3: {artistic_new}/10 ({artistic_new*10}%)")
        
        print("\n" + "="*90)
        print(f"IMPROVEMENT: Artistic representation increased from {artistic_old}/10 to {artistic_new}/10")
        print("="*90)

if __name__ == "__main__":
    compare_rankings()
