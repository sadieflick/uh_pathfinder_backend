"""Repository for RIASEC profile lookups and matched jobs retrieval."""
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text


class RiasecRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_profile(self, code: str) -> Optional[Dict]:
        """Get RIASEC profile by code using raw SQL to avoid relationship issues."""
        query = text("SELECT code FROM riasec.riasec_profiles WHERE UPPER(code) = UPPER(:code)")
        result = self.db.execute(query, {"code": code}).first()
        
        if result:
            # Return as dict to avoid ORM relationship issues
            return {"code": result.code}
        return None

    def top_matched_jobs(self, profile: Dict, limit: int = 15) -> List[dict]:
        """Return matched jobs with real titles and career data from onet and public schemas.
        
        Uses raw SQL to join interest_matched_jobs with onet occupation_data
        and public.occupation for salary/outlook information.
        Handles case-insensitive matching for RIASEC codes.
        """
        query = text("""
            SELECT 
                imj.occ_code, 
                od.title,
                o.median_annual_wage,
                o.employment_outlook
            FROM riasec.interest_matched_jobs imj
            JOIN onet.occupation_data od ON imj.occ_code = od.onetsoc_code
            LEFT JOIN public.occupation o ON imj.occ_code = o.onet_code
            WHERE UPPER(imj.fk_riasec_code) = UPPER(:code)
            ORDER BY imj.interest_sum DESC
            LIMIT :limit
        """)
        
        results = self.db.execute(query, {"code": profile["code"], "limit": limit}).all()
        return [
            {
                "occ_code": row.occ_code, 
                "title": row.title,
                "median_salary": row.median_annual_wage,
                "growth_outlook": row.employment_outlook
            }
            for row in results
        ]

    def get_interest_filtered_skills(self, riasec_code: str) -> List[Dict[str, any]]:
        """Get skills ranked by frequency in interest-matched jobs for a RIASEC code.
        
        Aggregates skill frequency across all jobs matched to the given RIASEC profile,
        filtered to the standard 40 CareerOneStop skills.
        
        Parameters
        ----------
        riasec_code : str
            3-letter RIASEC code (e.g., 'IRE')
        
        Returns
        -------
        list of dict
            Each dict contains: element_id, element_name, total_frequency
            Ordered by total_frequency DESC
        """
        # The 40 standard CareerOneStop skill element IDs
        skill_ids = [
            '2.C.7.b', '2.B.2.i', '2.A.1.e', '2.C.1.d', '2.C.4.d', 
            '2.B.1.e', '1.A.3.c.3', '2.C.1.f', '2.B.4.g', '2.B.1.d', 
            '2.B.3.e', '2.C.7.c', '2.B.1.f', '2.B.5.a', '2.A.1.f', 
            '2.B.3.m', '2.C.6', '2.C.4.e', '2.A.1.c', '2.C.1.e', 
            '2.A.2.d', '2.C.9.a', '2.C.8.a', '2.C.3.e', '2.C.5.b', 
            '2.C.1.b', '2.C.3.a', '2.B.3.k', '2.C.4.f', '1.A.1.d.1', 
            '2.C.1.a', '2.B.3.l', '2.B.5.b', '2.C.5.a', '2.C.2.a', 
            '2.A.1.d', '2.B.3.a', '2.C.1.c', '2.C.4.c', '2.C.3.d'
        ]
        
        query = text("""
            SELECT element_id, element_name, SUM(freq) as total_frequency
            FROM (
                SELECT DISTINCT 
                    ifs.skill_id as element_id,
                    cmr.element_name as element_name,
                    COUNT(ifs.frequency) as freq
                FROM riasec.interest_filtered_skills ifs
                JOIN onet.content_model_reference cmr
                    ON cmr.element_id = ifs.skill_id
                WHERE UPPER(ifs.fk_riasec_code) = UPPER(:riasec_code)
                    AND ifs.skill_id = ANY(:skill_ids)
                GROUP BY ifs.skill_id, cmr.element_name, ifs.frequency
            ) as skill_freq
            GROUP BY element_id, element_name
            ORDER BY total_frequency DESC
        """)
        
        results = self.db.execute(
            query, 
            {"riasec_code": riasec_code, "skill_ids": skill_ids}
        ).all()
        
        return [
            {
                "element_id": row.element_id,
                "element_name": row.element_name,
                "total_frequency": row.total_frequency
            }
            for row in results
        ]
