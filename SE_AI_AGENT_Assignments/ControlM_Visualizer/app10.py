import streamlit as st
import pandas as pd
import networkx as nx
import xml.etree.ElementTree as ET
from pyvis.network import Network
import tempfile
import os
import re
import json
import streamlit.components.v1 as components

# --- PAGE CONFIGURATION ---
st.set_page_config(
    layout="wide", 
    page_title="Control-M Lineage", 
    page_icon="🕸️",
    initial_sidebar_state="expanded"
)

# --- 🎨 THEME DEFINITIONS ---
THEMES = {
    "Dark Mode": {
        "bg_color": "#0e0e0e",
        "sidebar_bg": "#161616",
        "text_color": "#ffffff",
        "input_bg": "#2d2d2d",
        "input_text": "#ffffff",
        "input_border": "#555555",
        "placeholder": "#bbbbbb",
        "graph_bg": "#121212",
        "node_font": {"color": "#ffffff", "size": 20, "face": "Segoe UI"},
        "edge_color": "#666666",
        "node_default": {"bg": "#0a2e36", "border": "#00d4ff"}, 
        "node_highlight": {"bg": "#4a2c0a", "border": "#ff9900"}, 
        "node_start": {"bg": "#0a3618", "border": "#00ff41"}, 
        "node_end": {"bg": "#360a0a", "border": "#ff3333"},
        "glow_color": "#ffffff"
    },
    "Light Mode": {
        "bg_color": "#ffffff",
        "sidebar_bg": "#f4f4f4",
        "text_color": "#000000",
        "input_bg": "#ffffff",
        "input_text": "#000000",
        "input_border": "#888888",
        "placeholder": "#444444",
        "graph_bg": "#ffffff",
        "node_font": {"color": "#000000", "size": 20, "face": "Segoe UI"},
        "edge_color": "#555555",
        "node_default": {"bg": "#bbdefb", "border": "#0d47a1"}, 
        "node_highlight": {"bg": "#ffe0b2", "border": "#e65100"}, 
        "node_start": {"bg": "#c8e6c9", "border": "#1b5e20"}, 
        "node_end": {"bg": "#ffcdd2", "border": "#b71c1c"},
        "glow_color": "#ff0000"
    }
}

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    mode = st.radio("Theme:", ["Dark Mode", "Light Mode"], horizontal=True)
    theme = THEMES[mode]
    st.divider()
    uploaded_file = st.file_uploader("Upload XML", type=["xml"])
    show_data = st.checkbox("Show Raw Data", value=False)

# --- GLOBAL CSS ---
st.markdown(f"""
<style>
    /* MAIN UI COLORS */
    .stApp {{ background-color: {theme['bg_color']}; color: {theme['text_color']}; font-family: 'Segoe UI', sans-serif; }}
    [data-testid="stSidebar"] {{ background-color: {theme['sidebar_bg']}; border-right: 1px solid #ccc; }}
    h1, h2, h3, p, label, .stMarkdown {{ color: {theme['text_color']} !important; font-weight: 500 !important; }}
    
    /* INPUTS (High Contrast) */
    .stTextInput > div > div > input,
    .stMultiSelect > div > div > div,
    .stNumberInput > div > div > input {{
        background-color: {theme['input_bg']} !important;
        color: {theme['input_text']} !important;
        border: 1px solid {theme['input_border']} !important;
        font-weight: 600 !important;
        border-radius: 8px;
    }}
    
    /* PLACEHOLDER VISIBILITY */
    input::placeholder {{ color: {theme['placeholder']} !important; opacity: 1; }}
    .stMultiSelect div[role="button"] p {{ color: {theme['placeholder']} !important; font-weight: 600; }}
    .stMultiSelect span {{ color: {theme['input_text']} !important; }} 

    /* --- NEW: CUSTOM DOWNLOAD BUTTON STYLING --- */
    div[data-testid="stDownloadButton"] button {{
        background: linear-gradient(135deg, #2980b9 0%, #2c3e50 100%); /* Premium Blue Gradient */
        color: white !important;
        border: none;
        padding: 10px 24px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        width: 100%;
    }}
    div[data-testid="stDownloadButton"] button:hover {{
        background: linear-gradient(135deg, #3498db 0%, #34495e 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        color: white !important;
    }}
    div[data-testid="stDownloadButton"] button:active {{
        transform: translateY(0px);
    }}

    /* --- NEW: DATA TABLE HEADER HIGHLIGHT --- */
    .data-header {{
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%); /* Steel Blue Gradient */
        color: white;
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
        font-size: 16px;
        margin-top: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    
    /* Hide Footer */
    footer {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

# --- 1. PARSING LOGIC ---
@st.cache_data
def parse_controlm_xml(file):
    try:
        tree = ET.parse(file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"XML Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

    jobs = []
    cond_map = {}

    for job in root.findall(".//JOB"):
        name = job.get("JOBNAME")
        item = {"JobName": name, "Folder": job.get("PARENT_FOLDER") or "Root", "In": [], "Out": []}
        for out in job.findall("OUTCOND"):
            cname = out.get("NAME")
            if out.get("SIGN") == "+" and out.get("ODATE") == "ODAT":
                item["Out"].append(cname)
                if cname not in cond_map: cond_map[cname] = []
                cond_map[cname].append(name)
        for incon in job.findall("INCOND"):
            if incon.get("ODATE") == "ODAT":
                item["In"].append(incon.get("NAME"))
        jobs.append(item)

    edges = []
    for j in jobs:
        consumer = j["JobName"]
        for c in j["In"]:
            if c in cond_map:
                for producer in cond_map[c]:
                    edges.append({"Source": producer, "Target": consumer, "Condition": c})
    
    return pd.DataFrame(jobs), pd.DataFrame(edges)

# --- 2. GRAPH BUILDER ---
def build_graph(df_edges, all_jobs):
    G = nx.DiGraph()
    G.add_nodes_from(all_jobs)
    for _, r in df_edges.iterrows():
        G.add_edge(r["Source"], r["Target"], label=r["Condition"])
    return G

def filter_lineage(G, seeds, depth=None):
    nodes = set()
    for seed in seeds:
        seed = seed.strip()
        if seed in G.nodes:
            nodes.add(seed)
            if depth is None:
                nodes.update(nx.ancestors(G, seed))
                nodes.update(nx.descendants(G, seed))
            else:
                nodes.update(nx.ego_graph(G.reverse(), seed, radius=depth).nodes())
                nodes.update(nx.ego_graph(G, seed, radius=depth).nodes())
    return G.subgraph(nodes)

# --- 3. RENDERING ENGINE ---
def render_pyvis_html(G, search_list, theme_cfg):
    net = Network(height="850px", width="100%", bgcolor=theme_cfg['graph_bg'], font_color=theme_cfg['node_font']['color'], directed=True)
    
    try: topo = list(nx.topological_generations(G))
    except: topo = []
    level_map = {node: i for i, layer in enumerate(topo) for node in layer} if topo else {n: 0 for n in G.nodes()}

    for n in G.nodes():
        lvl = level_map.get(n, 0)
        style = theme_cfg['node_default']
        if n in search_list: style = theme_cfg['node_highlight']
        elif G.in_degree(n) == 0: style = theme_cfg['node_start']
        elif G.out_degree(n) == 0: style = theme_cfg['node_end']

        net.add_node(
            n, label=n, title=f"Job: {n}", level=lvl,
            color={
                'background': style['bg'], 'border': style['border'],
                'highlight': {'background': style['bg'], 'border': theme_cfg['glow_color']},
                'hover': {'background': style['bg'], 'border': style['border']}
            },
            font=theme_cfg['node_font'], shape='box', widthConstraint=200, borderWidth=2, margin=12
        )

    for s, t in G.edges():
        net.add_edge(s, t, color=theme_cfg['edge_color'], width=2)

    options_dict = {
        "layout": { "hierarchical": { "enabled": True, "direction": "LR", "sortMethod": "directed", "nodeSpacing": 200, "levelSeparation": 350 } },
        "edges": { "smooth": { "type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.5 } },
        "physics": { "hierarchicalRepulsion": {"nodeDistance": 220}, "stabilization": {"enabled": True, "iterations": 150} },
        # Disable default UI, we inject our own Premium UI
        "interaction": { "hover": True, "navigationButtons": False, "keyboard": True, "multiselect": True, "zoomView": True }
    }
    net.set_options(json.dumps(options_dict))
    html_content = net.generate_html()

    # --- INJECT PREMIUM BUTTONS UI ---
    custom_ui = f"""
    <div class="controls-wrapper">
        <div class="control-group">
            <button id="btnUp" class="ui-btn" title="Up">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 15l-6-6-6 6"/></svg>
            </button>
            <div class="row">
                <button id="btnLeft" class="ui-btn" title="Left">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
                </button>
                <button id="btnDown" class="ui-btn" title="Down">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
                </button>
                <button id="btnRight" class="ui-btn" title="Right">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
                </button>
            </div>
        </div>
        
        <div class="control-group vertical">
            <button id="btnZoomIn" class="ui-btn" title="Zoom In">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            </button>
            <button id="btnZoomOut" class="ui-btn" title="Zoom Out">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            </button>
            <button id="btnFit" class="ui-btn" title="Fit Screen">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>
            </button>
        </div>
    </div>

    <style>
        body {{
            background-color: {theme_cfg['graph_bg']};
            margin: 0; padding: 0;
            border: 1px solid {theme_cfg['input_border']};
            border-radius: 8px;
            overflow: hidden;
        }}
        #mynetwork {{ width: 100%; height: 100vh; }}

        .controls-wrapper {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 15px;
            z-index: 1000;
        }}
        
        .control-group {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 5px;
        }}
        
        .row {{ display: flex; gap: 5px; }}

        .ui-btn {{
            width: 40px; height: 40px;
            background: rgba(30, 30, 30, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            color: #ffffff;
            cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.2s ease;
            backdrop-filter: blur(4px);
        }}
        
        .ui-btn:hover {{
            background: #007bff;
            border-color: #0056b3;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 123, 255, 0.4);
        }}
    </style>

    <script type="text/javascript">
        network.on("afterDrawing", function() {{
            document.getElementById('btnZoomIn').onclick = function() {{ network.moveTo({{scale: network.getScale() + 0.3, animation: true}}); }};
            document.getElementById('btnZoomOut').onclick = function() {{ network.moveTo({{scale: network.getScale() - 0.3, animation: true}}); }};
            document.getElementById('btnFit').onclick = function() {{ network.fit({{animation: {{duration: 1000, easingFunction: 'easeInOutQuad'}} }}); }};
            
            const offset = 100;
            document.getElementById('btnUp').onclick = function() {{ 
                const pos = network.getViewPosition(); 
                network.moveTo({{position: {{x: pos.x, y: pos.y - offset}}, animation: true}}); 
            }};
            document.getElementById('btnDown').onclick = function() {{ 
                const pos = network.getViewPosition(); 
                network.moveTo({{position: {{x: pos.x, y: pos.y + offset}}, animation: true}}); 
            }};
            document.getElementById('btnLeft').onclick = function() {{ 
                const pos = network.getViewPosition(); 
                network.moveTo({{position: {{x: pos.x - offset, y: pos.y}}, animation: true}}); 
            }};
            document.getElementById('btnRight').onclick = function() {{ 
                const pos = network.getViewPosition(); 
                network.moveTo({{position: {{x: pos.x + offset, y: pos.y}}, animation: true}}); 
            }};
        }});
    </script>
    """
    
    html_content = html_content.replace('</head>', f'</head>')
    html_content = html_content.replace('</body>', f'{custom_ui}</body>')
    return html_content

# --- MAIN UI ---
col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
search_list = []
depth_limit = None

if uploaded_file:
    df_jobs, df_edges = parse_controlm_xml(uploaded_file)
    if not df_jobs.empty:
        all_jobs = sorted(df_jobs["JobName"].unique().tolist())
        
        with col1: st.markdown("### 🕸️ Control-M Lineage")
        with col2: sel_jobs = st.multiselect("Select Job(s):", all_jobs, placeholder="Choose Seed Job...")
        with col3: reg_val = st.text_input("Regex Filter", placeholder="e.g. ^PAY.*")
        with col4: 
            unlimited = st.checkbox("Full Depth", value=True)
            if not unlimited: depth_limit = st.number_input("Levels", 1, 10, 3)

        search_list = sel_jobs
        if reg_val:
            try:
                matches = [j for j in all_jobs if re.search(reg_val, j, re.IGNORECASE)]
                search_list = list(set(search_list + matches))
            except: pass

        G_full = build_graph(df_edges, all_jobs)
        
        if search_list:
            G_disp = filter_lineage(G_full, search_list, depth_limit)
            status = f"Filtered: {len(G_disp.nodes)} jobs"
        else:
            if len(G_full) > 500:
                G_disp = nx.DiGraph()
                status = "⚠️ Graph too large (500+). Use filters."
            else:
                G_disp = G_full
                status = f"Full View: {len(G_full)} jobs"

        if len(G_disp) > 0:
            st.caption(f"Status: {status}")
            final_html = render_pyvis_html(G_disp, search_list, theme)
            components.html(final_html, height=860, scrolling=False)
            
            # --- CUSTOMIZED DOWNLOAD BUTTON ---
            st.download_button("💾 Download HTML Report", final_html, "lineage.html", "text/html")
        
        if show_data:
            st.markdown('<div class="data-header">📋 Data Inspector</div>', unsafe_allow_html=True)
            st.dataframe(df_jobs, use_container_width=True)
else:
    st.info("👋 Welcome! Please upload a Control-M XML file in the sidebar to begin.")