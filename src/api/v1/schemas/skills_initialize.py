"""Pydantic schemas for interest-weighted skills assessment endpoints."""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional


# ============ Task Selection / Initialization ============

class SkillsInitializeRequest(BaseModel):
    """Request to initialize interest-weighted skills with task selections."""
    
    riasec_code: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="3-letter RIASEC code (e.g., 'IRE', case-insensitive)"
    )
    selected_skill_ids: List[str] = Field(
        default_factory=list,
        description="Element IDs of skills the user has performed ('I've done this')"
    )
    
    @field_validator("riasec_code")
    @classmethod
    def validate_riasec_code(cls, v: str) -> str:
        """Validate and uppercase RIASEC code."""
        v = v.upper()
        if not all(c in "RIASEC" for c in v):
            raise ValueError("RIASEC code must only contain letters R, I, A, S, E, C")
        return v


class PrescoredSkill(BaseModel):
    """A single skill with pre-scoring and metadata."""
    
    element_id: str = Field(..., description="O*NET element ID (e.g., '2.A.1.e')")
    element_name: str = Field(..., description="Skill name (e.g., 'Mathematics')")
    initial_score: float = Field(..., description="Pre-assigned score (DataPoint50 or DataPoint35)")
    score: float = Field(..., description="Current score after task selection bumps")
    rank: int = Field(..., description="Rank by interest-job frequency (1-40)")
    selected: bool = Field(..., description="Whether user selected this skill")
    
    # Anchor statements for user reference
    anchor_first: str = Field(default="", description="Beginner-level anchor (DataPoint20)")
    anchor_third: str = Field(default="", description="Mid-level anchor (DataPoint50)")
    anchor_last: str = Field(default="", description="Expert-level anchor (DataPoint80)")
    
    # Question and description
    question: str = Field(default="", description="Assessment question for this skill")
    easy_read_description: str = Field(default="", description="User-friendly skill description")
    
    # All DataPoint values (for future refinement)
    data_point_35: float = Field(default=0.0)
    data_point_50: float = Field(default=0.0)
    data_point_65: float = Field(default=0.0)
    data_point_80: float = Field(default=0.0)


class SkillsInitializeResponse(BaseModel):
    """Response with prescored skills and task selection bumps applied."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "riasec_code": "IRE",
                "skills": [
                    {
                        "element_id": "2.A.1.e",
                        "element_name": "Mathematics",
                        "initial_score": 3.06,
                        "score": 3.978,
                        "rank": 1,
                        "selected": True,
                        "anchor_third": "Use algebra or geometry...",
                        "question": "What is your level of math skill?",
                        "data_point_65": 3.978
                    }
                ],
                "refinement_required": ["2.A.1.e", "2.C.3.a"]
            }
        }
    )
    
    riasec_code: str = Field(..., description="Canonicalized RIASEC code")
    skills: List[PrescoredSkill] = Field(..., description="All 40 skills with scores")
    refinement_required: List[str] = Field(
        ..., 
        description="Element IDs of selected skills that need LLM refinement"
    )


# ============ SKA Payload ============

class SKAElement(BaseModel):
    """Single skill-rating element for CareerOneStop API."""
    
    ElementId: str = Field(..., description="O*NET element ID")
    DataValue: str = Field(..., description="Skill rating as string (e.g., '3.978')")


class SKAPayload(BaseModel):
    """CareerOneStop Skills Matcher API payload."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "SKAValueList": [
                    {"ElementId": "2.A.1.e", "DataValue": "3.978"},
                    {"ElementId": "2.C.3.a", "DataValue": "4.412"}
                ]
            }
        }
    )
    
    SKAValueList: List[SKAElement] = Field(
        ...,
        description="List of 40 skill ratings"
    )
