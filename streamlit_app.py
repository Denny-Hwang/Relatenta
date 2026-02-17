import os
import json
import requests
import streamlit as st
import pandas as pd
from urllib.parse import urljoin
import tempfile
from datetime import datetime
import time

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
BACKEND = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

st.set_page_config(page_title="Reatenta", layout="wide", page_icon="🔬")

# ============= Session State Management =============
if 'current_actor' not in st.session_state:
    st.session_state.current_actor = None
if 'actors_list' not in st.session_state:
    st.session_state.actors_list = []
if 'refresh_actors' not in st.session_state:
    st.session_state.refresh_actors = True
if 'search_hits' not in st.session_state:
    st.session_state.search_hits = []

# ============= API Functions =============
def api_get(path, params=None):
    r = requests.get(urljoin(BACKEND, path), params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def api_post(path, payload):
    r = requests.post(urljoin(BACKEND, path), json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def api_delete(path):
    r = requests.delete(urljoin(BACKEND, path), timeout=60)
    r.raise_for_status()
    return r.json()

def api_download(path):
    r = requests.get(urljoin(BACKEND, path), stream=True, timeout=120)
    r.raise_for_status()
    return r.content

# ============= Actor Management Functions =============
def refresh_actors_list(force=False):
    """Refresh the list of actors from the backend."""
    try:
        if force or st.session_state.refresh_actors:
            response = api_get("/actors")
            st.session_state.actors_list = response.get("actors", [])
            st.session_state.refresh_actors = False
            return True
    except Exception as e:
        st.error(f"Failed to fetch actors: {e}")
        st.session_state.actors_list = []
        return False
    return False

def create_new_actor(actor_name):
    """Create a new actor database."""
    try:
        api_post(f"/actors/{actor_name}/init", {})
        st.success(f"✅ Created new actor database: '{actor_name}'")
        
        time.sleep(0.5)
        response = api_get("/actors")
        st.session_state.actors_list = response.get("actors", [])
        st.session_state.current_actor = actor_name
        st.session_state.refresh_actors = False
        
        if 'new_actor_input' in st.session_state:
            del st.session_state['new_actor_input']
        
        return True
    except Exception as e:
        st.error(f"Failed to create actor: {e}")
        return False

def delete_actor(actor_name):
    """Delete an actor database."""
    try:
        api_delete(f"/actors/{actor_name}")
        st.success(f"🗑️ Deleted actor database: '{actor_name}'")
        
        if st.session_state.current_actor == actor_name:
            st.session_state.current_actor = None
        
        confirm_key = f'confirm_delete_{actor_name}'
        password_key = f'password_input_{actor_name}'
        
        if confirm_key in st.session_state:
            del st.session_state[confirm_key]
        if password_key in st.session_state:
            del st.session_state[password_key]
        
        st.session_state.refresh_actors = True
        time.sleep(0.2)
        refresh_actors_list(force=True)
        
        return True
    except Exception as e:
        st.error(f"Failed to delete actor: {e}")
        return False

def export_actor_data(actor_name):
    """Export actor data as CSV zip file."""
    try:
        data = api_download(f"/actors/{actor_name}/export")
        return data
    except Exception as e:
        st.error(f"Failed to export data: {e}")
        return None

# ============= Visualization Functions =============
def draw_pyvis_graph(graph_json: dict, viz_settings: dict = None, height: str="700px"):
    """Enhanced PyVis network visualization with clean tooltips"""
    try:
        from pyvis.network import Network
        import tempfile
        import os
        import math
        
        if viz_settings is None:
            viz_settings = {}
        
        node_size_min, node_size_max = viz_settings.get("node_size_range", (15, 40))
        font_size_min, font_size_max = viz_settings.get("font_size_range", (10, 16))
        edge_width_min, edge_width_max = viz_settings.get("edge_width_range", (0.5, 4.0))
        physics_iterations = viz_settings.get("physics_iterations", 200)
        auto_stop_physics = viz_settings.get("auto_stop_physics", True)
        
        node_connections = {}
        for edge in graph_json["edges"]:
            node_connections[edge["source"]] = node_connections.get(edge["source"], 0) + 1
            node_connections[edge["target"]] = node_connections.get(edge["target"], 0) + 1
        
        max_connections = max(node_connections.values()) if node_connections else 1
        
        net = Network(
            height=height, 
            width="100%", 
            bgcolor="#222222",
            font_color="white",
            notebook=False,
            directed=False
        )
        
        auto_stop_time = 5000 if auto_stop_physics else 0
        
        net.set_options(f"""
        {{
            "nodes": {{
                "font": {{
                    "size": {font_size_min},
                    "color": "white",
                    "strokeWidth": 3,
                    "strokeColor": "black"
                }},
                "borderWidth": 2,
                "borderWidthSelected": 3,
                "shadow": {{
                    "enabled": true,
                    "size": 10,
                    "x": 3,
                    "y": 3
                }}
            }},
            "edges": {{
                "color": {{
                    "color": "rgba(255,255,255,0.3)",
                    "highlight": "rgba(255,255,255,0.8)"
                }},
                "smooth": {{
                    "type": "continuous"
                }},
                "width": {edge_width_min},
                "selectionWidth": 3
            }},
            "physics": {{
                "enabled": true,
                "stabilization": {{
                    "enabled": true,
                    "iterations": {physics_iterations},
                    "updateInterval": 10
                }},
                "barnesHut": {{
                    "gravitationalConstant": -15000,
                    "centralGravity": 0.3,
                    "springLength": 150,
                    "springConstant": 0.04,
                    "damping": 0.95,
                    "avoidOverlap": 0.5
                }},
                "minVelocity": 0.75,
                "maxVelocity": 30
            }},
            "interaction": {{
                "hover": true,
                "hoverConnectedEdges": true,
                "navigationButtons": true,
                "keyboard": {{
                    "enabled": true,
                    "bindToWindow": false
                }},
                "zoomView": true,
                "dragView": true,
                "tooltipDelay": 100
            }},
            "layout": {{
                "improvedLayout": true,
                "randomSeed": 42
            }}
        }}
        """)
        
        for n in graph_json["nodes"]:
            node_id = n["id"]
            label = n.get("label", node_id)
            node_type = n.get("type", "default")
            
            connections = node_connections.get(node_id, 0)
            connection_ratio = connections / max_connections if max_connections > 0 else 0
            node_size = node_size_min + (connection_ratio * (node_size_max - node_size_min))
            
            font_size = font_size_min + (connection_ratio * (font_size_max - font_size_min))
            
            color_scheme = {
                "author": {"background": "#4A90E2", "border": "#2E5C8A"},
                "focus_author": {"background": "#FF6B6B", "border": "#CC5555"},
                "keyword": {"background": "#F5A623", "border": "#C17F00"},
                "focus_keyword": {"background": "#FF6B6B", "border": "#CC5555"},
                "org": {"background": "#7ED321", "border": "#5A9E00"},
                "focus_org": {"background": "#FF6B6B", "border": "#CC5555"},
                "nation": {"background": "#BD10E0", "border": "#8B0AA8"},
                "focus_nation": {"background": "#FF6B6B", "border": "#CC5555"}
            }
            
            colors = color_scheme.get(node_type, {"background": "#9013FE", "border": "#6609AC"})
            
            if node_type.startswith("focus_"):
                node_size = max(node_size, node_size_min + 10)
                font_size = max(font_size, font_size_min + 4)
            
            display_label = label[:30] + "..." if len(label) > 30 else label
            
            hover_text = f"{label}\n━━━━━━━━━━━━━━━\nType: {node_type.capitalize()}\nConnections: {connections}\nID: {node_id}"
            
            net.add_node(
                node_id, 
                label=display_label,
                title=hover_text,
                color={
                    "background": colors["background"],
                    "border": colors["border"],
                    "highlight": {
                        "background": colors["border"],
                        "border": "#FFD700"
                    }
                },
                size=node_size,
                shape="dot",
                font={"size": int(font_size), "color": "white"}
            )
        
        edge_weights = [float(e.get("weight", 1.0)) for e in graph_json["edges"]]
        max_weight = max(edge_weights) if edge_weights else 1
        
        for e in graph_json["edges"]:
            weight = float(e.get("weight", 1.0))
            weight_ratio = weight / max_weight if max_weight > 0 else 0
            edge_width = edge_width_min + (weight_ratio * (edge_width_max - edge_width_min))
            
            edge_tooltip = f"Connection Strength: {weight:.2f}"
            
            net.add_edge(
                e["source"], 
                e["target"], 
                value=edge_width,
                title=edge_tooltip,
                color={
                    "color": f"rgba(255,255,255,{0.2 + weight_ratio * 0.4})",
                    "highlight": "rgba(255,215,0,0.9)"
                }
            )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            net.save_graph(f.name)
            temp_file = f.name
        
        with open(temp_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        auto_stop_script = f"""
            setTimeout(function() {{
                if (window.network) {{
                    window.network.stopSimulation();
                }}
            }}, {auto_stop_time});
        """ if auto_stop_physics else ""
        
        enhanced_html = html_content.replace(
            "</head>",
            """
            <style>
                .vis-tooltip {
                    position: absolute;
                    visibility: hidden;
                    padding: 10px;
                    white-space: pre-line;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    font-size: 14px;
                    color: #000000;
                    background-color: rgba(255, 255, 255, 0.95);
                    border-radius: 8px;
                    border: 2px solid #333;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                    pointer-events: none;
                    z-index: 1000;
                    max-width: 300px;
                    line-height: 1.5;
                }
                
                .control-panel {
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: rgba(0,0,0,0.8);
                    padding: 12px;
                    border-radius: 8px;
                    color: white;
                    font-size: 13px;
                    font-family: 'Segoe UI', sans-serif;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.2);
                }
                
                .control-panel div {
                    margin: 4px 0;
                    display: flex;
                    align-items: center;
                }
                
                .control-panel .icon {
                    margin-right: 8px;
                }
            </style>
            </head>
            """
        ).replace(
            "</body>",
            f"""
            <div class="control-panel">
                <div><span class="icon">🖱️</span> Drag to pan view</div>
                <div><span class="icon">📌</span> Click node to select</div>
                <div><span class="icon">🔍</span> Scroll to zoom</div>
                <div><span class="icon">⌨️</span> Space to toggle physics</div>
            </div>
            <script>
                {auto_stop_script}
                
                document.addEventListener('keydown', function(e) {{
                    if (e.code === 'Space' && window.network) {{
                        e.preventDefault();
                        if (window.network.physics.options.enabled) {{
                            window.network.setOptions({{physics: {{enabled: false}}}});
                        }} else {{
                            window.network.setOptions({{physics: {{enabled: true}}}});
                        }}
                    }}
                }});
            </script>
            </body>
            """
        )
        
        os.unlink(temp_file)
        
        st.info("🎯 **Graph Controls:** Hover over nodes for details | Click and drag to move | Scroll to zoom | Press SPACE to toggle physics")
        st.components.v1.html(enhanced_html, height=750, scrolling=True)
        
    except Exception as e:
        st.error(f"Error creating graph visualization: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        draw_fallback_view(graph_json)

def draw_plotly_graph(graph_json: dict, viz_settings: dict = None):
    """Enhanced Plotly network visualization with multiple layout algorithms"""
    try:
        import plotly.graph_objects as go
        import networkx as nx
        import numpy as np
        
        if viz_settings is None:
            viz_settings = {}
        
        layout_type = viz_settings.get("plotly_layout", "spring")
        node_size_min, node_size_max = viz_settings.get("node_size_range", (15, 40))
        edge_width_min, edge_width_max = viz_settings.get("edge_width_range", (0.5, 4.0))
        
        G = nx.Graph()
        
        for node in graph_json["nodes"]:
            G.add_node(node["id"], label=node.get("label", node["id"]), type=node.get("type", "default"))
        
        for edge in graph_json["edges"]:
            G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1.0))
        
        node_degrees = dict(G.degree())
        max_degree = max(node_degrees.values()) if node_degrees else 1
        
        try:
            if layout_type == "spring":
                try:
                    pos = nx.spring_layout(G, k=2/np.sqrt(len(G.nodes())), iterations=50, seed=42)
                except:
                    pos = nx.spring_layout(G, iterations=50, seed=42)
            elif layout_type == "circular":
                pos = nx.circular_layout(G)
            elif layout_type == "kamada_kawai":
                try:
                    pos = nx.kamada_kawai_layout(G)
                except:
                    st.warning("Kamada-Kawai layout requires scipy. Using spring layout instead.")
                    pos = nx.spring_layout(G, iterations=50, seed=42)
            elif layout_type == "spectral":
                try:
                    pos = nx.spectral_layout(G)
                except:
                    st.warning("Spectral layout requires scipy. Using spring layout instead.")
                    pos = nx.spring_layout(G, iterations=50, seed=42)
            elif layout_type == "shell":
                shells = []
                nodes_by_degree = {}
                for node, degree in node_degrees.items():
                    if degree not in nodes_by_degree:
                        nodes_by_degree[degree] = []
                    nodes_by_degree[degree].append(node)
                
                for degree in sorted(nodes_by_degree.keys(), reverse=True):
                    shells.append(nodes_by_degree[degree])
                
                pos = nx.shell_layout(G, shells)
            else:
                pos = nx.spring_layout(G, iterations=50, seed=42)
        except Exception as e:
            st.warning(f"Layout algorithm failed: {e}. Using circular layout.")
            pos = nx.circular_layout(G)
        
        pos_array = np.array(list(pos.values()))
        if len(pos_array) > 0:
            pos_array = pos_array - pos_array.mean(axis=0)
            max_dist = np.abs(pos_array).max()
            if max_dist > 0:
                pos_array = pos_array / max_dist
            
            for i, node in enumerate(pos.keys()):
                pos[node] = tuple(pos_array[i])
        
        edge_traces = []
        edge_weights = []
        
        for edge in G.edges(data=True):
            weight = edge[2].get('weight', 1.0)
            edge_weights.append(weight)
        
        max_edge_weight = max(edge_weights) if edge_weights else 1
        
        edge_groups = {}
        for edge in G.edges(data=True):
            weight = edge[2].get('weight', 1.0)
            weight_ratio = weight / max_edge_weight if max_edge_weight > 0 else 0
            width = edge_width_min + (weight_ratio * (edge_width_max - edge_width_min))
            
            width_key = round(width * 2) / 2
            
            if width_key not in edge_groups:
                edge_groups[width_key] = {'x': [], 'y': [], 'weights': []}
            
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            
            edge_groups[width_key]['x'].extend([x0, x1, None])
            edge_groups[width_key]['y'].extend([y0, y1, None])
            edge_groups[width_key]['weights'].append(weight)
        
        for width, group in edge_groups.items():
            opacity = 0.2 + (width / (edge_width_max + edge_width_min)) * 0.5
            edge_trace = go.Scatter(
                x=group['x'], y=group['y'],
                mode='lines',
                line=dict(
                    width=width,
                    color=f'rgba(150, 150, 150, {opacity})'
                ),
                hoverinfo='skip',
                showlegend=False
            )
            edge_traces.append(edge_trace)
        
        node_traces = []
        node_types = {}
        
        for node in G.nodes():
            node_data = G.nodes[node]
            node_type = node_data.get('type', 'default')
            if node_type not in node_types:
                node_types[node_type] = {
                    'x': [], 'y': [], 'text': [], 'hover': [], 'sizes': [], 'ids': []
                }
            
            x, y = pos[node]
            degree = node_degrees[node]
            degree_ratio = degree / max_degree if max_degree > 0 else 0
            size = node_size_min + (degree_ratio * (node_size_max - node_size_min))
            
            text_label = node_data.get('label', node)
            if len(text_label) > 20:
                text_label = text_label[:20] + "..."
            
            hover_text = (
                f"{node_data.get('label', node)}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Type: {node_type.capitalize()}\n"
                f"Connections: {degree}"
            )
            
            node_types[node_type]['x'].append(x)
            node_types[node_type]['y'].append(y)
            node_types[node_type]['text'].append(text_label)
            node_types[node_type]['hover'].append(hover_text)
            node_types[node_type]['sizes'].append(size)
            node_types[node_type]['ids'].append(node)
        
        color_scheme = {
            'author': '#4A90E2',
            'focus_author': '#FF6B6B',
            'keyword': '#F5A623',
            'focus_keyword': '#FF6B6B',
            'org': '#7ED321',
            'focus_org': '#FF6B6B',
            'nation': '#BD10E0',
            'focus_nation': '#FF6B6B',
            'default': '#9013FE'
        }
        
        for node_type, nodes_data in node_types.items():
            node_trace = go.Scatter(
                x=nodes_data['x'],
                y=nodes_data['y'],
                mode='markers+text',
                name=node_type.capitalize(),
                text=nodes_data['text'],
                hovertext=nodes_data['hover'],
                hoverinfo='text',
                textposition='top center',
                textfont=dict(size=9, color='black'),
                marker=dict(
                    size=nodes_data['sizes'],
                    color=color_scheme.get(node_type, color_scheme['default']),
                    line=dict(width=2, color='white'),
                    opacity=0.9
                ),
                showlegend=True
            )
            node_traces.append(node_trace)
        
        fig = go.Figure(
            data=edge_traces + node_traces,
            layout=go.Layout(
                title=f"Network Graph - {layout_type.replace('_', ' ').title()} Layout",
                showlegend=True,
                hovermode='closest',
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=14,
                    font_family="Segoe UI"
                ),
                margin=dict(b=20, l=20, r=20, t=40),
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[-1.2, 1.2]
                ),
                yaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[-1.2, 1.2]
                ),
                plot_bgcolor='#f8f9fa',
                paper_bgcolor='white',
                height=700,
                legend=dict(
                    x=1.02,
                    y=1,
                    bgcolor='rgba(255,255,255,0.9)',
                    bordercolor='gray',
                    borderwidth=1
                ),
                dragmode='pan'
            )
        )
        
        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="left",
                    buttons=list([
                        dict(
                            args=[{"dragmode": "pan"}],
                            label="Pan",
                            method="relayout"
                        ),
                        dict(
                            args=[{"dragmode": "zoom"}],
                            label="Zoom",
                            method="relayout"
                        ),
                        dict(
                            args=[{"dragmode": "select"}],
                            label="Select",
                            method="relayout"
                        ),
                    ]),
                    pad={"r": 10, "t": 10},
                    showactive=True,
                    x=0.0,
                    xanchor="left",
                    y=1.15,
                    yanchor="top"
                ),
            ]
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        
        with st.expander("📊 Graph Statistics", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Nodes", len(G.nodes()))
                st.metric("Total Edges", len(G.edges()))
            with col2:
                st.metric("Average Degree", f"{2 * len(G.edges()) / len(G.nodes()):.2f}")
                st.metric("Graph Density", f"{nx.density(G):.3f}")
            with col3:
                components = list(nx.connected_components(G))
                st.metric("Connected Components", len(components))
                st.metric("Largest Component", len(max(components, key=len)) if components else 0)
        
    except Exception as e:
        st.error(f"Error creating Plotly visualization: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        draw_fallback_view(graph_json)

def draw_fallback_view(graph_json: dict):
    """Fallback view when visualization fails"""
    st.warning("Using fallback data view")
    
    tab1, tab2, tab3 = st.tabs(["📊 Summary", "🔵 Nodes", "🔗 Edges"])
    
    with tab1:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Nodes", len(graph_json["nodes"]))
        with col2:
            st.metric("Total Edges", len(graph_json["edges"]))
        with col3:
            avg_connections = (2 * len(graph_json["edges"])) / len(graph_json["nodes"]) if graph_json["nodes"] else 0
            st.metric("Avg Connections", f"{avg_connections:.1f}")
        
        if graph_json["nodes"]:
            node_types = {}
            for n in graph_json["nodes"]:
                t = n.get("type", "unknown")
                node_types[t] = node_types.get(t, 0) + 1
            
            st.write("**Node Type Distribution:**")
            for ntype, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
                st.write(f"- {ntype}: {count}")
    
    with tab2:
        if graph_json["nodes"]:
            nodes_df = pd.DataFrame(graph_json["nodes"])
            st.dataframe(nodes_df, use_container_width=True, height=400)
        else:
            st.write("No nodes to display")
    
    with tab3:
        if graph_json["edges"]:
            edges_df = pd.DataFrame(graph_json["edges"])
            edges_df = edges_df.sort_values("weight", ascending=False) if "weight" in edges_df.columns else edges_df
            st.dataframe(edges_df, use_container_width=True, height=400)
        else:
            st.write("No edges to display")

# ============= Sidebar Functions =============
def sidebar_actor_management():
    """Manage actors in the sidebar."""
    st.sidebar.header("🎭 Actor Management")
    
    if st.session_state.refresh_actors or not st.session_state.actors_list:
        refresh_actors_list(force=True)
    
    with st.sidebar.expander("➕ Create New Actor", expanded=False):
        with st.form("create_actor_form"):
            new_actor_name = st.text_input("Actor Name", 
                                          help="Enter a unique name for the research group/project")
            submitted = st.form_submit_button("Create", type="primary")
            
            if submitted and new_actor_name:
                if len(new_actor_name) >= 2:
                    if create_new_actor(new_actor_name):
                        st.rerun()
                else:
                    st.error("Name must be at least 2 characters")
    
    st.sidebar.subheader("📂 Select Active Actor")
    
    if st.session_state.actors_list:
        actor_options = []
        actor_map = {}
        for actor in st.session_state.actors_list:
            label = f"{actor['name']} ({actor.get('works', 0)} works, {actor.get('size_mb', 0):.1f} MB)"
            actor_options.append(label)
            actor_map[label] = actor['name']
        
        actor_options.insert(0, "-- Select an Actor --")
        actor_map["-- Select an Actor --"] = None
        
        current_selection = "-- Select an Actor --"
        if st.session_state.current_actor:
            for label, name in actor_map.items():
                if name == st.session_state.current_actor:
                    current_selection = label
                    break
        
        selected_label = st.sidebar.selectbox(
            "Active Database:",
            actor_options,
            index=actor_options.index(current_selection),
            key="actor_selector_widget"
        )
        
        new_actor = actor_map[selected_label]
        if new_actor != st.session_state.current_actor:
            st.session_state.current_actor = new_actor
            st.session_state.search_hits = []
        
        if st.session_state.current_actor:
            current_actor_data = next((a for a in st.session_state.actors_list 
                                      if a['name'] == st.session_state.current_actor), None)
            if current_actor_data:
                st.sidebar.info(f"""
                **Current Actor:** {st.session_state.current_actor}
                - Papers: {current_actor_data.get('works', 0)}
                - Authors: {current_actor_data.get('authors', 0)}
                - Organizations: {current_actor_data.get('organizations', 0)}
                - Size: {current_actor_data.get('size_mb', 0):.2f} MB
                """)
                
                col1, col2 = st.sidebar.columns(2)
                with col1:
                    if st.button("📥 Export CSV", key="export_btn"):
                        data = export_actor_data(st.session_state.current_actor)
                        if data:
                            st.download_button(
                                label="💾 Download",
                                data=data,
                                file_name=f"{st.session_state.current_actor}_export_{datetime.now().strftime('%Y%m%d')}.zip",
                                mime="application/zip",
                                key="download_export"
                            )
                
                with col2:
                    if f'confirm_delete_{st.session_state.current_actor}' not in st.session_state:
                        st.session_state[f'confirm_delete_{st.session_state.current_actor}'] = False
                    
                    if f'password_input_{st.session_state.current_actor}' not in st.session_state:
                        st.session_state[f'password_input_{st.session_state.current_actor}'] = ""
                    
                    confirm_key = f'confirm_delete_{st.session_state.current_actor}'
                    password_key = f'password_input_{st.session_state.current_actor}'
                    
                    if not st.session_state[confirm_key]:
                        if st.button("🗑️ Delete", key="delete_btn", type="secondary"):
                            if st.session_state.current_actor != "default":
                                st.session_state[confirm_key] = True
                                st.session_state[password_key] = ""
                                st.rerun()
                            else:
                                st.sidebar.error("Cannot delete default actor")
                    else:
                        st.sidebar.warning(f"⚠️ Delete '{st.session_state.current_actor}'?")
                        st.sidebar.caption("🔒 Enter password to confirm deletion")
                        
                        password = st.sidebar.text_input(
                            "Password:",
                            type="password",
                            value="",
                            key=f"password_widget_{st.session_state.current_actor}",
                            placeholder="Enter deletion password"
                        )
                        
                        col_confirm, col_cancel = st.sidebar.columns(2)
                        
                        with col_confirm:
                            if st.button("✅ Confirm", key="confirm_delete_with_password", type="primary"):
                                if password == "8888":
                                    actor_to_delete = st.session_state.current_actor
                                    if delete_actor(actor_to_delete):
                                        if confirm_key in st.session_state:
                                            del st.session_state[confirm_key]
                                        if password_key in st.session_state:
                                            del st.session_state[password_key]
                                        st.rerun()
                                    else:
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                                else:
                                    st.sidebar.error("❌ Incorrect password!")
                                    time.sleep(1)
                        
                        with col_cancel:
                            if st.button("❌ Cancel", key="cancel_delete"):
                                st.session_state[confirm_key] = False
                                st.session_state[password_key] = ""
                                st.rerun()
    else:
        st.sidebar.info("No actors found. Create one to start!")
    
    if st.sidebar.button("🔄 Refresh List", key="refresh_actors_btn"):
        refresh_actors_list(force=True)
        st.rerun()

def sidebar_ingest():
    """Data ingestion controls in sidebar."""
    if not st.session_state.current_actor:
        st.sidebar.warning("⚠️ Please select an actor first")
        return
    
    st.sidebar.header(f"📊 Data Ingestion")
    st.sidebar.caption(f"Actor: {st.session_state.current_actor}")
    
    # OpenAlex Search with Enhanced Display
    st.sidebar.subheader("🔍 OpenAlex Search")
    name = st.sidebar.text_input("Author/Researcher Name", value="", key="author_search")
    if st.sidebar.button("Search", key="search_btn") and name.strip():
        hits = api_get("/search-authors", params={"q": name.strip()})
        st.session_state.search_hits = hits

    if st.session_state.search_hits:
        st.sidebar.write("### 📋 Search Results")
        st.sidebar.caption("Review details to distinguish between authors with similar names")
        
        # Display enhanced author information
        for idx, hit in enumerate(st.session_state.search_hits):
            with st.sidebar.expander(f"👤 {hit.get('display_name', 'Unknown')}", expanded=idx<3):
                # Basic info
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Papers", hit.get('works_count', 0))
                    st.metric("H-Index", hit.get('h_index', 0))
                with col2:
                    st.metric("Citations", hit.get('cited_by_count', 0))
                    st.metric("i10-Index", hit.get('i10_index', 0))
                
                # Institution
                institution = hit.get('last_known_institution', 'N/A')
                inst_country = hit.get('institution_country', '')
                if inst_country:
                    st.write(f"🏢 **Institution:** {institution} ({inst_country})")
                else:
                    st.write(f"🏢 **Institution:** {institution}")
                
                # ORCID
                if hit.get('orcid'):
                    st.write(f"🔗 **ORCID:** {hit['orcid']}")
                
                # Research topics
                if hit.get('top_concepts'):
                    st.write("**🎯 Research Topics:**")
                    for concept in hit['top_concepts']:
                        st.write(f"- {concept['name']} ({concept['score']:.0%})")
                
                st.write(f"**ID:** `{hit['source_id']}`")
        
        # Multi-select for ingestion
        st.sidebar.write("---")
        st.sidebar.write("### ✅ Select Authors to Ingest")
        
        author_options = []
        for hit in st.session_state.search_hits:
            # Create detailed label for selection
            affiliation = hit.get('last_known_institution', 'No affiliation') or 'No affiliation'
            country = hit.get('institution_country', '')
            location = f"{affiliation} ({country})" if country else affiliation
            
            # Add research area if available
            research_area = ""
            if hit.get('top_concepts') and len(hit['top_concepts']) > 0:
                research_area = f" | {hit['top_concepts'][0]['name']}"
            
            label = f"{hit['display_name']} - {location}{research_area}"
            author_options.append((label, hit['source_id']))
        
        selected_labels = st.sidebar.multiselect(
            "Choose authors:",
            options=[label for label, _ in author_options],
            key="author_multiselect",
            help="Select one or more authors to import their publications"
        )
        
        sel = [source_id for label, source_id in author_options if label in selected_labels]
        
        if sel:
            st.sidebar.write(f"**Selected:** {len(sel)} author(s)")
            max_works = st.sidebar.slider("Max works per author", min_value=50, max_value=600, value=200, step=50)
            
            if st.sidebar.button("📥 Ingest Selected", type="primary", key="ingest_button"):
                with st.spinner(f"Ingesting to {st.session_state.current_actor}..."):
                    r = api_post(f"/{st.session_state.current_actor}/ingest/openalex", 
                               {"author_source_ids": sel, "max_works": max_works})
                    st.sidebar.success(f"✅ Ingested {r.get('ingested_works')} works")
                    st.session_state.search_hits = []
                    refresh_actors_list(force=True)
                    st.rerun()

    # CSV Import
    st.sidebar.subheader("📁 CSV Import")
    kind = st.sidebar.selectbox("Data Type", ["works", "authors", "affiliations", "keywords"])
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"], key="csv_upload")
    if uploaded and st.sidebar.button("📤 Import CSV"):
        text = uploaded.read().decode("utf-8")
        r = api_post(f"/{st.session_state.current_actor}/import/csv", 
                    {"kind": kind, "csv_text": text})
        st.sidebar.success(f"✅ Imported {r.get('rows')} rows")
        refresh_actors_list(force=True)
        st.rerun()

# ============= How to Use Tab =============
def how_to_use_tab():
    """Comprehensive guide on using the system."""
    st.header("📚 How to Use This Service")
    
    st.markdown("""
    Welcome to the **Multi-Actor Research Relationship Visualization Service**! This guide will help you 
    understand the system's capabilities and how to use each feature effectively.
    """)
    
    # Quick Start
    with st.expander("🚀 Quick Start Guide", expanded=True):
        st.markdown("""
        ### Getting Started in 5 Minutes
        
        1. **Create an Actor Database** (left sidebar)
           - Click "➕ Create New Actor"
           - Enter a name (e.g., "AI Research Team", "Stanford NLP")
           - Each actor has its own isolated database
        
        2. **Import Research Data**
           - Search for a researcher by name in the sidebar
           - Review their profile (papers, citations, institution)
           - Select one or more researchers
           - Click "📥 Ingest Selected" to import their publications
        
        3. **Visualize Relationships**
           - Go to the "Graph" tab
           - Choose a layer (authors, keywords, orgs, nations)
           - Set filters (year range, connection strength)
           - Click "🎨 Build Graph" to see the network
        
        4. **Analyze Patterns**
           - Use the "Heatmaps" tab for deeper analysis
           - Export your data anytime from the sidebar
        """)
    
    # Core Concepts
    with st.expander("🎯 Core Concepts", expanded=False):
        st.markdown("""
        ### What is an Actor?
        An **Actor** represents a research group, institution, or project with its own isolated database. 
        Think of it as a separate workspace for organizing related research.
        
        **Examples:**
        - "Stanford AI Lab" - Track all Stanford AI researchers
        - "Climate Science 2020-2024" - Focus on recent climate research
        - "My PhD Committee" - Analyze your committee members' work
        
        ### Multi-Actor System
        - **Isolation**: Each actor's data is completely separate
        - **Flexibility**: Create unlimited actors for different projects
        - **Comparison**: Compare networks across different research communities
        
        ### Data Sources
        - **OpenAlex**: Open database of 250M+ scholarly works
        - **CSV Import**: Upload your own structured data
        - **Automatic Extraction**: Keywords, institutions, and collaborations extracted automatically
        """)
    
    # Understanding Visualizations
    with st.expander("📊 Understanding Visualizations", expanded=False):
        st.markdown("""
        ### Network Graph Layers
        
        #### 1. 👥 Author Layer (Co-authorship Network)
        **What it shows:** Researchers and their collaborations
        
        **Node = Author** | **Edge = Co-authored papers**
        - Node size → Number of collaborations
        - Edge thickness → Number of shared publications
        - Color → Different groups/communities
        
        **Use cases:**
        - Identify key collaborators in a field
        - Find bridge researchers connecting communities
        - Discover research teams and their structures
        
        **Focus Mode:**
        - **Full Network**: Shows all authors, highlights selected ones in red
        - **Focus Only**: Shows only selected authors + their direct collaborators
        
        ---
        
        #### 2. 🔍 Keyword Layer (Topic Co-occurrence)
        **What it shows:** Research topics and their relationships
        
        **Node = Keyword** | **Edge = Papers discussing both topics**
        - Node size → Frequency of keyword usage
        - Edge thickness → Number of papers with both keywords
        
        **Use cases:**
        - Map the conceptual landscape of a field
        - Identify emerging topic combinations
        - Find interdisciplinary connections
        - Understand research focus areas
        
        ---
        
        #### 3. 🏢 Organization Layer (Institutional Collaboration)
        **What it shows:** Universities and research institutions
        
        **Node = Institution** | **Edge = Joint publications**
        - Shows which institutions collaborate most
        - Reveals international research partnerships
        
        **Use cases:**
        - Identify leading institutions in a field
        - Map global research networks
        - Find potential collaboration partners
        
        ---
        
        #### 4. 🌍 Nation Layer (International Collaboration)
        **What it shows:** Countries and their research partnerships
        
        **Node = Country** | **Edge = International co-authorships**
        - Reveals global research patterns
        - Shows geopolitical science networks
        
        **Use cases:**
        - Analyze international research trends
        - Identify global scientific collaborations
        - Study geographic distribution of research
        
        ---
        
        ### Heatmap Visualizations
        
        #### Author-Keyword Heatmap
        **Matrix showing which authors work on which topics**
        - Rows = Authors | Columns = Keywords
        - Color intensity = Number of papers
        - Helps identify author expertise areas
        
        #### Nation-Nation Heatmap
        **Matrix of international collaboration intensity**
        - Shows bilateral research relationships
        - Darker = More collaborative papers
        """)
    
    # Graph Controls
    with st.expander("🎮 Graph Controls & Features", expanded=False):
        st.markdown("""
        ### Filtering Options
        
        **Year Range**
        - Focus on specific time periods
        - Track how networks evolve over time
        - Example: Compare 2015-2020 vs 2020-2024
        
        **Edge Weight Minimum**
        - Filter out weak connections
        - Keep only strong collaborations (e.g., 3+ papers together)
        - Cleaner visualization for large networks
        
        **Focus Mode** (with Focus IDs specified)
        - **Full Network**: See the entire network with focus nodes highlighted in red
        - **Focus Only**: See only focus nodes and their immediate neighbors
        
        ### Finding IDs for Focus Mode
        
        Each layer has a built-in search helper:
        
        **For Authors:**
        1. Expand "👤 Find Author IDs"
        2. Search by name (e.g., "Geoffrey Hinton")
        3. Copy the ID numbers shown
        4. Paste into "Focus author IDs" (comma-separated)
        
        **For Keywords:**
        1. Expand "🔍 Find Keyword IDs"
        2. Search for topics (e.g., "deep learning")
        3. Copy relevant IDs
        
        **For Organizations:**
        1. Expand "🏢 Find Organization IDs"
        2. Search by institution name
        3. Copy the IDs you need
        
        **For Nations:**
        - Use 2-letter country codes (US, GB, DE, FR, CN, JP, etc.)
        - No search needed - codes are standardized
        
        ### Visualization Types
        
        **PyVis Network** (Default)
        - Interactive physics simulation
        - Drag nodes to rearrange
        - Auto-stabilization for clean layouts
        - Best for exploration
        
        **Plotly Network**
        - Multiple layout algorithms (spring, circular, spectral, etc.)
        - Statistical analysis tools
        - Better for presentations
        - Export-friendly
        
        ### Interaction Tips
        
        **PyVis:**
        - 🖱️ Drag to pan
        - 📌 Click nodes to select
        - 🔍 Scroll to zoom
        - ⌨️ Press SPACE to toggle physics
        
        **Plotly:**
        - Use toolbar for pan/zoom/select modes
        - Hover for detailed information
        - Double-click to reset view
        - Export as image from toolbar
        """)
    
    # Author Disambiguation
    with st.expander("🔎 Author Disambiguation", expanded=False):
        st.markdown("""
        ### Why Disambiguation Matters
        
        Multiple researchers may share the same name (e.g., "J. Smith"). Our enhanced search 
        provides detailed information to help you select the correct person:
        
        ### Identifying Information
        
        **📊 Publication Metrics**
        - **Papers**: Total number of publications
        - **Citations**: How often their work is cited
        - **H-Index**: Impact measure (papers with ≥h citations)
        - **i10-Index**: Papers with ≥10 citations
        
        **🏢 Institutional Affiliation**
        - Current or last known institution
        - Country location
        - Institution type (University, Company, etc.)
        
        **🎯 Research Topics**
        - Top 3 research areas with confidence scores
        - Helps distinguish researchers in different fields
        
        **🔗 ORCID**
        - Unique researcher identifier when available
        - Most reliable disambiguation method
        
        ### Best Practices
        
        1. **Check multiple attributes** - Don't rely on name alone
        2. **Verify institution** - Most researchers have stable affiliations
        3. **Review research topics** - Should match your expectations
        4. **Look at metrics** - H-index and papers count confirm career stage
        5. **Use ORCID when available** - The gold standard for identification
        
        ### Example
        ```
        ❌ "Michael Jordan" - Not enough info
        
        ✅ "Michael Jordan"
           - UC Berkeley (US)
           - 1,234 papers | 123,456 citations | H-Index: 178
           - Topics: Machine Learning (95%), Statistics (87%)
           - ORCID: 0000-0001-XXXX-XXXX
        ```
        """)
    
    # Data Management
    with st.expander("💾 Data Management", expanded=False):
        st.markdown("""
        ### Import Options
        
        **OpenAlex Import** (Recommended)
        - Automatic extraction of all metadata
        - Includes authors, institutions, keywords
        - Citation data and relationships
        - High quality, standardized data
        
        **CSV Import**
        - For custom or legacy data
        - Four types: works, authors, affiliations, keywords
        - See User Manual for format specifications
        
        ### Export Options
        
        **CSV Export**
        - Downloads complete database as ZIP file
        - Includes all tables in CSV format
        - Metadata file with summary statistics
        - Can be imported into other tools
        
        ### Actor Management
        
        **Creating Actors**
        - Name must be 2+ characters
        - Use descriptive names
        - Each actor is independent
        
        **Deleting Actors**
        - Requires password confirmation (8888)
        - Permanent deletion - cannot be undone
        - Cannot delete "default" actor
        
        **Storage**
        - Each actor database is a separate SQLite file
        - Stored in `./databases/` directory
        - Size shown in MB next to each actor
        """)
    
    # Advanced Tips
    with st.expander("💡 Pro Tips & Best Practices", expanded=False):
        st.markdown("""
        ### Workflow Recommendations
        
        **1. Start Small, Then Expand**
        - Begin with 1-2 key researchers (200 papers each)
        - Build the initial network
        - Add more researchers iteratively
        - This helps you understand the data quality
        
        **2. Use Time Windows**
        - Compare network evolution: 2010-2015 vs 2015-2020 vs 2020-2024
        - Identify emerging collaborations
        - Track how research communities change
        
        **3. Layer Analysis Strategy**
        - Start with Author layer → Understand who collaborates
        - Then Keyword layer → See what they work on
        - Then Organization layer → Find institutional patterns
        - Finally Nation layer → Global perspective
        
        **4. Focus Mode for Deep Dives**
        - Use "Focus Only" to study specific researchers' networks
        - Great for understanding a particular group
        - Reduces visual clutter on large networks
        
        **5. Combine Multiple Views**
        - Build author graph to find key researchers
        - Use author-keyword heatmap to understand their expertise
        - Check organization network for institutional context
        
        ### Performance Tips
        
        **For Large Datasets (500+ papers):**
        - Increase edge weight threshold (2.0 or higher)
        - Use narrower year ranges
        - Consider Focus Only mode
        - Disable physics auto-stabilization
        
        **For Better Visualizations:**
        - Adjust node size range for clarity
        - Try different layout algorithms (Plotly)
        - Export and edit in external tools if needed
        
        ### Common Use Cases
        
        **Research Collaboration Analysis**
        1. Import research group members
        2. Build author network
        3. Identify collaboration patterns
        4. Find potential new collaborators
        
        **Literature Review**
        1. Import key papers via CSV
        2. Build keyword network
        3. Map the conceptual landscape
        4. Identify gaps and opportunities
        
        **Institutional Benchmarking**
        1. Import researchers from multiple institutions
        2. Build organization network
        3. Compare collaboration patterns
        4. Identify partnership opportunities
        
        **Trend Analysis**
        1. Import papers from specific field
        2. Build keyword network for different time periods
        3. Compare network evolution
        4. Identify emerging topics
        """)
    
    # Troubleshooting
    with st.expander("🔧 Troubleshooting", expanded=False):
        st.markdown("""
        ### Common Issues & Solutions
        
        **Problem**: Graph is too cluttered
        - **Solution**: Increase edge weight minimum (try 2.0 or 3.0)
        - **Solution**: Use narrower year range
        - **Solution**: Enable Focus Only mode
        
        **Problem**: Author search returns too many results
        - **Solution**: Add more specific terms (first + last name)
        - **Solution**: Include institution name in search
        - **Solution**: Check ORCID if you have it
        
        **Problem**: Graph shows no nodes
        - **Solution**: Reduce edge weight threshold
        - **Solution**: Expand year range
        - **Solution**: Check if data was properly imported
        
        **Problem**: Slow performance
        - **Solution**: Close other browser tabs
        - **Solution**: Reduce number of papers imported
        - **Solution**: Use smaller actor databases
        
        **Problem**: Cannot find author IDs
        - **Solution**: Use the built-in search helper in each layer
        - **Solution**: Check if data was imported correctly
        - **Solution**: Verify you're in the correct actor database
        
        **Problem**: Ingestion is very slow
        - **Solution**: Reduce max works per author
        - **Solution**: Import fewer authors at once
        - **Solution**: Be patient - large imports take time
        
        ### Getting Help
        
        1. Check the User Manual (document provided)
        2. Review API documentation at http://localhost:8000/docs
        3. Check browser console for error messages
        4. Verify backend is running properly
        """)
    
    # Footer with key principles
    st.markdown("---")
    st.markdown("""
    ### 🎓 Key Principles
    
    **Quality over Quantity**: Start with focused, high-quality data rather than importing everything
    
    **Iterative Exploration**: Build networks incrementally, analyze, then expand
    
    **Multiple Perspectives**: Use different layers and visualizations to understand the complete picture
    
    **Context Matters**: Always consider the limitations of bibliometric data and network analysis
    """)

# ============= Main Tab Functions =============
def overview_tab():
    """Overview and statistics tab."""
    st.header("📈 System Overview")
    
    # Force refresh to get latest data
    refresh_actors_list(force=True)
    
    if not st.session_state.actors_list:
        st.info("No actor databases found. Create one from the sidebar to get started!")
        return
    
    st.subheader("🎭 Actor Databases")
    
    # Display actors as cards
    actors = st.session_state.actors_list
    for i in range(0, len(actors), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            if i + j < len(actors):
                actor = actors[i + j]
                with col:
                    with st.container():
                        st.metric(actor['name'], f"{actor.get('works', 0)} papers")
                        st.caption(f"""
                        Authors: {actor.get('authors', 0)}  
                        Orgs: {actor.get('organizations', 0)}  
                        Keywords: {actor.get('keywords', 0)}  
                        Size: {actor.get('size_mb', 0):.2f} MB
                        """)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Select", key=f"select_{actor['name']}"):
                                st.session_state.current_actor = actor['name']
                                st.rerun()
                        with col2:
                            data = export_actor_data(actor['name'])
                            if data:
                                st.download_button(
                                    "Export",
                                    data=data,
                                    file_name=f"{actor['name']}_export.zip",
                                    mime="application/zip",
                                    key=f"dl_{actor['name']}"
                                )
    
    # System statistics
    st.subheader("📊 System Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    total_works = sum(a.get('works', 0) for a in actors)
    total_authors = sum(a.get('authors', 0) for a in actors)
    total_size = sum(a.get('size_mb', 0) for a in actors)
    
    with col1:
        st.metric("Total Actors", len(actors))
    with col2:
        st.metric("Total Papers", total_works)
    with col3:
        st.metric("Total Authors", total_authors)
    with col4:
        st.metric("Total Size", f"{total_size:.1f} MB")

def graph_tab():
    """Graph visualization tab."""
    if not st.session_state.current_actor:
        st.warning("⚠️ Please select an actor from the sidebar to visualize data")
        return
    
    st.header(f"🔗 Graph Explorer - {st.session_state.current_actor}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        layer = st.selectbox("Layer", ["authors", "keywords", "orgs", "nations"], key="graph_layer")
    with col2:
        year_min = st.number_input("Year min", value=2000, step=1, key="graph_year_min")
    with col3:
        year_max = st.number_input("Year max", value=2025, step=1, key="graph_year_max")
    with col4:
        edge_min = st.slider("Edge weight min", 0.0, 10.0, 1.0, 0.5, key="graph_edge_min")

    # Dynamic focus helper based on layer
    if layer == "authors":
        with st.expander("👤 Find Author IDs", expanded=False):
            search_name = st.text_input("Search author name:", key="author_search_graph", 
                                       placeholder="Enter part of author's name...")
            if search_name and len(search_name) >= 2:
                try:
                    response = api_get(f"/{st.session_state.current_actor}/search-local-authors", 
                                     params={"q": search_name})
                    authors = response.get("authors", [])
                    
                    if authors:
                        st.write("**Found authors (click to copy ID):**")
                        cols = st.columns(3)
                        for i, author in enumerate(authors):
                            with cols[i % 3]:
                                st.code(f"{author['id']}", language=None)
                                st.caption(f"{author['name']}")
                        
                        if len(authors) >= 2:
                            example_ids = ",".join([str(author['id']) for author in authors[:2]])
                            st.info(f"💡 **Example focus input:** `{example_ids}`")
                    else:
                        st.write("No authors found matching your search.")
                except Exception as e:
                    st.error(f"Search error: {e}")
                    
    elif layer == "keywords":
        with st.expander("🔍 Find Keyword IDs", expanded=False):
            search_term = st.text_input("Search keyword:", key="keyword_search_graph",
                                       placeholder="Enter part of keyword...")
            if search_term and len(search_term) >= 2:
                try:
                    response = api_get(f"/{st.session_state.current_actor}/search-local-keywords", 
                                     params={"q": search_term})
                    keywords = response.get("keywords", [])
                    
                    if keywords:
                        st.write("**Found keywords (click to copy ID):**")
                        cols = st.columns(3)
                        for i, keyword in enumerate(keywords):
                            with cols[i % 3]:
                                st.code(f"{keyword['id']}", language=None)
                                st.caption(f"{keyword['term']}")
                        
                        if len(keywords) >= 2:
                            example_ids = ",".join([str(kw['id']) for kw in keywords[:2]])
                            st.info(f"💡 **Example focus input:** `{example_ids}`")
                    else:
                        st.write("No keywords found matching your search.")
                except Exception as e:
                    st.error(f"Search error: {e}")
                    
    elif layer == "orgs":
        with st.expander("🏢 Find Organization IDs", expanded=False):
            search_org = st.text_input("Search organization:", key="org_search_graph",
                                      placeholder="Enter part of organization name...")
            if search_org and len(search_org) >= 2:
                try:
                    response = api_get(f"/{st.session_state.current_actor}/search-local-orgs", 
                                     params={"q": search_org})
                    orgs = response.get("organizations", [])
                    
                    if orgs:
                        st.write("**Found organizations (click to copy ID):**")
                        cols = st.columns(2)
                        for i, org in enumerate(orgs):
                            with cols[i % 2]:
                                st.code(f"{org['id']}", language=None)
                                st.caption(f"{org['name']} ({org.get('country', 'N/A')})")
                        
                        if len(orgs) >= 2:
                            example_ids = ",".join([str(org['id']) for org in orgs[:2]])
                            st.info(f"💡 **Example focus input:** `{example_ids}`")
                    else:
                        st.write("No organizations found matching your search.")
                except Exception as e:
                    st.error(f"Search error: {e}")
                    
    elif layer == "nations":
        with st.expander("🌍 Find Nation Codes", expanded=False):
            st.write("**Common country codes:**")
            common_countries = [
                ("US", "United States"), ("GB", "United Kingdom"), ("DE", "Germany"),
                ("FR", "France"), ("CN", "China"), ("JP", "Japan"), ("KR", "South Korea"),
                ("CA", "Canada"), ("AU", "Australia"), ("IN", "India"), ("BR", "Brazil")
            ]
            
            cols = st.columns(3)
            for i, (code, name) in enumerate(common_countries):
                with cols[i % 3]:
                    st.code(code, language=None)
                    st.caption(name)
            
            st.info("💡 **Example focus input:** `US,GB,DE`")

    # Dynamic focus input based on layer
    focus_label_map = {
        "authors": "Focus author IDs (comma-separated, optional)",
        "keywords": "Focus keyword IDs (comma-separated, optional)", 
        "orgs": "Focus organization IDs (comma-separated, optional)",
        "nations": "Focus nation codes (comma-separated, optional)"
    }
    
    focus_help_map = {
        "authors": "Enter author IDs to focus the graph around specific researchers and their collaborators.",
        "keywords": "Enter keyword IDs to focus the graph around specific topics and related terms.",
        "orgs": "Enter organization IDs to focus the graph around specific institutions and their collaborators.",
        "nations": "Enter country codes (e.g., US, GB, DE) to focus the graph around specific nations and their collaborators."
    }
    
    focus_placeholder_map = {
        "authors": "e.g., 1,5,23",
        "keywords": "e.g., 12,45,78",
        "orgs": "e.g., 3,15,42",
        "nations": "e.g., US,GB,DE"
    }

    focus = st.text_input(
        focus_label_map[layer], 
        value="", 
        key="graph_focus", 
        help=focus_help_map[layer] + " Use the finder above to search for IDs.",
        placeholder=focus_placeholder_map[layer]
    )
    
    # Parse focus IDs based on layer
    focus_ids = None
    if focus:
        if layer == "nations":
            # For nations, keep as strings (country codes)
            focus_list = []
            for item in focus.split(","):
                item = item.strip().upper()
                if len(item) == 2:  # Country code
                    focus_list.append(item)
            focus_ids = focus_list if focus_list else None
        else:
            # For authors, keywords, orgs - numeric IDs
            focus_list = []
            for item in focus.split(","):
                item = item.strip()
                if item.isdigit():
                    focus_list.append(int(item))
            focus_ids = focus_list if focus_list else None

    # Focus mode toggle (only show when focus IDs are provided)
    focus_only = False
    if focus_ids:
        st.write("**Focus Mode Options:**")
        focus_mode = st.radio(
            "Choose focus mode:",
            options=["Full Network (highlight focus authors)", "Focus Only (show only focus authors + collaborators)"],
            index=0,
            key="focus_mode_radio",
            help="Full Network shows all authors with focus authors highlighted. Focus Only shows just the focus authors and their direct collaborators."
        )
        
        focus_only = focus_mode.startswith("Focus Only")
        
        if focus_only:
            st.info("🔍 **Focus Only Mode:** Showing only focus authors and their direct collaborators")
        else:
            st.info("🌐 **Full Network Mode:** Showing complete network with focus authors highlighted in red")

    # Show focus info if provided
    if focus_ids:
        try:
            if layer == "authors":
                response = api_post(f"/{st.session_state.current_actor}/validate-authors", focus_ids)
                validated_items = response.get("authors", [])
                
                focus_names = []
                for item in validated_items:
                    if item["exists"]:
                        focus_names.append(f"**{item['name']}** (ID: {item['id']})")
                    else:
                        focus_names.append(f"**Unknown Author** (ID: {item['id']})")
                        
            elif layer == "keywords":
                response = api_post(f"/{st.session_state.current_actor}/validate-keywords", focus_ids)
                validated_items = response.get("keywords", [])
                
                focus_names = []
                for item in validated_items:
                    if item["exists"]:
                        focus_names.append(f"**{item['term']}** (ID: {item['id']})")
                    else:
                        focus_names.append(f"**Unknown Keyword** (ID: {item['id']})")
                        
            elif layer == "orgs":
                response = api_post(f"/{st.session_state.current_actor}/validate-orgs", focus_ids)
                validated_items = response.get("organizations", [])
                
                focus_names = []
                for item in validated_items:
                    if item["exists"]:
                        focus_names.append(f"**{item['name']}** (ID: {item['id']})")
                    else:
                        focus_names.append(f"**Unknown Organization** (ID: {item['id']})")
                        
            elif layer == "nations":
                focus_names = [f"**{code}**" for code in focus_ids if isinstance(code, str)]
            
            if focus_names:
                layer_emoji = {"authors": "👤", "keywords": "🔍", "orgs": "🏢", "nations": "🌍"}
                st.info(f"{layer_emoji[layer]} **Focusing on {layer}:** {', '.join(focus_names)}")
        except Exception as e:
            st.warning(f"Could not validate focus {layer}: {e}")

    viz_type = st.radio("Visualization Type", ["PyVis Network", "Plotly Network"], horizontal=True, key="viz_type")
    
    with st.expander("🎨 Visualization Controls", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            node_size_range = st.slider("Node Size Range", min_value=5, max_value=100, 
                                       value=(15, 40), key="node_size_range")
            font_size_range = st.slider("Font Size Range", min_value=8, max_value=24,
                                       value=(10, 16), key="font_size_range")
        with col2:
            physics_iterations = st.slider("Physics Iterations (PyVis)", min_value=50, max_value=500,
                                          value=200, key="physics_iterations")
            auto_stop_physics = st.checkbox("Auto-stop Physics", value=True, key="auto_stop")
        with col3:
            edge_width_range = st.slider("Edge Width Range", min_value=0.1, max_value=10.0,
                                        value=(0.5, 4.0), key="edge_width_range")
            plotly_layout = st.selectbox("Plotly Layout", 
                                        ["spring", "circular", "kamada_kawai", "spectral", "shell"],
                                        key="plotly_layout")

    if st.button("🎨 Build Graph", key="build_graph_btn", type="primary"):
        with st.spinner("Building graph..."):
            try:
                graph_request = {
                    "layer": layer, 
                    "year_min": year_min, 
                    "year_max": year_max,
                    "edge_min_weight": edge_min, 
                    "focus_only": focus_only
                }
                
                if focus_ids:
                    if layer == "nations":
                        graph_request["focus_ids"] = focus_ids
                    else:
                        graph_request["focus_int_ids"] = focus_ids
                
                try:
                    g = api_post(f"/{st.session_state.current_actor}/graph", graph_request)
                except requests.exceptions.HTTPError as e:
                    st.error(f"HTTP Error: {e}")
                    try:
                        error_detail = e.response.json()
                        st.write("**Error details:**")
                        st.json(error_detail)
                    except:
                        st.write("**Raw error response:**")
                        st.code(e.response.text)
                    return
                except Exception as e:
                    st.error(f"Request Error: {e}")
                    return
                
                if not g.get('nodes'):
                    st.warning("No nodes found with the current filters. Try adjusting your parameters.")
                    return
                
                focus_count = len([n for n in g['nodes'] if n.get('focus', False)]) if focus_ids else 0
                total_authors = len([n for n in g['nodes'] if n.get('type') in ['author', 'focus_author']])
                
                if layer == "authors" and focus_count > 0:
                    if focus_only:
                        stats_msg = f"Focus Graph: {len(g['nodes'])} nodes, {len(g['edges'])} edges ({focus_count} focus authors + {total_authors - focus_count} collaborators)"
                    else:
                        stats_msg = f"Full Network: {len(g['nodes'])} nodes, {len(g['edges'])} edges ({focus_count} focus authors highlighted)"
                else:
                    stats_msg = f"Graph: {len(g['nodes'])} nodes, {len(g['edges'])} edges"
                    
                st.success(stats_msg)
                
                viz_settings = {
                    "node_size_range": node_size_range,
                    "font_size_range": font_size_range,
                    "physics_iterations": physics_iterations,
                    "auto_stop_physics": auto_stop_physics,
                    "edge_width_range": edge_width_range,
                    "plotly_layout": plotly_layout
                }
                
                if viz_type == "PyVis Network":
                    draw_pyvis_graph(g, viz_settings=viz_settings)
                else:
                    draw_plotly_graph(g, viz_settings=viz_settings)
                    
            except Exception as e:
                st.error(f"Error building graph: {e}")
                if "focus_author_ids" in str(e):
                    st.info("💡 Make sure the focus author IDs exist in your database. Use the Author ID finder above to search for valid IDs.")

def heatmap_tab():
    """Heatmap visualization tab."""
    if not st.session_state.current_actor:
        st.warning("⚠️ Please select an actor from the sidebar to visualize data")
        return
    
    st.header(f"🔥 Heatmaps - {st.session_state.current_actor}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        kind = st.selectbox("Kind", ["author_keyword", "nation_nation"], key="heatmap_kind")
    with col2:
        year_min = st.number_input("Year min", value=2000, step=1, key="heatmap_year_min")
    with col3:
        year_max = st.number_input("Year max", value=2025, step=1, key="heatmap_year_max")

    if st.button("📊 Compute Heatmap", key="compute_heatmap_btn", type="primary"):
        with st.spinner("Computing heatmap..."):
            hm = api_post(f"/{st.session_state.current_actor}/heatmap", 
                         {"kind": kind, "year_min": year_min, "year_max": year_max})
            if not hm.get("data"):
                st.warning("No data available for the selected parameters")
                return
            
            import plotly.express as px
            z = hm["data"]
            x = [c["label"] for c in hm["cols"]]
            y = [r["label"] for r in hm["rows"]]
            fig = px.imshow(z, labels=dict(x="Columns", y="Rows", color="Weight"),
                           x=x, y=y, aspect="auto", color_continuous_scale="Viridis")
            st.plotly_chart(fig, use_container_width=True)

# ============= Main Application =============
def main():
    st.title("🔬 Multi-Actor Research Relationship Visualization Service")
    
    # Sidebar
    with st.sidebar:
        sidebar_actor_management()
        st.sidebar.divider()
        sidebar_ingest()
    
    # Main content area - "How to Use" tab first
    tabs = st.tabs(["📚 How to Use", "📈 Overview", "🔗 Graph", "🔥 Heatmaps"])
    
    with tabs[0]:
        how_to_use_tab()
    with tabs[1]:
        overview_tab()
    with tabs[2]:
        graph_tab()
    with tabs[3]:
        heatmap_tab()

if __name__ == "__main__":
    main()