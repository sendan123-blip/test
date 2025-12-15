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

# --- 🎨 THEME DEFINITIONS (High Contrast) ---
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
        "nav_btn_filter": "invert(100%) brightness(200%)", # Bright White Icons
        "node_font": {"color": "#ffffff", "size": 20, "face": "Arial"},
        "edge_color": "#666666",
        # Node Colors
        "node_default": {"bg": "#0a2e36", "border": "#00d4ff"}, # Cyan/Teal
        "node_highlight": {"bg": "#4a2c0a", "border": "#ff9900"}, # Orange
        "node_start": {"bg": "#0a3618", "border": "#00ff41"}, # Green
        "node_end": {"bg": "#360a0a", "border": "#ff3333"}, # Red
        "glow_color": "#ffffff" # White glow on click
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
        "nav_btn_filter": "contrast(200%)", # Dark Grey Icons
        "node_font": {"color": "#000000", "size": 20, "face": "Arial"},
        "edge_color": "#555555",
        # Node Colors (High Contrast Pastels)
        "node_default": {"bg": "#bbdefb", "border": "#0d47a1"}, # Blue
        "node_highlight": {"bg": "#ffe0b2", "border": "#e65100"}, # Orange
        "node_start": {"bg": "#c8e6c9", "border": "#1b5e20"}, # Green
        "node_end": {"bg": "#ffcdd2", "border": "#b71c1c"}, # Red
        "glow_color": "#ff0000" # Red glow on click
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

# --- CSS INJECTION (The "Visibility Fix") ---
st.markdown(f"""
<style>
    /* 1. RESET STREAMLIT DEFAULTS */
    .stApp {{ background-color: {theme['bg_color']}; color: {theme['text_color']}; }}
    [data-testid="stSidebar"] {{ background-color: {theme['sidebar_bg']}; border-right: 1px solid #ccc; }}
    
    /* 2. TEXT VISIBILITY (Headers, Labels) - FORCED BOLD */
    h1, h2, h3, p, label, .stMarkdown {{ 
        color: {theme['text_color']} !important; 
        font-weight: 500 !important;
    }}
    
    /* 3. INPUT FIELDS (Dropdowns, Text Boxes) - HIGH CONTRAST */
    .stTextInput > div > div > input,
    .stMultiSelect > div > div > div,
    .stNumberInput > div > div > input {{
        background-color: {theme['input_bg']} !important;
        color: {theme['input_text']} !important;
        border: 1px solid {theme['input_border']} !important;
        font-weight: 600 !important; /* Thicker text */
    }}
    
    /* 4. PLACEHOLDER TEXT VISIBILITY */
    /* This targets the "Choose option..." text specifically */
    input::placeholder {{ color: {theme['placeholder']} !important; opacity: 1; }}
    .stMultiSelect div[role="button"] p {{ color: {theme['placeholder']} !important; font-weight: 600; }}
    .stMultiSelect span {{ color: {theme['input_text']} !important; }} 
    
    /* 5. NAVIGATION BUTTONS (Zoom/Pan) */
    .vis-network .vis-navigation .vis-button {{
        filter: {theme['nav_btn_filter']} !important;
    }}

    /* 6. GRAPH CONTAINER - NO MARGINS (Fixes Black Box) */
    .graph-container {{
        border: 1px solid {theme['input_border']};
        border-radius: 4px;
        background-color: {theme['graph_bg']};
        width: 100%;
        height: 850px;
        padding: 0px; 
        margin: 0px;
        overflow: hidden;
    }}
    iframe {{ width: 100% !important; height: 850px !important; }}

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
def render_pyvis(G, search_list, theme_cfg):
    # Set height to 100% to fill the Streamlit container
    net = Network(height="850px", width="100%", bgcolor=theme_cfg['graph_bg'], font_color=theme_cfg['node_font']['color'], directed=True)
    
    try:
        topo = list(nx.topological_generations(G))
        level_map = {node: i for i, layer in enumerate(topo) for node in layer}
    except:
        level_map = {n: 0 for n in G.nodes()}

    for n in G.nodes():
        lvl = level_map.get(n, 0)
        
        # Style Logic
        style = theme_cfg['node_default']
        if n in search_list: style = theme_cfg['node_highlight']
        elif G.in_degree(n) == 0: style = theme_cfg['node_start']
        elif G.out_degree(n) == 0: style = theme_cfg['node_end']

        net.add_node(
            n, label=n, title=f"Job: {n}\n(Click to highlight connections)", 
            level=lvl,
            color={
                'background': style['bg'], 
                'border': style['border'],
                'highlight': {'background': style['bg'], 'border': theme_cfg['glow_color']}, # Glow Color
                'hover': {'background': style['bg'], 'border': style['border']}
            },
            font=theme_cfg['node_font'],
            shape='box', 
            widthConstraint=200, # Wrap text
            borderWidth=2, margin=12
        )

    for s, t in G.edges():
        net.add_edge(s, t, color=theme_cfg['edge_color'], width=2)

    # VIS.JS OPTIONS (Python Dict to avoid JSON Errors)
    options_dict = {
        "layout": {
            "hierarchical": {
                "enabled": True,
                "direction": "LR",
                "sortMethod": "directed",
                "nodeSpacing": 200,
                "levelSeparation": 350
            }
        },
        "edges": {
            "smooth": {
                "type": "cubicBezier",
                "forceDirection": "horizontal",
                "roundness": 0.5
            }
        },
        "physics": {
            "hierarchicalRepulsion": {"nodeDistance": 220},
            "stabilization": {"enabled": True, "iterations": 100}
        },
        "interaction": {
            "hover": True,
            "navigationButtons": True,
            "keyboard": True,
            "multiselect": True,
            "zoomView": True,
            "selectConnectedEdges": True # Helps with highlighting
        }
    }
    
    net.set_options(json.dumps(options_dict))
    return net

# --- MAIN UI ---
col1, col2, col3, col4 = st.columns([1, 2, 1, 1])

search_list = []
depth_limit = None

if uploaded_file:
    df_jobs, df_edges = parse_controlm_xml(uploaded_file)
    if not df_jobs.empty:
        all_jobs = sorted(df_jobs["JobName"].unique().tolist())
        
        with col1:
            st.markdown("### 🕸️ Lineage")
        with col2:
            sel_jobs = st.multiselect("Select Job(s):", all_jobs, placeholder="Choose Seed Job...")
        with col3:
            reg_val = st.text_input("Regex Filter", placeholder="e.g. ^PAY.*")
        with col4:
            unlimited = st.checkbox("Full Depth", value=True)
            if not unlimited:
                depth_limit = st.number_input("Levels", 1, 10, 3)

        search_list = sel_jobs
        if reg_val:
            try:
                matches = [j for j in all_jobs if re.search(reg_val, j, re.IGNORECASE)]
                search_list = list(set(search_list + matches))
            except: pass

        # Build & Filter
        G_full = build_graph(df_edges, all_jobs)
        
        if search_list:
            G_disp = filter_lineage(G_full, search_list, depth_limit)
            status = f"Filtered View: {len(G_disp.nodes)} jobs"
        else:
            if len(G_full) > 500:
                G_disp = nx.DiGraph()
                status = "⚠️ Graph too large (500+). Use filters."
            else:
                G_disp = G_full
                status = f"Full View: {len(G_full)} jobs"

        # Render
        if len(G_disp) > 0:
            st.caption(f"Status: {status}")
            net = render_pyvis(G_disp, search_list, theme)
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                    net.save_graph(tmp.name)
                    path = tmp.name
                
                with open(path, 'r', encoding='utf-8') as f:
                    html_bytes = f.read()

                # GRAPH CONTAINER
                st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                components.html(html_bytes, height=850, scrolling=False)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Download
                st.download_button("💾 Download HTML Report", html_bytes, "lineage.html", "text/html")
                os.remove(path)
            except Exception as e:
                st.error(f"Render Error: {e}")
        
        if show_data:
            st.divider()
            st.dataframe(df_jobs)
else:
    st.info("👋 Welcome! Please upload a Control-M XML file in the sidebar to begin.")