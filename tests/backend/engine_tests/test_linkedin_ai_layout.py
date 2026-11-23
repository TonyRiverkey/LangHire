"""Run the actual browser scripts against a sanitized AI-search layout."""
import json
import shutil
import subprocess

import pytest

from core import job_capture
from engine.collect_fastpath import LINKEDIN_CARDS_JS


def snapshot(*, expanded=True, checked=True, city='Vancouver, BC (40 km)', standalone=False):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for DOM fixture')
    html = f'''
      <div role="button" aria-label="Location {city}">{city}</div>
      <div role="button"><div aria-label="Filter by Past week"><input type="checkbox" {'checked' if checked else ''}><label>Past week</label></div></div>
      <div role="button" componentkey="job-card-component-ref-12345"><p>HR Partner</p><p>Example Services</p><p>Vancouver, BC</p></div>
      <section><a aria-label="Company, Example Services." href="https://www.linkedin.com/company/example/">Example Services</a>
      <p><a href="https://www.linkedin.com/jobs/view/12345/">HR Partner</a></p><p>Vancouver, BC · 2 days ago · 10 applicants</p></section>
      <section><div><h2>About the job</h2></div><p><span data-testid="expandable-text-box">{'Real employee relations and manager coaching responsibilities. ' * 12}</span>
      {'' if expanded else '<button data-testid="expandable-text-button">… more</button>'}</p></section>'''
    if standalone:
        html=html.replace('<a href="https://www.linkedin.com/jobs/view/12345/">HR Partner</a>', 'HR Partner')
        html=html.replace('</section>\n      <section>', '<p><a href="https://www.linkedin.com/jobs/view/12345/">On-site</a></p></section>\n      <section>',1)
    script = """import { JSDOM } from 'jsdom';
const dom = new JSDOM(HTML, {url:'https://www.linkedin.com/jobs/search-results/?currentJobId=12345'});
global.document=dom.window.document;global.window=dom.window;global.location=dom.window.location;
Object.defineProperty(dom.window.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
dom.window.HTMLElement.prototype.getClientRects=function(){return [1];};
const search=(SEARCH)(SELECTOR);const capture=(CAPTURE)();const cards=JSON.parse((CARDS)());
process.stdout.write(JSON.stringify({search,capture,cards}));"""
    script=script.replace('JSDOM(HTML,', 'JSDOM('+json.dumps(html)+',').replace('SEARCH',job_capture.SEARCH_STATE_SCRIPT).replace('SELECTOR',json.dumps(job_capture.LOCATION_INPUT)).replace('CAPTURE',job_capture.CAPTURE_SCRIPT).replace('CARDS',LINKEDIN_CARDS_JS)
    result=subprocess.run([node,'--input-type=module','-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_ai_search_cards_and_linked_detail_are_verified():
    data=snapshot()
    assert job_capture.verified_search(data['search'],'Vancouver, BC','r604800')
    assert data['cards'][0]['url']=='https://www.linkedin.com/jobs/view/12345/'
    result=job_capture.posting_from_snapshot(data['capture'],'Vancouver, BC',expected_url=data['cards'][0]['url'],search_evidence=data['search']['location'])
    assert result['company']=='Example Services' and result['location']=='Vancouver, BC'


def test_ai_search_does_not_accept_unchecked_date_or_wrong_city():
    assert not job_capture.verified_search(snapshot(checked=False)['search'],'Vancouver, BC','r604800')
    assert not job_capture.verified_search(snapshot(city='Victoria, BC (40 km)')['search'],'Vancouver, BC','r604800')


def test_ai_collapsed_description_and_stale_detail_are_rejected():
    data=snapshot(expanded=False)
    with pytest.raises(ValueError,match='incomplete'):
        job_capture.posting_from_snapshot(data['capture'],'Vancouver, BC',search_evidence=data['search']['location'])
    data=snapshot();data['capture']['page_url']='https://www.linkedin.com/jobs/search-results/?currentJobId=99999'
    with pytest.raises(ValueError,match='different posting'):
        job_capture.posting_from_snapshot(data['capture'],'Vancouver, BC',search_evidence=data['search']['location'])


def test_plain_standalone_title_is_not_replaced_by_work_mode_chip():
    data=snapshot(standalone=True)
    assert data["capture"]["title"]=="HR Partner"
