"""Job search via JSearch (RapidAPI) with SerpAPI fallback."""
import time
from typing import Any
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


def search_jobs(
    query: str,
    location: str,
    date_posted: str,
    employment_type: str,
    remote_only: bool,
    require_sponsorship: bool,
    num_pages: int,
    rapidapi_key: str,
    serpapi_key: str,
) -> list[dict[str, Any]]:
    """
    Search jobs using JSearch API. Falls back to SerpAPI if JSearch key not set.
    Returns a flat list of normalized job dicts.
    """
    # Append sponsorship keywords to query when required
    effective_query = query
    if require_sponsorship:
        effective_query = f"{query} visa sponsorship"

    if rapidapi_key:
        results = _search_jsearch(
            effective_query, location, date_posted, employment_type,
            remote_only, num_pages, rapidapi_key,
        )
        if results:
            return results

    if serpapi_key:
        results = _search_serpapi(
            effective_query, location, date_posted, remote_only,
            num_pages, serpapi_key,
        )
        if results:
            return results

    return []


# ── JSearch (RapidAPI) ────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _jsearch_page(query: str, location: str, date_posted: str,
                  employment_type: str, remote_only: bool,
                  page: int, rapidapi_key: str) -> dict:
    params: dict[str, Any] = {
        "query": f"{query} in {location}" if location else query,
        "page": str(page),
        "num_pages": "1",
        "language": "en",
    }
    if date_posted:
        params["date_posted"] = date_posted
    if employment_type:
        params["employment_types"] = employment_type
    if remote_only:
        params["remote_jobs_only"] = "true"

    resp = requests.get(
        "https://jsearch.p.rapidapi.com/search",
        headers={
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        },
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _search_jsearch(
    query: str, location: str, date_posted: str,
    employment_type: str, remote_only: bool,
    num_pages: int, rapidapi_key: str,
) -> list[dict]:
    jobs = []
    for page in range(1, num_pages + 1):
        try:
            data = _jsearch_page(query, location, date_posted, employment_type,
                                  remote_only, page, rapidapi_key)
            raw_jobs = data.get("data", [])
            if not raw_jobs:
                break
            for j in raw_jobs:
                jobs.append(_normalize_jsearch(j))
            time.sleep(0.5)
        except Exception:
            break
    return jobs


def _normalize_jsearch(j: dict) -> dict:
    desc = j.get("job_description") or ""
    return {
        "id": j.get("job_id", ""),
        "title": j.get("job_title", ""),
        "company": j.get("employer_name", ""),
        "location": _format_location(j),
        "remote": j.get("job_is_remote", False),
        "employment_type": j.get("job_employment_type", ""),
        "date_posted": j.get("job_posted_at_datetime_utc", ""),
        "description": desc,
        "apply_url": j.get("job_apply_link") or j.get("job_google_link", ""),
        "source": "JSearch",
        "sponsorship_mentioned": _check_sponsorship(desc),
    }


def _format_location(j: dict) -> str:
    parts = [j.get("job_city"), j.get("job_state"), j.get("job_country")]
    return ", ".join(p for p in parts if p)


# ── SerpAPI (Google Jobs) ─────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _serpapi_page(query: str, location: str, date_posted: str,
                  start: int, serpapi_key: str) -> dict:
    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": query,
        "api_key": serpapi_key,
        "hl": "en",
    }
    if location:
        params["location"] = location
    if date_posted:
        params["chips"] = f"date_posted:{date_posted}"
    if start:
        params["start"] = str(start)

    resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _search_serpapi(
    query: str, location: str, date_posted: str,
    remote_only: bool, num_pages: int, serpapi_key: str,
) -> list[dict]:
    if remote_only and "remote" not in query.lower():
        query = f"remote {query}"

    jobs = []
    for page in range(num_pages):
        try:
            data = _serpapi_page(query, location, date_posted, page * 10, serpapi_key)
            raw_jobs = data.get("jobs_results", [])
            if not raw_jobs:
                break
            for j in raw_jobs:
                jobs.append(_normalize_serpapi(j))
            time.sleep(0.5)
        except Exception:
            break
    return jobs


def _normalize_serpapi(j: dict) -> dict:
    desc = j.get("description") or ""
    # Extract apply link
    apply_url = ""
    for link in j.get("apply_options", []):
        apply_url = link.get("link", "")
        break

    return {
        "id": j.get("job_id", ""),
        "title": j.get("title", ""),
        "company": j.get("company_name", ""),
        "location": j.get("location", ""),
        "remote": "remote" in (j.get("location") or "").lower(),
        "employment_type": "",
        "date_posted": j.get("detected_extensions", {}).get("posted_at", ""),
        "description": desc,
        "apply_url": apply_url,
        "source": "SerpAPI",
        "sponsorship_mentioned": _check_sponsorship(desc),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

SPONSORSHIP_KEYWORDS = [
    "visa sponsorship", "sponsor visa", "work authorization",
    "work permit", "sponsorship available", "h1b", "h-1b",
    "tn visa", "o-1", "green card", "immigration sponsorship",
    "will sponsor", "sponsoring", "visa support",
]


def _check_sponsorship(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in SPONSORSHIP_KEYWORDS)
