"""Capture the selected LinkedIn posting; never use agent memory as its source."""
import json
import re
from urllib.parse import parse_qs, urlsplit


CAPTURE_SCRIPT = r"""() => {
  const first = (selectors, root = document) => selectors.map(s => root.querySelector(s)).find(Boolean);
  const text = el => el ? (el.innerText || el.textContent || '').trim() : '';
  const description = first(['#job-details', '.jobs-description__content',
    '.jobs-description-content__text', '.show-more-less-html__markup']);
  const card = first(['.job-details-jobs-unified-top-card__container--two-pane',
    '.job-details-jobs-unified-top-card__container--one-pane',
    '.jobs-unified-top-card', '.top-card-layout']);
  const title = first(['.job-details-jobs-unified-top-card__job-title',
    '.jobs-unified-top-card__job-title', '.top-card-layout__title', 'h1'], card || document);
  const company = first(['.job-details-jobs-unified-top-card__company-name',
    '.jobs-unified-top-card__company-name', '.topcard__org-name-link'], card || document);
  const location = first(['.job-details-jobs-unified-top-card__primary-description-container',
    '.jobs-unified-top-card__bullet', '.topcard__flavor--bullet'], card || document);
  const searchLocation = first(['input[id*="jobs-search-box-location"]',
    'input[aria-label*="City, state"]', 'input[aria-label*="location"]']);
  const applyText = text(first(['.jobs-apply-button', '.jobs-apply-button--top-card']));
  const sourceLink = (title && title.closest('a[href*="/jobs/view/"]'))
    || (card && card.querySelector('a[href*="/jobs/view/"]'))
    || (/\/jobs\/view\//.test(window.location.pathname) && document.querySelector('link[rel="canonical"]'));
  return {page_url: window.location.href, title: text(title), company: text(company),
    location: text(location), metadata: text(card), description: text(description),
    source_job_url: sourceLink ? sourceLink.href : '',
    search_location: searchLocation ? searchLocation.value : '',
    easy_apply: /easy apply/i.test(applyText) ? true : (/apply/i.test(applyText) ? false : null)};
}"""

SEARCH_STATE_SCRIPT = r"""() => {
  const input = document.querySelector('input[id*="jobs-search-box-location"], input[aria-label*="City, state"], input[aria-label*="location"]');
  return {location: input ? input.value : '', text: (document.querySelector('main') || document.body).innerText};
}"""


async def verify_exhausted(browser_session, expected_location, evidence):
    page = await browser_session.get_current_page()
    if page is None:
        return False
    state = await page.evaluate(SEARCH_STATE_SCRIPT)
    state = json.loads(state) if isinstance(state, str) else state
    return (normalize(expected_location.split(",")[0]) in normalize(state.get("location", ""))
            and bool(evidence.strip()) and normalize(evidence) in normalize(state.get("text", ""))
            and bool(re.search(r"no (?:matching )?jobs|no (?:more )?results|you.ve viewed all|all jobs viewed|page 1 of 1", evidence, re.I)))


def canonical_job_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not (parts.hostname or "").endswith(".linkedin.com"):
        if parts.scheme != "https" or parts.hostname != "linkedin.com":
            raise ValueError("The selected page is not a LinkedIn job.")
    match = re.search(r"/jobs/view/(?:[^/]*-)?(\d+)(?:/|$)", parts.path)
    job_id = match.group(1) if match else parse_qs(parts.query).get("currentJobId", [""])[0]
    if not job_id.isdigit():
        raise ValueError("Open a specific job before capturing it.")
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def normalize(text):
    return " ".join(text.casefold().split())


def posting_from_snapshot(snapshot, expected_location):
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    url = canonical_job_url(snapshot.get("page_url", ""))
    try:
        source_url = canonical_job_url(snapshot.get("source_job_url", ""))
    except ValueError:
        raise ValueError("The selected posting's identity is not available yet. Wait for details or open the job in its own tab.") from None
    if source_url != url:
        raise ValueError("The selected details are still showing a different posting. Wait for the job to load.")
    for field in ("title", "company", "location", "description"):
        if not isinstance(snapshot.get(field), str) or not snapshot[field].strip():
            raise ValueError(f"Cannot capture the selected posting's {field}. Open or expand its details.")
    description = snapshot["description"].strip()
    if len(description) < 300:
        raise ValueError("The job description is incomplete. Expand it and capture again.")
    metadata = snapshot.get("metadata", "")
    if "no longer accepting applications" in normalize(metadata + "\n" + description):
        raise ValueError("This posting is no longer accepting applications.")
    # Verify the submitted search location independently of the URL's ignored location query.
    search_location = snapshot.get("search_location", "")
    if expected_location:
        city = expected_location.split(",")[0].strip()
        if not city or normalize(city) not in normalize(search_location):
            raise ValueError(f"Set the LinkedIn location control to {expected_location}, submit the search, then capture again.")
    return {"url": url, "title": snapshot["title"].strip(), "company": snapshot["company"].strip(),
            "location": snapshot["location"].strip(), "description": description,
            "description_source": url, "source": "linkedin", "source_metadata": metadata,
            "search_location": expected_location or "", "location_evidence": search_location,
            "easy_apply": snapshot.get("easy_apply") if type(snapshot.get("easy_apply")) is bool else None}


async def capture_posting(browser_session, expected_location):
    page = await browser_session.get_current_page()
    if page is None:
        raise ValueError("No selected job page is available.")
    return posting_from_snapshot(await page.evaluate(CAPTURE_SCRIPT), expected_location)
