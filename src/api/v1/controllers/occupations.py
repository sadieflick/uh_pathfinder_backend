"""Occupation endpoints for retrieving occupation data and associated programs."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.occupation_service import (
    get_programs_for_occupation,
    get_occupation_details,
    get_occupation_with_programs,
    get_top_skills_for_occupation
)

router = APIRouter(prefix="/occupations", tags=["occupations"])


@router.get("/")
async def list_occupations():
    """Placeholder: return a paginated list of occupations."""
    return {"items": [], "total": 0}


@router.get("/{onet_code}")
async def get_occupation(onet_code: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get details for a specific occupation by O*NET code.
    
    Args:
        onet_code: O*NET SOC code (e.g., '51-4041.00')
    
    Returns:
        Occupation details including title, description, wage, outlook, etc.
    """
    occupation = get_occupation_details(db, onet_code)
    
    if not occupation:
        raise HTTPException(status_code=404, detail=f"Occupation {onet_code} not found")
    
    return occupation


@router.get("/{onet_code}/programs")
async def get_occupation_programs(
    onet_code: str, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all programs associated with a specific occupation.
    
    This endpoint returns programs that have been matched to the occupation
    through semantic similarity analysis (occupation → pathway → program).
    
    Args:
        onet_code: O*NET SOC code (e.g., '51-4041.00')
    
    Returns:
        Dictionary containing:
        - occupation: Basic occupation details
        - programs: List of associated programs
        - program_count: Total number of matching programs
    
    Example:
        GET /api/v1/occupations/51-4041.00/programs
        
        Returns programs for "Machinists" occupation, which might include
        Automotive Maintenance, Aviation Maintenance, and related technical programs.
    """
    result = get_occupation_with_programs(db, onet_code)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Occupation {onet_code} not found")
    
    return result


@router.get("/{onet_code}/programs/summary")
async def get_occupation_programs_summary(
    onet_code: str,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get a simplified list of programs for an occupation (programs only, no occupation details).
    
    Args:
        onet_code: O*NET SOC code
    
    Returns:
        List of program dictionaries
    """
    programs = get_programs_for_occupation(db, onet_code)
    
    if not programs:
        # Check if occupation exists
        occupation = get_occupation_details(db, onet_code)
        if not occupation:
            raise HTTPException(status_code=404, detail=f"Occupation {onet_code} not found")
    
    return programs


@router.get("/{onet_code}/top-skills")
async def get_occupation_top_skills(
    onet_code: str,
    limit: int = 5,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get top skills (Importance scale) for an occupation.

    Args:
        onet_code: O*NET SOC code
        limit: Maximum number of skills to return (default 5)

    Returns:
        List of skill dicts: [{element_id, element_name, score}]
    """
    # Verify occupation exists
    occupation = get_occupation_details(db, onet_code)
    if not occupation:
        raise HTTPException(status_code=404, detail=f"Occupation {onet_code} not found")

    skills = get_top_skills_for_occupation(db, onet_code, limit=limit)
    return skills
