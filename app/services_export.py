"""Export service for actor databases to CSV format."""

import pandas as pd
import io
import zipfile
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models
from .db import get_db
from datetime import datetime

def export_actor_to_csv(actor_name: str) -> bytes:
    """
    Export all data from an actor's database to CSV files in a zip archive.
    
    Returns:
        bytes: Zip file containing CSV files
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        with get_db(actor_name) as db:
            
            # Export Works
            works = db.execute(select(models.Work)).scalars().all()
            if works:
                works_data = []
                for w in works:
                    venue = db.get(models.Venue, w.venue_id) if w.venue_id else None
                    works_data.append({
                        'id': w.id,
                        'doi': w.doi,
                        'source_uid': w.source_uid,
                        'title': w.title,
                        'abstract': w.abstract[:500] if w.abstract else None,  # Truncate long abstracts
                        'year': w.year,
                        'venue': venue.name if venue else None,
                        'venue_type': venue.type if venue else None,
                        'url': w.url,
                        'type': w.type,
                        'language': w.language,
                        'source': w.source
                    })
                works_df = pd.DataFrame(works_data)
                csv_buffer = io.StringIO()
                works_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_works.csv', csv_buffer.getvalue())
            
            # Export Authors
            authors = db.execute(select(models.Author)).scalars().all()
            if authors:
                authors_data = []
                for a in authors:
                    authors_data.append({
                        'id': a.id,
                        'display_name': a.display_name,
                        'normalized_name': a.normalized_name,
                        'orcid': a.orcid
                    })
                authors_df = pd.DataFrame(authors_data)
                csv_buffer = io.StringIO()
                authors_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_authors.csv', csv_buffer.getvalue())
            
            # Export Work-Author relationships
            work_authors = db.execute(select(models.WorkAuthor)).scalars().all()
            if work_authors:
                wa_data = []
                for wa in work_authors:
                    work = db.get(models.Work, wa.work_id)
                    author = db.get(models.Author, wa.author_id)
                    if work and author:
                        wa_data.append({
                            'work_id': wa.work_id,
                            'work_title': work.title[:100],
                            'work_doi': work.doi,
                            'author_id': wa.author_id,
                            'author_name': author.display_name,
                            'position': wa.position,
                            'corresponding': wa.corresponding
                        })
                wa_df = pd.DataFrame(wa_data)
                csv_buffer = io.StringIO()
                wa_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_work_authors.csv', csv_buffer.getvalue())
            
            # Export Organizations
            orgs = db.execute(select(models.Organization)).scalars().all()
            if orgs:
                orgs_data = []
                for o in orgs:
                    orgs_data.append({
                        'id': o.id,
                        'name': o.name,
                        'country_code': o.country_code,
                        'city': o.city
                    })
                orgs_df = pd.DataFrame(orgs_data)
                csv_buffer = io.StringIO()
                orgs_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_organizations.csv', csv_buffer.getvalue())
            
            # Export Affiliations
            affiliations = db.execute(select(models.WorkAffiliation)).scalars().all()
            if affiliations:
                aff_data = []
                for aff in affiliations:
                    work = db.get(models.Work, aff.work_id)
                    author = db.get(models.Author, aff.author_id) if aff.author_id else None
                    org = db.get(models.Organization, aff.org_id) if aff.org_id else None
                    if work:
                        aff_data.append({
                            'work_id': aff.work_id,
                            'work_title': work.title[:100],
                            'author_id': aff.author_id,
                            'author_name': author.display_name if author else None,
                            'org_id': aff.org_id,
                            'org_name': org.name if org else aff.org_label_raw,
                            'country_code': aff.country_code,
                            'year': aff.year
                        })
                aff_df = pd.DataFrame(aff_data)
                csv_buffer = io.StringIO()
                aff_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_affiliations.csv', csv_buffer.getvalue())
            
            # Export Keywords
            keywords = db.execute(select(models.Keyword)).scalars().all()
            if keywords:
                kw_data = []
                for k in keywords:
                    kw_data.append({
                        'id': k.id,
                        'term_norm': k.term_norm,
                        'term_display': k.term_display,
                        'vocabulary': k.vocabulary
                    })
                kw_df = pd.DataFrame(kw_data)
                csv_buffer = io.StringIO()
                kw_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_keywords.csv', csv_buffer.getvalue())
            
            # Export Work-Keyword relationships
            work_keywords = db.execute(select(models.WorkKeyword)).scalars().all()
            if work_keywords:
                wk_data = []
                for wk in work_keywords:
                    work = db.get(models.Work, wk.work_id)
                    keyword = db.get(models.Keyword, wk.keyword_id)
                    if work and keyword:
                        wk_data.append({
                            'work_id': wk.work_id,
                            'work_title': work.title[:100],
                            'keyword_id': wk.keyword_id,
                            'keyword': keyword.term_display,
                            'weight': wk.weight,
                            'extractor': wk.extractor
                        })
                wk_df = pd.DataFrame(wk_data)
                csv_buffer = io.StringIO()
                wk_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_work_keywords.csv', csv_buffer.getvalue())
            
            # Export Venues
            venues = db.execute(select(models.Venue)).scalars().all()
            if venues:
                venues_data = []
                for v in venues:
                    venues_data.append({
                        'id': v.id,
                        'name': v.name,
                        'type': v.type,
                        'issn': v.issn,
                        'publisher': v.publisher
                    })
                venues_df = pd.DataFrame(venues_data)
                csv_buffer = io.StringIO()
                venues_df.to_csv(csv_buffer, index=False)
                zip_file.writestr(f'{actor_name}_venues.csv', csv_buffer.getvalue())
            
            # Add metadata file
            metadata = {
                'actor_name': actor_name,
                'export_date': datetime.now().isoformat(),
                'total_works': len(works) if works else 0,
                'total_authors': len(authors) if authors else 0,
                'total_organizations': len(orgs) if orgs else 0,
                'total_keywords': len(keywords) if keywords else 0,
                'total_venues': len(venues) if venues else 0
            }
            metadata_df = pd.DataFrame([metadata])
            csv_buffer = io.StringIO()
            metadata_df.to_csv(csv_buffer, index=False)
            zip_file.writestr(f'{actor_name}_metadata.csv', csv_buffer.getvalue())
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()