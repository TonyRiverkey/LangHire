import copy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import load_settings, save_settings, load_profile, save_profile
from resume import main_resume
from resume.application_documents import text_pdf


@pytest.fixture
def resume_flow(data_dir, monkeypatch):
    source = data_dir / "original.pdf"
    text_pdf("Candidate\nHRIS administration and real experience", source)
    save_settings({"resume_path": str(source)})
    save_profile({"name": "Candidate", "skills": ["HRIS"], "notes": "Existing notes"})
    job = {"skills_to_consider": [{"skill": "Workforce reporting"}]}
    monkeypatch.setattr(main_resume, "get_job", lambda _: copy.deepcopy(job))
    from core import llm_factory
    async def invoke(messages):
        assert "I produced monthly workforce reports" in messages[0].content
        return SimpleNamespace(completion="Candidate\nHRIS administration\nProduced monthly workforce reports")
    monkeypatch.setattr(llm_factory, "create_llm", lambda _: SimpleNamespace(ainvoke=invoke))
    app = FastAPI()
    app.include_router(main_resume.router)
    return TestClient(app), source


def make_draft(client):
    response = client.post("/main-resume/draft", json={"job_url": "https://example.com/a", "skills": [
        {"skill": "Workforce reporting", "experience": "I produced monthly workforce reports"}]})
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_needs_confirmation_and_preserves_source(resume_flow):
    client, source = resume_flow
    original = source.read_bytes()
    draft = make_draft(client)
    assert load_settings()["resume_path"] == str(source)
    assert load_profile()["skills"] == ["HRIS"]
    response = client.post("/main-resume/activate", json={"id": draft["id"]})
    assert response.status_code == 200
    assert load_settings()["resume_path"].endswith("draft.pdf")
    assert source.read_bytes() == original
    assert load_profile()["skills"] == ["HRIS", "Workforce reporting"]


def test_unconfirmed_skills_and_stale_source_are_rejected(resume_flow):
    client, source = resume_flow
    response = client.post("/main-resume/draft", json={"job_url": "https://example.com/a", "skills": [
        {"skill": "Imaginary credential", "experience": "I produced monthly workforce reports"}]})
    assert response.status_code == 400
    draft = make_draft(client)
    text_pdf("Changed source", source)
    assert client.post("/main-resume/activate", json={"id": draft["id"]}).status_code == 409
    assert load_settings()["resume_path"] == str(source)
