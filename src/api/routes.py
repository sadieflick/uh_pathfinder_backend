from fastapi import APIRouter

# v1 routers
from src.api.v1.controllers.assessment import router as assessment_router
from src.api.v1.controllers.occupations import router as occupations_router
from src.api.v1.controllers.programs import router as programs_router
from src.api.v1.controllers.sectors import router as sectors_router
from src.api.v1.controllers.apitest import router as apitest_router
from src.api.v1.controllers.skills_init import router as skills_init_router

# Aggregated router for the API
api_router = APIRouter()

# Mount versioned routers; prefixes are defined within each router
api_router.include_router(assessment_router)
api_router.include_router(occupations_router)
api_router.include_router(programs_router)
api_router.include_router(sectors_router)
api_router.include_router(apitest_router)
api_router.include_router(skills_init_router)