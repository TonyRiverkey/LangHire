import asyncio
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

import pytest

from cli import collect_jobs as collector
from core import job_capture
from resume import job_review


@pytest.fixture
def environment(tmp_path, monkeypatch):
    path = tmp_path / "jobs.json"
    existing = {"https://www.linkedin.com/jobs/view/9999999999/": {"title": "Existing", "status": "pending"}}
    path.write_text(json.dumps(existing))
    monkeypatch.setattr(collector, "JOBS_FILE", path)
    monkeypatch.setattr(collector.config, "JOBS_FILE", path)
    monkeypatch.setattr(collector.config, "JOBS_LOCK", tmp_path / "jobs.lock")
    monkeypatch.setattr(collector, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(collector, "load_llm_settings", lambda: {"provider": "copilot"})
    def create_model(settings):
        assert settings["provider"] == "copilot"
        return SimpleNamespace(provider="copilot")
    monkeypatch.setattr(collector, "create_llm", create_model)
    review = {"role_fit": "relevant", "location_fit": "within_target", "closed": False,
              "salary": {"evidence": "CAD 90,000 per year"}, "profile_questions": []}
    monkeypatch.setattr(job_review, "review_job", AsyncMock(return_value=review))
    state = SimpleNamespace(actions=["capture"], agents=[], review=review, path=path, existing=existing)
    state.final_message = "Claimed success"

    class Page:
        def __init__(self, browser):
            self.browser = browser

        async def evaluate(self, script):
            location = self.browser.location
            if script == job_capture.SEARCH_STATE_SCRIPT:
                return {"location": location, "text": "No more results"}
            job_id = "1111111111" if "Vancouver" in location else "2222222222"
            return {"page_url": f"https://www.linkedin.com/jobs/search/?currentJobId={job_id}",
                    "source_job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                    "title": "HR Business Partner", "company": "Example Employer", "location": location,
                    "metadata": f"HR Business Partner, Example Employer, {location}",
                    "description": "Real posting responsibilities and qualifications. " * 20,
                    "search_location": location, "easy_apply": False}

    class Browser:
        def __init__(self, **kwargs):
            self.location = ""
            self.kill = AsyncMock()

        async def get_current_page(self):
            return Page(self)

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
            return SimpleNamespace(is_successful=lambda: True, final_result=lambda: state.final_message)

    monkeypatch.setattr(collector, "BrowserSession", Browser)
    monkeypatch.setattr(collector, "Agent", Agent)
    return state


PROFILE = {"target_locations": ["Vancouver, BC", "Victoria, BC"], "target_job_titles": ["HR Business Partner"]}


async def test_separate_city_searches_capture_full_descriptions_and_preserve_existing_jobs(environment):
    report = {"locations": []}
    found = await collector.collect_for_title("HR Business Partner", environment.existing, PROFILE, 2, report=report)
    assert len(found) == 2
    assert [item["location"] for item in report["locations"]] == PROFILE["target_locations"]
    assert all(item["status"] == "complete" for item in report["locations"])
    saved = json.loads(environment.path.read_text())
    assert len(saved) == 3
    assert saved[next(iter(environment.existing))] == environment.existing[next(iter(environment.existing))]
    assert all(job["description"].startswith("Real posting") for job in found)
    assert all(job["fit_review"]["role_fit"] == "relevant" for job in found)
    assert len(environment.agents) == 2


async def test_model_success_without_capture_or_exhaustion_is_failure(environment):
    environment.actions = []
    report = {"locations": []}
    assert await collector.collect_for_title("HR", environment.existing, PROFILE, 2, report=report) == []
    assert all(item["status"] == "failed" and item["attempts"] == 2 for item in report["locations"])
    assert len(environment.agents) == 4


async def test_explicit_exhausted_search_can_complete_with_no_new_jobs(environment):
    environment.actions = ["exhaust"]
    report = {"locations": []}
    assert await collector.collect_for_title("HR", environment.existing, PROFILE, 2, report=report) == []
    assert all(item["status"] == "complete" and item["saved"] == 0 for item in report["locations"])
    assert len(environment.agents) == 2


async def test_unrelated_unverified_and_closed_jobs_are_not_saved(environment):
    environment.review["location_fit"] = "uncertain"
    environment.actions = ["capture", "exhaust"]
    report = {"locations": []}
    assert await collector.collect_for_title("HR", environment.existing, PROFILE, 2, report=report) == []
    assert all(item["skipped"] == 1 for item in report["locations"])
    assert json.loads(environment.path.read_text()) == environment.existing


async def test_cap_and_duplicate_protection(environment):
    environment.actions = ["capture"] * 5
    report = {"locations": []}
    found = await collector.collect_for_title("HR", environment.existing, PROFILE, 1, report=report)
    assert len(found) == 1
    assert len(environment.agents) == 1
    assert report["locations"][1]["status"] == "not_searched"


async def test_edits_made_during_ai_review_are_preserved(environment, monkeypatch):
    async def review(*args):
        current = json.loads(environment.path.read_text())
        current[next(iter(environment.existing))]["status"] = "applied"
        environment.path.write_text(json.dumps(current))
        return environment.review
    monkeypatch.setattr(job_review, "review_job", review)
    await collector.collect_for_title("HR", environment.existing, PROFILE, 1)
    assert json.loads(environment.path.read_text())[next(iter(environment.existing))]["status"] == "applied"


async def test_login_blocker_is_reported_without_retry(environment):
    environment.actions = []
    environment.final_message = "LinkedIn requires sign-in."
    report = {"locations": []}
    await collector.collect_for_title("HR", environment.existing, PROFILE, 2, report=report)
    assert all(item["status"] == "blocked" and item["attempts"] == 1 for item in report["locations"])


async def test_finished_capture_callbacks_cannot_write_late_or_use_next_city(environment):
    await collector.collect_for_title("HR", environment.existing, PROFILE, 2)
    before = environment.path.read_text()
    first_agent = environment.agents[0]
    action = first_agent.kwargs["tools"].registry.registry.actions["capture_selected_job"]
    with pytest.raises(asyncio.CancelledError):
        await action.function(params=action.param_model(), browser_session=first_agent.browser)
    assert environment.path.read_text() == before
