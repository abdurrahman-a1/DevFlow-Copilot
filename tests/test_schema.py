import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.spec_schema import ProjectSpecification
from app.services import ollama_service

client = TestClient(app)


def test_schema_rejects_missing_required_fields():
    invalid_payload = '{"features": [], "user_stories": []}'  # missing project_summary
    with pytest.raises(ValidationError):
        ProjectSpecification.model_validate_json(invalid_payload)


def test_schema_rejects_invalid_priority():
    bad_priority = """
    {
        "project_summary": "A valid summary string that is long enough.",
        "features": [{"name": "Login", "description": "User login", "priority": "urgent"}],
        "user_stories": [],
        "assumptions": [],
        "open_questions": []
    }
    """
    with pytest.raises(ValidationError):
        ProjectSpecification.model_validate_json(bad_priority)


def test_api_handles_too_short_input_gracefully():
    response = client.post(
        "/api/v1/generate",
        json={"project_name": "Short Test", "raw_text": "hi"},
    )
    assert response.status_code == 422
    assert "too short" in response.json()["detail"].lower()


def test_api_handles_ollama_runtime_failure_gracefully(monkeypatch):
    def fake_chat(*args, **kwargs):
        raise RuntimeError("Connection refused to Ollama daemon")

    monkeypatch.setattr(ollama_service.ollama, "chat", fake_chat)

    response = client.post(
        "/api/v1/generate",
        json={
            "project_name": "Offline Runtime Test",
            "raw_text": "Build a basic employee directory with search and profile views.",
        },
    )
    assert response.status_code == 503
    assert "ollama runtime error" in response.json()["detail"].lower()