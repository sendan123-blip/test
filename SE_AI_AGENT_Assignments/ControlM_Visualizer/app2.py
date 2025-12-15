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
st.set_page_config(layout="wide", page_title="Control-M Lineage (Dark Mode)", page_icon="🕸️")

# --- 🌑 DARK MODE & "CONTROL ROOM" CSS ---
st.markdown("""
<style>
    /* 1. GLOBAL DARK THEME */
    .stApp {
        background-color: #121212; /* Deep Black/Grey */
        color: #e0e0e0;
    }
    
    /* 2. SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #1e1e1e;
        border-right: 1px solid #333;
    }
    
    /* 3. TEXT & HEADERS */
    h1, h2, h3, p, label {
        color: #e0e0e0 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }
    
    /* 4. INPUT FIELDS (Dark Grey) */
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea,
    .stMultiSelect > div > div > div {
        background-color: #2d2d2d;
        color: #ffffff;
        border: 1px solid #444;
        border-radius: 4px;
    }
    
    /* 5. BUTTONS (Neon Blue) */
    div[data-testid="stButton"] button {
        background-color: #007acc !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        font-weight: 600 !important;
        transition: all 0.2s;
    }
    div[data-testid="stButton"] button:hover {
        background-color: #009be5 !important;
        box-shadow: 0 0 10px #009be5;
    }

    /* 6. GRAPH CONTAINER */
    .graph-container {
        border: 1px solid #444;
        border-radius: 8px;
        background-color: #1e1e1e; /* Matches PyVis background */
        padding: 5px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    
    /* 7. UPLOAD BOX */
    [data-testid="stFileUploader"] {
        background-color: #1e1e1e;
        border: 1px dashed #555;
        border-radius: 8px;
        padding: 15px;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- 1. XML PARSING LOGIC (Same Robust Engine) ---
@st.cache_data
def parse_controlm_xml(uploaded_file):
    try:
        tree = ET.parse(uploaded_file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"Failed to parse XML: {e}")
        return pd.DataFrame(), pd.DataFrame()

    jobs_data = []
    conditions_map = {}

    for job in root.findall(".//JOB"):
        job_name = job.get("JOBNAME")
        folder = job.get("PARENT_FOLDER") or "Root"
        job_type = job.get("TASKTYPE") or "Command"
        
        current_job = {
            "JobName": job_name,
            "Folder": folder,
            "Type": job_type,
            "InConditions": [],
            "OutConditions": []
        }

        for out in job.findall("OUTCOND"):
            cond_name = out.get("NAME")
            sign = out.get("SIGN")
            odate = out.get("ODATE")
            if sign == "+" and odate == "ODAT":
                current_job["OutConditions"].append(cond_name)
                if cond_name not in conditions_map:
                    conditions_map[cond_name] = []
                conditions_map[cond_name].append(job_name)

        for incon in job.findall("INCOND"):
            cond_name = incon.get("NAME")
            odate = incon.get("ODATE")
            if odate == "ODAT": 
                current_job["InConditions"].append(cond_name)
        
        jobs_data.append(current_job)

    edges = []
    for job in jobs_data:
        consumer_job = job["JobName"]
        for cond in job["InConditions"]:
            if cond in conditions_map:
                for producer_job in conditions_map[cond]:
                    edges.append({
                        "Source": producer_job,
                        "Target": consumer_job,
                        "Condition": cond
                    })
    
    return pd.DataFrame(jobs_data), pd.DataFrame(edges)

# --- 2. GRAPH & SEARCH LOGIC ---
def build_network_graph(df_edges, all_jobs_list):
    G = nx.DiGraph()
    G.add_nodes_from(all_jobs_list)
    for _, row in df_edges.iterrows():
        G.add_edge(row["Source"], row["Target"], label=row["Condition"])
    return G

def get_full_lineage_subgraph(G, search_jobs):
    relevant_nodes = set()
    for job in search_jobs:
        job = job.strip()
        if job in G.nodes:
            relevant_nodes.add(job)
            relevant_nodes.update(nx.ancestors(G, job))
            relevant_nodes.update(nx.descendants(G, job))
    return G.subgraph(relevant_nodes)

# --- 3. PYVIS GRAPH STYLING (MATCHING THE SCREENSHOT) ---
def render_interactive_graph(G, search_jobs_list):
    # DARK BACKGROUND (Hex #1e1e1e matches the container)
    net = Network(height="800px", width="100%", bgcolor="#1e1e1e", font_color="#e0e0e0", directed=True)
    
    # Calculate Levels for Hierarchy
    try:
        topo_gen = list(nx.topological_generations(G))
        level_map = {}
        for layer_idx, layer_nodes in enumerate(topo_gen):
            for node in layer_nodes:
                level_map[node] = layer_idx
    except:
        level_map = {node: 0 for node in G.nodes()}

    for node in G.nodes():
        level = level_map.get(node, 0)
        
        # --- SCREENSHOT STYLE MATCHING ---
        # Default: Neon Cyan Border, Dark Fill
        bg_color = "#0a2e36"   # Dark Cyan/Teal
        border_color = "#00d4ff" # Neon Cyan
        border_width = 2
        font_size = 16
        shape_type = "box"
        
        # SEARCHED / SELECTED NODES (Orange in your screenshot)
        if node in search_jobs_list:
            bg_color = "#4a2c0a" # Dark Orange
            border_color = "#ff9900" # Neon Orange
            border_width = 4
            font_size = 20
        
        # START NODES (Greenish in your screenshot)
        elif G.in_degree(node) == 0:
            bg_color = "#0a3618" 
            border_color = "#00ff41" # Matrix Green
        
        # END NODES (Reddish)
        elif G.out_degree(node) == 0:
            bg_color = "#360a0a"
            border_color = "#ff3333"

        net.add_node(node, label=node, title=f"Job: {node}\nLevel: {level}", 
                     color={'background': bg_color, 'border': border_color, 
                            'highlight': {'border': '#ffffff', 'background': '#555555'}}, # Click Highlight
                     borderWidth=border_width, 
                     shape=shape_type, 
                     font={'size': font_size, 'face': 'Segoe UI', 'color': '#ffffff'},
                     level=level,
                     margin=10)

    for source, target, data in G.edges(data=True):
        # Neon Blue Edges
        net.add_edge(source, target, color="#007acc", width=1.5, arrowStrikethrough=False, 
                     title=f"Condition: {data.get('label')}")

    # --- INTERACTION SETTINGS ---
    # This enables the "Click to Highlight" functionality you requested
    net.set_options("""
    var options = {
      "nodes": {
        "shape": "box",
        "font": { "size": 16 }
      },
      "edges": {
        "color": { "inherit": false },
        "smooth": { "type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.4 }
      },
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "nodeSpacing": 200,
          "levelSeparation": 250
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true,
        "multiselect": true 
      },
      "physics": {
        "hierarchicalRepulsion": {
            "nodeDistance": 200,
            "damping": 0.09
        }
      }
    }
    """)
    return net

# --- MAIN UI LAYOUT ---

st.title("Control-M Lineage Enhanced")
st.markdown("Job Dependencies (Offline Compatible)")

# TOP BAR LAYOUT (Mimicking the screenshot controls)
col1, col2, col3 = st.columns([1, 4, 1])

with col1:
    with st.expander("📂 Upload & Settings", expanded=True):
        uploaded_file = st.file_uploader("Upload XML", type=["xml"], label_visibility="collapsed")
        show_data = st.checkbox("Show Data Tables", value=False)

search_list = []

if uploaded_file:
    df_jobs, df_edges = parse_controlm_xml(uploaded_file)
    if not df_jobs.empty:
        all_jobs = sorted(df_jobs["JobName"].unique().tolist())
        
        # SEARCH BAR IN THE MIDDLE (Like a dashboard tool)
        with col2:
            # 1. Regex/Text Search
            col_search_a, col_search_b = st.columns([2, 1])
            with col_search_a:
                selected_jobs = st.multiselect("Select Job(s) to Trace:", all_jobs)
            with col_search_b:
                regex_val = st.text_input("Regex Filter:", placeholder="e.g. ^PAYROLL.*")

            # Logic to Combine Filters
            search_list = selected_jobs
            if regex_val:
                try:
                    regex_matches = [j for j in all_jobs if re.search(regex_val, j, re.IGNORECASE)]
                    search_list = list(set(search_list + regex_matches))
                except:
                    st.error("Invalid Regex")

        # RENDER LOGIC
        G_full = build_network_graph(df_edges, df_jobs["JobName"].tolist())
        
        if search_list:
            G_display = get_full_lineage_subgraph(G_full, search_list)
            status_text = f"Rendered: {len(search_list)} Seed Jobs | Depth: Full | Nodes: {len(G_display.nodes)}"
        else:
            if len(G_full.nodes) > 500:
                st.warning("⚠️ Graph too large. Use search filter.")
                G_display = nx.DiGraph()
                status_text = "Waiting for input..."
            else:
                G_display = G_full
                status_text = f"Full View: {len(G_full.nodes)} Jobs"
        
        # STATUS INDICATOR (Top Right)
        with col3:
            st.info(status_text)

        # GRAPH RENDERING
        if len(G_display.nodes) > 0:
            net = render_interactive_graph(G_display, search_list)
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
                    net.save_graph(tmp_file.name)
                    tmp_file_path = tmp_file.name
                
                with open(tmp_file_path, 'r', encoding='utf-8') as f:
                    html_bytes = f.read()

                # RENDER GRAPH IN DARK CONTAINER
                st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                components.html(html_bytes, height=800, scrolling=False)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Legend (Matches Screenshot Colors)
                st.markdown("""
                <div style='margin-top: 10px; display: flex; gap: 20px; color: #aaa; font-size: 0.9em;'>
                    <span><span style='color:#00ff41'>■</span> Start</span>
                    <span><span style='color:#ff9900'>■</span> Selected/Seed</span>
                    <span><span style='color:#ff3333'>■</span> End</span>
                    <span><span style='color:#00d4ff'>■</span> Normal Job</span>
                </div>
                """, unsafe_allow_html=True)

                os.remove(tmp_file_path)

            except Exception as e:
                st.error(f"Graph Error: {e}")
        
        # DATA TABLES (Optional Toggle)
        if show_data:
            st.divider()
            t1, t2 = st.tabs(["Jobs List", "Edges"])
            with t1: st.dataframe(df_jobs, use_container_width=True)
            with t2: st.dataframe(df_edges, use_container_width=True)

else:
    # Empty State - Dark Mode
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; color: #555;">
        <h2>No Data Loaded</h2>
        <p>Please upload a Control-M XML file to begin.</p>
    </div>
    """, unsafe_allow_html=True)