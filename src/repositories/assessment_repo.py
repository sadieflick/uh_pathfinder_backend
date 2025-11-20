import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from src.core.config import ONESTOP_USERID, ONESTOP_API_KEY

logger = logging.getLogger(__name__)


class AssessmentRepository:
    """Repository for external assessment-related data sources.

    Currently handles calls to the CareerOneStop Skills Matcher API.
    """

    CAREERONESTOP_BASE = "https://api.careeronestop.org/v1/skillsmatcher"
    TIMEOUT_SECONDS = 20.0

    def __init__(self) -> None:
        # Future: accept a configurable HTTP client or session if needed
        pass

    def get_150_jobs_from_cos(self, ska_values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Call the CareerOneStop API and return the SKA-ranked job list.

        Parameters
        ----------
        ska_values: dict
            Dict containing a "SKAValueList" key with the list of skill rating entries.

        Returns
        -------
        list of dict
            Each entry from "SKARankList" in the API response. Empty list on failure.
        """
        user_id = ONESTOP_USERID
        api_key = ONESTOP_API_KEY

        if not user_id or not api_key:
            logger.warning("CareerOneStop credentials missing; returning empty list.")
            return []

        url = f"{self.CAREERONESTOP_BASE}/{user_id}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = json.dumps(ska_values)
        logger.debug("Posting SKA payload to CareerOneStop: %s", payload[:250])

        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                resp = client.post(url, headers=headers, data=payload)
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("CareerOneStop HTTP error %s: %s", e.response.status_code, e)
            return []
        except httpx.TimeoutException:
            logger.error("CareerOneStop request timed out after %.1fs", self.TIMEOUT_SECONDS)
            return []
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error calling CareerOneStop: %s", e)
            return []

        try:
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to decode CareerOneStop JSON: %s", e)
            return []

        rank_list: Optional[List[Dict[str, Any]]] = data.get("SKARankList")
        if not rank_list:
            logger.warning("CareerOneStop response missing SKARankList key: %s", list(data.keys()))
            return []
        logger.info("Retrieved %d SKA-ranked jobs from CareerOneStop", len(rank_list))
        return rank_list


if __name__ == "__main__":  # pragma: no cover - manual test harness
    from src.services.static_references.example_ska_values import ska_values as example_payload

    repo = AssessmentRepository()
    jobs = repo.get_150_jobs_from_cos(example_payload)
    print(f"Retrieved {len(jobs)} jobs.")
    if jobs:
        print(json.dumps(jobs[:3], indent=2))