from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func
from typing import Optional, List, Dict, Any, Tuple
from . import models
from datetime import datetime

def get_or_create_venue(db: Session, name: Optional[str], vtype: Optional[str], issn: Optional[str], publisher: Optional[str]) -> Optional[models.Venue]:
    if not name:
        return None
    q = db.execute(select(models.Venue).where(models.Venue.name == name)).scalar_one_or_none()
    if q:
        return q
    obj = models.Venue(name=name, type=vtype, issn=issn, publisher=publisher)
    db.add(obj)
    db.flush()
    return obj

def get_or_create_author(db: Session, display_name: str, normalized_name: Optional[str]=None, orcid: Optional[str]=None) -> models.Author:
    norm = (normalized_name or display_name).strip().lower()
    q = db.execute(select(models.Author).where(models.Author.normalized_name == norm)).scalar_one_or_none()
    if q:
        return q
    obj = models.Author(display_name=display_name, normalized_name=norm, orcid=orcid)
    db.add(obj)
    db.flush()
    db.add(models.AuthorAlias(author_id=obj.id, raw_name=display_name, source="ingest", confidence=0.9))
    return obj

def get_or_create_keyword(db: Session, term: str, display: Optional[str]=None, vocab: Optional[str]=None) -> models.Keyword:
    norm = term.strip().lower()
    q = db.execute(select(models.Keyword).where(models.Keyword.term_norm == norm)).scalar_one_or_none()
    if q:
        return q
    obj = models.Keyword(term_norm=norm, term_display=display or term, vocabulary=vocab)
    db.add(obj)
    db.flush()
    return obj

def get_or_create_org(db: Session, name: str, country: Optional[str]=None, city: Optional[str]=None) -> models.Organization:
    q = db.execute(select(models.Organization).where(models.Organization.name == name)).scalar_one_or_none()
    if q:
        return q
    obj = models.Organization(name=name, country_code=country, city=city)
    db.add(obj)
    db.flush()
    return obj

def upsert_work_from_openalex(db: Session, w: Dict[str, Any]) -> models.Work:
    doi = (w.get("doi") or "").lower() if w.get("doi") else None
    source_uid = w.get("id")  # full URL
    title = w.get("title") or "(untitled)"
    abstract = None
    if isinstance(w.get("abstract"), str):
        abstract = w["abstract"]
    elif "abstract_inverted_index" in w:
        # reconstruct abstract from inverted index (OpenAlex)
        inv = w["abstract_inverted_index"] or {}
        tokens = sorted([(pos, word) for word, poss in inv.items() for pos in poss], key=lambda x: x[0])
        abstract = " ".join([t[1] for t in tokens]) if tokens else None
    year = None
    if w.get("publication_year"):
        year = int(w["publication_year"])
    venue_name = None
    venue_type = None
    issn = None
    publisher = None
    if w.get("host_venue"):
        hv = w["host_venue"]
        venue_name = hv.get("display_name")
        issn = (hv.get("issn") or [None])[0] if isinstance(hv.get("issn"), list) and hv.get("issn") else hv.get("issn")
        venue_type = hv.get("type")
        publisher = hv.get("publisher")
    venue = get_or_create_venue(db, venue_name, venue_type, issn, publisher) if venue_name else None

    # Get URL safely
    url = None
    primary_location = w.get("primary_location") or {}
    if primary_location and isinstance(primary_location, dict):
        source = primary_location.get("source") or {}
        if source and isinstance(source, dict):
            url = source.get("url")
    
    # If no URL from primary_location, try best_oa_location
    if not url:
        best_oa = w.get("best_oa_location") or {}
        if best_oa and isinstance(best_oa, dict):
            url = best_oa.get("url")

    # check existing
    existing = None
    if doi:
        existing = db.execute(select(models.Work).where(models.Work.doi == doi)).scalar_one_or_none()
    if not existing and source_uid:
        existing = db.execute(select(models.Work).where(models.Work.source_uid == source_uid, models.Work.source == "OpenAlex")).scalar_one_or_none()

    if existing:
        # simple update
        existing.title = title
        existing.abstract = abstract
        existing.year = year
        existing.venue_id = venue.id if venue else None
        existing.url = url
        existing.type = w.get("type")
        existing.language = w.get("language")
        existing.raw_json = w
        
        # Clear existing relationships to avoid duplicates
        db.execute(delete(models.WorkAuthor).where(models.WorkAuthor.work_id == existing.id))
        db.execute(delete(models.WorkAffiliation).where(models.WorkAffiliation.work_id == existing.id))
        db.execute(delete(models.WorkKeyword).where(models.WorkKeyword.work_id == existing.id))
        db.flush()
        
        # Re-add authors, affiliations, and keywords (same code as for new work)
        for idx, auth in enumerate((w.get("authorships") or [])):
            a_display = (auth.get("author") or {}).get("display_name") or "Unknown"
            a_orcid = (auth.get("author") or {}).get("orcid")
            author = get_or_create_author(db, a_display, orcid=a_orcid)
            db.add(models.WorkAuthor(work_id=existing.id, author_id=author.id, position=idx, corresponding=False))

            # affiliations
            inst = (auth.get("institutions") or [])
            if inst:
                for inst_item in inst:
                    org_name = inst_item.get("display_name")
                    country = (inst_item.get("country_code") or "")
                    org = get_or_create_org(db, org_name, country=country) if org_name else None
                    db.add(models.WorkAffiliation(
                        work_id=existing.id, author_id=author.id,
                        org_id=org.id if org else None,
                        org_label_raw=org_name, year=year, country_code=country or None
                    ))

        # keywords from OpenAlex concepts
        for c in (w.get("concepts") or []):
            kw = get_or_create_keyword(db, c.get("display_name") or "", display=c.get("display_name"), vocab="openalex_concept")
            if kw:
                db.add(models.WorkKeyword(work_id=existing.id, keyword_id=kw.id, weight=float(c.get("score") or 1.0), extractor="openalex"))
        
        return existing

    obj = models.Work(
        doi=doi, source_uid=source_uid, title=title, abstract=abstract, year=year,
        venue_id=venue.id if venue else None,
        url=url,
        type=w.get("type"), language=w.get("language"), source="OpenAlex", raw_json=w
    )
    db.add(obj)
    db.flush()

    # authors
    for idx, auth in enumerate((w.get("authorships") or [])):
        a_display = (auth.get("author") or {}).get("display_name") or "Unknown"
        a_orcid = (auth.get("author") or {}).get("orcid")
        author = get_or_create_author(db, a_display, orcid=a_orcid)
        db.add(models.WorkAuthor(work_id=obj.id, author_id=author.id, position=idx, corresponding=False))

        # affiliations
        inst = (auth.get("institutions") or [])
        if inst:
            for inst_item in inst:
                org_name = inst_item.get("display_name")
                country = (inst_item.get("country_code") or "")
                org = get_or_create_org(db, org_name, country=country) if org_name else None
                db.add(models.WorkAffiliation(
                    work_id=obj.id, author_id=author.id,
                    org_id=org.id if org else None,
                    org_label_raw=org_name, year=year, country_code=country or None
                ))

    # keywords from OpenAlex concepts
    for c in (w.get("concepts") or []):
        kw = get_or_create_keyword(db, c.get("display_name") or "", display=c.get("display_name"), vocab="openalex_concept")
        if kw:
            db.add(models.WorkKeyword(work_id=obj.id, keyword_id=kw.id, weight=float(c.get("score") or 1.0), extractor="openalex"))

    return obj

def recompute_coauthor_edges(db: Session):
    # Simple aggregation: for each work, add +1 to each pair of coauthors
    db.execute(delete(models.CoauthorEdge))
    pairs = {}
    works = db.execute(select(models.Work.id)).scalars().all()
    for wid in works:
        auth_ids = db.execute(select(models.WorkAuthor.author_id).where(models.WorkAuthor.work_id == wid)).scalars().all()
        auth_ids = sorted(set(auth_ids))
        for i in range(len(auth_ids)):
            for j in range(i+1, len(auth_ids)):
                a, b = auth_ids[i], auth_ids[j]
                key = (a, b)
                pairs[key] = pairs.get(key, 0) + 1
    for (a, b), w in pairs.items():
        db.add(models.CoauthorEdge(a_id=a, b_id=b, weight=float(w), evidence_count=w))
    db.flush()

def recompute_org_edges(db: Session):
    """Compute organization collaboration edges based on co-authorship."""
    db.execute(delete(models.OrgEdge))
    # For each work, get set of organizations; add +1 for each pair
    works = db.execute(select(models.Work.id)).scalars().all()
    from itertools import combinations
    
    pairs = {}
    for wid in works:
        orgs = db.execute(
            select(models.WorkAffiliation.org_id)
            .where(models.WorkAffiliation.work_id == wid, models.WorkAffiliation.org_id.isnot(None))
        ).scalars().all()
        orgs = sorted(set([o for o in orgs if o]))
        
        for o1, o2 in combinations(orgs, 2):
            key = tuple(sorted([o1, o2]))  # Ensure consistent ordering
            pairs[key] = pairs.get(key, 0) + 1
    
    for (o1, o2), weight in pairs.items():
        db.add(models.OrgEdge(org1_id=o1, org2_id=o2, weight=float(weight)))
    db.flush()

def recompute_nation_edges(db: Session):
    db.execute(delete(models.NationEdge))
    db.flush()  # Ensure deletes are committed before inserts
    
    # For each work, get set of nations; add +1 for each pair
    works = db.execute(select(models.Work.id)).scalars().all()
    from itertools import combinations
    
    # Use a dictionary to accumulate weights
    nation_pairs = {}
    
    for wid in works:
        nations = db.execute(
            select(models.WorkAffiliation.country_code)
            .where(models.WorkAffiliation.work_id == wid, models.WorkAffiliation.country_code.isnot(None))
        ).scalars().all()
        nations = sorted(set([n for n in nations if n]))
        
        for n1, n2 in combinations(nations, 2):
            # Ensure consistent ordering
            pair = tuple(sorted([n1, n2]))
            nation_pairs[pair] = nation_pairs.get(pair, 0) + 1
    
    # Now insert all edges at once
    for (n1, n2), weight in nation_pairs.items():
        edge = models.NationEdge(n1=n1, n2=n2, weight=float(weight), last_updated=datetime.utcnow())
        db.add(edge)
    
    db.flush()

def merge_authors(db: Session, kept_id: int, removed_id: int, reason: str | None, user: str | None):
    # reassign WorkAuthor, WorkAffiliation to kept
    db.execute(update(models.WorkAuthor).where(models.WorkAuthor.author_id == removed_id).values(author_id=kept_id))
    db.execute(update(models.WorkAffiliation).where(models.WorkAffiliation.author_id == removed_id).values(author_id=kept_id))
    # delete removed author aliases move to kept
    aliases = db.execute(select(models.AuthorAlias).where(models.AuthorAlias.author_id == removed_id)).scalars().all()
    for al in aliases:
        al.author_id = kept_id
    # delete removed author
    db.execute(delete(models.Author).where(models.Author.id == removed_id))
    # log
    db.add(models.MergeLog(entity_type="author", kept_id=str(kept_id), removed_id=str(removed_id), reason=reason, user=user))
    # recompute edges
    recompute_coauthor_edges(db)
    recompute_org_edges(db)
    recompute_nation_edges(db)