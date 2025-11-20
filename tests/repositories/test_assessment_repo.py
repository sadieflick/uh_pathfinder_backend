import json
from typing import Any, Dict

import pytest

from src.repositories.assessment_repo import AssessmentRepository


class DummyResponse:
    def __init__(self, status_code: int, json_data: Dict[str, Any]):
        self.status_code = status_code
        self._json = json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self) -> Dict[str, Any]:  # noqa: D401
        return self._json


class DummyClient:
    def __init__(self, response: DummyResponse):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):  # noqa: D401
        return self._response


@pytest.fixture
def example_payload() -> Dict[str, Any]:
    return {"SKAValueList": [{"ElementId": "2.C.1.a", "DataValue": "3.295"}]}


def test_get_150_jobs_from_cos_success(monkeypatch, example_payload):
    repo = AssessmentRepository()

    dummy_rank_list = [{"ONetCode": "11-1111.00", "Title": "Chief Example Officer", "Score": 99}]
    dummy_response = DummyResponse(200, {"SKARankList": dummy_rank_list})

    import src.repositories.assessment_repo as ar_mod

    monkeypatch.setattr(ar_mod.httpx, "Client", lambda timeout: DummyClient(dummy_response))
    # Provide fake credentials so the method proceeds
    monkeypatch.setattr(ar_mod, "ONESTOP_USERID", "fakeuser")
    monkeypatch.setattr(ar_mod, "ONESTOP_API_KEY", "fakekey")

    results = repo.get_150_jobs_from_cos(example_payload)
    assert results == dummy_rank_list


def test_get_150_jobs_from_cos_missing_credentials(monkeypatch, example_payload):
    repo = AssessmentRepository()
    import src.repositories.assessment_repo as ar_mod
    monkeypatch.setattr(ar_mod, "ONESTOP_USERID", "")
    monkeypatch.setattr(ar_mod, "ONESTOP_API_KEY", "")
    assert repo.get_150_jobs_from_cos(example_payload) == []


def test_get_150_jobs_from_cos_missing_rank_list(monkeypatch, example_payload):
    repo = AssessmentRepository()
    import src.repositories.assessment_repo as ar_mod
    dummy_response = DummyResponse(200, {"unexpected": []})
    monkeypatch.setattr(ar_mod.httpx, "Client", lambda timeout: DummyClient(dummy_response))
    monkeypatch.setattr(ar_mod, "ONESTOP_USERID", "fakeuser")
    monkeypatch.setattr(ar_mod, "ONESTOP_API_KEY", "fakekey")
    assert repo.get_150_jobs_from_cos(example_payload) == []
