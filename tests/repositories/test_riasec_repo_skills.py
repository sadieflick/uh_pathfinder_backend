"""Tests for RiasecRepository.get_interest_filtered_skills method."""
import pytest
from sqlalchemy import text

from src.repositories.riasec_repo import RiasecRepository


@pytest.fixture
def sample_riasec_repo(db_session):
    """Create a repository instance with a test DB session."""
    return RiasecRepository(db_session)


def test_get_interest_filtered_skills_returns_list(sample_riasec_repo):
    """Verify method returns a list (may be empty if no data in test DB)."""
    result = sample_riasec_repo.get_interest_filtered_skills("IRE")
    assert isinstance(result, list)


def test_get_interest_filtered_skills_structure(sample_riasec_repo):
    """If results exist, validate structure of returned dicts."""
    result = sample_riasec_repo.get_interest_filtered_skills("IRE")
    
    if result:  # Only validate if data exists
        first = result[0]
        assert "element_id" in first
        assert "element_name" in first
        assert "total_frequency" in first
        assert isinstance(first["element_id"], str)
        assert isinstance(first["element_name"], str)
        assert isinstance(first["total_frequency"], int)


def test_get_interest_filtered_skills_ordering(sample_riasec_repo):
    """Verify results are ordered by total_frequency DESC."""
    result = sample_riasec_repo.get_interest_filtered_skills("IRE")
    
    if len(result) > 1:
        frequencies = [skill["total_frequency"] for skill in result]
        assert frequencies == sorted(frequencies, reverse=True), \
            "Skills should be ordered by total_frequency descending"


def test_get_interest_filtered_skills_case_insensitive(sample_riasec_repo):
    """Verify RIASEC code matching is case-insensitive."""
    result_upper = sample_riasec_repo.get_interest_filtered_skills("IRE")
    result_lower = sample_riasec_repo.get_interest_filtered_skills("ire")
    result_mixed = sample_riasec_repo.get_interest_filtered_skills("IrE")
    
    # All should return the same results
    assert len(result_upper) == len(result_lower) == len(result_mixed)


def test_get_interest_filtered_skills_invalid_code(sample_riasec_repo):
    """Non-existent RIASEC codes should return empty list."""
    result = sample_riasec_repo.get_interest_filtered_skills("ZZZ")
    assert result == []


def test_get_interest_filtered_skills_filters_to_40_skills(sample_riasec_repo):
    """Verify only the 40 standard CareerOneStop skills are returned."""
    result = sample_riasec_repo.get_interest_filtered_skills("IRE")
    
    # Result should be <= 40 (the standard skill set)
    assert len(result) <= 40
    
    # All element_ids should be in the standard 40 skill list
    standard_skills = {
        '2.C.7.b', '2.B.2.i', '2.A.1.e', '2.C.1.d', '2.C.4.d', 
        '2.B.1.e', '1.A.3.c.3', '2.C.1.f', '2.B.4.g', '2.B.1.d', 
        '2.B.3.e', '2.C.7.c', '2.B.1.f', '2.B.5.a', '2.A.1.f', 
        '2.B.3.m', '2.C.6', '2.C.4.e', '2.A.1.c', '2.C.1.e', 
        '2.A.2.d', '2.C.9.a', '2.C.8.a', '2.C.3.e', '2.C.5.b', 
        '2.C.1.b', '2.C.3.a', '2.B.3.k', '2.C.4.f', '1.A.1.d.1', 
        '2.C.1.a', '2.B.3.l', '2.B.5.b', '2.C.5.a', '2.C.2.a', 
        '2.A.1.d', '2.B.3.a', '2.C.1.c', '2.C.4.c', '2.C.3.d'
    }
    
    for skill in result:
        assert skill["element_id"] in standard_skills, \
            f"Skill {skill['element_id']} not in standard 40 skills"
