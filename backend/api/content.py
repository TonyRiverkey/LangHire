"""Resume tailoring and cover letters."""
from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter

from core import db
from core.llm_factory import ainvoke_text

from core.config import load_llm_settings, load_profile
from models import CoverLetterRequest, JobUrlRequest, RefineRequest, TailorRequest

from .common import api_error, llm_text

router = APIRouter()
_log = logging.getLogger("backend")

_HASH = re.compile(r"^[0-9a-f]{8,64}$")


# ── Resume Tailoring ──────────────────────────────────────────────────────

@router.post("/resume/tailor")
async def tailor_resumes(body: TailorRequest):
    """Generate tailored resumes for one or more jobs."""
    from resume.tailor import tailor_resume

    job_urls = body.job_urls
    options = body.options.model_dump()

    jobs = db.read_jobs()
    results = []

    for url in job_urls:
        job = jobs.get(url)
        if not job:
            results.append({"url": url, "status": "error", "message": "Job not found"})
            continue
        description = job.get("description") or ""
        if not description.strip():
            results.append({"url": url, "status": "error", "message": "Collect the full job description before tailoring."})
            continue
        if job.get("status") == "in_progress":
            results.append({"url": url, "status": "error", "message": "Wait for the current application to finish."})
            continue
        try:
            result = await tailor_resume(url, description, options)
            await _save_tailoring(job, result["path"])
            results.append({"url": url, "status": "done", "path": result["path"], "content": result["content"],
                            "warnings": result.get("warnings", [])})
        except Exception as e:
            results.append({"url": url, "status": "error", "message": str(e)})

    return {"success": True, "results": results}


@router.post("/resume/tailor/refine")
async def refine_tailored_resume(body: RefineRequest):
    """Refine an existing tailored resume with additional instructions."""
    from resume.tailor import tailor_resume

    job_url = body.job_url
    instruction = body.instruction

    jobs = db.read_jobs()
    job = jobs.get(job_url)
    if not job:
        return api_error("not_found", "Job not found", 404)

    description = job.get("description") or ""
    if not description.strip():
        return api_error("missing_description", "Collect the full job description before tailoring.")
    if job.get("status") == "in_progress":
        return api_error("application_running", "Wait for the current application to finish.", 409)
    options = body.options.model_dump()

    try:
        # The instruction goes in its own prompt slot; it used to be appended to the job description
        result = await tailor_resume(job_url, description, options, refinement=instruction)
        await _save_tailoring(job, result["path"])
        return {"success": True, "content": result["content"], "path": result["path"],
                "warnings": result.get("warnings", [])}
    except Exception as e:
        return api_error("tailor_error", str(e), 500)


async def _save_tailoring(job: dict, path: str) -> None:
    from resume.skill_suggestions import suggest_skills
    from resume.tailor import tailoring_fingerprint

    description = job.get("description") or ""
    expected = {"status": job.get("status"), "description": description}
    fingerprint = tailoring_fingerprint(description, path)
    if not db.update_job(job["url"], if_unchanged=expected,
                         tailored_resume_path=path, tailoring_fingerprint=fingerprint,
                         skills_to_consider=[]):
        raise ValueError("The job changed while tailoring. Generate the resume again.")
    settings = load_llm_settings()
    if not settings.get("provider"):
        return
    try:
        suggestions = await asyncio.wait_for(
            suggest_skills(description, load_profile().get("skills", []), settings), timeout=45,
        )
        db.update_job(job["url"], if_unchanged={**expected, "tailoring_fingerprint": fingerprint},
                      skills_to_consider=suggestions)
    except Exception as error:
        _log.info("Optional skill suggestions unavailable: %s", type(error).__name__)


@router.post("/resume/tailor/get-by-url")
async def get_tailored_by_url(body: JobUrlRequest):
    """Get tailored resume content by job URL."""
    from resume.tailor import get_tailored_content
    result = get_tailored_content(body.job_url)
    if not result:
        return api_error("not_found", "No tailored resume for this job", 404)
    return {"success": True, "content": result["content"], "path": result["path"]}


@router.get("/resume/tailor/{url_hash}")
async def get_tailored_resume(url_hash: str):
    """Get tailored resume content by URL hash."""
    if not _HASH.match(url_hash):
        return api_error("invalid_hash", "Invalid id", 400)
    from resume.tailor import _get_tailored_dir
    md_path = _get_tailored_dir() / f"{url_hash}.md"
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"
    if not md_path.exists():
        return api_error("not_found", "No tailored resume found", 404)
    return {
        "success": True,
        "content": md_path.read_text(encoding="utf-8"),
        "path": str(pdf_path) if pdf_path.exists() else None,
    }


@router.delete("/resume/tailor/{url_hash}")
async def delete_tailored(url_hash: str):
    """Delete a tailored resume."""
    if not _HASH.match(url_hash):
        return api_error("invalid_hash", "Invalid id", 400)
    from resume.tailor import _get_tailored_dir
    md_path = _get_tailored_dir() / f"{url_hash}.md"
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"
    if md_path.exists():
        md_path.unlink()
    if pdf_path.exists():
        pdf_path.unlink()
    return {"success": True}


# ── Cover Letter Generation ───────────────────────────────────────────────

@router.post("/cover-letter/generate")
async def generate_cover_letter(body: CoverLetterRequest):
    """Generate a tailored cover letter using LLM based on job description + profile."""
    job_description = body.job_description.strip()
    job_title = body.job_title
    company = body.company

    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        return api_error("no_llm", "No LLM configured. Set up an LLM provider in Settings first.")

    profile = load_profile()

    prompt = (
        "Write a professional cover letter for the following job application.\n\n"
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n"
        f"JOB DESCRIPTION:\n{job_description}\n\n"
        f"CANDIDATE PROFILE:\n"
        f"Name: {profile.get('name', '')}\n"
        f"Current Role: {profile.get('current_role', '')}\n"
        f"Years of Experience: {profile.get('years_of_experience', 0)}\n"
        f"Skills: {', '.join(profile.get('skills', []))}\n"
        f"Education: {profile.get('education', {}).get('degree', '')} from {profile.get('education', {}).get('school', '')}\n"
        f"Languages: {', '.join(profile.get('languages', []))}\n\n"
        "INSTRUCTIONS:\n"
        "- Write 3-4 paragraphs\n"
        "- Highlight relevant skills and experience that match the job requirements\n"
        "- Be professional but not overly formal\n"
        "- Do NOT make up experience or skills the candidate doesn't have\n"
        "- Output ONLY the cover letter text — no subject line, headers, or metadata\n"
    )

    try:
        from core.llm_factory import create_llm
        llm = create_llm(llm_settings)
        response = await ainvoke_text(llm, prompt)
        text = llm_text(response)
        return {"success": True, "cover_letter": text.strip()}
    except Exception as e:
        return api_error("llm_error", f"Cover letter generation failed: {str(e)}", 500)
