"""Service for interest-weighted skills assessment and pre-scoring."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.repositories.riasec_repo import RiasecRepository

logger = logging.getLogger(__name__)

# Path to static skill definitions
STATIC_DIR = Path(__file__).parent / "static_references"
SKILLS_FILE = STATIC_DIR / "oneStop40Skills.json"


class SkillsPrescoringService:
    """Handles interest-weighted skill pre-scoring based on RIASEC profiles.
    
    Pre-scores the 40 CareerOneStop skills based on:
    - Top 20 skills by interest-job frequency → DataPoint50
    - Remaining 20 skills → DataPoint35
    """

    def __init__(self) -> None:
        self._skills_reference: Dict[str, Dict[str, Any]] = {}
        self._load_skills_reference()

    def _load_skills_reference(self) -> None:
        """Load oneStop40Skills.json into a lookup dict keyed by ElementId."""
        if self._skills_reference:
            return
        
        raw = json.loads(SKILLS_FILE.read_text())
        for skill in raw:
            element_id = skill.get("ElementId")
            if element_id:
                self._skills_reference[element_id] = skill
        
        logger.info("Loaded %d skill definitions from oneStop40Skills.json", len(self._skills_reference))

    def prescore_skills(self, riasec_code: str, db: Session) -> Dict[str, Any]:
        """Pre-score 40 skills for a given RIASEC code.
        
        Parameters
        ----------
        riasec_code : str
            3-letter RIASEC code (e.g., 'IRE')
        db : Session
            SQLAlchemy database session
        
        Returns
        -------
        dict
            {
                "riasec_code": "IRE",
                "skills": [
                    {
                        "element_id": "2.A.1.e",
                        "element_name": "Mathematics",
                        "initial_score": 3.06,
                        "rank": 1,
                        "anchor_third": "Use algebra...",
                        "anchor_last": "Use advanced math...",
                        "question": "What is your level...",
                        "easy_read_description": "Using math..."
                    },
                    ...
                ]
            }
        """
        repo = RiasecRepository(db)
        
        # Get interest-filtered skills ranked by frequency
        ranked_skills = repo.get_interest_filtered_skills(riasec_code)
        
        if not ranked_skills:
            logger.warning("No interest-filtered skills found for RIASEC code %s", riasec_code)
            # Fall back to returning all 40 skills at DataPoint35
            ranked_skills = [
                {"element_id": eid, "element_name": self._skills_reference.get(eid, {}).get("ElementName", ""), "total_frequency": 0}
                for eid in self._skills_reference.keys()
            ]
        
        # Build prescored skill list
        prescored_skills: List[Dict[str, Any]] = []
        
        for idx, skill_data in enumerate(ranked_skills):
            element_id = skill_data["element_id"]
            skill_ref = self._skills_reference.get(element_id)
            
            if not skill_ref:
                logger.warning("Skill %s not found in reference file", element_id)
                continue
            
            # Top 20 → DataPoint50, rest → DataPoint35
            if idx < 20:
                initial_score = skill_ref.get("DataPoint50", 3.0)
            else:
                initial_score = skill_ref.get("DataPoint35", 2.5)
            
            prescored_skills.append({
                "element_id": element_id,
                "element_name": skill_data["element_name"],
                "initial_score": initial_score,
                "rank": idx + 1,
                "anchor_first": skill_ref.get("AnchorFirst", ""),
                "anchor_third": skill_ref.get("AnchorThrid", ""),  # Note: typo in JSON
                "anchor_last": skill_ref.get("AnchorLast", ""),
                "question": skill_ref.get("Question", ""),
                "easy_read_description": skill_ref.get("EasyReadDescription", ""),
                "data_point_35": skill_ref.get("DataPoint35", 0.0),
                "data_point_50": skill_ref.get("DataPoint50", 0.0),
                "data_point_65": skill_ref.get("DataPoint65", 0.0),
                "data_point_80": skill_ref.get("DataPoint80", 0.0),
            })
        
        return {
            "riasec_code": riasec_code.upper(),
            "skills": prescored_skills
        }

    def apply_task_selection(
        self,
        riasec_code: str,
        selected_skill_ids: List[str],
        db: Session
    ) -> Dict[str, Any]:
        """Apply task selection bumps: selected skills → DataPoint65.
        
        Parameters
        ----------
        riasec_code : str
            3-letter RIASEC code
        selected_skill_ids : list of str
            Element IDs of skills the user has performed
        db : Session
            SQLAlchemy database session
        
        Returns
        -------
        dict
            {
                "riasec_code": "IRE",
                "skills": [...],  // All 40 skills with bumped scores
                "refinement_required": ["2.A.1.e", ...]  // Selected skill IDs
            }
        """
        # Get prescored skills
        prescored = self.prescore_skills(riasec_code, db)
        
        selected_set = set(selected_skill_ids)
        refinement_required: List[str] = []
        
        for skill in prescored["skills"]:
            element_id = skill["element_id"]
            
            if element_id in selected_set:
                # Bump to DataPoint65
                skill["score"] = skill["data_point_65"]
                skill["selected"] = True
                refinement_required.append(element_id)
            else:
                # Keep initial score (DataPoint50 or DataPoint35)
                skill["score"] = skill["initial_score"]
                skill["selected"] = False
        
        return {
            "riasec_code": prescored["riasec_code"],
            "skills": prescored["skills"],
            "refinement_required": refinement_required
        }

    def build_ska_payload(self, skills: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build CareerOneStop SKA payload from skill scores.
        
        Parameters
        ----------
        skills : list of dict
            Each dict must have "element_id" and "score" keys
        
        Returns
        -------
        dict
            {
                "SKAValueList": [
                    {"ElementId": "2.A.1.e", "DataValue": "3.978"},
                    ...
                ]
            }
        """
        ska_list = [
            {
                "ElementId": skill["element_id"],
                "DataValue": str(skill["score"])
            }
            for skill in skills
        ]
        
        return {"SKAValueList": ska_list}
