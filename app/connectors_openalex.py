import re
import requests
from typing import List, Dict, Any, Tuple

OPENALEX = "https://api.openalex.org"

# ORCID pattern: 0000-0001-2345-6789 (last char can be X)
_ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


def _format_author_result(item: dict) -> Dict[str, Any]:
    """Convert a raw OpenAlex author record to our standard format."""
    author_info = {
        "id": item["id"],
        "display_name": item.get("display_name"),
        "works_count": item.get("works_count", 0),
        "cited_by_count": item.get("cited_by_count", 0),
        "orcid": item.get("orcid"),
        "last_known_institution": None,
        "institution_country": None,
        "institution_type": None,
        "top_concepts": [],
        "works_api_url": item.get("works_api_url"),
        "h_index": item.get("summary_stats", {}).get("h_index", 0) if item.get("summary_stats") else 0,
        "i10_index": item.get("summary_stats", {}).get("i10_index", 0) if item.get("summary_stats") else 0,
    }

    last_institution = item.get("last_known_institution")
    if last_institution and isinstance(last_institution, dict):
        author_info["last_known_institution"] = last_institution.get("display_name")
        author_info["institution_country"] = last_institution.get("country_code")
        author_info["institution_type"] = last_institution.get("type")

    concepts = item.get("x_concepts", [])
    if concepts:
        sorted_concepts = sorted(concepts, key=lambda x: x.get("score", 0), reverse=True)
        author_info["top_concepts"] = [
            {"name": c.get("display_name"), "score": c.get("score", 0)}
            for c in sorted_concepts[:3]
        ]

    return author_info


def detect_query_type(query: str) -> str:
    """Detect whether the query is a name, ORCID, or Google Scholar URL.

    Returns one of: 'orcid', 'google_scholar', 'name'
    """
    q = query.strip()

    # Google Scholar URL
    if "scholar.google." in q:
        return "google_scholar"

    # ORCID URL
    if "orcid.org/" in q:
        return "orcid"

    # Bare ORCID number
    if _ORCID_RE.fullmatch(q):
        return "orcid"

    return "name"


def search_authors_by_name(name: str, per_page: int = 25) -> List[Dict[str, Any]]:
    """Search for authors by name via OpenAlex."""
    params = {"search": name, "per_page": per_page}
    r = requests.get(f"{OPENALEX}/authors", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return [_format_author_result(item) for item in data.get("results", [])]


def search_author_by_orcid(orcid_input: str) -> Tuple[List[Dict[str, Any]], str]:
    """Search for an author by ORCID via OpenAlex.

    Accepts formats:
      - 0000-0001-2345-6789
      - https://orcid.org/0000-0001-2345-6789

    Returns (results, method) where method is 'orcid' or 'orcid_name_fallback'.
    """
    q = orcid_input.strip()

    # Extract bare ORCID from URL
    if "orcid.org/" in q:
        q = q.split("orcid.org/")[-1].strip().rstrip("/")

    match = _ORCID_RE.search(q)
    if not match:
        return [], "orcid"
    orcid = match.group(0)

    # Direct lookup (faster)
    try:
        r = requests.get(f"{OPENALEX}/authors/orcid:{orcid}", timeout=30)
        if r.status_code == 200:
            item = r.json()
            if item.get("id"):
                return [_format_author_result(item)], "orcid"
    except Exception:
        pass

    # Fallback: filter search
    try:
        params = {"filter": f"orcid:{orcid}"}
        r = requests.get(f"{OPENALEX}/authors", params=params, timeout=30)
        if r.status_code == 200:
            data = r.json()
            results = [_format_author_result(item) for item in data.get("results", [])]
            if results:
                return results, "orcid"
    except Exception:
        pass

    # Last resort: resolve name from ORCID.org, then search by name
    name = _resolve_orcid_name(orcid)
    if name:
        return search_authors_by_name(name), "orcid_name_fallback"

    return [], "orcid"


def search_author_by_google_scholar(url: str) -> Tuple[List[Dict[str, Any]], str]:
    """Try to resolve a Google Scholar profile to an OpenAlex author.

    Strategy:
      1. Fetch the Google Scholar profile page
      2. Extract name and ORCID (if linked on the page)
      3. If ORCID found → exact OpenAlex lookup
      4. Otherwise → search OpenAlex by name

    Returns (results, method) where method is 'scholar_orcid', 'scholar_name', etc.
    """
    info = _resolve_google_scholar_profile(url.strip())
    if not info:
        return [], "scholar_failed"

    # If an ORCID was found on the Scholar page, try exact lookup
    if info.get("orcid"):
        results, method = search_author_by_orcid(info["orcid"])
        if results:
            return results, "scholar_orcid"

    # Fall back to name search
    if info.get("name"):
        return search_authors_by_name(info["name"]), "scholar_name"

    return [], "scholar_failed"


def _resolve_google_scholar_profile(url: str) -> dict | None:
    """Extract author info (name, ORCID, affiliation) from a Google Scholar profile."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None

        text = r.text
        info: Dict[str, str] = {}

        # Extract name: <div id="gsc_prf_in">Author Name</div>
        m = re.search(r'id="gsc_prf_in"[^>]*>([^<]+)</\s*div>', text)
        if m:
            info["name"] = m.group(1).strip()
        else:
            # Fallback: <title>Author Name - Google Scholar</title>
            m = re.search(r"<title>(.+?)(?:\s*[-–—]\s*Google Scholar)?</title>", text)
            if m:
                name = m.group(1).strip()
                if name and name.lower() != "google scholar":
                    info["name"] = name

        # Try to extract ORCID link from the page
        m = re.search(r'orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])', text)
        if m:
            info["orcid"] = m.group(1)

        # Extract affiliation
        m = re.search(r'class="gsc_prf_il"[^>]*>([^<]+)<', text)
        if m:
            info["affiliation"] = m.group(1).strip()

        return info if info else None

    except Exception:
        return None


def _resolve_orcid_name(orcid: str) -> str | None:
    """Fetch author name from ORCID.org as fallback when OpenAlex has no match.

    Tries the ORCID public API (JSON) first, then falls back to HTML scraping.
    """
    # Method 1: ORCID public API (works without auth for public records)
    try:
        headers = {"Accept": "application/json"}
        r = requests.get(
            f"https://pub.orcid.org/v3.0/{orcid}/personal-details",
            headers=headers, timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            name_obj = data.get("name") or {}
            given = (name_obj.get("given-names") or {}).get("value", "") or ""
            family = (name_obj.get("family-name") or {}).get("value", "") or ""
            full = f"{given} {family}".strip()
            if full:
                return full
    except Exception:
        pass

    # Method 2: scrape the ORCID.org HTML page
    try:
        r = requests.get(f"https://orcid.org/{orcid}", timeout=15)
        if r.status_code == 200:
            m = re.search(r"<title>(.+?)(?:\s*[-–—]\s*ORCID)?</title>", r.text)
            if m:
                name = m.group(1).strip()
                if name and name.lower() != "orcid":
                    return name
    except Exception:
        pass

    return None


def list_author_works(openalex_author_id: str, per_page: int = 200, max_pages: int = 3) -> List[Dict[str, Any]]:
    """Fetch author's works from OpenAlex."""
    if openalex_author_id.startswith("https://"):
        author_filter = openalex_author_id.split("/")[-1]
    else:
        author_filter = openalex_author_id

    works = []
    page = 1
    while page <= max_pages:
        params = {
            "filter": f"author.id:A{author_filter.replace('A','')}" if not author_filter.startswith("A") else f"author.id:{author_filter}",
            "per_page": per_page,
            "page": page,
            "sort": "cited_by_count:desc"
        }
        r = requests.get(f"{OPENALEX}/works", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        works.extend(data.get("results", []))
        if "meta" in data and data["meta"].get("next_cursor") is None and len(data.get("results", [])) < per_page:
            break
        page += 1
    return works
