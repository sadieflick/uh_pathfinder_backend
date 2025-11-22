from pydantic import BaseModel, Field
from typing import List, Optional, Dict


# ---------------- RIASEC Interest -----------------
class RiasecCodeRequest(BaseModel):
    riasec_code: str = Field(min_length=3, max_length=3, pattern="^[RIASEC]{3}$")
    # Optional limit for number of top jobs to return (defaults to 50, max 150 with enriched scoring)
    limit: Optional[int] = Field(default=50, ge=1, le=150)
    # Optional SKA integration flag (requires CareerOneStop credentials)
    include_ska: Optional[bool] = Field(default=False)


class OccupationLite(BaseModel):
    onet_code: str
    title: str
    median_salary: Optional[float] = None
    growth_outlook: Optional[str] = None
    # Enriched ranking metadata (populated when using balanced composite scoring)
    composite_score: Optional[float] = None
    interest_sum: Optional[float] = None
    interests_count: Optional[int] = None
    ska_rank: Optional[int] = None  # CareerOneStop Skills Matcher rank (1-150)


class SkillDefinition(BaseModel):
    element_id: str
    name: str
    question: str
    easy_read_description: str
    anchor_first: str
    anchor_third: str
    anchor_last: str
    # Raw baseline distribution points (no user scoring yet)
    data_point_20: float
    data_point_35: float
    data_point_50: float
    data_point_65: float
    data_point_80: float


class RiasecResult(BaseModel):
    riasec_code: str
    occupation_pool: List[str]
    top10_jobs: List[OccupationLite]
    # Optional: deliver baseline skill definitions to hydrate panel immediately
    skills_panel: List[SkillDefinition]
    # Optional: skill frequency aggregation from interest-matched jobs
    skill_frequencies: Optional[Dict[str, int]] = None  # element_id -> total_frequency
    # Optional: SKA integration status
    ska_available: Optional[bool] = None


# ---------------- Skill Panel & Weighting -----------------
class SkillRatingsSubmission(BaseModel):
    riasec_code: str
    ratings: Dict[str, float]  # element_id -> user raw rating (e.g., mapped to 1..5 or DataValue)


class SkillWeighted(BaseModel):
    element_id: str
    raw_rating: float
    normalized_score: float
    adjusted_weight: float


class SkillWeightsResponse(BaseModel):
    riasec_code: str
    weighted_skills: List[SkillWeighted]
    category_weights: Dict[str, float]


# Backward compatibility placeholders (if old endpoints still referenced)
class InterestQuizRequest(BaseModel):
    responses: List[int]


class InterestQuizResponse(BaseModel):
    session_id: str
    top_codes: List[str]
    scores: dict


class SkillTriageResponse(BaseModel):
    skills: List[dict]
