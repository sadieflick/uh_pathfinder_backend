"""Service for occupation-related operations."""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.models.public_schema.occupation import Occupation
from src.models.public_schema.program import Program
from src.models.public_schema.associations import program_occupation_association
from src.utils.text import fix_dict_encoding


def get_programs_for_occupation(db: Session, onet_code: str) -> List[Dict[str, Any]]:
    """
    Get all programs associated with a given occupation code.
    
    Args:
        db: Database session
        onet_code: O*NET SOC code (e.g., '51-4041.00')
    
    Returns:
        List of program dictionaries with full details
    """
    # Query programs through the association table
    stmt = (
        select(Program)
        .join(
            program_occupation_association,
            Program.id == program_occupation_association.c.program_id
        )
        .where(program_occupation_association.c.occupation_onet_code == onet_code)
    )
    
    programs = db.execute(stmt).scalars().all()
    
    # Convert to dictionaries
    result = []
    for program in programs:
        program_dict = {
            "id": program.id,
            "name": program.name,
            "description": program.description,
            "pathway_id": program.pathway_id,
            "institution_id": program.institution_id,
            "degree_type": program.degree_type,
            "duration_years": program.duration_years,
            "total_credits": program.total_credits,
            "cost_per_credit": program.cost_per_credit,
            "program_url": program.program_url,
            "program_links": program.program_links,
            "prerequisites": program.prerequisites,
            "delivery_modes": program.delivery_modes,
        }
        # Fix any encoding issues in the program data
        result.append(fix_dict_encoding(program_dict))
    
    return result


def get_occupation_details(db: Session, onet_code: str) -> Dict[str, Any] | None:
    """
    Get details for a specific occupation.
    
    Args:
        db: Database session
        onet_code: O*NET SOC code
    
    Returns:
        Occupation details dictionary or None if not found
    """
    stmt = select(Occupation).where(Occupation.onet_code == onet_code)
    occupation = db.execute(stmt).scalar_one_or_none()
    
    if not occupation:
        return None
    
    # Also get the O*NET occupation data for title
    from src.models.onet_schema.onet_occupation import OnetOccupation
    onet_stmt = select(OnetOccupation).where(OnetOccupation.onet_code == onet_code)
    onet_occ = db.execute(onet_stmt).scalar_one_or_none()
    
    occupation_dict = {
        "onet_code": occupation.onet_code,
        "title": onet_occ.title if onet_occ else None,
        "description": onet_occ.description if onet_occ else None,
        "median_annual_wage": occupation.median_annual_wage,
        "employment_outlook": occupation.employment_outlook,
        "job_zone": occupation.job_zone,
        "interest_codes": occupation.interest_codes,
        "interest_scores": occupation.interest_scores,
        "onet_url": occupation.onet_url,
    }
    
    # Fix any encoding issues
    return fix_dict_encoding(occupation_dict)


def get_occupation_with_programs(db: Session, onet_code: str) -> Dict[str, Any] | None:
    """
    Get occupation details along with associated programs.
    
    Args:
        db: Database session
        onet_code: O*NET SOC code
    
    Returns:
        Dictionary with occupation details and programs list, or None if not found
    """
    occupation = get_occupation_details(db, onet_code)
    
    if not occupation:
        return None
    
    programs = get_programs_for_occupation(db, onet_code)
    
    return {
        "occupation": occupation,
        "programs": programs,
        "program_count": len(programs)
    }
