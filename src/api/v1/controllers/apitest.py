from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter
from sqlalchemy import text

from src.core.config import settings
from src.db.session import get_engine


router = APIRouter(prefix="/apitest", tags=["diagnostics"]) 


@router.get("", summary="Basic API and DB connectivity check")
def api_test() -> Dict[str, Any]:
    """Lightweight endpoint to verify the API is reachable and the database
    connection works. Never exposes secrets.

    Returns a JSON object with:
    - status: "ok"
    - timestamp: ISO-8601 in UTC
    - app_name: from settings
    - db: { connected, dialect, error }
    """

    ts = datetime.now(timezone.utc).isoformat()

    db_connected: bool = False
    db_error: Optional[str] = None
    db_dialect: Optional[str] = None

    try:
        engine = get_engine()
        db_dialect = engine.dialect.name
        # Perform a trivial query to validate connectivity
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:  # noqa: BLE001 - return error context to caller
        # Intentionally swallow errors and report them in payload; the endpoint
        # should still return 200 to distinguish API reachability from DB state.
        db_error = str(e)

    return {
        "status": "ok",
        "timestamp": ts,
        "app_name": settings.app_name,
        "db": {
            "connected": db_connected,
            "dialect": db_dialect,
            "error": db_error,
        },
    }
