import json
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.spec_schema import (
    AcceptanceCriterion,
    DeliveryCommsPack,
    EngineeringArtifactsBundle,
    FeatureItem,
    ImplementationPlan,
    ProjectSpecification,
    QATestCase,
    UserStoryItem,
)
from app.services import ollama_service

client = TestClient(app)


def _mock_spec() -> ProjectSpecification:
    return ProjectSpecification(
        project_summary="Simple leave request portal for employees and managers.",
        features=[FeatureItem(name="Leave Submission", description="Submit leave dates", priority="high")],
        user_stories=[UserStoryItem(role="Employee", goal="submit leave", benefit="request time off")],
        assumptions=["Single company workspace"],
        open_questions=["Are public holidays excluded automatically?"],
        evidence_notes=["[TEXT] Employees submit leave requests"],
    )


def _mock_bundle() -> EngineeringArtifactsBundle:
    return EngineeringArtifactsBundle(
        acceptance_criteria=[
            AcceptanceCriterion(
                story_id="US-001",
                given="an authenticated employee on the leave form",
                when="they submit valid start and end dates",
                then="a pending leave request is created",
            )
        ],
        implementation_plan=ImplementationPlan(
            frontend=["Leave request form view"],
            backend=["POST /leaves endpoint"],
            data=["LeaveRequest table"],
            apis=["POST /api/leaves"],
            dependencies=["Holiday calendar rules (open question)"],
            risks=["Overlapping leave dates if validation is omitted"],
        ),
        qa_test_cases=[
            QATestCase(
                test_id="TC-001",
                category="positive",
                title="Submit valid leave",
                steps=["Enter future dates", "Click Submit"],
                expected_result="Request saved with status Pending",
            ),
            QATestCase(
                test_id="TC-002",
                category="negative",
                title="End date before start date",
                steps=["Enter end date earlier than start date", "Click Submit"],
                expected_result="Validation error displayed",
            ),
            QATestCase(
                test_id="TC-003",
                category="edge",
                title="Same-day single-day leave",
                steps=["Set start date equal to end date", "Click Submit"],
                expected_result="Creates 1-day leave request",
            ),
        ],
        developer_prompt="Implement a leave request form and POST /api/leaves endpoint following US-001.",
        client_update="Scoped the Leave Request MVP including submission form and validation rules.",
        release_notes="v0.1 Draft: Added employee leave submission workflow.",
    )


def test_generate_and_export_engineering_artifacts(monkeypatch):
    monkeypatch.setattr(ollama_service, "generate_specification", lambda **kwargs: _mock_spec())
    monkeypatch.setattr(ollama_service, "generate_engineering_artifacts", lambda **kwargs: _mock_bundle())

    # 1. Create specification run
    spec_res = client.post(
        "/api/v1/generate",
        json={"project_name": "Leave Portal", "raw_text": "Employees submit leave requests online."},
    )
    assert spec_res.status_code == 200
    run_id = spec_res.json()["run_id"]

    # 2. Generate linked engineering artifacts
    art_res = client.post(f"/api/v1/runs/{run_id}/artifacts")
    assert art_res.status_code == 200
    body = art_res.json()
    assert body["run_id"] == run_id
    assert len(body["artifacts"]["qa_test_cases"]) == 3

    # 3. Verify Markdown export
    md_res = client.get(f"/api/v1/runs/{run_id}/export?format=markdown")
    assert md_res.status_code == 200
    assert "# DevFlow Copilot Delivery Package" in md_res.text
    assert "## 5. Acceptance Criteria" in md_res.text

    # 4. Verify JSON export
    json_res = client.get(f"/api/v1/runs/{run_id}/export?format=json")
    assert json_res.status_code == 200
    exported = json.loads(json_res.text)
    assert exported["run_id"] == run_id
    assert "engineering_artifacts" in exported


def test_artifacts_missing_run_returns_404():
    res = client.post("/api/v1/runs/999999/artifacts")
    assert res.status_code == 404