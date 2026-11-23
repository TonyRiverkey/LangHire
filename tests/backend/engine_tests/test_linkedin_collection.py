import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from engine import collect_fastpath, linkedin


def test_search_state_tolerates_document_before_body_is_created():
    import shutil
    import subprocess
    import pytest
    from core.job_capture import SEARCH_STATE_SCRIPT
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the browser script regression')
    script = ("global.document={querySelectorAll:()=>[],querySelector:()=>null,body:null};"
              "global.location={href:'about:blank'};"
              "const state=("+SEARCH_STATE_SCRIPT+")('input');"
              "if(state.text!=='' || state.location!=='')process.exit(1);")
    subprocess.run([node,'-e',script],check=True,capture_output=True)


async def test_pagination_keeps_reading_while_distinct_cards_are_arriving(monkeypatch):
    monkeypatch.setattr(collect_fastpath.asyncio, "sleep", AsyncMock())
    batches = [[{"url": f"job-{i}"}] for i in range(6)]
    batches.extend([batches[-1]] * 3)
    reads = iter(batches)

    async def evaluate(script):
        if script == collect_fastpath.LINKEDIN_CARDS_JS:
            return json.dumps(next(reads))
        return "scrolled"

    cards = await collect_fastpath.collect_cards(None, "", want=10, page=SimpleNamespace(evaluate=evaluate))
    assert len(cards) == 6


async def test_wrong_search_location_is_corrected_before_capture(monkeypatch):
    monkeypatch.setattr(linkedin.asyncio, "sleep", AsyncMock())
    control = SimpleNamespace(click=AsyncMock(), fill=AsyncMock())
    page = SimpleNamespace(goto=AsyncMock(), evaluate=AsyncMock(return_value="true"),
                           get_elements_by_css_selector=AsyncMock(return_value=[control]))
    browser = SimpleNamespace(start=AsyncMock(), get_current_page=AsyncMock(return_value=page))
    wrong = {"location": "Victoria, BC", "dates": ["Past week"]}
    right = {"location": "Vancouver, British Columbia, Canada", "dates": ["Past week"]}
    monkeypatch.setattr(linkedin.job_capture, "search_state", AsyncMock(side_effect=[wrong] * 4 + [right]))
    selected, state = await linkedin._verified_search_page(browser, "search-url", "Vancouver, BC", "r604800")
    assert selected is page
    assert state == right
    control.fill.assert_awaited_once_with("Vancouver, BC")


async def test_ai_search_selects_visible_recent_location_before_capture(monkeypatch):
    from core import job_capture
    monkeypatch.setattr(linkedin.asyncio,'sleep',AsyncMock())
    opener=SimpleNamespace(click=AsyncMock())
    hidden_legacy=SimpleNamespace(click=AsyncMock(),fill=AsyncMock())
    async def elements(selector):
        return [hidden_legacy] if selector==job_capture.LOCATION_INPUT else [opener]
    page=SimpleNamespace(goto=AsyncMock(),evaluate=AsyncMock(return_value='https://www.linkedin.com/jobs/search-results/?geoId=12345'),get_elements_by_css_selector=elements)
    browser=SimpleNamespace(start=AsyncMock(),get_current_page=AsyncMock(return_value=page))
    wrong={'location':'Victoria, BC (40 km)','dates':['Past week'],'ai_location_control':True}
    right={'location':'Vancouver, BC (40 km)','dates':['Past week']}
    monkeypatch.setattr(job_capture,'search_state',AsyncMock(side_effect=[wrong]*4+[right]))
    _,state=await linkedin._verified_search_page(browser,'search-url','Vancouver, BC','r604800')
    assert state==right
    opener.click.assert_awaited_once()
    hidden_legacy.fill.assert_not_awaited()
    assert page.goto.await_args_list[-1].args[0]=='https://www.linkedin.com/jobs/search-results/?geoId=12345'


def test_only_exact_fully_read_result_counts_verify_completion():
    from core.job_capture import all_displayed_results_read
    state={'result_count':3,'rendered_count':3,'has_next_page':False}
    assert all_displayed_results_read(state,3)
    assert not all_displayed_results_read(state,2)
    assert not all_displayed_results_read({**state,'has_next_page':True},3)
    assert not all_displayed_results_read({**state,'result_count':None},3)


async def test_location_history_does_not_follow_external_or_non_search_link(monkeypatch):
    import pytest
    from core import job_capture
    monkeypatch.setattr(linkedin.asyncio,'sleep',AsyncMock())
    legacy=SimpleNamespace(click=AsyncMock(),fill=AsyncMock())
    opener=SimpleNamespace(click=AsyncMock())
    async def elements(selector):return [legacy] if selector==job_capture.LOCATION_INPUT else [opener]
    page=SimpleNamespace(goto=AsyncMock(),evaluate=AsyncMock(return_value='https://example.test/jobs/search?geoId=123'),get_elements_by_css_selector=elements)
    browser=SimpleNamespace(start=AsyncMock(),get_current_page=AsyncMock(return_value=page))
    monkeypatch.setattr(job_capture,'search_state',AsyncMock(return_value={'location':'Victoria, BC','dates':['Past week'],'ai_location_control':True}))
    with pytest.raises(ValueError,match='Could not verify'):
        await linkedin._verified_search_page(browser,'search-url','Vancouver, BC','r604800')
    assert page.goto.await_count==1
    legacy.fill.assert_not_awaited()
