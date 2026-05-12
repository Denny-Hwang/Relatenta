from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Dict, Any, List, Optional
from . import models

def author_keyword_heat(db: Session, year_min: int | None, year_max: int | None) -> Dict[str, Any]:
    # matrix rows: authors, cols: keywords, values: counts
    # limit to top N authors/keywords for simplicity
    from collections import defaultdict

    # Single JOIN: pull all (work_id, author_id) pairs in year range
    wa_q = (
        select(models.WorkAuthor.work_id, models.WorkAuthor.author_id)
        .join(models.Work, models.WorkAuthor.work_id == models.Work.id)
    )
    if year_min is not None: wa_q = wa_q.where(models.Work.year >= year_min)
    if year_max is not None: wa_q = wa_q.where(models.Work.year <= year_max)

    wk_q = (
        select(models.WorkKeyword.work_id, models.WorkKeyword.keyword_id)
        .join(models.Work, models.WorkKeyword.work_id == models.Work.id)
    )
    if year_min is not None: wk_q = wk_q.where(models.Work.year >= year_min)
    if year_max is not None: wk_q = wk_q.where(models.Work.year <= year_max)

    work_to_authors: dict[int, set[int]] = defaultdict(set)
    for wid, aid in db.execute(wa_q).all():
        work_to_authors[wid].add(aid)

    work_to_kws: dict[int, set[int]] = defaultdict(set)
    for wid, kid in db.execute(wk_q).all():
        work_to_kws[wid].add(kid)

    ak = defaultdict(int)
    author_tot = defaultdict(int)
    kw_tot = defaultdict(int)

    for wid, authors_set in work_to_authors.items():
        kws_set = work_to_kws.get(wid)
        if not kws_set:
            continue
        for a in authors_set:
            for k in kws_set:
                ak[(a, k)] += 1
                author_tot[a] += 1
                kw_tot[k] += 1

    # choose top 30 authors and top 30 keywords
    top_authors = [aid for aid, _ in sorted(author_tot.items(), key=lambda x: x[1], reverse=True)[:30]]
    top_keywords = [kid for kid, _ in sorted(kw_tot.items(), key=lambda x: x[1], reverse=True)[:30]]

    rows = [{"id": a, "label": (db.get(models.Author, a).display_name if db.get(models.Author, a) else f"A{a}")} for a in top_authors]
    cols = [{"id": k, "label": (db.get(models.Keyword, k).term_display if db.get(models.Keyword, k) else f"K{k}")} for k in top_keywords]

    data = []
    for a in top_authors:
        row_vals = []
        for k in top_keywords:
            row_vals.append(ak.get((a, k), 0))
        data.append(row_vals)

    return {"rows": rows, "cols": cols, "data": data}

def nation_nation_heat(db: Session, year_min: int | None, year_max: int | None) -> Dict[str, Any]:
    # use NationEdge table
    edges = db.execute(select(models.NationEdge)).scalars().all()
    nations = sorted(set([e.n1 for e in edges] + [e.n2 for e in edges]))
    idx = {n: i for i, n in enumerate(nations)}
    m = [[0.0 for _ in nations] for __ in nations]
    for e in edges:
        i, j = idx[e.n1], idx[e.n2]
        m[i][j] += e.weight
        m[j][i] += e.weight
    rows = [{"id": i, "label": n} for n, i in idx.items()]
    cols = [{"id": i, "label": n} for n, i in idx.items()]
    return {"rows": rows, "cols": cols, "data": m}