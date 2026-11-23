import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

import pytest

from core import db, job_capture
from engine import linkedin as collector, prompts
from engine.events import RunContext
from resume import job_review


@pytest.fixture
def environment(data_dir, monkeypatch):
    existing = {"https://www.linkedin.com/jobs/view/9999999999/": {"title": "Existing", "status": "pending"}}
    db.write_jobs(existing)
    existing = db.read_jobs()
    monkeypatch.setattr(collector.sc, "get_llm", lambda: SimpleNamespace(provider="copilot"))

    async def no_cards(*args, **kwargs):
        return []

    monkeypatch.setattr(collector, "collect_cards", no_cards)
    review = {"role_fit": "relevant", "location_fit": "within_target", "closed": False,
              "role_reason": "Relevant advisory scope.", "location_evidence": "Verified city",
              "salary": {"evidence": "CAD 90,000 per year"}, "profile_questions": []}
    monkeypatch.setattr(job_review, "review_job", AsyncMock(return_value=review))
    state = SimpleNamespace(actions=["capture"], agents=[], review=review, existing=existing, native=False)
    state.final_message = "Claimed success"

    class Page:
        def __init__(self, browser):
            self.browser = browser

        async def goto(self, url):
            self.browser.posting_url = url
            city = parse_qs(urlsplit(url).query).get('location')
            if city:
                self.browser.location = city[0]

        async def evaluate(self, script, *args):
            location = self.browser.location
            if script == job_capture.SEARCH_STATE_SCRIPT:
                return {"location": location, "dates": ["Past week"], "text": "No more results"}
            job_id = "1111111111" if "Vancouver" in location else "2222222222"
            return {"page_url": self.browser.posting_url or f"https://www.linkedin.com/jobs/search/?currentJobId={job_id}",
                    "source_job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                    "title": "HR Business Partner", "company": "Example Employer", "location": location,
                    "metadata": f"HR Business Partner, Example Employer, {location}",
                    "description": "Real posting responsibilities and qualifications. " * 20,
                    "search_location": location, "easy_apply": False}

    class Browser:
        def __init__(self, **kwargs):
            self.location = ""
            self.posting_url = ""
            self.kill = AsyncMock()

        async def get_current_page(self):
            return Page(self)

        async def start(self):
            if not state.native:
                raise RuntimeError('Fixture forces navigation fallback')

        async def get_pages(self):
            return [Page(self)]

        async def new_page(self, url=None):
            page = Page(self)
            if url:
                await page.goto(url)
            return page

    class Agent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.stopped = False
            self.browser = kwargs["browser_session"]
            self.browser.location = parse_qs(urlsplit(kwargs["initial_actions"][0]["navigate"]["url"]).query)["location"][0]
            state.agents.append(self)

        def stop(self):
            self.stopped = True

        async def run(self, **kwargs):
            actions = self.kwargs["tools"].registry.registry.actions
            for operation in state.actions:
                if self.stopped:
                    break
                name = "finish_search" if operation == "exhaust" else "capture_selected_job"
                action = actions[name]
                values = {"evidence": "No more results"} if operation == "exhaust" else {}
                await action.function(params=action.param_model(**values), browser_session=self.browser)
            return SimpleNamespace(is_successful=lambda: True, final_result=lambda: state.final_message, usage=None)

    monkeypatch.setattr(collector, "make_browser_session", Browser)
    monkeypatch.setattr(collector, "Agent", Agent)
    return state


PROFILE = {"target_locations": ["Vancouver, BC", "Victoria, BC"], "target_job_titles": ["HR Business Partner"]}


async def collect(title, cap, *, report=None):
    plugin = prompts.registry().get_by_name("linkedin")
    return await collector.collect_title(plugin, title, PROFILE, cap, {}, RunContext("test", "collect"),
                                         report if report is not None else {"locations": []})


async def test_separate_city_searches_capture_full_descriptions_and_preserve_existing_jobs(environment):
    report = {"locations": []}
    found = await collect("HR Business Partner", 2, report=report)
    assert found == 2
    assert [item["location"] for item in report["locations"]] == PROFILE["target_locations"]
    assert all(item["status"] == "complete" for item in report["locations"])
    saved = db.read_jobs()
    assert len(saved) == 3
    assert saved[next(iter(environment.existing))] == environment.existing[next(iter(environment.existing))]
    assert all(job["description"].startswith("Real posting") for job in saved.values() if job["title"] != "Existing")
    assert all(job["fit_review"]["role_fit"] == "relevant" for job in saved.values() if job["title"] != "Existing")
    assert len(environment.agents) == 2


async def test_model_success_without_capture_or_exhaustion_is_failure(environment):
    environment.actions = []
    report = {"locations": []}
    assert await collect("HR", 2, report=report) == 0
    assert all(item["status"] == "failed" and item["attempts"] == 1 for item in report["locations"])
    assert len(environment.agents) == 2  # one bounded fallback per city


async def test_explicit_exhausted_search_can_complete_with_no_new_jobs(environment):
    environment.actions = ["exhaust"]
    report = {"locations": []}
    assert await collect("HR", 2, report=report) == 0
    assert all(item["status"] == "complete" and item["saved"] == 0 for item in report["locations"])
    assert len(environment.agents) == 2


async def test_unrelated_unverified_and_closed_jobs_are_not_saved(environment):
    environment.review["location_fit"] = "uncertain"
    environment.actions = ["capture", "exhaust"]
    report = {"locations": []}
    assert await collect("HR", 2, report=report) == 0
    assert all(item["skipped"] == 1 for item in report["locations"])
    assert db.read_jobs() == environment.existing


async def test_cap_and_duplicate_protection(environment):
    environment.actions = ["capture"] * 5
    report = {"locations": []}
    found = await collect("HR", 1, report=report)
    assert found == 1
    assert len(environment.agents) == 1
    assert report["locations"][1]["status"] == "not_searched"


async def test_edits_made_during_ai_review_are_preserved(environment, monkeypatch):
    async def review(*args):
        db.update_job(next(iter(environment.existing)), status="applied")
        return environment.review
    monkeypatch.setattr(job_review, "review_job", review)
    await collect("HR", 1)
    assert db.read_jobs()[next(iter(environment.existing))]["status"] == "applied"


async def test_login_blocker_is_reported_without_retry(environment):
    environment.actions = []
    environment.final_message = "LinkedIn requires sign-in."
    report = {"locations": []}
    await collect("HR", 2, report=report)
    assert all(item["status"] == "blocked" and item["attempts"] == 1 for item in report["locations"])


async def test_finished_capture_callbacks_cannot_write_late_or_use_next_city(environment):
    await collect("HR", 2)
    before = db.read_jobs()
    first_agent = environment.agents[0]
    action = first_agent.kwargs["tools"].registry.registry.actions["capture_selected_job"]
    with pytest.raises(asyncio.CancelledError):
        await action.function(params=action.param_model(), browser_session=first_agent.browser)
    assert db.read_jobs() == before


async def test_fast_capture_checks_city_and_reads_the_actual_posting(environment, monkeypatch):
    environment.native = True
    async def cards(browser, url, want, *, page=None):
        browser.location = parse_qs(urlsplit(url).query)["location"][0]
        job_id = "1111111111" if browser.location.startswith("Vancouver") else "2222222222"
        return [{"url": f"https://www.linkedin.com/jobs/view/{job_id}/", "title": "Untrusted card title"}]

    monkeypatch.setattr(collector, "collect_cards", cards)
    assert await collect("HR", 2) == 2
    assert not environment.agents
    saved = [job for job in db.read_jobs().values() if job["title"] != "Existing"]
    assert all(job["title"] == "HR Business Partner" and job["description_source"] == job["url"] for job in saved)
    assert {job["search_location"] for job in saved} == set(PROFILE["target_locations"])
