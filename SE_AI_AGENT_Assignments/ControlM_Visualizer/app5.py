import streamlit as st
import pandas as pd
import networkx as nx
import xml.etree.ElementTree as ET
from pyvis.network import Network
import tempfile
import os
import re
import streamlit.components.v1 as components

# --- PAGE CONFIGURATION ---
st.set_page_config(
    layout="wide", 
    page_title="Control-M Lineage", 
    page_icon="🕸️",
    initial_sidebar_state="expanded"
)

# --- THEME MANAGEMENT ---
# We define color palettes for both modes here
THEMES = {
    "Dark": {
        "page_bg": "#0e0e0e",
        "text": "#e0e0e0",
        "sidebar_bg": "#161616",
        "input_bg": "#262626",
        "graph_bg": "#121212",
        "node_default_bg": "#0a2e36", # Dark Teal
        "node_default_border": "#00d4ff", # Neon Cyan
        "node_text": "#ffffff",
        "edge_color": "#005f73",
        "nav_filter": "invert(23%) sepia(98%) saturate(7472%) hue-rotate(358deg) brightness(96%) contrast(115%)" # Red
    },
    "Light": {
        "page_bg": "#ffffff",
        "text": "#000000",
        "sidebar_bg": "#f8f9fa",
        "input_bg": "#ffffff",
        "graph_bg": "#ffffff",
        "node_default_bg": "#e3f2fd", # Light Blue
        "node_default_border": "#1565c0", # Dark Blue
        "node_text": "#000000",
        "edge_color": "#b0bec5", # Grey
        "nav_filter": "invert(100%)" # Standard Grey/Black buttons
    }
}

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # 1. THEME TOGGLE
    theme_mode = st.radio("Display Mode:", ["Dark", "Light"], horizontal=True)
    current_theme = THEMES[theme_mode]
    
    st.divider()
    
    # 2. UPLOAD
    uploaded_file = st.file_uploader("Upload XML", type=["xml"])
    show_data = st.checkbox("Show Data Tables", value=False)
    
    st.info("💡 Tip: Use Light Mode for printing PDFs.")

# --- DYNAMIC CSS GENERATION ---
css_styles = f"""
<style>
    /* GLOBAL THEME */
    .stApp {{ background-color: {current_theme['page_bg']}; color: {current_theme['text']}; }}
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: {current_theme['sidebar_bg']}; border-right: 1px solid #333; }}
    
    /* INPUT FIELDS */
    .stTextInput > div > div > input, 
    .stMultiSelect > div > div > div, 
    .stNumberInput > div > div > input {{
        background-color: {current_theme['input_bg']}; 
        color: {current_theme['text']}; 
        border: 1px solid #444;
    }}
    
    /* NAVIGATION BUTTONS (RED in Dark, Standard in Light) */
    .vis-network .vis-navigation .vis-button {{
        filter: {current_theme['nav_filter']} !important;
        opacity: 0.9;
    }}
    .vis-network .vis-navigation .vis-button:hover {{
        opacity: 1;
    }}
    
    /* GRAPH CONTAINER */
    .graph-container {{
        border: 1px solid #333;
        border-radius: 8px;
        background-color: {current_theme['graph_bg']}; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        width: 100%;
        height: 900px;
        position: relative;
    }}
    
    /* LAYOUT TWEAKS */
    .main .block-container {{ padding-top: 1rem; max-width: 100%; }}
    footer {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
</style>
"""
st.markdown(css_styles, unsafe_allow_html=True)

# --- 1. XML PARSING LOGIC ---
@st.cache_data
def parse_controlm_xml(uploaded_file):
    try:
        tree = ET.parse(uploaded_file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"XML Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

    jobs_data = []
    conditions_map = {}

    for job in root.findall(".//JOB"):
        job_name = job.get("JOBNAME")
        folder = job.get("PARENT_FOLDER") or "Root"
        
        current_job = {
            "JobName": job_name,
            "Folder": folder,
            "InConditions": [],
            "OutConditions": []
        }

        # Out-Conditions
        for out in job.findall("OUTCOND"):
            cond_name = out.get("NAME")
            if out.get("SIGN") == "+" and out.get("ODATE") == "ODAT":
                current_job["OutConditions"].append(cond_name)
                if cond_name not in conditions_map: conditions_map[cond_name] = []
                conditions_map[cond_name].append(job_name)

        # In-Conditions
        for incon in job.findall("INCOND"):
            if incon.get("ODATE") == "ODAT": 
                current_job["InConditions"].append(incon.get("NAME"))
        
        jobs_data.append(current_job)

    edges = []
    for job in jobs_data:
        consumer = job["JobName"]
        for cond in job["InConditions"]:
            if cond in conditions_map:
                for producer in conditions_map[cond]:
                    edges.append({"Source": producer, "Target": consumer, "Condition": cond})
    
    return pd.DataFrame(jobs_data), pd.DataFrame(edges)

# --- 2. GRAPH LOGIC ---
def build_network_graph(df_edges, all_jobs):
    G = nx.DiGraph()
    G.add_nodes_from(all_jobs)
    for _, row in df_edges.iterrows():
        G.add_edge(row["Source"], row["Target"], label=row["Condition"])
    return G

# --- 2b. DEPTH-AWARE LINEAGE ---
def get_lineage_subgraph(G, search_jobs, depth=None):
    nodes = set()
    for job in search_jobs:
        job = job.strip()
        if job in G.nodes:
            nodes.add(job)
            
            if depth is None:
                nodes.update(nx.ancestors(G, job))
                nodes.update(nx.descendants(G, job))
            else:
                upstream = nx.ego_graph(G.reverse(), job, radius=depth)
                nodes.update(upstream.nodes())
                downstream = nx.ego_graph(G, job, radius=depth)
                nodes.update(downstream.nodes())
                
    return G.subgraph(nodes)

# --- 3. GRAPH RENDERING ---
def render_graph(G, search_list, theme):
    # Set PyVis height to match container
    net = Network(height="900px", width="100%", bgcolor=theme['graph_bg'], font_color=theme['text'], directed=True)
    
    try:
        topo = list(nx.topological_generations(G))
        level_map = {node: i for i, layer in enumerate(topo) for node in layer}
    except:
        level_map = {node: 0 for node in G.nodes()}

    for node in G.nodes():
        level = level_map.get(node, 0)
        
        # DEFAULT COLORS FROM THEME
        bg_color = theme['node_default_bg']
        border_color = theme['node_default_border']
        text_color = theme['node_text']
        
        # HIGHLIGHT COLORS (Mode Dependent)
        if node in search_list:
            bg_color = "#ff9800" if theme_mode == "Dark" else "#ffe0b2" # Orange
            border_color = "#e65100"
        elif G.in_degree(node) == 0:
            bg_color = "#2e7d32" if theme_mode == "Dark" else "#c8e6c9" # Green
            border_color = "#1b5e20"
        elif G.out_degree(node) == 0:
            bg_color = "#c62828" if theme_mode == "Dark" else "#ffcdd2" # Red
            border_color = "#b71c1c"

        # NODE CONFIGURATION
        net.add_node(node, label=node, title=f"{node}", 
                     color={
                         'background': bg_color, 
                         'border': border_color,
                         'highlight': {'background': bg_color, 'border': '#FFD700'}, # Gold highlight
                         'hover': {'background': bg_color, 'border': border_color}
                     },
                     borderWidth=2, 
                     borderWidthSelected=3,
                     shape="box", 
                     # FORCE TEXT WRAPPING
                     widthConstraint=200, 
                     font={'size': 18, 'face': 'Segoe UI', 'color': text_color}, 
                     level=level, margin=10)

    for s, t, d in G.edges(data=True):
        net.add_edge(s, t, color=theme['edge_color'], width=2)

    # VIS.JS OPTIONS - Fixed Spacing & Layout
    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "nodeSpacing": 200, 
          "levelSeparation": 300
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
          "hierarchicalRepulsion": { "nodeDistance": 220 },
          "stabilization": { "enabled": true, "iterations": 100 }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true,
        "multiselect": true,
        "zoomView": true
      }
    }
    """)
    return net

# --- MAIN UI BODY ---
col1, col2, col3, col4, col5 = st.columns([1.5, 2, 1.5, 1, 1])

search_list = []
depth_limit = None

if uploaded_file:
    df_jobs, df_edges = parse_controlm_xml(uploaded_file)
    if not df_jobs.empty:
        all_jobs = sorted(df_jobs["JobName"].unique().tolist())
        
        with col1: 
            st.markdown(f"### 🕸️ Lineage Ops")
        
        with col2:
            sel_jobs = st.multiselect("Select Seed Job(s):", all_jobs, label_visibility="collapsed", placeholder="Select Seed Job...")
        with col3:
            reg_val = st.text_input("Regex", label_visibility="collapsed", placeholder="Regex Filter (e.g. ^PAY.*)")
        with col4:
            unlimited = st.checkbox("Unlimited Depth", value=True)
        with col5:
             if not unlimited:
                 depth_limit = st.number_input("Levels", min_value=1, value=3, label_visibility="collapsed")
             else:
                 depth_limit = None 

        # MERGE FILTERS
        search_list = sel_jobs
        if reg_val:
            try:
                matches = [j for j in all_jobs if re.search(reg_val, j, re.IGNORECASE)]
                search_list = list(set(search_list + matches))
            except: pass

        # BUILD GRAPH
        G_full = build_network_graph(df_edges, df_jobs["JobName"].tolist())
        
        if search_list:
            G_display = get_lineage_subgraph(G_full, search_list, depth=depth_limit)
            status = f"TRACING {len(search_list)} SEEDS ({len(G_display.nodes)} Related Jobs)"
        else:
            if len(G_full.nodes) > 400:
                G_display = nx.DiGraph()
                status = "WAITING FOR INPUT"
            else:
                G_display = G_full
                status = f"FULL VIEW ({len(G_full.nodes)} JOBS)"
        
        # RENDER GRAPH
        if len(G_display.nodes) > 0:
            net = render_graph(G_display, search_list, current_theme)
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                    net.save_graph(tmp.name)
                    path = tmp.name
                with open(path, 'r', encoding='utf-8') as f:
                    html_bytes = f.read()
                
                # STATUS & DOWNLOAD ROW
                d_col1, d_col2 = st.columns([4, 1])
                with d_col1:
                    st.markdown(f"**Status: {status}**")
                with d_col2:
                    st.download_button(
                        label="📄 Download HTML", 
                        data=html_bytes, 
                        file_name="lineage_report.html", 
                        mime="text/html"
                    )

                # GRAPH CONTAINER
                st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                components.html(html_bytes, height=900, scrolling=False)
                st.markdown('</div>', unsafe_allow_html=True)
                os.remove(path)
            except Exception as e:
                st.error(f"Render Error: {e}")
        
        if show_data:
            st.divider()
            st.dataframe(df_jobs)
else:
    st.info("👈 Please upload a Control-M XML file in the sidebar.")