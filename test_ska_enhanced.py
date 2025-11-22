"""Test SKA-enhanced RIASEC endpoint."""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.services.assessment_service import AssessmentService
from src.api.v1.schemas.assessment import RiasecCodeRequest
import json

def test_ska_enhanced():
    url = os.getenv('DATABASE_URL') or 'postgresql://postgres:cronk112482@localhost:5432/uhpathfinder'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        db = Session(bind=conn)
        service = AssessmentService()
        
        print("="*90)
        print("TEST 1: Basic enriched scoring (no SKA)")
        print("="*90)
        request = RiasecCodeRequest(riasec_code="ACR", limit=10, include_ska=False)
        result = service.process_riasec_code(request, db)
        
        print(f"RIASEC Code: {result.riasec_code}")
        print(f"Occupation pool size: {len(result.occupation_pool)}")
        print(f"SKA Available: {result.ska_available}")
        print(f"Skill frequencies count: {len(result.skill_frequencies) if result.skill_frequencies else 0}")
        print(f"\nTop 5 Jobs (Interest-only scoring):")
        for idx, job in enumerate(result.top10_jobs[:5], 1):
            print(f"  {idx}. {job.title[:50]:<50} | Score: {job.composite_score:.5f} | SKA Rank: {job.ska_rank or 'N/A'}")
        
        print("\n" + "="*90)
        print("TEST 2: SKA-enhanced scoring (include_ska=True)")
        print("="*90)
        request_ska = RiasecCodeRequest(riasec_code="ACR", limit=10, include_ska=True)
        result_ska = service.process_riasec_code(request_ska, db)
        
        print(f"RIASEC Code: {result_ska.riasec_code}")
        print(f"Occupation pool size: {len(result_ska.occupation_pool)}")
        print(f"SKA Available: {result_ska.ska_available}")
        print(f"Skill frequencies: {list(result_ska.skill_frequencies.keys())[:5] if result_ska.skill_frequencies else []}")
        print(f"\nTop 5 Jobs (SKA-enhanced scoring):")
        for idx, job in enumerate(result_ska.top10_jobs[:5], 1):
            ska_status = f"#{job.ska_rank}" if job.ska_rank else "Not in SKA"
            print(f"  {idx}. {job.title[:45]:<45} | Score: {job.composite_score:.5f} | SKA: {ska_status}")
        
        print("\n" + "="*90)
        print("Sample API Response Structure:")
        print("="*90)
        sample = {
            "riasec_code": result_ska.riasec_code,
            "occupation_pool": result_ska.occupation_pool[:3],
            "top10_jobs": [
                {
                    "onet_code": j.onet_code,
                    "title": j.title,
                    "composite_score": j.composite_score,
                    "interest_sum": float(j.interest_sum) if j.interest_sum else None,
                    "interests_count": j.interests_count,
                    "ska_rank": j.ska_rank,
                    "median_salary": j.median_salary,
                    "growth_outlook": j.growth_outlook,
                }
                for j in result_ska.top10_jobs[:3]
            ],
            "skill_frequencies": dict(list(result_ska.skill_frequencies.items())[:5]) if result_ska.skill_frequencies else {},
            "ska_available": result_ska.ska_available,
            "skills_panel_count": len(result_ska.skills_panel)
        }
        print(json.dumps(sample, indent=2))

if __name__ == "__main__":
    test_ska_enhanced()
