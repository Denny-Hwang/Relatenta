import io
import os
import zipfile
import tempfile

import streamlit as st
import pandas as pd
from sqlalchemy import select, func
from datetime import datetime

from app.db import get_db, init_db, reset_db, get_stats
from app import connectors_openalex as oa
from app import crud
from app import models
from app.services_graph import build_graph
from app.services_heatmap import author_keyword_heat, nation_nation_heat
from app.services_export import export_to_csv
from app.services_report import gather_report

st.set_page_config(page_title="Relatenta", layout="wide", page_icon="🔬")

# Ensure DB exists on every run
init_db()

# ============= Session State =============
if "search_hits" not in st.session_state:
    st.session_state.search_hits = []

# ============= Visualization =============


def draw_pyvis_graph(graph_json: dict, viz_settings: dict | None = None, height: str = "700px"):
    """PyVis interactive network graph."""
    try:
        from pyvis.network import Network

        if viz_settings is None:
            viz_settings = {}

        node_size_min, node_size_max = viz_settings.get("node_size_range", (15, 40))
        font_size_min, font_size_max = viz_settings.get("font_size_range", (10, 16))
        edge_width_min, edge_width_max = viz_settings.get("edge_width_range", (0.5, 4.0))
        physics_iterations = viz_settings.get("physics_iterations", 200)
        auto_stop_physics = viz_settings.get("auto_stop_physics", True)

        node_connections: dict[str, int] = {}
        for edge in graph_json["edges"]:
            node_connections[edge["source"]] = node_connections.get(edge["source"], 0) + 1
            node_connections[edge["target"]] = node_connections.get(edge["target"], 0) + 1
        max_connections = max(node_connections.values()) if node_connections else 1

        net = Network(height=height, width="100%", bgcolor="#222222", font_color="white", notebook=False, directed=False)
        auto_stop_time = 5000 if auto_stop_physics else 0

        net.set_options(f"""
        {{
            "nodes": {{
                "font": {{"size": {font_size_min}, "color": "white", "strokeWidth": 3, "strokeColor": "black"}},
                "borderWidth": 2, "borderWidthSelected": 3,
                "shadow": {{"enabled": true, "size": 10, "x": 3, "y": 3}}
            }},
            "edges": {{
                "color": {{"color": "rgba(255,255,255,0.3)", "highlight": "rgba(255,255,255,0.8)"}},
                "smooth": {{"type": "continuous"}}, "width": {edge_width_min}, "selectionWidth": 3
            }},
            "physics": {{
                "enabled": true,
                "stabilization": {{"enabled": true, "iterations": {physics_iterations}, "updateInterval": 10}},
                "barnesHut": {{"gravitationalConstant": -15000, "centralGravity": 0.3, "springLength": 150,
                              "springConstant": 0.04, "damping": 0.95, "avoidOverlap": 0.5}},
                "minVelocity": 0.75, "maxVelocity": 30
            }},
            "interaction": {{
                "hover": true, "hoverConnectedEdges": true, "navigationButtons": true,
                "keyboard": {{"enabled": true, "bindToWindow": false}}, "zoomView": true, "dragView": true, "tooltipDelay": 100
            }},
            "layout": {{"improvedLayout": true, "randomSeed": 42}}
        }}
        """)

        color_scheme = {
            "author": {"background": "#4A90E2", "border": "#2E5C8A"},
            "focus_author": {"background": "#FF6B6B", "border": "#CC5555"},
            "keyword": {"background": "#F5A623", "border": "#C17F00"},
            "focus_keyword": {"background": "#FF6B6B", "border": "#CC5555"},
            "org": {"background": "#7ED321", "border": "#5A9E00"},
            "focus_org": {"background": "#FF6B6B", "border": "#CC5555"},
            "nation": {"background": "#BD10E0", "border": "#8B0AA8"},
            "focus_nation": {"background": "#FF6B6B", "border": "#CC5555"},
        }

        for n in graph_json["nodes"]:
            node_id = n["id"]
            label = n.get("label", node_id)
            node_type = n.get("type", "default")
            connections = node_connections.get(node_id, 0)
            ratio = connections / max_connections if max_connections else 0
            node_size = node_size_min + ratio * (node_size_max - node_size_min)
            font_size = font_size_min + ratio * (font_size_max - font_size_min)
            colors = color_scheme.get(node_type, {"background": "#9013FE", "border": "#6609AC"})
            if node_type.startswith("focus_"):
                node_size = max(node_size, node_size_min + 10)
                font_size = max(font_size, font_size_min + 4)
            display_label = label[:30] + "..." if len(label) > 30 else label
            hover_text = f"{label}\n━━━━━━━━━━━━━━━\nType: {node_type.capitalize()}\nConnections: {connections}\nID: {node_id}"
            net.add_node(
                node_id, label=display_label, title=hover_text,
                color={"background": colors["background"], "border": colors["border"],
                       "highlight": {"background": colors["border"], "border": "#FFD700"}},
                size=node_size, shape="dot",
                font={"size": int(font_size), "color": "white"},
            )

        edge_weights = [float(e.get("weight", 1.0)) for e in graph_json["edges"]]
        max_weight = max(edge_weights) if edge_weights else 1
        for e in graph_json["edges"]:
            weight = float(e.get("weight", 1.0))
            weight_ratio = weight / max_weight if max_weight else 0
            edge_width = edge_width_min + weight_ratio * (edge_width_max - edge_width_min)
            net.add_edge(
                e["source"], e["target"], value=edge_width,
                title=f"Connection Strength: {weight:.2f}",
                color={"color": f"rgba(255,255,255,{0.2 + weight_ratio * 0.4})", "highlight": "rgba(255,215,0,0.9)"},
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            net.save_graph(f.name)
            temp_file = f.name
        with open(temp_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        auto_stop_script = f"setTimeout(function(){{ if(window.network){{ window.network.stopSimulation(); }} }}, {auto_stop_time});" if auto_stop_physics else ""

        enhanced_html = html_content.replace(
            "</head>",
            """<style>
            .vis-tooltip { position:absolute; visibility:hidden; padding:10px; white-space:pre-line;
                font-family:'Segoe UI',sans-serif; font-size:14px; color:#000; background:rgba(255,255,255,0.95);
                border-radius:8px; border:2px solid #333; box-shadow:0 4px 6px rgba(0,0,0,0.3);
                pointer-events:none; z-index:1000; max-width:300px; line-height:1.5; }
            .control-panel { position:absolute; top:10px; right:10px; background:rgba(0,0,0,0.8);
                padding:12px; border-radius:8px; color:white; font-size:13px; font-family:'Segoe UI',sans-serif;
                backdrop-filter:blur(10px); border:1px solid rgba(255,255,255,0.2); }
            .control-panel div { margin:4px 0; display:flex; align-items:center; }
            .control-panel .icon { margin-right:8px; }
            </style></head>""",
        ).replace(
            "</body>",
            f"""<div class="control-panel">
                <div><span class="icon">🖱️</span> Drag to pan view</div>
                <div><span class="icon">📌</span> Click node to select</div>
                <div><span class="icon">🔍</span> Scroll to zoom</div>
                <div><span class="icon">⌨️</span> Space to toggle physics</div>
            </div>
            <script>
                {auto_stop_script}
                document.addEventListener('keydown', function(e){{
                    if(e.code==='Space' && window.network){{ e.preventDefault();
                        if(window.network.physics.options.enabled){{ window.network.setOptions({{physics:{{enabled:false}}}});
                        }} else {{ window.network.setOptions({{physics:{{enabled:true}}}}); }} }} }});
            </script></body>""",
        )

        os.unlink(temp_file)
        st.info("**Graph Controls:** Hover for details | Click & drag to move | Scroll to zoom | SPACE to toggle physics")
        st.components.v1.html(enhanced_html, height=750, scrolling=True)

    except Exception as e:
        st.error(f"Error creating graph visualization: {e}")
        import traceback
        st.code(traceback.format_exc())
        _draw_fallback(graph_json)


def _draw_fallback(graph_json: dict):
    """Fallback table view when PyVis fails."""
    st.warning("Using fallback data view")
    tab1, tab2, tab3 = st.tabs(["Summary", "Nodes", "Edges"])
    with tab1:
        c1, c2 = st.columns(2)
        c1.metric("Total Nodes", len(graph_json["nodes"]))
        c2.metric("Total Edges", len(graph_json["edges"]))
    with tab2:
        if graph_json["nodes"]:
            st.dataframe(pd.DataFrame(graph_json["nodes"]), use_container_width=True, height=400)
    with tab3:
        if graph_json["edges"]:
            st.dataframe(pd.DataFrame(graph_json["edges"]), use_container_width=True, height=400)


# ============= Sidebar =============


def sidebar_data():
    """Sidebar: search, ingest, export, restore."""
    stats = get_stats()

    # --- Current data summary ---
    st.sidebar.header("Database")
    if stats["works"] > 0:
        st.sidebar.info(
            f"Papers: {stats['works']} | Authors: {stats['authors']}\n"
            f"Orgs: {stats['organizations']} | Keywords: {stats['keywords']}"
        )

        col1, col2 = st.sidebar.columns(2)
        with col1:
            try:
                zip_bytes = export_to_csv()
                st.download_button(
                    "Export CSV", data=zip_bytes,
                    file_name=f"relatenta_export_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip", key="export_btn",
                )
            except Exception as e:
                st.error(f"Export error: {e}")
        with col2:
            if st.button("Clear All", key="clear_btn"):
                st.session_state.confirm_clear = True
                st.rerun()

        if st.session_state.get("confirm_clear"):
            st.sidebar.warning("This will delete all data.")
            c1, c2 = st.sidebar.columns(2)
            with c1:
                if st.button("Confirm", key="confirm_clear_btn", type="primary"):
                    reset_db()
                    st.session_state.confirm_clear = False
                    st.session_state.search_hits = []
                    st.rerun()
            with c2:
                if st.button("Cancel", key="cancel_clear_btn"):
                    st.session_state.confirm_clear = False
                    st.rerun()
    else:
        st.sidebar.info("No data yet. Search and ingest authors below.")

    st.sidebar.divider()

    # --- OpenAlex search ---
    st.sidebar.header("Search")
    query = st.sidebar.text_input(
        "Name, ORCID, or Google Scholar URL",
        key="author_search",
        placeholder="e.g., Geoffrey Hinton / 0000-0001-... / scholar.google.com/...",
    )
    if st.sidebar.button("Search", key="search_btn") and query.strip():
        try:
            qtype = oa.detect_query_type(query.strip())
            if qtype == "orcid":
                st.session_state.search_hits = oa.search_author_by_orcid(query.strip())
                if not st.session_state.search_hits:
                    st.sidebar.warning("No author found for this ORCID.")
            elif qtype == "google_scholar":
                with st.spinner("Resolving Google Scholar profile..."):
                    st.session_state.search_hits = oa.search_author_by_google_scholar(query.strip())
                if not st.session_state.search_hits:
                    st.sidebar.warning("Could not resolve Google Scholar profile. Try searching by name instead.")
            else:
                st.session_state.search_hits = oa.search_authors_by_name(query.strip())
        except Exception as e:
            st.sidebar.error(f"Search failed: {e}")

    if st.session_state.search_hits:
        st.sidebar.write("### Search Results")
        for idx, hit in enumerate(st.session_state.search_hits):
            with st.sidebar.expander(f"{hit.get('display_name', 'Unknown')}", expanded=idx < 3):
                c1, c2 = st.columns(2)
                c1.metric("Papers", hit.get("works_count", 0))
                c2.metric("Citations", hit.get("cited_by_count", 0))
                inst = hit.get("last_known_institution", "N/A")
                country = hit.get("institution_country", "")
                st.write(f"**Institution:** {inst}" + (f" ({country})" if country else ""))
                if hit.get("orcid"):
                    st.write(f"**ORCID:** {hit['orcid']}")
                if hit.get("h_index") is not None:
                    st.write(f"**H-index:** {hit['h_index']}")
                if hit.get("top_concepts"):
                    st.write("**Research Topics:**")
                    for c in hit["top_concepts"]:
                        st.write(f"- {c['name']} ({c['score']:.0%})")
                sid = hit["id"].split("/")[-1] if hit["id"].startswith("http") else hit["id"]
                st.write(f"**ID:** `{sid}`")

        st.sidebar.write("---")
        st.sidebar.write("### Select Authors to Ingest")
        author_options = []
        for hit in st.session_state.search_hits:
            aff = hit.get("last_known_institution", "N/A") or "N/A"
            papers = hit.get("works_count", 0)
            top_topic = ""
            if hit.get("top_concepts"):
                top_topic = hit["top_concepts"][0]["name"]
            label = f"{hit['display_name']} | {aff} | {papers} papers"
            if top_topic:
                label += f" | {top_topic}"
            sid = hit["id"].split("/")[-1] if hit["id"].startswith("http") else hit["id"]
            author_options.append((label, sid))

        selected_labels = st.sidebar.multiselect(
            "Choose authors:", [l for l, _ in author_options], key="author_multiselect",
        )
        sel = [sid for l, sid in author_options if l in selected_labels]

        if sel:
            max_works = st.sidebar.slider("Max works per author", 50, 600, 200, 50)
            if st.sidebar.button("Ingest Selected", type="primary", key="ingest_btn"):
                with st.spinner("Ingesting data from OpenAlex..."):
                    total = 0
                    with get_db() as db:
                        for author_id in sel:
                            works = oa.list_author_works(author_id, per_page=200, max_pages=max(1, max_works // 200))
                            for w in works:
                                crud.upsert_work_from_openalex(db, w)
                                total += 1
                        crud.recompute_coauthor_edges(db)
                        crud.recompute_nation_edges(db)
                        try:
                            crud.recompute_org_edges(db)
                        except Exception:
                            pass
                    st.sidebar.success(f"Ingested {total} works")
                    st.session_state.search_hits = []
                    st.rerun()

    st.sidebar.divider()

    # --- CSV Import ---
    st.sidebar.header("CSV Import")
    kind = st.sidebar.selectbox("Data Type", ["works", "authors", "affiliations", "keywords"])
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"], key="csv_upload")
    if uploaded and st.sidebar.button("Import CSV"):
        text = uploaded.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(text))
        with get_db() as db:
            _import_csv(db, kind, df)
            crud.recompute_coauthor_edges(db)
            crud.recompute_nation_edges(db)
            try:
                crud.recompute_org_edges(db)
            except Exception:
                pass
        st.sidebar.success(f"Imported {len(df)} rows")
        st.rerun()

    # --- ZIP Restore ---
    st.sidebar.header("Restore from Export")
    st.sidebar.caption("Upload a previously exported ZIP to restore data")
    zip_file = st.sidebar.file_uploader("Upload ZIP", type=["zip"], key="zip_restore")
    if zip_file and st.sidebar.button("Restore Data", key="restore_btn"):
        _restore_from_zip(zip_file)
        st.rerun()


def _import_csv(db, kind: str, df: pd.DataFrame):
    """Import CSV data into the database."""
    if kind == "works":
        for _, r in df.iterrows():
            w = {
                "id": r.get("source_uid") or r.get("doi") or "",
                "doi": r.get("doi"),
                "title": r.get("title"),
                "publication_year": int(r["year"]) if not pd.isna(r.get("year")) else None,
                "host_venue": {"display_name": r.get("venue")},
                "type": r.get("type"),
                "language": r.get("language"),
                "authorships": [],
                "concepts": [
                    {"display_name": t.strip(), "score": 1.0}
                    for t in str(r.get("keywords") or "").split(";") if t.strip()
                ],
            }
            crud.upsert_work_from_openalex(db, w)
    elif kind == "authors":
        for _, r in df.iterrows():
            work = None
            if not pd.isna(r.get("work_doi")):
                work = db.execute(select(models.Work).where(models.Work.doi == str(r["work_doi"]).lower())).scalar_one_or_none()
            if not work and not pd.isna(r.get("work_title")):
                work = db.execute(select(models.Work).where(models.Work.title == str(r["work_title"]))).scalar_one_or_none()
            if not work:
                continue
            a = crud.get_or_create_author(db, r.get("author_name", "Unknown"))
            db.add(models.WorkAuthor(work_id=work.id, author_id=a.id, position=int(r.get("position") or 0)))
    elif kind == "affiliations":
        for _, r in df.iterrows():
            work = None
            if not pd.isna(r.get("work_doi")):
                work = db.execute(select(models.Work).where(models.Work.doi == str(r["work_doi"]).lower())).scalar_one_or_none()
            if not work and not pd.isna(r.get("work_title")):
                work = db.execute(select(models.Work).where(models.Work.title == str(r["work_title"]))).scalar_one_or_none()
            if not work:
                continue
            a = crud.get_or_create_author(db, r.get("author_name", "Unknown"))
            org = crud.get_or_create_org(db, r.get("org_name", "Unknown"), country=str(r.get("country_code") or "").upper() or None)
            db.add(models.WorkAffiliation(work_id=work.id, author_id=a.id, org_id=org.id, org_label_raw=org.name, country_code=org.country_code))
    elif kind == "keywords":
        for _, r in df.iterrows():
            work = None
            if not pd.isna(r.get("work_doi")):
                work = db.execute(select(models.Work).where(models.Work.doi == str(r["work_doi"]).lower())).scalar_one_or_none()
            if not work and not pd.isna(r.get("work_title")):
                work = db.execute(select(models.Work).where(models.Work.title == str(r["work_title"]))).scalar_one_or_none()
            if not work:
                continue
            kw = crud.get_or_create_keyword(db, r.get("term", "").strip())
            db.add(models.WorkKeyword(work_id=work.id, keyword_id=kw.id, weight=1.0, extractor="manual"))


def _restore_from_zip(zip_file):
    """Restore data from a previously exported ZIP file."""
    try:
        reset_db()
        zip_bytes = zip_file.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            with get_db() as db:
                # Import works first
                works_file = next((n for n in names if n.endswith("works.csv") and "work_" not in n), None)
                if works_file:
                    df = pd.read_csv(io.StringIO(zf.read(works_file).decode("utf-8")))
                    for _, r in df.iterrows():
                        w = {
                            "id": r.get("source_uid") or r.get("doi") or "",
                            "doi": r.get("doi") if not pd.isna(r.get("doi")) else None,
                            "title": r.get("title"),
                            "publication_year": int(r["year"]) if not pd.isna(r.get("year")) else None,
                            "host_venue": {"display_name": r.get("venue") if not pd.isna(r.get("venue")) else None},
                            "type": r.get("type") if not pd.isna(r.get("type")) else None,
                            "language": r.get("language") if not pd.isna(r.get("language")) else None,
                            "authorships": [],
                            "concepts": [],
                        }
                        crud.upsert_work_from_openalex(db, w)

                # Import work-author relationships
                wa_file = next((n for n in names if "work_authors" in n), None)
                if wa_file:
                    df = pd.read_csv(io.StringIO(zf.read(wa_file).decode("utf-8")))
                    _import_csv(db, "authors", df)

                # Import affiliations
                aff_file = next((n for n in names if "affiliations" in n), None)
                if aff_file:
                    df = pd.read_csv(io.StringIO(zf.read(aff_file).decode("utf-8")))
                    _import_csv(db, "affiliations", df)

                # Import work-keywords
                wk_file = next((n for n in names if "work_keywords" in n), None)
                if wk_file:
                    df = pd.read_csv(io.StringIO(zf.read(wk_file).decode("utf-8")))
                    if "keyword" in df.columns:
                        df = df.rename(columns={"keyword": "term"})
                    _import_csv(db, "keywords", df)

                # Recompute edges
                crud.recompute_coauthor_edges(db)
                crud.recompute_nation_edges(db)
                try:
                    crud.recompute_org_edges(db)
                except Exception:
                    pass

        st.sidebar.success("Data restored successfully")
    except Exception as e:
        st.sidebar.error(f"Restore failed: {e}")


# ============= Tabs =============


def how_to_use_tab():
    st.header("How to Use")
    st.markdown("""
    Welcome to **Relatenta** — a research relationship visualization service.
    """)

    with st.expander("Quick Start", expanded=True):
        st.markdown("""
        ### Getting Started

        1. **Search for a researcher** in the left sidebar (e.g., "Geoffrey Hinton")
        2. **Review the search results** — check institution, H-index, and topics to pick the right person
        3. **Select one or more authors** and click "Ingest Selected"
        4. **Go to the Graph tab** — pick a layer and click "Build Graph"

        > **Note:** Data is stored in memory only.
        > Use "Export CSV" to save your work before closing the browser.
        """)

    with st.expander("Graph Layers", expanded=False):
        st.markdown("""
        | Layer | Nodes | Edges | Use Case |
        |-------|-------|-------|----------|
        | **Authors** | Researchers | Co-authored papers | Collaboration network |
        | **Keywords** | Topics | Papers with both topics | Research landscape |
        | **Organizations** | Institutions | Joint publications | Partnership analysis |
        | **Nations** | Countries | International co-authorships | Global patterns |
        """)

    with st.expander("Graph Controls", expanded=False):
        st.markdown("""
        - Drag to pan the view
        - Click nodes to select and highlight connections
        - Scroll to zoom in/out
        - Press SPACE to toggle physics simulation
        - Use **Focus Mode** to highlight or isolate specific nodes
        """)

    with st.expander("Data Persistence", expanded=False):
        st.markdown("""
        This app uses an in-memory database. Data is lost when the session ends.

        **To save:** Click "Export CSV" in the sidebar to download a ZIP file.
        **To restore:** Use "Restore from Export" to upload a previously saved ZIP.
        """)


def graph_tab():
    stats = get_stats()
    if stats["works"] == 0:
        st.info("No data yet. Search and ingest authors from the sidebar to get started.")
        return

    st.header("Network Graph")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        layer = st.selectbox("Layer", ["authors", "keywords", "orgs", "nations"], key="graph_layer")
    with c2:
        year_min = st.number_input("Year min", value=2000, step=1, key="graph_year_min")
    with c3:
        year_max = st.number_input("Year max", value=2025, step=1, key="graph_year_max")
    with c4:
        edge_min = st.slider("Edge weight min", 0.0, 10.0, 1.0, 0.5, key="graph_edge_min")

    # Focus ID search helpers
    _render_focus_helper(layer)

    focus_placeholder = {
        "authors": "e.g., 1,5,23", "keywords": "e.g., 12,45,78",
        "orgs": "e.g., 3,15,42", "nations": "e.g., US,GB,DE",
    }
    focus = st.text_input(
        f"Focus {layer} IDs (comma-separated, optional)",
        key="graph_focus", placeholder=focus_placeholder[layer],
    )

    focus_ids = _parse_focus_ids(layer, focus)

    focus_only = False
    if focus_ids:
        mode = st.radio(
            "Focus mode:", ["Full Network (highlight)", "Focus Only (isolate)"],
            index=0, key="focus_mode", horizontal=True,
        )
        focus_only = mode.startswith("Focus Only")

    # Viz settings
    with st.expander("Visualization Controls", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            node_size_range = st.slider("Node Size Range", 5, 100, (15, 40), key="node_size_range")
            font_size_range = st.slider("Font Size Range", 8, 24, (10, 16), key="font_size_range")
        with c2:
            physics_iterations = st.slider("Physics Iterations", 50, 500, 200, key="physics_iters")
            auto_stop = st.checkbox("Auto-stop Physics", value=True, key="auto_stop")
        with c3:
            edge_width_range = st.slider("Edge Width Range", 0.1, 10.0, (0.5, 4.0), key="edge_width_range")

    if st.button("Build Graph", type="primary", key="build_graph_btn"):
        with st.spinner("Building graph..."):
            try:
                with get_db() as db:
                    g = build_graph(db, layer, year_min, year_max, edge_min, focus_ids, focus_only)
                if not g["nodes"]:
                    st.warning("No nodes found. Try lowering edge weight or widening the year range.")
                    return
                st.success(f"Graph: {len(g['nodes'])} nodes, {len(g['edges'])} edges")
                draw_pyvis_graph(g, viz_settings={
                    "node_size_range": node_size_range,
                    "font_size_range": font_size_range,
                    "physics_iterations": physics_iterations,
                    "auto_stop_physics": auto_stop,
                    "edge_width_range": edge_width_range,
                })
            except Exception as e:
                st.error(f"Error building graph: {e}")


def heatmap_tab():
    stats = get_stats()
    if stats["works"] == 0:
        st.info("No data yet. Search and ingest authors from the sidebar to get started.")
        return

    st.header("Heatmaps")

    c1, c2, c3 = st.columns(3)
    with c1:
        kind = st.selectbox("Kind", ["author_keyword", "nation_nation"], key="heatmap_kind")
    with c2:
        year_min = st.number_input("Year min", value=2000, step=1, key="hm_year_min")
    with c3:
        year_max = st.number_input("Year max", value=2025, step=1, key="hm_year_max")

    if st.button("Compute Heatmap", type="primary", key="compute_hm_btn"):
        with st.spinner("Computing heatmap..."):
            with get_db() as db:
                if kind == "author_keyword":
                    hm = author_keyword_heat(db, year_min, year_max)
                elif kind == "nation_nation":
                    hm = nation_nation_heat(db, year_min, year_max)
                else:
                    hm = {"rows": [], "cols": [], "data": []}

            if not hm.get("data"):
                st.warning("No data available for the selected parameters")
                return

            import plotly.express as px
            x = [c["label"] for c in hm["cols"]]
            y = [r["label"] for r in hm["rows"]]
            row_count = len(y)
            fig_height = max(500, row_count * 28 + 200)
            fig = px.imshow(
                hm["data"], labels=dict(x="Columns", y="Rows", color="Weight"),
                x=x, y=y, aspect="auto", color_continuous_scale="Viridis",
            )
            fig.update_layout(height=fig_height, margin=dict(l=10, r=10, t=30, b=80))
            st.plotly_chart(fig, use_container_width=True)


def report_tab():
    stats = get_stats()
    if stats["works"] == 0:
        st.info("No data yet. Search and ingest authors from the sidebar to get started.")
        return

    st.header("Analytic Report")

    report_name = st.text_input(
        "Report name (used in PDF filename)",
        value=st.session_state.get("report_name", ""),
        placeholder="e.g., Geoffrey Hinton",
        key="report_name_input",
    )
    if report_name:
        st.session_state.report_name = report_name

    if st.button("Generate Report", type="primary", key="gen_report_btn"):
        with st.spinner("Analyzing data..."):
            with get_db() as db:
                rpt = gather_report(db)
            st.session_state.report_data = rpt

    if "report_data" not in st.session_state:
        st.caption("Click **Generate Report** to analyze your data.")
        return

    rpt = st.session_state.report_data
    year_label = ""
    if rpt["year_min"] and rpt["year_max"]:
        year_label = f"{rpt['year_min']} – {rpt['year_max']}"

    # ---- Summary Metrics ----
    st.subheader("Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Papers", f"{rpt['n_works']:,}")
    m2.metric("Authors", f"{rpt['n_authors']:,}")
    m3.metric("Organizations", f"{rpt['n_orgs']:,}")
    m4.metric("Keywords", f"{rpt['n_keywords']:,}")
    m5.metric("Venues", f"{rpt['n_venues']:,}")
    if year_label:
        st.caption(f"Publication years: {year_label}")

    st.divider()

    # ---- Publication Trend ----
    if rpt["pub_trend"]:
        st.subheader("Publication Trend")
        import plotly.express as px
        df_trend = pd.DataFrame(rpt["pub_trend"])
        fig_trend = px.bar(
            df_trend, x="year", y="count",
            labels={"year": "Year", "count": "Papers"},
            color_discrete_sequence=["#4A90E2"],
        )
        fig_trend.update_layout(height=350, margin=dict(l=40, r=20, t=30, b=40))
        st.plotly_chart(fig_trend, use_container_width=True)

    # ---- Two-column layout: Authors & Keywords ----
    col_left, col_right = st.columns(2)

    with col_left:
        if rpt["top_authors"]:
            st.subheader("Top Authors")
            df_auth = pd.DataFrame(rpt["top_authors"])
            fig_auth = px.bar(
                df_auth.iloc[:15], x="papers", y="name", orientation="h",
                labels={"papers": "Papers", "name": ""},
                color_discrete_sequence=["#4A90E2"],
            )
            fig_auth.update_layout(
                height=max(350, len(df_auth.iloc[:15]) * 28 + 80),
                margin=dict(l=10, r=20, t=10, b=30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_auth, use_container_width=True)

    with col_right:
        if rpt["top_keywords"]:
            st.subheader("Top Research Topics")
            df_kw = pd.DataFrame(rpt["top_keywords"])
            fig_kw = px.bar(
                df_kw.iloc[:15], x="count", y="term", orientation="h",
                labels={"count": "Occurrences", "term": ""},
                color_discrete_sequence=["#F5A623"],
            )
            fig_kw.update_layout(
                height=max(350, len(df_kw.iloc[:15]) * 28 + 80),
                margin=dict(l=10, r=20, t=10, b=30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_kw, use_container_width=True)

    st.divider()

    # ---- Country & Venue distribution ----
    col_left2, col_right2 = st.columns(2)

    with col_left2:
        if rpt["country_dist"]:
            st.subheader("Country Distribution")
            df_cc = pd.DataFrame(rpt["country_dist"])
            fig_cc = px.bar(
                df_cc, x="country", y="papers",
                labels={"country": "Country", "papers": "Papers"},
                color_discrete_sequence=["#7ED321"],
            )
            fig_cc.update_layout(height=350, margin=dict(l=40, r=20, t=10, b=40))
            st.plotly_chart(fig_cc, use_container_width=True)

    with col_right2:
        if rpt["top_venues"]:
            st.subheader("Top Venues")
            df_v = pd.DataFrame(rpt["top_venues"])
            fig_v = px.bar(
                df_v, x="papers", y="venue", orientation="h",
                labels={"papers": "Papers", "venue": ""},
                color_discrete_sequence=["#BD10E0"],
            )
            fig_v.update_layout(
                height=max(350, len(df_v) * 28 + 80),
                margin=dict(l=10, r=20, t=10, b=30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_v, use_container_width=True)

    st.divider()

    # ---- Collaboration & Topic Relationships ----
    col_left3, col_right3 = st.columns(2)

    with col_left3:
        if rpt["top_collabs"]:
            st.subheader("Strongest Collaborations")
            df_col = pd.DataFrame(rpt["top_collabs"])
            df_col["pair"] = df_col["author_a"] + "  &  " + df_col["author_b"]
            fig_collab = px.bar(
                df_col.iloc[:10], x="papers", y="pair", orientation="h",
                labels={"papers": "Co-authored Papers", "pair": ""},
                color_discrete_sequence=["#4A90E2"],
            )
            fig_collab.update_layout(
                height=max(300, len(df_col.iloc[:10]) * 35 + 80),
                margin=dict(l=10, r=20, t=10, b=30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_collab, use_container_width=True)

    with col_right3:
        if rpt["top_kw_pairs"]:
            st.subheader("Topic Co-occurrence")
            df_kwp = pd.DataFrame(rpt["top_kw_pairs"])
            df_kwp["pair"] = df_kwp["keyword_a"] + "  &  " + df_kwp["keyword_b"]
            fig_kwp = px.bar(
                df_kwp.iloc[:10], x="co_occurrences", y="pair", orientation="h",
                labels={"co_occurrences": "Co-occurrences", "pair": ""},
                color_discrete_sequence=["#F5A623"],
            )
            fig_kwp.update_layout(
                height=max(300, len(df_kwp.iloc[:10]) * 35 + 80),
                margin=dict(l=10, r=20, t=10, b=30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_kwp, use_container_width=True)

    st.divider()

    # ---- Highlight Works ----
    if rpt.get("highlight_works"):
        st.subheader("Highlight Papers")
        st.caption("Top cited papers in your dataset")
        for i, w in enumerate(rpt["highlight_works"][:10]):
            citation_badge = f"**{w['cited_by_count']:,} citations**" if w["cited_by_count"] else "Citations: N/A"
            title_display = w["title"]
            if w.get("link"):
                title_display = f"[{w['title']}]({w['link']})"
            year_str = f"({w['year']})" if w["year"] else ""
            venue_str = f"*{w['venue']}*" if w["venue"] else ""

            with st.container():
                st.markdown(
                    f"**{i+1}.** {title_display} {year_str}\n\n"
                    f"   {w['authors']}\n\n"
                    f"   {venue_str}  —  {citation_badge}"
                )
                if i < len(rpt["highlight_works"][:10]) - 1:
                    st.markdown("---")

    st.divider()

    # ---- Collaboration Network Graph ----
    if rpt.get("graph_nodes") and rpt.get("graph_edges"):
        st.subheader("Collaboration Network")
        st.caption("Top co-author connections (strongest collaborations)")
        graph_fig = _render_network_graph(rpt)
        if graph_fig is not None:
            st.pyplot(graph_fig)

    st.divider()

    # ---- PDF Download ----
    st.subheader("Download Report")
    if st.button("Generate PDF", key="gen_pdf_btn"):
        with st.spinner("Creating PDF..."):
            pdf_bytes = _generate_report_pdf(rpt)
            st.session_state.report_pdf = pdf_bytes
    if "report_pdf" in st.session_state:
        name_part = st.session_state.get("report_name", "").strip()
        if name_part:
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name_part).strip().replace(" ", "_")
            pdf_filename = f"Relatenta_report_{safe_name}.pdf"
        else:
            pdf_filename = f"Relatenta_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        st.download_button(
            "Download PDF",
            data=st.session_state.report_pdf,
            file_name=pdf_filename,
            mime="application/pdf",
            key="dl_pdf_btn",
        )


def _render_network_graph(rpt: dict):
    """Render a co-author network graph using networkx + matplotlib."""
    try:
        import networkx as nx
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        G = nx.Graph()
        id_to_label = {n["id"]: n["label"] for n in rpt["graph_nodes"]}
        for n in rpt["graph_nodes"]:
            G.add_node(n["id"], label=n["label"])
        for e in rpt["graph_edges"]:
            G.add_edge(e["a"], e["b"], weight=e["weight"])

        if len(G.nodes) == 0:
            return None

        # spring layout with weight-based attraction
        pos = nx.spring_layout(G, k=2.5, iterations=80, seed=42, weight="weight")

        # node sizing by degree
        degrees = dict(G.degree())
        max_deg = max(degrees.values()) if degrees else 1
        node_sizes = [300 + 1200 * (degrees[n] / max_deg) for n in G.nodes]

        # edge widths by weight
        weights = [G[u][v]["weight"] for u, v in G.edges]
        max_w = max(weights) if weights else 1
        edge_widths = [0.5 + 3.5 * (w / max_w) for w in weights]
        edge_alphas = [0.3 + 0.5 * (w / max_w) for w in weights]

        fig, ax = plt.subplots(figsize=(11, 8.5))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#1a1a2e")

        # draw edges with varying alpha
        for (u, v), width, alpha in zip(G.edges, edge_widths, edge_alphas):
            x = [pos[u][0], pos[v][0]]
            y = [pos[u][1], pos[v][1]]
            ax.plot(x, y, color="white", linewidth=width, alpha=alpha, zorder=1)

        # draw nodes
        node_colors = ["#4A90E2"] * len(G.nodes)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes,
                               node_color=node_colors, edgecolors="#2E5C8A",
                               linewidths=1.5, alpha=0.9)

        # labels — truncate long names
        labels = {}
        for n in G.nodes:
            name = id_to_label.get(n, str(n))
            labels[n] = name[:20] + "..." if len(name) > 20 else name
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=8,
                                font_color="white", font_weight="bold")

        ax.set_title("Co-author Network (Top Collaborations)", fontsize=14,
                     fontweight="bold", color="white", pad=15)
        ax.axis("off")
        fig.tight_layout()
        return fig
    except Exception:
        return None


def _generate_report_pdf(rpt: dict) -> bytes:
    """Generate a multi-page PDF report using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # --- Page 1: Title + Summary ---
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        fig.patch.set_facecolor("#FAFAFA")

        ax.text(0.5, 0.88, "Relatenta", fontsize=32, fontweight="bold",
                ha="center", va="top", color="#2C3E50")
        ax.text(0.5, 0.80, "Analytic Report", fontsize=18, ha="center",
                va="top", color="#7F8C8D")

        year_label = ""
        if rpt["year_min"] and rpt["year_max"]:
            year_label = f"Period: {rpt['year_min']} – {rpt['year_max']}"

        summary_text = (
            f"Papers: {rpt['n_works']:,}     Authors: {rpt['n_authors']:,}     "
            f"Organizations: {rpt['n_orgs']:,}\n"
            f"Keywords: {rpt['n_keywords']:,}     Venues: {rpt['n_venues']:,}\n"
            f"{year_label}"
        )
        ax.text(0.5, 0.62, summary_text, fontsize=14, ha="center", va="top",
                color="#34495E", linespacing=1.8,
                bbox=dict(boxstyle="round,pad=0.8", facecolor="#ECF0F1",
                          edgecolor="#BDC3C7", alpha=0.9))

        from datetime import datetime as _dt
        ax.text(0.5, 0.10, f"Generated: {_dt.now().strftime('%Y-%m-%d %H:%M')}",
                fontsize=10, ha="center", color="#95A5A6")
        pdf.savefig(fig)
        plt.close(fig)

        # --- Page 2: Publication Trend ---
        if rpt["pub_trend"]:
            fig, ax = plt.subplots(figsize=(11, 8.5))
            years = [d["year"] for d in rpt["pub_trend"]]
            counts = [d["count"] for d in rpt["pub_trend"]]
            ax.bar(years, counts, color="#4A90E2", edgecolor="white", linewidth=0.5)
            ax.set_title("Publication Trend", fontsize=16, fontweight="bold", pad=15)
            ax.set_xlabel("Year")
            ax.set_ylabel("Papers")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 3: Top Authors ---
        if rpt["top_authors"]:
            data = rpt["top_authors"][:15]
            fig, ax = plt.subplots(figsize=(11, 8.5))
            names = [d["name"][:30] for d in data][::-1]
            papers = [d["papers"] for d in data][::-1]
            ax.barh(names, papers, color="#4A90E2", edgecolor="white", linewidth=0.5)
            ax.set_title("Top Authors by Paper Count", fontsize=16, fontweight="bold", pad=15)
            ax.set_xlabel("Papers")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 4: Top Keywords ---
        if rpt["top_keywords"]:
            data = rpt["top_keywords"][:15]
            fig, ax = plt.subplots(figsize=(11, 8.5))
            terms = [d["term"][:35] for d in data][::-1]
            cnts = [d["count"] for d in data][::-1]
            ax.barh(terms, cnts, color="#F5A623", edgecolor="white", linewidth=0.5)
            ax.set_title("Top Research Topics", fontsize=16, fontweight="bold", pad=15)
            ax.set_xlabel("Occurrences")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 5: Country Distribution ---
        if rpt["country_dist"]:
            data = rpt["country_dist"][:15]
            fig, ax = plt.subplots(figsize=(11, 8.5))
            countries = [d["country"] for d in data]
            papers = [d["papers"] for d in data]
            ax.bar(countries, papers, color="#7ED321", edgecolor="white", linewidth=0.5)
            ax.set_title("Country Distribution", fontsize=16, fontweight="bold", pad=15)
            ax.set_xlabel("Country")
            ax.set_ylabel("Papers")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 6: Collaborations & Topic Co-occurrence ---
        if rpt["top_collabs"] or rpt["top_kw_pairs"]:
            n_rows = (1 if rpt["top_collabs"] else 0) + (1 if rpt["top_kw_pairs"] else 0)
            fig, axes = plt.subplots(n_rows, 1, figsize=(11, 8.5))
            if n_rows == 1:
                axes = [axes]
            ax_idx = 0

            if rpt["top_collabs"]:
                data = rpt["top_collabs"][:10]
                ax = axes[ax_idx]
                pairs = [f"{d['author_a'][:20]}  &  {d['author_b'][:20]}" for d in data][::-1]
                papers = [d["papers"] for d in data][::-1]
                ax.barh(pairs, papers, color="#4A90E2", edgecolor="white", linewidth=0.5)
                ax.set_title("Strongest Collaborations", fontsize=14, fontweight="bold", pad=10)
                ax.set_xlabel("Co-authored Papers")
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax_idx += 1

            if rpt["top_kw_pairs"]:
                data = rpt["top_kw_pairs"][:10]
                ax = axes[ax_idx]
                pairs = [f"{d['keyword_a'][:20]}  &  {d['keyword_b'][:20]}" for d in data][::-1]
                co = [d["co_occurrences"] for d in data][::-1]
                ax.barh(pairs, co, color="#F5A623", edgecolor="white", linewidth=0.5)
                ax.set_title("Topic Co-occurrence", fontsize=14, fontweight="bold", pad=10)
                ax.set_xlabel("Co-occurrences")
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)

            fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 7: Top Venues ---
        if rpt["top_venues"]:
            data = rpt["top_venues"][:12]
            fig, ax = plt.subplots(figsize=(11, 8.5))
            venues = [d["venue"][:45] for d in data][::-1]
            papers = [d["papers"] for d in data][::-1]
            ax.barh(venues, papers, color="#BD10E0", edgecolor="white", linewidth=0.5)
            ax.set_title("Top Venues", fontsize=16, fontweight="bold", pad=15)
            ax.set_xlabel("Papers")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 8: Highlight Papers ---
        if rpt.get("highlight_works"):
            works = rpt["highlight_works"][:10]
            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.axis("off")
            fig.patch.set_facecolor("#FAFAFA")
            ax.set_title("Highlight Papers (Top Cited)", fontsize=18,
                         fontweight="bold", pad=20, color="#2C3E50")

            line_height = 0.88 / max(len(works), 1)
            for i, w in enumerate(works):
                cite_str = f"{w['cited_by_count']:,} citations" if w["cited_by_count"] else "N/A"
                year_str = f"({w['year']})" if w["year"] else ""
                title_line = f"{i+1}. {w['title'][:80]}{'...' if len(w['title']) > 80 else ''} {year_str}"
                detail_line = f"    {w['authors'][:65]}{'...' if len(w['authors']) > 65 else ''}"
                venue_cite = f"    {w['venue'][:45]}  —  {cite_str}"
                link_line = f"    {w['link']}" if w.get("link") else ""

                y = 0.93 - i * line_height
                ax.text(0.02, y, title_line, fontsize=8.5, fontweight="bold",
                        va="top", color="#2C3E50", transform=ax.transAxes)
                ax.text(0.02, y - line_height * 0.22, detail_line, fontsize=7.5,
                        va="top", color="#7F8C8D", transform=ax.transAxes)
                ax.text(0.02, y - line_height * 0.44, venue_cite, fontsize=7.5,
                        va="top", color="#34495E", transform=ax.transAxes,
                        style="italic")
                if link_line:
                    ax.text(0.02, y - line_height * 0.66, link_line, fontsize=6.5,
                            va="top", color="#2980B9", transform=ax.transAxes)

            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

        # --- Page 9: Collaboration Network Graph ---
        if rpt.get("graph_nodes") and rpt.get("graph_edges"):
            graph_fig = _render_network_graph(rpt)
            if graph_fig is not None:
                pdf.savefig(graph_fig)
                plt.close(graph_fig)

    buf.seek(0)
    return buf.read()


# ============= Helpers =============


def _render_focus_helper(layer: str):
    """Render in-database search helpers for finding focus IDs."""
    if layer == "authors":
        with st.expander("Find Author IDs", expanded=False):
            q = st.text_input("Search author name:", key="author_search_graph", placeholder="Enter part of name...")
            if q and len(q) >= 2:
                with get_db() as db:
                    rows = db.execute(
                        select(models.Author.id, models.Author.display_name)
                        .where(func.lower(models.Author.display_name).contains(q.lower()))
                        .order_by(models.Author.display_name).limit(15)
                    ).all()
                if rows:
                    cols = st.columns(3)
                    for i, (aid, name) in enumerate(rows):
                        with cols[i % 3]:
                            st.code(str(aid))
                            st.caption(name)
                else:
                    st.write("No authors found.")
    elif layer == "keywords":
        with st.expander("Find Keyword IDs", expanded=False):
            q = st.text_input("Search keyword:", key="kw_search_graph", placeholder="Enter part of keyword...")
            if q and len(q) >= 2:
                with get_db() as db:
                    rows = db.execute(
                        select(models.Keyword.id, models.Keyword.term_display)
                        .where(func.lower(models.Keyword.term_display).contains(q.lower()))
                        .order_by(models.Keyword.term_display).limit(15)
                    ).all()
                if rows:
                    cols = st.columns(3)
                    for i, (kid, term) in enumerate(rows):
                        with cols[i % 3]:
                            st.code(str(kid))
                            st.caption(term)
                else:
                    st.write("No keywords found.")
    elif layer == "orgs":
        with st.expander("Find Organization IDs", expanded=False):
            q = st.text_input("Search organization:", key="org_search_graph", placeholder="Enter part of name...")
            if q and len(q) >= 2:
                with get_db() as db:
                    rows = db.execute(
                        select(models.Organization.id, models.Organization.name, models.Organization.country_code)
                        .where(func.lower(models.Organization.name).contains(q.lower()))
                        .order_by(models.Organization.name).limit(15)
                    ).all()
                if rows:
                    cols = st.columns(2)
                    for i, (oid, name, cc) in enumerate(rows):
                        with cols[i % 2]:
                            st.code(str(oid))
                            st.caption(f"{name} ({cc or 'N/A'})")
                else:
                    st.write("No organizations found.")
    elif layer == "nations":
        with st.expander("Nation Codes", expanded=False):
            common = [
                ("US", "United States"), ("GB", "United Kingdom"), ("DE", "Germany"),
                ("FR", "France"), ("CN", "China"), ("JP", "Japan"), ("KR", "South Korea"),
                ("CA", "Canada"), ("AU", "Australia"), ("IN", "India"),
            ]
            cols = st.columns(3)
            for i, (code, name) in enumerate(common):
                with cols[i % 3]:
                    st.code(code)
                    st.caption(name)


def _parse_focus_ids(layer: str, focus_str: str):
    """Parse comma-separated focus IDs from text input."""
    if not focus_str:
        return None
    if layer == "nations":
        ids = [s.strip().upper() for s in focus_str.split(",") if len(s.strip()) == 2]
        return ids if ids else None
    else:
        ids = []
        for s in focus_str.split(","):
            s = s.strip()
            if s.isdigit():
                ids.append(int(s))
        return ids if ids else None


# ============= Main =============


def main():
    st.title("Relatenta")
    st.caption("Research Relationship Visualization")

    with st.sidebar:
        sidebar_data()

    tabs = st.tabs(["How to Use", "Graph", "Heatmaps", "Report"])
    with tabs[0]:
        how_to_use_tab()
    with tabs[1]:
        graph_tab()
    with tabs[2]:
        heatmap_tab()
    with tabs[3]:
        report_tab()


if __name__ == "__main__":
    main()
