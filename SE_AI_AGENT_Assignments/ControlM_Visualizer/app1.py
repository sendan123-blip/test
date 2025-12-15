import streamlit as st
import pandas as pd
import networkx as nx
import xml.etree.ElementTree as ET
from pyvis.network import Network
import tempfile
import os
import streamlit.components.v1 as components

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Lineage X-Ray", page_icon="🕸️")

# --- APPLE / NEXT-GEN CSS INJECTION ---
st.markdown("""
<style>
    /* 1. GLOBAL TYPOGRAPHY & BACKGROUND */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        color: #1d1d1f;
    }
    
    /* Main App Background - Apple Light Grey */
    .stApp {
        background-color: #F5F5F7;
    }

    /* 2. SIDEBAR STYLING (Glassmorphismish) */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #d2d2d7;
        box-shadow: 4px 0 24px rgba(0,0,0,0.02);
    }
    
    /* 3. HEADERS & TITLES */
    h1 {
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #1d1d1f;
        padding-bottom: 10px;
    }
    
    h2, h3 {
        font-weight: 600;
        color: #1d1d1f;
    }

    /* 4. CARDS & CONTAINERS (The "Island" Look) */
    /* We will use st.container() later, but this targets dataframes and charts */
    .stDataFrame, .stPlotlyChart {
        background: white;
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #e5e5ea;
    }

    /* 5. BUTTONS (Apple "Pill" Style) */
    .stButton > button {
        background-color: #0071e3 !important; /* Apple Blue */
        color: white !important;
        border-radius: 980px !important; /* Pill shape */
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 500 !important;
        font-size: 15px !important;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0,113,227,0.3);
    }
    
    .stButton > button:hover {
        background-color: #0077ED !important;
        transform: scale(1.02);
        box-shadow: 0 4px 12px rgba(0,113,227,0.4);
    }

    /* 6. INPUT FIELDS & WIDGETS */
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea,
    .stMultiSelect > div > div > div {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #d2d2d7;
        color: #1d1d1f;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #0071e3;
        box-shadow: 0 0 0 4px rgba(0,113,227,0.1);
    }

    /* 7. UPLOAD BOX */
    [data-testid="stFileUploader"] {
        border-radius: 18px;
        border: 1px dashed #d2d2d7;
        padding: 20px;
        background: #fafafa;
        transition: border 0.3s;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: #0071e3;
        background: #f0f8ff;
    }

    /* 8. SCROLLBARS (Hidden/Sleek) */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: transparent; 
    }
    ::-webkit-scrollbar-thumb {
        background: #c1c1c1; 
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8; 
    }
    
    /* 9. RESPONSIVE TEXT FOR MOBILE */
    @media (max-width: 640px) {
        h1 { font-size: 24px; }
        .stButton > button { width: 100%; }
    }
</style>
""", unsafe_allow_html=True)

# --- 1. XML PARSING ENGINE ---
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

# --- 2. GRAPH LOGIC ---
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

# --- 3. VISUALIZATION ENGINE ---
def render_interactive_graph(G, search_jobs_list):
    # Using a clean white background for the network canvas
    net = Network(height="700px", width="100%", bgcolor="#ffffff", font_color="#1d1d1f", directed=True)
    
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
        
        # Apple-inspired Pastel Palette
        palette = ["#E3F2FD", "#FFF3E0", "#E8F5E9", "#F3E5F5", "#E0F7FA", "#FFEBEE"]
        border_palette = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0", "#00BCD4", "#F44336"]
        
        color_bg = palette[level % len(palette)]
        border_col = border_palette[level % len(border_palette)]
        border_w = 1
        
        # Highlight Logic
        if node in search_jobs_list:
            color_bg = "#FFF9C4" # Light Amber
            border_col = "#FFC107" # Deep Amber
            border_w = 3

        if G.in_degree(node) == 0:
            border_col = "#2E7D32" # Dark Green
            border_w = 4

        if G.out_degree(node) == 0:
            border_col = "#D32F2F" # Dark Red
            border_w = 4
        
        net.add_node(node, label=node, title=f"{node}", 
                     color={'background': color_bg, 'border': border_col},
                     borderWidth=border_w, shape="box", 
                     font={'size': 14, 'face': 'Inter'},
                     level=level)

    for source, target, data in G.edges(data=True):
        net.add_edge(source, target, color="#BDBDBD", width=1)

    net.set_options("""
    var options = {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "nodeSpacing": 160,
          "levelSeparation": 220
        }
      },
      "physics": {
        "hierarchicalRepulsion": {
            "nodeDistance": 160
        }
      },
      "interaction": {
        "navigationButtons": true,
        "hover": true
      }
    }
    """)
    return net

# --- MAIN UI LAYOUT ---

# Top Title Section
st.title("Lineage X-Ray")
st.markdown("<h3 style='font-weight: 400; color: #86868b; margin-top: -20px;'>Control-M Batch Dependency Visualizer</h3>", unsafe_allow_html=True)
st.markdown("---")

# SIDEBAR
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3233/3233496.png", width=50) # Placeholder icon
    st.markdown("### Data Input")
    uploaded_file = st.file_uploader("Upload XML", type=["xml"])
    
    search_list = []
    show_data = False
    
    if uploaded_file:
        df_jobs, df_edges = parse_controlm_xml(uploaded_file)
        if not df_jobs.empty:
            all_jobs = sorted(df_jobs["JobName"].unique().tolist())
            st.success(f"✓ {len(all_jobs)} Jobs Loaded")
            st.markdown("### Filters")
            selected_jobs = st.multiselect("Select Jobs", all_jobs)
            paste_jobs = st.text_area("Or Paste List (Comma separated)", height=100)
            
            search_list = selected_jobs
            if paste_jobs:
                pasted_list = [x.strip() for x in paste_jobs.split(",") if x.strip()]
                valid_pasted = [j for j in pasted_list if j in all_jobs]
                search_list = list(set(search_list + valid_pasted))
            
            st.markdown("---")
            show_data = st.checkbox("Show Raw Data Tables", value=True)

# MAIN CONTENT
if uploaded_file and 'df_jobs' in locals() and not df_jobs.empty:
    
    G_full = build_network_graph(df_edges, df_jobs["JobName"].tolist())
    
    # Logic to determine subgraph
    if search_list:
        G_display = get_full_lineage_subgraph(G_full, search_list)
        status_msg = f"Tracing **{len(search_list)}** jobs → found **{len(G_display.nodes)}** dependencies."
    else:
        if len(G_full.nodes) > 300:
            st.warning("Graph is too large to render automatically. Please select jobs in the sidebar.")
            G_display = nx.DiGraph()
            status_msg = "Waiting for selection..."
        else:
            G_display = G_full
            status_msg = f"Displaying full flow ({len(G_full.nodes)} jobs)."

    # Status Bar (Styled like a notification)
    st.markdown(f"""
    <div style="background-color: white; border-radius: 12px; padding: 15px; border: 1px solid #e5e5ea; margin-bottom: 20px; display: flex; align-items: center;">
        <span style="font-size: 20px; margin-right: 10px;">⚡</span>
        <span style="font-weight: 500; color: #1d1d1f;">{status_msg}</span>
    </div>
    """, unsafe_allow_html=True)

    # Graph Rendering
    if len(G_display.nodes) > 0:
        net = render_interactive_graph(G_display, search_list)
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
                net.save_graph(tmp_file.name)
                tmp_file_path = tmp_file.name
            
            with open(tmp_file_path, 'r', encoding='utf-8') as f:
                html_bytes = f.read()

            # The Graph Container with Shadow
            st.markdown('<div style="border-radius: 18px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #e5e5ea;">', unsafe_allow_html=True)
            components.html(html_bytes, height=700, scrolling=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Action Buttons Row
            col1, col2 = st.columns([1, 4])
            with col1:
                st.download_button("Download Report", data=html_bytes, file_name="lineage.html", mime="text/html")
            
            os.remove(tmp_file_path)

        except Exception as e:
            st.error(f"Graph Error: {e}")

    # Data Tables Section
    if show_data:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("### Data Inspector")
        tab1, tab2 = st.tabs(["Jobs", "Dependencies"])
        
        # Styling Dataframes is handled by global CSS, but we wrapper them for layout
        with tab1:
            st.dataframe(df_jobs, use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(df_edges, use_container_width=True, hide_index=True)

elif not uploaded_file:
    # Empty State - Centered Hero Section
    st.markdown("""
    <div style="text-align: center; padding: 50px 20px;">
        <h2 style="color: #d2d2d7; font-weight: 400;">No Data Loaded</h2>
        <p style="color: #86868b;">Upload a Control-M XML file from the sidebar to begin analyzing lineage.</p>
    </div>
    """, unsafe_allow_html=True)