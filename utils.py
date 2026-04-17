import json
import os
import pandas as pd
import streamlit as st
from config import PERSIST_FILE


# ── File Parsing ──────────────────────────────────────────────────────────────

def parse_uploaded_file(uploaded_file) -> pd.DataFrame | None:
    """Parse CSV, Excel, or TSV into a DataFrame."""
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(uploaded_file)
        elif name.endswith(".tsv") or name.endswith(".txt"):
            return pd.read_csv(uploaded_file, sep="\t")
        elif name.endswith(".xlsx") or name.endswith(".xls"):
            return pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file type. Please upload CSV, TSV, or Excel.")
            return None
    except Exception as e:
        st.error(f"Failed to parse file: {e}")
        return None


# ── Session Persistence ───────────────────────────────────────────────────────

def load_persisted_config() -> dict:
    """Load saved API token, data center, survey ID from local file."""
    if os.path.exists(PERSIST_FILE):
        try:
            with open(PERSIST_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_persisted_config(api_token: str, data_center: str, survey_id: str):
    """Save config to local JSON file."""
    try:
        with open(PERSIST_FILE, "w") as f:
            json.dump({
                "api_token": api_token,
                "data_center": data_center,
                "survey_id": survey_id,
            }, f)
    except Exception:
        pass


# ── Formatting ────────────────────────────────────────────────────────────────

def build_embedded_data_payload(row: pd.Series, selected_cols: list) -> dict:
    """Build embeddedData dict from a DataFrame row."""
    return {col: str(row[col]) if pd.notna(row[col]) else "" for col in selected_cols}


def status_badge(success: bool, status_code: int = None) -> str:
    """Return a colored status string."""
    if success:
        return f"✅ {status_code or 'OK'}"
    return f"❌ {status_code or 'Error'}"
