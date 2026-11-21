from types import SimpleNamespace

import pymupdf
import pytest

from core import profile_extraction as extraction
from core import llm_factory
from core.config import load_profile, save_profile, save_settings


def test_fill_missing_preserves_answers_and_rejects_wrong_types():
    existing = {"name": "Saved Name", "skills": [], "education": {"school": "", "degree": "Saved"},
                "years_of_experience": 0, "willing_to_relocate": False}
    result = extraction.fill_missing(existing, {
        "name": "AI Name", "skills": [" HR ", "HR", None, 2],
        "education": {"school": "College", "degree": "Other", "extra": "ignored"},
        "years_of_experience": True, "willing_to_relocate": 1, "unknown": "ignored",
    })
    assert result == {**existing, "skills": ["HR"], "education": {"school": "College", "degree": "Saved"}}
    assert existing["skills"] == []


def test_extracted_languages_supplement_existing_english_default():
    assert extraction.fill_missing({"languages": ["English"]}, {"languages": ["French", "English"]}) == {
        "languages": ["English", "French"]}


@pytest.fixture
def resume(data_dir):
    path = data_dir / "resume.pdf"
    with pymupdf.open() as doc:
        for _ in range(6):
            doc.new_page().insert_textbox((20, 20, 570, 800), "Experience and HR skills.\n" * 50)
        doc.new_page().insert_text((30, 30), "Final-page education: Bachelor's degree at Example University, 2015")
        doc.save(path)
    save_settings({"resume_path": str(path)})
    return path


@pytest.mark.asyncio
async def test_full_resume_extracts_education_and_preserves_preferences(resume, monkeypatch):
    async def invoke(messages):
        prompt = messages[0].content
        assert len(prompt) > 6000
        assert "Final-page education" in prompt
        # Simulate answers saved while the AI request was running.
        profile = load_profile()
        profile["name"] = "User's saved name"
        profile["target_locations"] = ["Vancouver, BC", "Victoria, BC"]
        save_profile(profile)
        return SimpleNamespace(completion='{"name":"AI Name","education":{"degree":"Bachelor","school":"Example University","graduation":"2015"},"skills":{"technical":["HRIS"],"soft":["Communication"]},"salary_expectation":{"min":1},"work_authorization":"Invented"}')
    monkeypatch.setattr(llm_factory, "create_llm", lambda _: SimpleNamespace(ainvoke=invoke))
    result = await extraction.parse_resume_to_profile()
    assert result["success"] is True
    saved = load_profile()
    assert saved["name"] == "User's saved name"
    assert saved["education"]["school"] == "Example University"
    assert saved["skills"] == ["HRIS", "Communication"]
    assert saved["target_locations"] == ["Vancouver, BC", "Victoria, BC"]
    assert saved["salary_expectation"]["min"] == 50000
    assert saved["work_authorization"] == ""
    assert result["fields_filled"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ['{}', '[]', 'not json', '{"skills":42}'])
async def test_empty_or_invalid_extraction_never_reports_success(resume, monkeypatch, response):
    before = load_profile()
    async def invoke(_):
        return SimpleNamespace(completion=response)
    monkeypatch.setattr(llm_factory, "create_llm", lambda _: SimpleNamespace(ainvoke=invoke))
    result = await extraction.parse_resume_to_profile()
    assert result["success"] is False
    assert load_profile() == before
