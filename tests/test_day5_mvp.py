from fastapi.testclient import TestClient
from app.main import app
from app.schemas.spec_schema import FeatureItem, ProjectSpecification, UserStoryItem
from app.api import routes

client = TestClient(app)


def _stub_spec() -> ProjectSpecification:
    return ProjectSpecification(
        project_summary="Inventory alert system for warehouse supervisors.",
        features=[FeatureItem(name="Low Stock Alert", description="Notify when stock is low", priority="high")],
        user_stories=[UserStoryItem(role="Supervisor", goal="receive alerts", benefit="reorder on time")],
        assumptions=["Email alerts used"],
        open_questions=["What is the minimum threshold?"],
        evidence_notes=["[TEXT] Notify when stock is low"],
    )


def test_human_review_workflow_and_history(monkeypatch):
    monkeypatch.setattr(routes, "generate_specification", lambda **kwargs: _stub_spec())

    gen_res = client.post(
        "/api/v1/generate",
        json={"project_name": "Warehouse Alerts", "raw_text": "Notify supervisors when stock drops low."},
    )
    assert gen_res.status_code == 200
    body = gen_res.json()
    assert body["review_status"] == "draft"

    # Approve artifact
    rev_res = client.post(
        f"/api/v1/artifacts/{body['artifact_id']}/review",
        json={"action": "approved", "reviewer_note": "Looks accurate"},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["review_status"] == "approved"

    # Verify history & run detail reflect approved state
    detail_res = client.get(f"/api/v1/runs/{body['run_id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["review_status"] == "approved"
    assert len(detail_res.json()["review_history"]) >= 1