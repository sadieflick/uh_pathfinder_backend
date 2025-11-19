import httpx
from sqlalchemy.orm import Session
import json
# from fastapi import Depends
# from core.database import get_db
from src.core.config import ONET_USERNAME, ONET_PASSWORD

class AssessmentRepository:
    # , db: Session = Depends(get_db) (removing temporarily to test the API call independently)
    def __init__(self):
        # self.db = db
        pass

    def get_150_jobs_from_cos(self, ska_values: str) -> list:
        """
        Calls the CareerOneStop API to get SKA-ranked jobs.
        (This is your get150jobs.py code)
        """
        USER_ID = ONET_USERNAME  # You'll get these from core.config
        API_KEY = ONET_PASSWORD
        
        url = f"https://api.careeronestop.org/v1/skillsmatcher/{USER_ID}"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        json_payload = json.dumps(ska_values)

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, data=json_payload, timeout=15.0)
                response.raise_for_status() # Raise error for 4xx/5xx
                
                data = response.json()
                if "SKARankList" in data:
                    return data["SKARankList"]
                return []
        except httpx.HTTPStatusError as e:
            print(f"HTTP error calling CareerOneStop: {e}")
            return []
        except Exception as e:
            print(f"Error: {e}")
            return []