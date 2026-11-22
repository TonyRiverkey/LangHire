import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.job_capture import canonical_job_url, posting_from_snapshot, capture_posting, verify_exhausted, location_matches


def snapshot(**changes):
    return {"page_url": "https://www.linkedin.com/jobs/search/?currentJobId=1234567890",
            "source_job_url": "https://www.linkedin.com/jobs/view/1234567890/",
            "title": "HR Business Partner", "company": "Example Employer", "location": "Victoria, BC",
            "description": "Employment duties and qualifications. " * 20,
            "metadata": "HR Business Partner at Example Employer in Victoria, BC", "easy_apply": False,
            "search_location": "Victoria, British Columbia, Canada", **changes}


@pytest.mark.parametrize("url", ["https://www.linkedin.com/jobs/view/1234567890/",
    "https://ca.linkedin.com/jobs/view/hr-business-partner-at-example-1234567890",
    "https://www.linkedin.com/jobs/search/?currentJobId=1234567890"])
def test_canonical_job_urls(url):
    assert canonical_job_url(url) == "https://www.linkedin.com/jobs/view/1234567890/"


@pytest.mark.parametrize("url", ["https://linkedin.com.evil.test/jobs/view/123/",
    "http://www.linkedin.com/jobs/view/123/", "https://www.linkedin.com/feed/"])
def test_non_job_urls_are_rejected(url):
    with pytest.raises(ValueError):
        canonical_job_url(url)


def test_saved_description_is_page_text_not_model_memory():
    raw = snapshot()
    job = posting_from_snapshot(json.dumps(raw), "Victoria, BC")
    assert job["description"] == raw["description"].strip()
    assert job["description_source"] == job["url"]
    assert job["easy_apply"] is False
    assert job["location_evidence"] == raw["search_location"]


@pytest.mark.parametrize("change", [{"description": "Short summary"}, {"company": ""},
    {"search_location": "Greater Vancouver Metropolitan Area"},
    {"metadata": "No longer accepting applications"}])
def test_incomplete_wrong_city_and_closed_postings_are_rejected(change):
    with pytest.raises(ValueError):
        posting_from_snapshot(snapshot(**change), "Victoria, BC")


@pytest.mark.parametrize("source", ["", "https://www.linkedin.com/jobs/view/2222222222/"])
def test_stale_details_cannot_be_saved_under_a_new_job_id(source):
    with pytest.raises(ValueError):
        posting_from_snapshot(snapshot(source_job_url=source), "Victoria, BC")


async def test_capture_uses_current_page_only():
    page = SimpleNamespace(evaluate=AsyncMock(return_value=snapshot()))
    browser = SimpleNamespace(get_current_page=AsyncMock(return_value=page))
    assert (await capture_posting(browser, "Victoria, BC"))["company"] == "Example Employer"


async def test_exhaustion_requires_visible_message_and_correct_city():
    page = SimpleNamespace(evaluate=AsyncMock(return_value={"location": "Victoria, BC", "text": "No matching jobs found"}))
    browser = SimpleNamespace(get_current_page=AsyncMock(return_value=page))
    assert await verify_exhausted(browser, "Victoria, BC", "No matching jobs found")
    assert not await verify_exhausted(browser, "Vancouver, BC", "No matching jobs found")
    assert not await verify_exhausted(browser, "Victoria, BC", "All jobs viewed")
    assert not await verify_exhausted(browser, "Victoria, BC", "jobs")


def test_visible_search_city_must_be_in_the_requested_region():
    assert location_matches("Vancouver, BC", "Vancouver, British Columbia, Canada")
    assert not location_matches("Vancouver, BC", "Vancouver, WA")
