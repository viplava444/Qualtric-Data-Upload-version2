import json
import time
import pandas as pd
import streamlit as st

from api_client import make_request, get_base_url
from utils import parse_uploaded_file, build_embedded_data_payload, status_badge


def render():
    st.markdown("### 📝 Update Embedded Data")
    st.markdown("Upload a file containing `responseId` and embedded data fields to update responses in bulk.")
    st.divider()

    # ── Fetch shared config from session state ────────────────────────────────
    api_token   = st.session_state.get("api_token", "")
    data_center = st.session_state.get("data_center", "")
    survey_id   = st.session_state.get("survey_id", "")

    if not api_token or not survey_id:
        st.warning("⚠️ Please fill in your **API Token** and **Survey ID** in the sidebar before proceeding.")
        return

    # ── STEP 1: Upload ────────────────────────────────────────────────────────
    st.markdown("#### Step 1 — Upload File")
    uploaded = st.file_uploader(
        "Upload your data file",
        type=["csv", "tsv", "txt", "xlsx", "xls"],
        help="File must contain a `responseId` column.",
    )

    if uploaded is None:
        st.info("📂 Upload a CSV, TSV, or Excel file to get started.")
        return

    df = parse_uploaded_file(uploaded)
    if df is None:
        return

    # Validate responseId column
    if "responseId" not in df.columns:
        st.error("❌ File must contain a `responseId` column.")
        return

    st.success(f"✅ File loaded — **{len(df)} rows**, **{len(df.columns)} columns**")
    st.divider()

    # ── STEP 2: Configure Fields ──────────────────────────────────────────────
    st.markdown("#### Step 2 — Select Embedded Data Fields")

    other_cols = [c for c in df.columns if c != "responseId"]

    if not other_cols:
        st.error("No columns found besides `responseId`.")
        return

    # Select All / Deselect All buttons
    col_a, col_b, _ = st.columns([1, 1, 6])
    with col_a:
        if st.button("✅ Select All", use_container_width=True):
            st.session_state["selected_cols"] = other_cols
    with col_b:
        if st.button("⬜ Deselect All", use_container_width=True):
            st.session_state["selected_cols"] = []

    default_selected = st.session_state.get("selected_cols", other_cols)

    # Render checkboxes in a 3-column grid
    num_cols = 3
    grid = st.columns(num_cols)
    selected_cols = []
    for i, col in enumerate(other_cols):
        with grid[i % num_cols]:
            checked = col in default_selected
            if st.checkbox(col, value=checked, key=f"col_chk_{col}"):
                selected_cols.append(col)

    st.session_state["selected_cols"] = selected_cols

    # resetRecordedDate toggle
    reset_date = st.toggle("🔄 Reset Recorded Date", value=True, help="Set `resetRecordedDate` to true in payload.")
    st.divider()

    if not selected_cols:
        st.warning("Please select at least one field.")
        return

    # ── STEP 3: Preview ───────────────────────────────────────────────────────
    st.markdown("#### Step 3 — Preview Respondents")

    max_rows = len(df)
    preview_n = st.slider(
        "Number of rows to preview",
        min_value=1,
        max_value=max_rows,
        value=min(5, max_rows),
        step=1,
    )

    preview_df = df[["responseId"] + selected_cols].head(preview_n)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    # Show JSON preview for first row
    with st.expander("🔍 Preview JSON payload (first row)"):
        first_row = df.iloc[0]
        sample_payload = {
            "surveyId": survey_id,
            "resetRecordedDate": reset_date,
            "embeddedData": build_embedded_data_payload(first_row, selected_cols),
        }
        st.json(sample_payload)

    st.divider()

    # ── STEP 4: Submit ────────────────────────────────────────────────────────
    st.markdown("#### Step 4 — Submit Updates")

    total = len(df)
    st.info(f"Ready to update **{total} response(s)** using **{len(selected_cols)} embedded data field(s)**.")

    if st.button("🚀 Submit All Updates", type="primary", use_container_width=True):
        base_url   = get_base_url(data_center)
        results    = []
        progress   = st.progress(0, text="Starting...")
        status_box = st.empty()

        for i, (_, row) in enumerate(df.iterrows()):
            response_id = str(row["responseId"]).strip()
            endpoint    = f"{base_url}/responses/{response_id}"
            body        = {
                "surveyId": survey_id,
                "resetRecordedDate": reset_date,
                "embeddedData": build_embedded_data_payload(row, selected_cols),
            }

            result = make_request("PUT", endpoint, api_token, body)
            results.append({
                "responseId":   response_id,
                "status":       status_badge(result["success"], result["status_code"]),
                "success":      result["success"],
                "status_code":  result["status_code"],
                "raw_response": result["data"],
                "error":        result["error"],
            })

            pct  = (i + 1) / total
            text = f"Processing {i+1}/{total} — {response_id}"
            progress.progress(pct, text=text)
            status_box.caption(text)
            time.sleep(0.05)  # slight delay to avoid rate limiting

        progress.empty()
        status_box.empty()
        st.session_state["update_results"] = results

    # ── STEP 5: Results ───────────────────────────────────────────────────────
    if "update_results" in st.session_state:
        results = st.session_state["update_results"]
        st.divider()
        st.markdown("#### Results")

        success_count = sum(1 for r in results if r["success"])
        fail_count    = len(results) - success_count

        m1, m2, m3 = st.columns(3)
        m1.metric("Total",    len(results))
        m2.metric("✅ Success", success_count)
        m3.metric("❌ Failed",  fail_count)

        st.markdown("---")

        # Results table
        summary_df = pd.DataFrame([
            {"responseId": r["responseId"], "Status": r["status"], "HTTP Code": r["status_code"]}
            for r in results
        ])
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # Per-row raw response expanders (failures first)
        failed  = [r for r in results if not r["success"]]
        success = [r for r in results if r["success"]]
        ordered = failed + success

        if failed:
            st.markdown("**❌ Failed Responses (expand for details):**")
        for r in ordered:
            label = f"{r['status']} — {r['responseId']}"
            with st.expander(label, expanded=not r["success"]):
                if r["error"]:
                    st.error(r["error"])
                st.json(r["raw_response"])

        # Download results as CSV
        st.download_button(
            label="⬇️ Download Results CSV",
            data=summary_df.to_csv(index=False),
            file_name="update_results.csv",
            mime="text/csv",
            use_container_width=True,
        )
