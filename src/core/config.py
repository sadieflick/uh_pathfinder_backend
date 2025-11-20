import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseModel):
    app_name: str = "UH Pathfinder Backend"
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/uhpathfinder")

    # CareerOneStop (Skills Matcher) primary credentials
    onestop_userid: str = os.getenv("ONESTOP_USERID", "")
    onestop_api_key: str = os.getenv("ONESTOP_API_KEY", "")

    # Legacy O*NET credential variables (retain for forwards compatibility)
    onet_username: str = os.getenv("ONET_USERNAME", "")
    onet_password: str = os.getenv("ONET_PASSWORD", "")

    # LLM API keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")


settings = Settings()  # type: ignore[arg-type]

# Explicit exports for current usage
ONESTOP_USERID = settings.onestop_userid
ONESTOP_API_KEY = settings.onestop_api_key

# Backward compatibility exports mapping prior variable names to new ones
ONET_USERNAME = settings.onestop_userid  # deprecated usage path
ONET_PASSWORD = settings.onestop_api_key  # deprecated usage path

