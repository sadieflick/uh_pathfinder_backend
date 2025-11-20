"""Tests for SkillsPrescoringService."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.skills_prescoring_service import SkillsPrescoringService


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def prescoring_service():
    """Create a SkillsPrescoringService instance."""
    return SkillsPrescoringService()


@pytest.fixture
def sample_ranked_skills():
    """Sample output from get_interest_filtered_skills."""
    return [
        {"element_id": "2.A.1.e", "element_name": "Mathematics", "total_frequency": 150},
        {"element_id": "2.C.3.a", "element_name": "Computers and Electronics", "total_frequency": 140},
        {"element_id": "2.B.2.i", "element_name": "Complex Problem Solving", "total_frequency": 130},
        # ... would have 37 more in real data
    ]


def test_skills_reference_loads(prescoring_service):
    """Verify skills reference data is loaded from JSON."""
    assert len(prescoring_service._skills_reference) > 0
    assert "2.A.1.e" in prescoring_service._skills_reference
    
    math_skill = prescoring_service._skills_reference["2.A.1.e"]
    assert math_skill["ElementName"] == "Mathematics"
    assert "DataPoint50" in math_skill
    assert "DataPoint65" in math_skill


@patch("src.services.skills_prescoring_service.RiasecRepository")
def test_prescore_skills_returns_correct_structure(
    mock_repo_class, 
    prescoring_service, 
    mock_db_session,
    sample_ranked_skills
):
    """Verify prescore_skills returns expected data structure."""
    mock_repo = mock_repo_class.return_value
    mock_repo.get_interest_filtered_skills.return_value = sample_ranked_skills
    
    result = prescoring_service.prescore_skills("IRE", mock_db_session)
    
    assert result["riasec_code"] == "IRE"
    assert "skills" in result
    assert len(result["skills"]) == len(sample_ranked_skills)
    
    first_skill = result["skills"][0]
    assert "element_id" in first_skill
    assert "element_name" in first_skill
    assert "initial_score" in first_skill
    assert "rank" in first_skill
    assert first_skill["rank"] == 1


@patch("src.services.skills_prescoring_service.RiasecRepository")
def test_prescore_top_20_get_datapoint50(
    mock_repo_class,
    prescoring_service,
    mock_db_session
):
    """Verify top 20 skills are assigned DataPoint50 scores."""
    # Create 40 mock skills
    mock_skills = [
        {"element_id": f"2.A.{i}", "element_name": f"Skill {i}", "total_frequency": 100 - i}
        for i in range(40)
    ]
    
    mock_repo = mock_repo_class.return_value
    mock_repo.get_interest_filtered_skills.return_value = mock_skills
    
    # Mock the skills reference to have consistent DataPoint values
    with patch.object(prescoring_service, "_skills_reference", {
        f"2.A.{i}": {
            "ElementId": f"2.A.{i}",
            "ElementName": f"Skill {i}",
            "DataPoint35": 2.5,
            "DataPoint50": 3.5,
            "DataPoint65": 4.5,
            "DataPoint80": 5.5,
            "Question": "Test?",
            "EasyReadDescription": "Test desc",
            "AnchorFirst": "First",
            "AnchorThrid": "Third",
            "AnchorLast": "Last"
        }
        for i in range(40)
    }):
        result = prescoring_service.prescore_skills("IRE", mock_db_session)
    
    # First 20 should have DataPoint50 (3.5)
    for i in range(20):
        assert result["skills"][i]["initial_score"] == 3.5, \
            f"Skill at rank {i+1} should have DataPoint50 score"
    
    # Remaining should have DataPoint35 (2.5)
    for i in range(20, 40):
        assert result["skills"][i]["initial_score"] == 2.5, \
            f"Skill at rank {i+1} should have DataPoint35 score"


@patch("src.services.skills_prescoring_service.RiasecRepository")
def test_apply_task_selection_bumps_selected(
    mock_repo_class,
    prescoring_service,
    mock_db_session
):
    """Verify selected skills are bumped to DataPoint65."""
    mock_skills = [
        {"element_id": "2.A.1.e", "element_name": "Mathematics", "total_frequency": 150},
        {"element_id": "2.C.3.a", "element_name": "Computers", "total_frequency": 140},
    ]
    
    mock_repo = mock_repo_class.return_value
    mock_repo.get_interest_filtered_skills.return_value = mock_skills
    
    with patch.object(prescoring_service, "_skills_reference", {
        "2.A.1.e": {
            "ElementId": "2.A.1.e",
            "ElementName": "Mathematics",
            "DataPoint35": 2.142,
            "DataPoint50": 3.06,
            "DataPoint65": 3.978,
            "DataPoint80": 4.896,
            "Question": "Math?",
            "EasyReadDescription": "Math desc",
            "AnchorFirst": "Add",
            "AnchorThrid": "Algebra",
            "AnchorLast": "Calculus"
        },
        "2.C.3.a": {
            "ElementId": "2.C.3.a",
            "ElementName": "Computers",
            "DataPoint35": 2.408,
            "DataPoint50": 3.41,
            "DataPoint65": 4.412,
            "DataPoint80": 5.414,
            "Question": "Comp?",
            "EasyReadDescription": "Comp desc",
            "AnchorFirst": "Use",
            "AnchorThrid": "Create",
            "AnchorLast": "Build"
        }
    }):
        result = prescoring_service.apply_task_selection(
            "IRE",
            ["2.A.1.e"],  # Only select Mathematics
            mock_db_session
        )
    
    # Find the skills in the result
    math_skill = next(s for s in result["skills"] if s["element_id"] == "2.A.1.e")
    comp_skill = next(s for s in result["skills"] if s["element_id"] == "2.C.3.a")
    
    # Math should be bumped to DataPoint65
    assert math_skill["selected"] is True
    assert math_skill["score"] == 3.978
    
    # Computers should keep initial score (DataPoint50 since it's rank 1)
    assert comp_skill["selected"] is False
    assert comp_skill["score"] == 3.41  # DataPoint50
    
    # Refinement required should only include selected
    assert result["refinement_required"] == ["2.A.1.e"]


def test_build_ska_payload(prescoring_service):
    """Verify SKA payload is built correctly for CareerOneStop."""
    skills = [
        {"element_id": "2.A.1.e", "score": 3.978},
        {"element_id": "2.C.3.a", "score": 4.412},
        {"element_id": "2.B.2.i", "score": 3.31},
    ]
    
    payload = prescoring_service.build_ska_payload(skills)
    
    assert "SKAValueList" in payload
    assert len(payload["SKAValueList"]) == 3
    
    # Verify structure
    first = payload["SKAValueList"][0]
    assert "ElementId" in first
    assert "DataValue" in first
    assert first["ElementId"] == "2.A.1.e"
    assert first["DataValue"] == "3.978"
    
    # All DataValues should be strings
    for item in payload["SKAValueList"]:
        assert isinstance(item["DataValue"], str)


@patch("src.services.skills_prescoring_service.RiasecRepository")
def test_prescore_handles_missing_skills_reference(
    mock_repo_class,
    prescoring_service,
    mock_db_session
):
    """Verify graceful handling when skill not found in reference."""
    mock_skills = [
        {"element_id": "FAKE.ID", "element_name": "Fake Skill", "total_frequency": 100}
    ]
    
    mock_repo = mock_repo_class.return_value
    mock_repo.get_interest_filtered_skills.return_value = mock_skills
    
    result = prescoring_service.prescore_skills("IRE", mock_db_session)
    
    # Should skip the fake skill
    assert len(result["skills"]) == 0


@patch("src.services.skills_prescoring_service.RiasecRepository")
def test_prescore_handles_empty_results(
    mock_repo_class,
    prescoring_service,
    mock_db_session
):
    """Verify fallback when no skills found for RIASEC code."""
    mock_repo = mock_repo_class.return_value
    mock_repo.get_interest_filtered_skills.return_value = []
    
    result = prescoring_service.prescore_skills("ZZZ", mock_db_session)
    
    # Should still return structure with riasec_code
    assert result["riasec_code"] == "ZZZ"
    # Skills list may be populated from reference as fallback
    assert isinstance(result["skills"], list)
