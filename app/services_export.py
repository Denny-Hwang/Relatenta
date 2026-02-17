"""Export database to CSV format."""

import io
import zipfile
from datetime import datetime

import pandas as pd
from sqlalchemy import select

from . import models
from .db import get_db


def export_to_csv() -> bytes:
    """
    Export all data from the database to CSV files in a zip archive.

    Returns:
        bytes: Zip file containing CSV files
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        with get_db() as db:
            # Works
            works = db.execute(select(models.Work)).scalars().all()
            if works:
                rows = []
                for w in works:
                    venue = db.get(models.Venue, w.venue_id) if w.venue_id else None
                    rows.append({
                        "id": w.id, "doi": w.doi, "source_uid": w.source_uid,
                        "title": w.title,
                        "abstract": w.abstract[:500] if w.abstract else None,
                        "year": w.year,
                        "venue": venue.name if venue else None,
                        "venue_type": venue.type if venue else None,
                        "url": w.url, "type": w.type, "language": w.language,
                        "source": w.source,
                    })
                _write_csv(zf, "works.csv", rows)

            # Authors
            authors = db.execute(select(models.Author)).scalars().all()
            if authors:
                _write_csv(zf, "authors.csv", [
                    {"id": a.id, "display_name": a.display_name,
                     "normalized_name": a.normalized_name, "orcid": a.orcid}
                    for a in authors
                ])

            # Work-Author
            work_authors = db.execute(select(models.WorkAuthor)).scalars().all()
            if work_authors:
                rows = []
                for wa in work_authors:
                    work = db.get(models.Work, wa.work_id)
                    author = db.get(models.Author, wa.author_id)
                    if work and author:
                        rows.append({
                            "work_id": wa.work_id, "work_title": work.title[:100],
                            "work_doi": work.doi, "author_id": wa.author_id,
                            "author_name": author.display_name,
                            "position": wa.position, "corresponding": wa.corresponding,
                        })
                _write_csv(zf, "work_authors.csv", rows)

            # Organizations
            orgs = db.execute(select(models.Organization)).scalars().all()
            if orgs:
                _write_csv(zf, "organizations.csv", [
                    {"id": o.id, "name": o.name, "country_code": o.country_code, "city": o.city}
                    for o in orgs
                ])

            # Affiliations
            affiliations = db.execute(select(models.WorkAffiliation)).scalars().all()
            if affiliations:
                rows = []
                for aff in affiliations:
                    work = db.get(models.Work, aff.work_id)
                    author = db.get(models.Author, aff.author_id) if aff.author_id else None
                    org = db.get(models.Organization, aff.org_id) if aff.org_id else None
                    if work:
                        rows.append({
                            "work_id": aff.work_id, "work_title": work.title[:100],
                            "work_doi": work.doi,
                            "author_id": aff.author_id,
                            "author_name": author.display_name if author else None,
                            "org_id": aff.org_id,
                            "org_name": org.name if org else aff.org_label_raw,
                            "country_code": aff.country_code, "year": aff.year,
                        })
                _write_csv(zf, "affiliations.csv", rows)

            # Keywords
            keywords = db.execute(select(models.Keyword)).scalars().all()
            if keywords:
                _write_csv(zf, "keywords.csv", [
                    {"id": k.id, "term_norm": k.term_norm,
                     "term_display": k.term_display, "vocabulary": k.vocabulary}
                    for k in keywords
                ])

            # Work-Keyword
            work_keywords = db.execute(select(models.WorkKeyword)).scalars().all()
            if work_keywords:
                rows = []
                for wk in work_keywords:
                    work = db.get(models.Work, wk.work_id)
                    keyword = db.get(models.Keyword, wk.keyword_id)
                    if work and keyword:
                        rows.append({
                            "work_id": wk.work_id, "work_title": work.title[:100],
                            "keyword_id": wk.keyword_id, "keyword": keyword.term_display,
                            "weight": wk.weight, "extractor": wk.extractor,
                        })
                _write_csv(zf, "work_keywords.csv", rows)

            # Venues
            venues = db.execute(select(models.Venue)).scalars().all()
            if venues:
                _write_csv(zf, "venues.csv", [
                    {"id": v.id, "name": v.name, "type": v.type,
                     "issn": v.issn, "publisher": v.publisher}
                    for v in venues
                ])

            # Metadata
            _write_csv(zf, "metadata.csv", [{
                "export_date": datetime.now().isoformat(),
                "total_works": len(works) if works else 0,
                "total_authors": len(authors) if authors else 0,
                "total_organizations": len(orgs) if orgs else 0,
                "total_keywords": len(keywords) if keywords else 0,
                "total_venues": len(venues) if venues else 0,
            }])

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def _write_csv(zf: zipfile.ZipFile, filename: str, rows: list[dict]):
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    zf.writestr(filename, buf.getvalue())
