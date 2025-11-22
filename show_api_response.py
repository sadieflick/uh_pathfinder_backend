"""Generate sample API response showing enriched metadata."""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.services.assessment_service import AssessmentService
from src.api.v1.schemas.assessment import RiasecCodeRequest
import json

url = os.getenv('DATABASE_URL') or 'postgresql://postgres:cronk112482@localhost:5432/uhpathfinder'
engine = create_engine(url)

with engine.connect() as conn:
    db = Session(bind=conn)
    service = AssessmentService()
    
    request = RiasecCodeRequest(riasec_code="ACR", limit=5)
    result = service.process_riasec_code(request, db)
    
    # Convert to dict for JSON serialization
    response_dict = {
        "riasec_code": result.riasec_code,
        "occupation_pool": result.occupation_pool[:5],
        "top10_jobs": [
            {
                "onet_code": j.onet_code,
                "title": j.title,
                "median_salary": j.median_salary,
                "growth_outlook": j.growth_outlook,
                "composite_score": j.composite_score,
                "interest_sum": float(j.interest_sum) if j.interest_sum else None,
                "interests_count": j.interests_count,
            }
            for j in result.top10_jobs[:5]
        ],
        "skills_panel_count": len(result.skills_panel)
    }
    
    print("Sample API Response (POST /api/v1/assessment/riasec):")
    print("="*80)
    print(json.dumps(response_dict, indent=2))
    print("="*80)
    print("\n✅ Ranking metadata now includes:")
    print("  • composite_score - Balanced scoring result (0-1 range)")
    print("  • interest_sum - Sum of RIASEC letter scores for this occupation")
    print("  • interests_count - Number of profile letters in occupation's top-3")
