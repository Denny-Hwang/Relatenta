from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AuthorHit(BaseModel):
    source_id: str
    display_name: str
    works_count: int = 0
    last_known_institution: Optional[str] = None

class IngestRequest(BaseModel):
    author_source_ids: List[str] = Field(..., description="List of OpenAlex author IDs like A12345")
    max_works: int = 200

class GraphRequest(BaseModel):
    layer: str = Field("authors", description="authors|keywords|orgs|nations")
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    edge_min_weight: float = 0.0
    focus_author_ids: Optional[List[int]] = None

class GraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class HeatmapRequest(BaseModel):
    kind: str = Field("author_keyword", description="author_keyword|nation_nation")
    year_min: Optional[int] = None
    year_max: Optional[int] = None

class CSVImportRequest(BaseModel):
    kind: str = Field(..., description="works|authors|affiliations|keywords")
    csv_text: str

class MergeRequest(BaseModel):
    kept_author_id: int
    removed_author_id: int
    reason: Optional[str] = None
    user: Optional[str] = None

class GraphRequest(BaseModel):
    layer: str = Field("authors", description="authors|keywords|orgs|nations")
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    edge_min_weight: float = 0.0
    focus_ids: Optional[List[str]] = None  # For nation codes (strings)
    focus_int_ids: Optional[List[int]] = None  # For numeric IDs (authors, keywords, orgs)
    focus_author_ids: Optional[List[int]] = None  # Keep for backward compatibility
    focus_only: bool = False