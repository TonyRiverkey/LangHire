import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.job_capture import canonical_job_url, posting_from_snapshot, capture_posting, verify_exhausted, location_matches, verified_search


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
    message = "You've viewed all jobs for this search"
    page.evaluate.return_value = {"location": "Victoria, BC", "text": f"Job results\n{message}"}
    assert await verify_exhausted(browser, "Victoria, BC", message)


def test_visible_search_city_must_be_in_the_requested_region():
    assert location_matches("Vancouver, BC", "Vancouver, British Columbia, Canada")
    assert not location_matches("Vancouver, BC", "Vancouver, WA")


def test_standalone_capture_uses_verified_search_without_search_control():
    url = "https://www.linkedin.com/jobs/view/1234567890/"
    raw = snapshot(page_url=url, standalone_detail=True, source_job_url="", search_location="")
    assert posting_from_snapshot(raw, "Victoria, BC", expected_url=url,
                                 search_evidence="Victoria, BC (40 km)")["url"] == url
    with pytest.raises(ValueError, match="selected card"):
        posting_from_snapshot(raw, "Victoria, BC", expected_url="https://www.linkedin.com/jobs/view/4444444444/",
                              search_evidence="Victoria, BC")
    with pytest.raises(ValueError, match="different posting"):
        posting_from_snapshot({**raw, "source_job_url": "https://www.linkedin.com/jobs/view/4444444444/"},
                              "Victoria, BC", expected_url=url, search_evidence="Victoria, BC")
    with pytest.raises(ValueError, match="incomplete"):
        posting_from_snapshot({**raw, "description_collapsed": True}, "Victoria, BC",
                              expected_url=url, search_evidence="Victoria, BC")


def test_search_verifies_visible_city_and_active_date():
    assert verified_search({"location": "Vancouver, BC (40 km)", "dates": ["Past week"]},
                           "Vancouver, BC", "r604800")
    assert not verified_search({"location": "Victoria, BC", "dates": ["Past week"]},
                               "Vancouver, BC", "r604800")
    assert not verified_search({"location": "Vancouver, BC", "dates": ["Date posted"]},
                               "Vancouver, BC", "r604800")


@pytest.mark.parametrize("standalone", [False, True])
def test_capture_selectors_against_linkedin_layouts(standalone):
    from core.chromium import find_playwright_chromium
    from core.job_capture import CAPTURE_SCRIPT, SEARCH_STATE_SCRIPT, LOCATION_INPUT

    playwright = pytest.importorskip("playwright.sync_api")
    chromium = find_playwright_chromium()
    if not chromium:
        pytest.skip("Chromium is unavailable")
    url = "https://www.linkedin.com/jobs/view/1234567890/"
    description = "Employment duties and qualifications. " * 20
    search = """
        <form><input aria-label="Location" value="Vancouver"><input type="hidden" name="geoId" value="456"></form>
        <button aria-expanded="false">Past week</button>
        <span class="job-search-card__location">Vancouver, British Columbia, Canada</span>
    """
    html = f"""
        <div class="top-card-layout"><h2 class="top-card-layout__title">HR Business Partner</h2>
        <a class="topcard__org-name-link">Example Employer</a>
        <span class="topcard__flavor--bullet">Vancouver, BC</span></div>
        <div class="show-more-less-html__markup">{description}</div>
    """ if standalone else f"""
        {search}
        <div class="job-details-jobs-unified-top-card" data-entity-urn="urn:li:jobPosting:1234567890">
        <h1>HR Business Partner</h1><a class="job-details-jobs-unified-top-card__company-name">Example Employer</a>
        <span class="job-details-jobs-unified-top-card__primary-description-container">Vancouver, BC</span></div>
        <div id="job-details">{description}</div>
    """
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch(executable_path=chromium)
        try:
            page = browser.new_page()
            page.route("https://www.linkedin.com/**", lambda route: route.fulfill(body=html, content_type="text/html"))
            page.goto(url if standalone else "https://www.linkedin.com/jobs/search/?currentJobId=1234567890")
            if not standalone:
                assert verified_search(page.evaluate(SEARCH_STATE_SCRIPT, LOCATION_INPUT), "Vancouver, BC", "r604800")
            captured = posting_from_snapshot(page.evaluate(CAPTURE_SCRIPT), "Vancouver, BC",
                                             expected_url=url, search_evidence="Vancouver, BC")
            assert captured["description"] == description.strip()
            assert captured["url"] == url
        finally:
            browser.close()
