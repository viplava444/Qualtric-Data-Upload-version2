import streamlit as st
from config import DATA_CENTERS, APP_TITLE, APP_ICON
from utils import load_persisted_config, save_persisted_config
from tabs import tab_embedded, tab_placeholder

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label {
        color: #a0aec0 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f8fafc;
        padding: 8px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #4f46e5 !important;
        color: white !important;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        border: none;
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4338ca, #6d28d9);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4);
    }

    /* Dividers */
    hr { border-color: #e2e8f0; margin: 1rem 0; }

    /* Headers */
    h3 { color: #1e293b !important; font-weight: 700 !important; }
    h4 { color: #334155 !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)


# ── Load Persisted Config (once per session) ──────────────────────────────────
if "config_loaded" not in st.session_state:
    saved = load_persisted_config()
    st.session_state["api_token"]   = saved.get("api_token", "")
    st.session_state["data_center"] = saved.get("data_center", DATA_CENTERS[0])
    st.session_state["survey_id"]   = saved.get("survey_id", "")
    st.session_state["config_loaded"] = True


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.markdown("---")

    st.markdown("**🔐 Authentication**")
    api_token = st.text_input(
        "API Token",
        value=st.session_state["api_token"],
        type="password",
        placeholder="Paste your X-API-TOKEN",
    )

    st.markdown("**🌐 Data Center**")
    dc_index = DATA_CENTERS.index(st.session_state["data_center"]) \
               if st.session_state["data_center"] in DATA_CENTERS else 0
    data_center = st.selectbox("Data Center", DATA_CENTERS, index=dc_index)

    st.markdown("**📋 Survey ID**")
    survey_id = st.text_input(
        "Survey ID",
        value=st.session_state["survey_id"],
        placeholder="e.g. SV_xxxxxxxx",
    )

    st.markdown("---")

    if st.button("💾 Save Config", use_container_width=True):
        save_persisted_config(api_token, data_center, survey_id)
        st.success("Config saved!")

    # Live connection indicator
    st.markdown("---")
    if api_token and survey_id:
        st.markdown("🟢 **Config ready**")
        st.caption(f"`{data_center}.qualtrics.com`")
    else:
        missing = []
        if not api_token:  missing.append("API Token")
        if not survey_id:  missing.append("Survey ID")
        st.markdown("🔴 **Missing:** " + ", ".join(missing))

    # Persist in session state
    st.session_state["api_token"]   = api_token
    st.session_state["data_center"] = data_center
    st.session_state["survey_id"]   = survey_id


# ── Tab Router ────────────────────────────────────────────────────────────────
st.markdown(f"# {APP_ICON} {APP_TITLE}")
st.caption(f"Connected to: `https://{data_center}.qualtrics.com`")
st.markdown("---")

TAB_DEFINITIONS = [
    ("📝 Update Responses",   tab_embedded),
    ("🔍 Retrieve Response",  tab_placeholder),
    ("🗑️ Delete Response",    tab_placeholder),
    ("➕ Tab 4",              tab_placeholder),
    ("➕ Tab 5",              tab_placeholder),
    ("➕ Tab 6",              tab_placeholder),
]

tab_labels  = [t[0] for t in TAB_DEFINITIONS]
tab_modules = [t[1] for t in TAB_DEFINITIONS]

tabs = st.tabs(tab_labels)

for tab, module in zip(tabs, tab_modules):
    with tab:
        module.render()
