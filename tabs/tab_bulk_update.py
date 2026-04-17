import json
import time
import pandas as pd
import streamlit as st

from api_client import make_request, get_base_url
from utils import parse_uploaded_file, build_embedded_data_payload


# ── Constants ─────────────────────────────────────────────────────────────────
POLL_INTERVAL_SEC = 10
MAX_POLL_ATTEMPTS = 60  # 60 × 10s = 10 min max polling
JOB_STATUSES = {
    "queued":     ("🟡", "Queued",      "warning"),
    "inProgress": ("🔵", "In Progress", "info"),
    "complete":   ("✅", "Complete",    "success"),
    "failed":     ("❌", "Failed",      "error"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_bulk_payload(df: pd.DataFrame, selected_cols: list, reset_date: bool, ignore_missing: bool) -> dict:
    """Build the full POST body for the bulk update job."""
    updates = []
    for _, row in df.iterrows():
        updates.append({
            "responseId":        str(row["responseId"]).strip(),
            "resetRecordedDate": reset_date,
            "embeddedData":      build_embedded_data_payload(row, selected_cols),
        })
    return {
        "updates":                updates,
        "ignoreMissingResponses": ignore_missing,
    }


def poll_job_status(base_url: str, survey_id: str, api_token: str, progress_id: str) -> dict:
    """Poll the job status endpoint once."""
    endpoint = f"{base_url}/surveys/{survey_id}/update-responses/{progress_id}"
    return make_request("GET", endpoint, api_token)


def render_status_badge(status: str) -> str:
    icon, label, _ = JOB_STATUSES.get(status, ("❓", status, "info"))
    return f"{icon} {label}"


# ── Main Render ───────────────────────────────────────────────────────────────

def render():
    st.markdown("### 📦 Bulk Update Responses")
    st.markdown(
        "Submit a **single batch job** to update embedded data across thousands of responses at once. "
        "Uses Qualtrics' preferred `startUpdateResponsesJob` endpoint."
    )

    # Limits callout
    with st.expander("ℹ️ API Limits & Notes", expanded=False):
        st.markdown("""
        - **Max:** 250,000 responseIds per job — no duplicates allowed
        - **Body size:** < 5MB inline · < 750MB via `fileUrl`
        - **Job SLO:** up to 1 hour · up to 6 hours total (including queue)
        - **Queuing:** Only one job per survey runs at a time — others are queued
        - **Survey Flow:** Fields must exist in Survey Flow to be visible after update
        """)

    st.divider()

    # ── Shared config ─────────────────────────────────────────────────────────
    api_token   = st.session_state.get("api_token", "")
    data_center = st.session_state.get("data_center", "")
    survey_id   = st.session_state.get("survey_id", "")

    if not api_token or not survey_id:
        st.warning("⚠️ Please fill in your **API Token** and **Survey ID** in the sidebar before proceeding.")
        return

    base_url = get_base_url(data_center)

    # ── Input Mode Toggle ─────────────────────────────────────────────────────
    st.markdown("#### Step 1 — Choose Input Mode")
    input_mode = st.radio(
        "How would you like to provide the data?",
        ["📂 Upload File (Inline JSON)", "🔗 File URL"],
        horizontal=True,
        help="Inline: upload CSV/Excel/TSV directly. File URL: host a JSON file and provide its URL."
    )
    st.divider()

    df            = None
    selected_cols = []
    file_url      = None

    # ── MODE A: File Upload ───────────────────────────────────────────────────
    if input_mode == "📂 Upload File (Inline JSON)":

        st.markdown("#### Step 2 — Upload File")
        uploaded = st.file_uploader(
            "Upload your data file",
            type=["csv", "tsv", "txt", "xlsx", "xls"],
            help="File must contain a `responseId` column.",
            key="bulk_uploader",
        )

        if uploaded is None:
            st.info("📂 Upload a CSV, TSV, or Excel file to get started.")
            return

        df = parse_uploaded_file(uploaded)
        if df is None:
            return

        if "responseId" not in df.columns:
            st.error("❌ File must contain a `responseId` column.")
            return

        # Duplicate check
        dupes = df["responseId"].duplicated().sum()
        if dupes > 0:
            st.error(f"❌ File contains **{dupes} duplicate responseId(s)**. Qualtrics does not allow duplicates in a single job.")
            return

        # Size check (~5MB limit for inline)
        payload_estimate_kb = df.memory_usage(deep=True).sum() / 1024
        if payload_estimate_kb > 4500:
            st.warning(f"⚠️ Estimated payload size is ~{payload_estimate_kb:.0f} KB — close to the 5MB inline limit. Consider using File URL mode.")

        st.success(f"✅ File loaded — **{len(df)} rows**, **{len(df.columns)} columns**")
        st.divider()

        # ── Field Selection ───────────────────────────────────────────────────
        st.markdown("#### Step 3 — Select Embedded Data Fields")
        other_cols = [c for c in df.columns if c != "responseId"]

        if not other_cols:
            st.error("No columns found besides `responseId`.")
            return

        col_a, col_b, _ = st.columns([1, 1, 6])
        with col_a:
            if st.button("✅ Select All", key="bulk_sel_all", use_container_width=True):
                st.session_state["bulk_selected_cols"] = other_cols
        with col_b:
            if st.button("⬜ Deselect All", key="bulk_desel_all", use_container_width=True):
                st.session_state["bulk_selected_cols"] = []

        default_selected = st.session_state.get("bulk_selected_cols", other_cols)
        grid = st.columns(3)
        for i, col in enumerate(other_cols):
            with grid[i % 3]:
                checked = col in default_selected
                if st.checkbox(col, value=checked, key=f"bulk_chk_{col}"):
                    selected_cols.append(col)
        st.session_state["bulk_selected_cols"] = selected_cols

        if not selected_cols:
            st.warning("Please select at least one field.")
            return

        st.divider()

        # ── Options ───────────────────────────────────────────────────────────
        st.markdown("#### Step 4 — Configure Options")
        c1, c2 = st.columns(2)
        with c1:
            reset_date = st.toggle("🔄 Reset Recorded Date", value=True,
                help="Sets recorded date to current time.")
        with c2:
            ignore_missing = st.toggle("⚠️ Ignore Missing Responses", value=False,
                help="Skip responseIds that don't exist instead of marking them as warnings.")
        st.divider()

        # ── Preview ───────────────────────────────────────────────────────────
        st.markdown("#### Step 5 — Preview")
        max_rows  = len(df)
        preview_n = st.slider("Rows to preview", 1, min(max_rows, 100), min(5, max_rows), key="bulk_preview_slider")
        preview_df = df[["responseId"] + selected_cols].head(preview_n)
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

        with st.expander("🔍 Preview full JSON payload"):
            sample = build_bulk_payload(
                df.head(3), selected_cols, reset_date, ignore_missing
            )
            st.json(sample)
            st.caption(f"Full job will contain **{len(df)}** update entries.")

        st.divider()

        # ── Submit ────────────────────────────────────────────────────────────
        st.markdown("#### Step 6 — Submit Job")
        st.info(f"Ready to submit **{len(df)} response(s)** with **{len(selected_cols)} field(s)** as a single batch job.")

        if st.button("🚀 Start Bulk Update Job", type="primary", use_container_width=True, key="bulk_submit_inline"):
            payload  = build_bulk_payload(df, selected_cols, reset_date, ignore_missing)
            endpoint = f"{base_url}/surveys/{survey_id}/update-responses"

            with st.spinner("Submitting job to Qualtrics..."):
                result = make_request("POST", endpoint, api_token, payload)

            if result["success"]:
                progress_id = result["data"].get("result", {}).get("progressId")
                st.session_state["bulk_progress_id"]  = progress_id
                st.session_state["bulk_job_submitted"] = True
                st.session_state["bulk_raw_submit"]    = result["data"]
                st.rerun()
            else:
                st.error(f"❌ Job submission failed: {result['error']}")
                with st.expander("Raw error response"):
                    st.json(result["data"])

    # ── MODE B: File URL ──────────────────────────────────────────────────────
    else:
        st.markdown("#### Step 2 — Provide File URL")
        st.markdown("""
        Host a JSON file at a publicly accessible URL. The file must contain:
        ```json
        {
          "updates": [
            { "responseId": "R_xxx", "resetRecordedDate": true, "embeddedData": {"FIELD": "VALUE"} }
          ],
          "ignoreMissingResponses": false
        }
        ```
        """)

        file_url = st.text_input(
            "File URL",
            placeholder="https://your-server.com/updates.json",
            help="Must be publicly accessible. Content-Type: application/json. Max size: 750MB.",
            key="bulk_file_url",
        )
        st.divider()

        if not file_url:
            st.info("🔗 Enter a valid file URL to continue.")
            return

        st.markdown("#### Step 3 — Submit Job")
        st.info("The job will fetch data directly from your URL.")

        if st.button("🚀 Start Bulk Update Job (via URL)", type="primary", use_container_width=True, key="bulk_submit_url"):
            payload  = {"fileUrl": file_url}
            endpoint = f"{base_url}/surveys/{survey_id}/update-responses"

            with st.spinner("Submitting job to Qualtrics..."):
                result = make_request("POST", endpoint, api_token, payload)

            if result["success"]:
                progress_id = result["data"].get("result", {}).get("progressId")
                st.session_state["bulk_progress_id"]  = progress_id
                st.session_state["bulk_job_submitted"] = True
                st.session_state["bulk_raw_submit"]    = result["data"]
                st.rerun()
            else:
                st.error(f"❌ Job submission failed: {result['error']}")
                with st.expander("Raw error response"):
                    st.json(result["data"])

    # ── Job Status Polling ────────────────────────────────────────────────────
    if st.session_state.get("bulk_job_submitted") and st.session_state.get("bulk_progress_id"):
        progress_id = st.session_state["bulk_progress_id"]

        st.divider()
        st.markdown("#### Job Status")

        # Show submission details
        col1, col2 = st.columns(2)
        col1.info(f"**Progress ID:** `{progress_id}`")
        col2.info(f"**Survey ID:** `{survey_id}`")

        with st.expander("📋 Raw submission response"):
            st.json(st.session_state.get("bulk_raw_submit", {}))

        st.markdown("---")

        # Polling UI
        status_placeholder  = st.empty()
        details_placeholder = st.empty()

        # Manual re-check button
        col_poll, col_reset = st.columns([2, 1])
        with col_poll:
            check_now = st.button("🔄 Check Status Now", use_container_width=True, key="bulk_check_now")
        with col_reset:
            if st.button("🗑️ Clear Job", use_container_width=True, key="bulk_clear_job"):
                for key in ["bulk_job_submitted", "bulk_progress_id", "bulk_raw_submit", "bulk_last_status"]:
                    st.session_state.pop(key, None)
                st.rerun()

        # Auto-poll logic
        last_status = st.session_state.get("bulk_last_status", None)
        should_poll = check_now or (last_status not in ["complete", "failed", None])

        if should_poll or last_status is None:
            with st.spinner("Checking job status..."):
                poll_result = poll_job_status(base_url, survey_id, api_token, progress_id)

            if poll_result["success"]:
                result_data = poll_result["data"].get("result", {})
                status      = result_data.get("status", "unknown")
                st.session_state["bulk_last_status"]  = status
                st.session_state["bulk_last_result"]  = poll_result["data"]

                icon, label, stype = JOB_STATUSES.get(status, ("❓", status, "info"))

                with status_placeholder.container():
                    if stype == "success":
                        st.success(f"{icon} Job **{label}** — all responses updated successfully!")
                    elif stype == "error":
                        st.error(f"{icon} Job **{label}** — check details below.")
                    elif stype == "warning":
                        st.warning(f"{icon} Job is **{label}** — waiting to start...")
                    else:
                        st.info(f"{icon} Job is **{label}** — processing...")

                with details_placeholder.container():
                    # Progress metrics
                    pct = result_data.get("percentComplete", None)
                    if pct is not None:
                        st.progress(int(pct) / 100, text=f"{pct}% complete")

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Status", label)
                    m2.metric("Progress ID", progress_id[:12] + "...")
                    m3.metric("% Complete", f"{pct}%" if pct is not None else "—")

                    with st.expander("🔍 Full status response"):
                        st.json(poll_result["data"])

                # Auto-rerun if still running
                if status in ["queued", "inProgress"]:
                    st.caption(f"⏱️ Auto-refreshing in {POLL_INTERVAL_SEC}s... (job can take up to 1 hour)")
                    time.sleep(POLL_INTERVAL_SEC)
                    st.rerun()

            else:
                status_placeholder.error(f"❌ Failed to fetch status: {poll_result['error']}")

        elif last_status in ["complete", "failed"]:
            # Show last known status without re-polling
            icon, label, stype = JOB_STATUSES.get(last_status, ("❓", last_status, "info"))
            last_result = st.session_state.get("bulk_last_result", {})

            with status_placeholder.container():
                if stype == "success":
                    st.success(f"{icon} Job **{label}**")
                else:
                    st.error(f"{icon} Job **{label}**")

            with details_placeholder.container():
                with st.expander("🔍 Full status response"):
                    st.json(last_result)
