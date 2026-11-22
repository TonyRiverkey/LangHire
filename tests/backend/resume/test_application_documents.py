import copy
from types import SimpleNamespace

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import save_settings, save_profile
from resume import application_documents as documents
PRODUCTION_GENERATE_LETTER = documents.generate_letter


@pytest.fixture
def workflow(data_dir, monkeypatch):
    source = data_dir / "source.pdf"
    documents.text_pdf("Candidate Resume\nReal HR experience", source)
    save_settings({"resume_path": str(source)})
    save_profile({"name": "Candidate", "skills": ["HRIS"]})
    jobs = {"https://example.com/a": {"url": "https://example.com/a", "title": "HR Partner", "company": "Alpha", "status": "pending",
                                    "description": "Please save your cover letter and resume as one PDF document."},
            "https://example.com/b": {"url": "https://example.com/b", "title": "HR Manager", "company": "Beta", "status": "pending",
                                    "description": "Include a cover letter with your resume."}}
    from core import shared_config
    monkeypatch.setattr(shared_config, "read_jobs", lambda: copy.deepcopy(jobs))
    monkeypatch.setattr(shared_config, "update_job", lambda url, **fields: jobs[url].update(copy.deepcopy(fields)))
    monkeypatch.setattr(documents, "verified_tailored_path", lambda job: str(source))
    async def generate(job):
        return f"Dear {job['company']},\nJob-specific HR experience."
    monkeypatch.setattr(documents, "generate_letter", generate)
    app = FastAPI()
    app.include_router(documents.router)
    return SimpleNamespace(client=TestClient(app), jobs=jobs, source=source)


@pytest.mark.parametrize("text,mode", [
    ("Upload a resume", "none"), ("Cover letter optional", "none"),
    ("No cover letter required", "none"), ("Please include a cover letter", "separate"),
    ("A cover letter is not required", "none"), ("Upload a covering letter", "separate"),
    ("Save your (1) cover letter, and (2) resume as one pdf document", "combined"),
])
def test_required_format(text, mode):
    assert documents.required_mode(text) == mode


def test_generated_pdf_preserves_unicode_and_paginates_long_text(tmp_path):
    path = tmp_path / "letter.pdf"
    line = "Martínez — I’m experienced in HR. " + "x" * 180
    text = "\n".join([line] * 60)
    documents.text_pdf(text, path)
    with pymupdf.open(path) as pdf:
        assert len(pdf) > 1
        extracted = "".join(page.get_text() for page in pdf)
        assert "".join(extracted.split()) == "".join(text.split())
        for page in pdf:
            assert all(0 <= block[0] < block[2] <= 612 and 0 <= block[1] < block[3] <= 792 for block in page.get_text("blocks"))


def prepare(workflow, url="https://example.com/a", **fields):
    response = workflow.client.post("/application-documents/prepare", json={"job_url": url, **fields})
    assert response.status_code == 200, response.text
    return response.json()


def approve(workflow, url="https://example.com/a"):
    response = workflow.client.post("/application-documents/review", json={"job_url": url})
    assert response.status_code == 200, response.text


def test_combined_pdf_order_and_explicit_review(workflow):
    state = prepare(workflow)
    assert state["ready"] is False
    combined = next(file for file in state["current"]["files"] if file["kind"] == "combined")
    with pymupdf.open(documents.asset_path(combined["asset"])) as pdf:
        assert len(pdf) == 2
        assert "Dear Alpha" in pdf[0].get_text()
        assert "Candidate Resume" in pdf[1].get_text()
    approve(workflow)
    assert documents.documents("https://example.com/a")["ready"] is True
    response = workflow.client.get("/application-documents/file/" + combined["asset"])
    assert response.status_code == 200 and response.content.startswith(b"%PDF-")


def test_letters_and_attempts_are_isolated_and_immutable(workflow):
    a = prepare(workflow)["current"]
    b = prepare(workflow, "https://example.com/b")["current"]
    assert "Alpha" in a["letter"] and "Beta" in b["letter"]
    assert a["files"][0]["asset"] != b["files"][0]["asset"]
    approve(workflow)
    attempt, primary, provided = documents.start_attempt(workflow.jobs["https://example.com/a"])
    assert primary.endswith("application.pdf") and provided == [primary]
    original = documents.asset_path(a["files"][0]["asset"]).read_bytes()
    prepare(workflow, letter="Dear Alpha,\nA revised letter")
    documents.finish_attempt("https://example.com/a", attempt["id"], "applied")
    history = documents.documents("https://example.com/a")["attempts"]
    assert history[0]["letter"] == a["letter"] and history[0]["status"] == "applied"
    assert documents.asset_path(history[0]["files"][0]["asset"]).read_bytes() == original


def test_separate_files_are_supplied_without_combined(workflow):
    prepare(workflow, "https://example.com/b")
    approve(workflow, "https://example.com/b")
    _, primary, provided = documents.start_attempt(workflow.jobs["https://example.com/b"])
    assert primary.endswith("resume.pdf")
    assert len(provided) == 2 and any(path.endswith("cover-letter.pdf") for path in provided)


def test_document_record_cannot_be_reused_for_another_employer(workflow):
    prepare(workflow)
    approve(workflow)
    workflow.jobs["https://example.com/b"]["application_documents"] = copy.deepcopy(workflow.jobs["https://example.com/a"]["application_documents"])
    with pytest.raises(ValueError): documents.validated_documents(workflow.jobs["https://example.com/b"])


def test_attempt_records_only_successful_uploads_of_reviewed_files(workflow):
    prepare(workflow)
    approve(workflow)
    attempt, primary, _ = documents.start_attempt(workflow.jobs["https://example.com/a"])
    history = [SimpleNamespace(model_output=SimpleNamespace(action=[{"upload_file": {"path": primary}}]), result=[SimpleNamespace(error=None)]),
               SimpleNamespace(model_output=SimpleNamespace(action=[{"upload_file": {"path": "/unreviewed.pdf"}}]), result=[SimpleNamespace(error=None)])]
    documents.finish_attempt("https://example.com/a", attempt["id"], "applied", history)
    saved = workflow.jobs["https://example.com/a"]["application_attempts"][0]
    assert saved["uploaded_assets"] == [next(file["asset"] for file in attempt["files"] if file["kind"] == "combined")]


@pytest.mark.parametrize("change", ["profile", "job", "resume", "file"])
def test_changes_invalidate_review(workflow, change):
    state = prepare(workflow)
    approve(workflow)
    if change == "profile": save_profile({"name": "Changed", "skills": []})
    elif change == "job": workflow.jobs["https://example.com/a"]["description"] += " New requirement."
    elif change == "resume": documents.text_pdf("Changed resume", workflow.source)
    else: documents.asset_path(state["current"]["files"][0]["asset"]).write_bytes(b"tampered")
    with pytest.raises(ValueError): documents.validated_documents(workflow.jobs["https://example.com/a"])


def test_missing_letter_or_combined_format_is_blocked(workflow):
    for mode in ("none", "separate"):
        response = workflow.client.post("/application-documents/prepare", json={"job_url": "https://example.com/a", "mode": mode})
        assert response.status_code == 400
    response = workflow.client.post("/application-documents/prepare", json={"job_url": "https://example.com/b", "letter": ""})
    assert response.status_code == 400
    assert workflow.client.get("/application-documents/file/not-a-version/resume.pdf").status_code == 404


def test_profile_changes_during_generation_do_not_create_a_reviewable_letter(workflow, monkeypatch):
    async def change_profile(job):
        save_profile({"name": "Changed while AI was running"})
        return "Letter generated from the old profile"
    monkeypatch.setattr(documents, "generate_letter", change_profile)
    response = workflow.client.post("/application-documents/prepare", json={"job_url": "https://example.com/a"})
    assert response.status_code == 400
    assert "application_documents" not in workflow.jobs["https://example.com/a"]


def test_oversized_ai_letter_is_rejected(workflow, monkeypatch):
    async def oversized(job): return "x" * 30001
    monkeypatch.setattr(documents, "generate_letter", oversized)
    response = workflow.client.post("/application-documents/prepare", json={"job_url": "https://example.com/a"})
    assert response.status_code == 400
    assert "application_documents" not in workflow.jobs["https://example.com/a"]


@pytest.mark.asyncio
async def test_copilot_completion_is_used_for_letter(workflow, monkeypatch):
    from core import llm_factory
    async def invoke(messages):
        assert "Alpha" in messages[0].content
        return SimpleNamespace(completion="Dear Alpha,\nSupported experience.")
    monkeypatch.setattr(llm_factory, "create_llm", lambda _: SimpleNamespace(ainvoke=invoke))
    # The fixture's generator stub is replaced by the production function here.
    assert await PRODUCTION_GENERATE_LETTER(workflow.jobs["https://example.com/a"]) == "Dear Alpha,\nSupported experience."


@pytest.mark.asyncio
async def test_application_worker_only_receives_reviewed_job_files(workflow, monkeypatch):
    from unittest.mock import AsyncMock
    from cli import apply_jobs
    prepare(workflow)
    approve(workflow)
    captured = {}
    class Browser:
        async def close(self): pass
    result = SimpleNamespace(history=[], is_successful=lambda: True, errors=lambda: [])
    class Agent:
        def __init__(self, **kwargs): captured.update(kwargs)
        async def run(self): return result
    monkeypatch.setattr(apply_jobs, "Agent", Agent)
    monkeypatch.setattr(apply_jobs, "BrowserSession", lambda **_: Browser())
    monkeypatch.setattr(apply_jobs, "claim_job", lambda _: True)
    monkeypatch.setattr(apply_jobs.config, "validate_job_url", lambda _: True)
    monkeypatch.setattr(apply_jobs.config, "get_llm", lambda: object())
    monkeypatch.setattr(apply_jobs, "BLOCKED_DOMAINS", [])
    monkeypatch.setattr(apply_jobs, "refresh_credentials", lambda: True)
    monkeypatch.setattr(apply_jobs, "get_memory_store", lambda: SimpleNamespace(
        extract_domain=lambda _: "example.com", get_domain_memories=lambda *a, **k: [], detect_ats_platform=lambda _: "unknown"))
    monkeypatch.setattr(apply_jobs, "build_memory_context", lambda profile, *a, **k: profile["cover_letter"])
    monkeypatch.setattr(apply_jobs, "save_job_status", AsyncMock())
    monkeypatch.setattr(apply_jobs, "save_new_qa", AsyncMock())
    monkeypatch.setattr(apply_jobs, "extract_from_history", lambda _: ({}, {}))
    monkeypatch.setattr(apply_jobs, "extract_learnings_from_markers", lambda _: [])
    monkeypatch.setattr(apply_jobs, "extract_learnings_via_llm", lambda *a, **k: [])
    monkeypatch.setattr(apply_jobs, "MetricsStore", lambda: SimpleNamespace(record_run=lambda **_: None))
    status = await apply_jobs.apply_to_job(workflow.jobs["https://example.com/a"], {"cover_letter": "WRONG GLOBAL LETTER"}, {}, [], True, 1)
    assert status == "applied"
    assert len(captured["available_file_paths"]) == 1
    assert captured["available_file_paths"][0].endswith("application.pdf")
    assert "Dear Alpha" in captured["extend_system_message"]
    assert "WRONG GLOBAL LETTER" not in captured["extend_system_message"]
    assert "STOP without submitting" in captured["extend_system_message"]
    assert workflow.jobs["https://example.com/a"]["application_attempts"][0]["status"] == "applied"


@pytest.mark.asyncio
async def test_worker_blocks_unreviewed_documents_before_browser_start(workflow, monkeypatch):
    from cli import apply_jobs
    from unittest.mock import Mock
    prepare(workflow)
    browser = Mock()
    monkeypatch.setattr(apply_jobs, "BrowserSession", browser)
    monkeypatch.setattr(apply_jobs.config, "validate_job_url", lambda _: True)
    monkeypatch.setattr(apply_jobs, "BLOCKED_DOMAINS", [])
    assert await apply_jobs.apply_to_job(workflow.jobs["https://example.com/a"], {}, {}, [], True, 1) == "skipped"
    browser.assert_not_called()
