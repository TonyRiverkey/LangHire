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
    '.jobs-unified-top-card', '.top-card-layout', '.job-details-jobs-unified-top-card',
    '.jobs-details__main-content', '.jobs-search__job-details--container']);
  const title = first(['.job-details-jobs-unified-top-card__job-title',
    '.jobs-unified-top-card__job-title', '.top-card-layout__title', 'h1', 'h2'], card || document);
  const company = first(['.job-details-jobs-unified-top-card__company-name',
    '.jobs-unified-top-card__company-name', '.topcard__org-name-link'], card || document);
  const location = first(['.job-details-jobs-unified-top-card__primary-description-container',
    '.jobs-unified-top-card__bullet', '.topcard__flavor--bullet'], card || document);
  const searchLocation = first(['input[id*="jobs-search-box-location"]',
    'input[aria-label*="City, state"]', 'input[aria-label*="location" i]']);
  const applyText = text(first(['.jobs-apply-button', '.jobs-apply-button--top-card']));
  const titleLink = title && (title.closest('a[href*="/jobs/view/"]') || title.querySelector('a[href*="/jobs/view/"]'));
  const detail = (title || card)?.closest('[data-job-id], [data-entity-urn*="jobPosting:"]');
  const detailId = detail?.getAttribute('data-job-id') || detail?.getAttribute('data-entity-urn')?.match(/jobPosting:(\d+)$/)?.[1];
  const canonical = /\/jobs\/view\//.test(window.location.pathname) && document.querySelector('link[rel="canonical"]');
  return {page_url: window.location.href, title: text(title), company: text(company),
    location: text(location), metadata: text(card), description: text(description),
    source_job_url: titleLink?.href || (/^\d+$/.test(detailId || '') ? 'https://www.linkedin.com/jobs/view/' + detailId + '/' : '') || canonical?.href || '',
    canonical_url: canonical?.href || '',
    standalone_detail: /^\/jobs\/view\//.test(window.location.pathname) && Boolean(card && title && company && location && description),
    description_collapsed: Boolean(description && (description.matches('[aria-expanded="false"]') ||
      Array.from(description.querySelectorAll('button[aria-expanded="false"]')).some(b => /more/i.test(text(b))))),
    search_location: searchLocation ? searchLocation.value : '',
    easy_apply: /easy apply/i.test(applyText) ? true : (/apply/i.test(applyText) ? false : null)};
}"""

LOCATION_INPUT = 'input[id*="jobs-search-box-location"], input[aria-label*="City, state"], input[aria-label*="location" i], input[name="location"]'
SEARCH_STATE_SCRIPT = r"""(locationSelector) => {
  const visible = el => el.getClientRects().length > 0;
  const input = Array.from(document.querySelectorAll(locationSelector)).find(visible);
  const controls = Array.from(document.querySelectorAll(
    'button[aria-pressed="true"], button[aria-expanded], [aria-checked="true"], button.jobs-search-dropdown__button'))
    .filter(visible).flatMap(el => [el.innerText.trim(), el.getAttribute('aria-label') || '']);
  const guestLocations = Array.from(document.querySelectorAll('.job-search-card__location'))
    .filter(visible).map(el => el.innerText.trim());
  return {location: input?.value || '', dates: controls, url: location.href, guest_locations: guestLocations,
    geo_id: input?.closest('form')?.querySelector('input[name="geoId"]')?.value || '',
    text: (document.querySelector('main') || document.body)?.innerText || ''};
}"""


async def search_state(browser_session, *, page=None):
    page = page or await browser_session.get_current_page()
    if page is None:
        return {}
    state = await page.evaluate(SEARCH_STATE_SCRIPT, LOCATION_INPUT)
    return json.loads(state) if isinstance(state, str) else state


def location_matches(expected, visible):
    target = [normalize(part) for part in expected.split(",")]
    visible = re.sub(r"\s*\(\d+\s*(?:km|mi)\)\s*$", "", visible, flags=re.I)
    found = [normalize(part) for part in visible.split(",")]
    if not target[0] or target[0] != found[0] or len(found) < len(target):
        return False

    # The search field may expand a region abbreviation ("BC" → "British Columbia").
    def region_matches(a, b):
        def initials(value):
            return "".join(word[0] for word in value.split())
        return a == b or (len(a) > 1 and a == initials(b)) or (len(b) > 1 and b == initials(a))

    return all(region_matches(a, b) for a, b in zip(target[1:], found[1:]))


DATE_LABELS = {"r86400": "past 24 hours", "r604800": "past week", "r2592000": "past month"}
END_OF_RESULTS = re.compile(
    r"^\s*(?:no (?:matching )?jobs(?: found)?|no (?:more )?results(?: found)?|"
    r"you['’]ve viewed all(?: (?:the )?jobs(?: for this search)?)?|all jobs viewed|page 1 of 1)[.!]?\s*$",
    re.I | re.M,
)


def verified_search(state, city, date_posted=None):
    if not search_location_evidence(state, city):
        return False
    if date_posted:
        label = DATE_LABELS.get(date_posted)
        return bool(label and any(normalize(value) == label or f"{label} filter is currently applied" in normalize(value)
                                  for value in state.get("dates", [])))
    return True


def search_location_evidence(state, city):
    visible = state.get("location", "")
    if location_matches(city, visible):
        return visible
    # The public search abbreviates the resolved location to its city name.
    if state.get("geo_id") and normalize(visible) == normalize(city.split(",")[0]):
        return next((place for place in state.get("guest_locations", []) if location_matches(city, place)), "")
    return ""


def exhausted(state, evidence):
    return (bool(evidence.strip()) and normalize(evidence) in normalize(state.get("text", ""))
            and bool(END_OF_RESULTS.search(evidence)))


async def verify_exhausted(browser_session, expected_location, evidence, date_posted=None):
    state = await search_state(browser_session)
    return (verified_search(state, expected_location, date_posted)
            and exhausted(state, evidence))


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


def posting_from_snapshot(snapshot, expected_location, *, expected_url=None, search_evidence=None):
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    url = canonical_job_url(snapshot.get("page_url", ""))
    if expected_url and url != canonical_job_url(expected_url):
        raise ValueError("Loaded posting does not match the selected card.")
    try:
        source_url = canonical_job_url(snapshot.get("source_job_url", ""))
    except ValueError:
        if not (expected_url and snapshot.get("standalone_detail")
                and not snapshot.get("source_job_url") and not snapshot.get("canonical_url")):
            raise ValueError("The selected posting's identity is not available yet. Wait for details or open the job in its own tab.") from None
        source_url = url
    if source_url != url:
        raise ValueError("The selected details are still showing a different posting. Wait for the job to load.")
    if snapshot.get("canonical_url") and canonical_job_url(snapshot["canonical_url"]) != url:
        raise ValueError("Loaded posting has a different canonical job ID.")
    for field in ("title", "company", "location", "description"):
        if not isinstance(snapshot.get(field), str) or not snapshot[field].strip():
            raise ValueError(f"Cannot capture the selected posting's {field}. Open or expand its details.")
    description = snapshot["description"].strip()
    if len(description) < 300 or snapshot.get("description_collapsed"):
        raise ValueError("The job description is incomplete. Expand it and capture again.")
    metadata = snapshot.get("metadata", "")
    if "no longer accepting applications" in normalize(metadata + "\n" + description):
        raise ValueError("This posting is no longer accepting applications.")
    # Verify the submitted search location independently of the URL's ignored location query.
    search_location = search_evidence if search_evidence is not None else snapshot.get("search_location", "")
    if expected_location:
        if not location_matches(expected_location, search_location):
            raise ValueError(f"Set the LinkedIn location control to {expected_location}, submit the search, then capture again.")
    return {"url": url, "title": snapshot["title"].strip(), "company": snapshot["company"].strip(),
            "location": snapshot["location"].strip(), "description": description,
            "description_source": url, "source": "linkedin", "source_metadata": metadata,
            "search_location": expected_location or "", "location_evidence": search_location,
            "easy_apply": snapshot.get("easy_apply") if type(snapshot.get("easy_apply")) is bool else None}


async def capture_posting(browser_session, expected_location, *, page=None, expected_url=None, search_evidence=None):
    page = page or await browser_session.get_current_page()
    if page is None:
        raise ValueError("No selected job page is available.")
    return posting_from_snapshot(await page.evaluate(CAPTURE_SCRIPT), expected_location,
                                 expected_url=expected_url, search_evidence=search_evidence)
