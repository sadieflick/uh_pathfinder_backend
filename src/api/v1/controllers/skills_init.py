"""Skills assessment endpoints: initialization, refinement, and matching."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.v1.schemas.skills_initialize import (
    SkillsInitializeRequest,
    SkillsInitializeResponse,
    SKAPayload,
)
from src.db.session import get_db
from src.services.skills_prescoring_service import SkillsPrescoringService

router = APIRouter(prefix="/assessment/skills", tags=["skills-assessment"])


@router.post("/initialize", response_model=SkillsInitializeResponse)
def initialize_skills(
    payload: SkillsInitializeRequest,
    db: Session = Depends(get_db),
) -> SkillsInitializeResponse:
    """Initialize interest-weighted skills assessment with task selection.
    
    Pre-scores 40 CareerOneStop skills based on RIASEC interest profile:
    - Top 20 skills by frequency in interest-matched jobs → DataPoint50
    - Bottom 20 skills → DataPoint35
    - Skills user has performed ("I've done this") → bumped to DataPoint65
    
    Returns all 40 skills with scores and metadata for display/refinement.
    
    **Workflow:**
    1. User completes RIASEC quiz
    2. User reviews top skills and selects tasks they've performed
    3. Call this endpoint with RIASEC code + selected skill IDs
    4. Receive prescored skills ready for optional LLM refinement
    
    **Next Steps:**
    - Display skills to user with scores and anchors
    - For selected skills (refinement_required), optionally use `/refine` endpoint
    - Build final SKA payload for CareerOneStop with `/matches` endpoint
    """
    service = SkillsPrescoringService()
    
    try:
        result = service.apply_task_selection(
            riasec_code=payload.riasec_code,
            selected_skill_ids=payload.selected_skill_ids,
            db=db
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error initializing skills: {str(e)}"
        ) from e
    
    # Convert service response to Pydantic model
    return SkillsInitializeResponse(**result)


@router.post("/payload", response_model=SKAPayload)
def build_ska_payload(
    payload: SkillsInitializeRequest,
    db: Session = Depends(get_db),
) -> SKAPayload:
    """Build CareerOneStop SKA payload from initialized skills.
    
    Convenience endpoint to get a ready-to-submit payload for CareerOneStop API
    without needing to extract and format the skills list yourself.
    
    **Use case:**
    - Skip LLM refinement and submit skills directly to CareerOneStop
    - Get payload format for testing/debugging
    
    **Alternative:** Use `/initialize` then call CareerOneStop directly from frontend.
    """
    service = SkillsPrescoringService()
    
    try:
        result = service.apply_task_selection(
            riasec_code=payload.riasec_code,
            selected_skill_ids=payload.selected_skill_ids,
            db=db
        )
        
        payload_dict = service.build_ska_payload(result["skills"])
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error building SKA payload: {str(e)}"
        ) from e
    
    return SKAPayload(**payload_dict)
