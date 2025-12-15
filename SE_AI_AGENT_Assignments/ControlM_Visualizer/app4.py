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
    page_title="Control-M Lineage (Dark Ops)", 
    page_icon="🕸️",
    initial_sidebar_state="expanded"
)

# --- 🎨 CSS STYLING ---
st.markdown("""
<style>
    /* 1. GLOBAL DARK THEME */
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    
    /* 2. INPUTS & SIDEBAR */
    [data-testid="stSidebar"] { background-color: #161616; border-right: 1px solid #333; }
    .stTextInput > div > div > input, 
    .stMultiSelect > div > div > div, 
    .stNumberInput > div > div > input {
        background-color: #262626; color: white; border: 1px solid #444;
    }
    
    /* 3. NAVIGATION BUTTONS VISIBILITY FIX */
    /* We use a CSS filter to turn the default green buttons into Bright White/Grey */
    .vis-network .vis-navigation .vis-button {
        filter: brightness(3) grayscale(1) !important; 
        opacity: 0.9;
    }
    .vis-network .vis-navigation .vis-button:hover {
        filter: brightness(4) grayscale(1) !important;
        opacity: 1;
    }
    
    /* 4. GRAPH CONTAINER */
    .graph-container {
        border: 1px solid #333;
        border-radius: 4px;
        background-color: #121212; 
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.05);
        width: 100%;
        position: relative;
    }
    
    /* 5. LAYOUT TWEAKS */
    .main .block-container { padding-top: 1rem; max-width: 100%; }
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

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
                # Unlimited Depth
                nodes.update(nx.ancestors(G, job))
                nodes.update(nx.descendants(G, job))
            else:
                # Limited Depth
                upstream = nx.ego_graph(G.reverse(), job, radius=depth)
                nodes.update(upstream.nodes())
                downstream = nx.ego_graph(G, job, radius=depth)
                nodes.update(downstream.nodes())
                
    return G.subgraph(nodes)

# --- 3. GRAPH RENDERING ---
def render_graph(G, search_list):
    net = Network(height="85vh", width="100%", bgcolor="#121212", font_color="#e0e0e0", directed=True)
    
    try:
        topo = list(nx.topological_generations(G))
        level_map = {node: i for i, layer in enumerate(topo) for node in layer}
    except:
        level_map = {node: 0 for node in G.nodes()}

    for node in G.nodes():
        level = level_map.get(node, 0)
        
        # COLOR LOGIC
        bg_color = "#0a2e36"   # Dark Teal
        border_color = "#00d4ff" # Neon Cyan
        
        if node in search_list:
            bg_color = "#4a2c0a" # Orange
            border_color = "#ff9900" 
        elif G.in_degree(node) == 0:
            bg_color = "#0a3618" # Green
            border_color = "#00ff41" 
        elif G.out_degree(node) == 0:
            bg_color = "#360a0a" # Red
            border_color = "#ff3333"

        # NODE CONFIG
        net.add_node(node, label=node, title=f"{node}", 
                     color={
                         'background': bg_color, 
                         'border': border_color,
                         'highlight': {'background': bg_color, 'border': '#ffffff'},
                         'hover': {'background': '#1f1f1f', 'border': border_color}
                     },
                     borderWidth=2, borderWidthSelected=4,
                     shape="box", 
                     font={'size': 20, 'face': 'Segoe UI', 'color': '#ffffff'}, 
                     level=level, margin=14)

    for s, t, d in G.edges(data=True):
        net.add_edge(s, t, color="#005f73", width=2)

    # VIS.JS OPTIONS - CURVY ARROWS ENABLED
    net.set_options("""
    var options = {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "nodeSpacing": 200, 
          "levelSeparation": 280
        }
      },
      "edges": {
        "smooth": {
            "type": "cubicBezier",
            "forceDirection": "horizontal",
            "roundness": 0.4
        }
      },
      "physics": { "hierarchicalRepulsion": { "nodeDistance": 220 } },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true,
        "multiselect": true,
        "selectConnectedEdges": true
      }
    }
    """)
    return net

# --- MAIN UI ---
with st.sidebar:
    st.header("Settings")
    uploaded_file = st.file_uploader("Upload XML", type=["xml"])
    show_data = st.checkbox("Show Data Tables", value=False)

# COMPACT FILTER BAR
col1, col2, col3, col4, col5 = st.columns([1.5, 2, 1.5, 1, 1])

search_list = []
depth_limit = None

if uploaded_file:
    df_jobs, df_edges = parse_controlm_xml(uploaded_file)
    if not df_jobs.empty:
        all_jobs = sorted(df_jobs["JobName"].unique().tolist())
        
        with col1: st.markdown("### 🕸️ Lineage Ops")
        
        with col2:
            sel_jobs = st.multiselect("Select Seed Job(s):", all_jobs, label_visibility="collapsed", placeholder="Choose Seed Job...")

        with col3:
            reg_val = st.text_input("Regex", label_visibility="collapsed", placeholder="Regex Filter (e.g. ^PAY.*)")

        with col4:
            unlimited = st.checkbox("Unlimited Depth", value=True)
            
        with col5:
             if not unlimited:
                 depth_val = st.number_input("Levels", min_value=1, value=3, label_visibility="collapsed")
                 depth_limit = depth_val
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
            status = f"🟢 TRACING {len(search_list)} SEEDS"
            if depth_limit: status += f" (Depth: {depth_limit})"
        else:
            if len(G_full.nodes) > 400:
                G_display = nx.DiGraph()
                status = "🟡 WAITING FOR INPUT"
            else:
                G_display = G_full
                status = f"🔵 FULL VIEW ({len(G_full.nodes)} JOBS)"
        
        # RENDER GRAPH
        if len(G_display.nodes) > 0:
            net = render_graph(G_display, search_list)
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                    net.save_graph(tmp.name)
                    path = tmp.name
                with open(path, 'r', encoding='utf-8') as f:
                    html_bytes = f.read()
                
                st.markdown(f"**{status}**")
                st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                components.html(html_bytes, height=850, scrolling=False)
                st.markdown('</div>', unsafe_allow_html=True)
                os.remove(path)
            except Exception as e:
                st.error(f"Render Error: {e}")
        
        if show_data:
            st.divider()
            st.dataframe(df_jobs)
else:
    st.info("Please upload a Control-M XML file.")