from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import resume_upload


def client():
    app = FastAPI()
    app.post("/resume/upload")(resume_upload.upload_resume)
    return TestClient(app)


def test_upload_stores_pdf_with_generated_path(data_dir):
    content = b"%PDF-1.4\nresume contents"
    response = client().post("/resume/upload", content=content)
    assert response.status_code == 200
    path = Path(response.json()["resume_path"])
    assert path.parent == data_dir / "resumes"
    assert path.suffix == ".pdf"
    assert path.read_bytes() == content
    second = client().post("/resume/upload", content=content)
    assert second.json()["resume_path"] != str(path)


def test_invalid_pdf_is_not_stored(data_dir):
    for content in (b"", b"not a PDF"):
        response = client().post("/resume/upload", content=content)
        assert response.status_code == 400
    assert not (data_dir / "resumes").exists()


def test_upload_limit_is_enforced_while_streaming(data_dir, monkeypatch):
    monkeypatch.setattr(resume_upload, "MAX_RESUME_BYTES", 8)
    response = client().post("/resume/upload", content=b"%PDF-1.4\ntoo large")
    assert response.status_code == 413
    assert not (data_dir / "resumes").exists()


def test_upload_stores_word_resume(data_dir):
    from io import BytesIO
    from docx import Document
    from resume.text import resume_text

    buffer = BytesIO()
    source = Document()
    source.add_paragraph("Candidate Word resume")
    source.save(buffer)
    response = client().post("/resume/upload", content=buffer.getvalue())
    assert response.status_code == 200
    path = Path(response.json()["resume_path"])
    assert path.parent == data_dir / "resumes"
    assert path.suffix == ".docx"
    assert resume_text(path) == "Candidate Word resume"
