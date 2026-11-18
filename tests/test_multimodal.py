from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rejects_unsupported_file_extension():
    response = client.post(
        "/api/v1/generate-multimodal",
        data={"project_name": "Bad Upload Test", "raw_text": ""},
        files={"image": ("malware.exe", b"MZ-fake-binary", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "unsupported file type" in response.json()["detail"].lower()


def test_rejects_empty_text_and_no_image():
    response = client.post(
        "/api/v1/generate-multimodal",
        data={"project_name": "Empty Multimodal Test", "raw_text": "   "},
    )
    assert response.status_code == 422