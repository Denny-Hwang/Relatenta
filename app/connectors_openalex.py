import requests
from typing import List, Dict, Any, Tuple

OPENALEX = "https://api.openalex.org"

def search_authors_by_name(name: str, per_page: int = 25) -> List[Dict[str, Any]]:
    """Search for authors with enhanced disambiguation information."""
    params = {"search": name, "per_page": per_page}
    r = requests.get(f"{OPENALEX}/authors", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = []
    
    for item in data.get("results", []):
        # Extract comprehensive author information for disambiguation
        author_info = {
            "id": item["id"],  # e.g., https://openalex.org/A123
            "display_name": item.get("display_name"),
            "works_count": item.get("works_count", 0),
            "cited_by_count": item.get("cited_by_count", 0),
            "orcid": item.get("orcid"),
            
            # Institution information
            "last_known_institution": None,
            "institution_country": None,
            "institution_type": None,
            
            # Research areas (top 3 concepts)
            "top_concepts": [],
            
            # Additional metadata
            "works_api_url": item.get("works_api_url"),
            "h_index": item.get("summary_stats", {}).get("h_index", 0) if item.get("summary_stats") else 0,
            "i10_index": item.get("summary_stats", {}).get("i10_index", 0) if item.get("summary_stats") else 0,
        }
        
        # Extract institution details
        last_institution = item.get("last_known_institution")
        if last_institution and isinstance(last_institution, dict):
            author_info["last_known_institution"] = last_institution.get("display_name")
            author_info["institution_country"] = last_institution.get("country_code")
            author_info["institution_type"] = last_institution.get("type")
        
        # Extract top research concepts/topics
        concepts = item.get("x_concepts", [])
        if concepts:
            # Sort by score and take top 3
            sorted_concepts = sorted(concepts, key=lambda x: x.get("score", 0), reverse=True)
            author_info["top_concepts"] = [
                {
                    "name": c.get("display_name"),
                    "score": c.get("score", 0)
                }
                for c in sorted_concepts[:3]
            ]
        
        results.append(author_info)
    
    return results

def list_author_works(openalex_author_id: str, per_page: int = 200, max_pages: int = 3) -> List[Dict[str, Any]]:
    """Fetch author's works from OpenAlex."""
    # openalex_author_id should be like "A123..." or full URL
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