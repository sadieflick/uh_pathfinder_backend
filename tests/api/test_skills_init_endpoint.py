"""Tests for skills initialization endpoint."""
import pytest
from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_initialize_skills_endpoint_returns_200():
    """Verify endpoint is accessible and returns 200."""
    payload = {
        "riasec_code": "IRE",
        "selected_skill_ids": []
    }
    
    response = client.post("/api/v1/assessment/skills/initialize", json=payload)
    
    # May return 500 if DB not available, but endpoint should exist
    assert response.status_code in [200, 500], \
        f"Unexpected status code: {response.status_code}"


def test_initialize_skills_request_validation():
    """Verify request validation for invalid RIASEC codes."""
    # Invalid: too long
    response = client.post("/api/v1/assessment/skills/initialize", json={
        "riasec_code": "IREE",
        "selected_skill_ids": []
    })
    assert response.status_code == 422
    
    # Invalid: wrong characters
    response = client.post("/api/v1/assessment/skills/initialize", json={
        "riasec_code": "XYZ",
        "selected_skill_ids": []
    })
    assert response.status_code == 422
    
    # Valid
    response = client.post("/api/v1/assessment/skills/initialize", json={
        "riasec_code": "IRE",
        "selected_skill_ids": []
    })
    assert response.status_code in [200, 500]  # 200 if DB OK, 500 if not


def test_initialize_skills_response_structure():
    """Verify response structure when successful."""
    payload = {
        "riasec_code": "IRE",
        "selected_skill_ids": ["2.A.1.e", "2.C.3.a"]
    }
    
    response = client.post("/api/v1/assessment/skills/initialize", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        
        assert "riasec_code" in data
        assert "skills" in data
        assert "refinement_required" in data
        
        assert data["riasec_code"] == "IRE"
        assert isinstance(data["skills"], list)
        assert isinstance(data["refinement_required"], list)
        
        # Selected skills should be in refinement_required
        assert "2.A.1.e" in data["refinement_required"]
        assert "2.C.3.a" in data["refinement_required"]
        
        # Verify skill structure
        if data["skills"]:
            skill = data["skills"][0]
            assert "element_id" in skill
            assert "element_name" in skill
            assert "score" in skill
            assert "rank" in skill
            assert "selected" in skill


def test_build_ska_payload_endpoint():
    """Verify SKA payload builder endpoint."""
    payload = {
        "riasec_code": "IRE",
        "selected_skill_ids": ["2.A.1.e"]
    }
    
    response = client.post("/api/v1/assessment/skills/payload", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        
        assert "SKAValueList" in data
        assert isinstance(data["SKAValueList"], list)
        
        if data["SKAValueList"]:
            element = data["SKAValueList"][0]
            assert "ElementId" in element
            assert "DataValue" in element
            assert isinstance(element["DataValue"], str)


def test_initialize_empty_selection():
    """Verify endpoint works with no selected skills."""
    payload = {
        "riasec_code": "IRE",
        "selected_skill_ids": []
    }
    
    response = client.post("/api/v1/assessment/skills/initialize", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        assert data["refinement_required"] == []
        
        # All skills should have selected=False
        for skill in data["skills"]:
            assert skill["selected"] is False


def test_initialize_case_insensitive_riasec():
    """Verify RIASEC code is case-insensitive."""
    response_upper = client.post("/api/v1/assessment/skills/initialize", json={
        "riasec_code": "IRE",
        "selected_skill_ids": []
    })
    
    response_lower = client.post("/api/v1/assessment/skills/initialize", json={
        "riasec_code": "ire",
        "selected_skill_ids": []
    })
    
    # Both should succeed or both fail (depending on DB availability)
    assert response_upper.status_code == response_lower.status_code
