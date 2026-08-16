# admin_dashboard/app.py
#
# PriceGuard — Admin Dashboard
# Streamlit app for reviewing, filtering, and actioning complaints
# submitted through the PriceGuard mobile app.

import requests
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(
    page_title="PriceGuard Admin Dashboard",
    page_icon="🛡️",
    layout="wide",
)

# ============================================================
# CONFIG
# ============================================================
DEFAULT_BASE_URL = "https://priceguard-vrpg.onrender.com"
DEFAULT_HOARDING_THRESHOLD_PCT = 30  # reported price this much above model's expected price = alert

if "base_url" not in st.session_state:
    st.session_state.base_url = DEFAULT_BASE_URL
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "admin_email" not in st.session_state:
    st.session_state.admin_email = None
if "complaints_df" not in st.session_state:
    st.session_state.complaints_df = None


# ============================================================
# STATUS CATEGORIZATION
# (used for both KPI grouping and map pin colors — kept in one
# place so the two never drift out of sync)
# ============================================================
def categorize_status(status: str) -> str:
    """
    Buckets every possible ComplaintStatus value into one of three
    groups. Written with substring matching (not an exact enum list)
    so it keeps working if new statuses are added later without
    needing a matching dashboard update.
    """
    if status is None:
        return "Pending"
    s = status.lower()
    if s.startswith("auto-rejected") or s == "dismissed":
        return "Rejected"
    if s == "verified":
        return "Verified"
    # everything else: pending, suspicious:*, potential coordinated attack,
    # pending manual review*, pending manual verification* — all "needs a human"
    return "Pending"


STATUS_COLORS = {
    "Verified": [220, 20, 60, 200],   # red, per spec: Red = Verified Overpricing
    "Pending": [255, 200, 0, 200],    # yellow
    "Rejected": [130, 130, 130, 200],  # gray
}


# ============================================================
# ENTERPRISE THEME (call once, first line of main())
#
# CAVEAT: sections 2-4 target Streamlit's internal data-testid /
# data-baseweb attributes, which are undocumented and can shift between
# Streamlit versions. Kept in this one function so it's easy to disable
# entirely (just don't call it) if a future Streamlit upgrade breaks
# something — the .streamlit/config.toml theme is unaffected either way.
# ============================================================
def inject_enterprise_theme():
    st.markdown(
        """
        <style>
        /* ------------------------------------------------------
           1. TYPOGRAPHY — Inter for a clean, authoritative look
        ------------------------------------------------------ */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        h1, h2, h3 {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #F0F2F5;
        }

        h1 {
            font-size: 1.9rem;
            border-bottom: 2px solid #2E7D5B;
            padding-bottom: 0.5rem;
            margin-bottom: 1.2rem;
        }

        h3 {
            font-size: 1.15rem;
            color: #9CA8B4;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }

        /* ------------------------------------------------------
           2. METRIC CARDS — elevated, bordered panels instead of
              bare numbers
        ------------------------------------------------------ */
        [data-testid="stMetric"] {
            background: linear-gradient(180deg, #1A2129 0%, #161C23 100%);
            border: 1px solid #2A333D;
            border-radius: 10px;
            padding: 1.1rem 1.3rem;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
            transition: border-color 0.15s ease;
        }

        [data-testid="stMetric"]:hover {
            border-color: #2E7D5B;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #8B96A3;
            font-weight: 600;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.9rem;
            font-weight: 800;
            color: #F0F2F5;
        }

        [data-testid="stMetricDelta"] {
            font-weight: 600;
        }

        /* ------------------------------------------------------
           3. LAYOUT & SPACING
        ------------------------------------------------------ */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }

        /* Native bordered containers (st.container(border=True)) restyled
           as clean panels */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px !important;
            border: 1px solid #2A333D !important;
            background-color: #151B22;
            padding: 0.4rem;
        }

        [data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #2A333D;
        }

        /* Breathing room around charts */
        [data-testid="stPlotlyChart"], .stPydeckChart, [data-testid="stVegaLiteChart"] {
            padding: 0.5rem 0;
        }

        /* ------------------------------------------------------
           4. TABS — pill-style navigation instead of plain text links
        ------------------------------------------------------ */
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background-color: #161C23;
            padding: 6px;
            border-radius: 10px;
            border: 1px solid #2A333D;
        }

        .stTabs [data-baseweb="tab"] {
            height: 42px;
            border-radius: 8px;
            padding: 0 18px;
            background-color: transparent;
            color: #9CA8B4;
            font-weight: 600;
            font-size: 0.9rem;
            border: none;
            transition: all 0.15s ease;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background-color: #1E2630;
            color: #E6E9EC;
        }

        .stTabs [aria-selected="true"] {
            background-color: #2E7D5B !important;
            color: #FFFFFF !important;
        }

        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }

        /* ------------------------------------------------------
           5. HIDE STREAMLIT BRANDING
        ------------------------------------------------------ */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header [data-testid="stToolbar"] { visibility: hidden; }
        [data-testid="stDecoration"] { display: none; }
        .stDeployButton { display: none; }

        /* ------------------------------------------------------
           6. MISC POLISH
        ------------------------------------------------------ */
        [data-testid="stSidebar"] {
            background-color: #12171D;
            border-right: 1px solid #2A333D;
        }

        .stButton button {
            border-radius: 8px;
            font-weight: 600;
            border: 1px solid #2A333D;
        }

        .stAlert {
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# CUSTOM SELECTBOX BEHAVIOR (Details & Actions dropdown only)
#
# CAVEATS — read before relying on this for a live demo:
#   - Streamlit's selectbox is built on an internal library (BaseWeb) with
#     no supported customization API. Works on Streamlit 1.51.0 by
#     targeting its current DOM structure; a future Streamlit upgrade could
#     change that structure and silently break this.
#   - Disabling typing requires actual JavaScript — CSS cannot prevent
#     keyboard input. This uses a small script that finds the dropdown's
#     input field and sets it read-only, while leaving click-to-open
#     working normally.
# ============================================================
def inject_complaint_selectbox_styling():
    st.markdown(
        """
        <style>
        #complaint-select-marker + div div[data-baseweb="select"] {
            cursor: pointer !important;
        }
        #complaint-select-marker + div div[data-baseweb="select"] * {
            cursor: pointer !important;
        }
        #complaint-select-marker + div div[data-baseweb="select"] input {
            caret-color: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.components.v1.html(
        """
        <script>
        function lockComplaintSelectbox() {
            const doc = window.parent.document;
            const marker = doc.getElementById("complaint-select-marker");
            if (!marker) return;
            const wrapper = marker.nextElementSibling;
            if (!wrapper) return;
            const input = wrapper.querySelector('div[data-baseweb="select"] input');
            if (input && !input.readOnly) {
                input.readOnly = true;
            }
        }
        setInterval(lockComplaintSelectbox, 400);
        </script>
        """,
        height=0,
    )


# ============================================================
# API HELPERS
# ============================================================
def api_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def login(email: str, password: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            f"{st.session_state.base_url}/api/users/login",
            data={"username": email, "password": password},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Could not reach backend at {st.session_state.base_url} — {e}"

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        return False, f"Login failed: {detail}"

    token = resp.json().get("access_token")
    st.session_state.access_token = token
    st.session_state.admin_email = email
    return True, "Logged in."


def fetch_complaints() -> tuple[bool, str]:
    try:
        resp = requests.get(
            f"{st.session_state.base_url}/api/admin/complaints",
            headers=api_headers(),
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Could not reach backend — {e}"

    if resp.status_code == 401:
        st.session_state.access_token = None
        return False, "Session expired — please log in again."
    if resp.status_code != 200:
        return False, f"Failed to fetch complaints: {resp.status_code} {resp.text}"

    data = resp.json()
    if not data:
        st.session_state.complaints_df = pd.DataFrame()
        return True, "No complaints found."

    df = pd.DataFrame(data)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert("Asia/Karachi")
    df["reviewed_at"] = pd.to_datetime(df["reviewed_at"], utc=True).dt.tz_convert("Asia/Karachi")
    df["status_category"] = df["status"].apply(categorize_status)

    df["map_latitude"] = df["device_latitude"].fillna(df["market_latitude"])
    df["map_longitude"] = df["device_longitude"].fillna(df["market_longitude"])
    df["location_source"] = df["device_latitude"].apply(
        lambda v: "Device GPS" if pd.notnull(v) else "Market (fallback)"
    )

    st.session_state.complaints_df = df
    return True, f"Loaded {len(df)} complaints."


# ============================================================
# NEW — BACKGROUND POLLING FOR NEW COMPLAINTS
#
# Uses st.fragment(run_every=...), a native Streamlit feature (available
# since 1.33, well before this app's 1.51.0) that reruns just this function
# on a timer WITHOUT resetting the whole page/session — unlike a browser
# reload, login state and everything else stays intact.
#
# Only triggers a full app refresh (st.rerun()) when the complaint count
# actually changed, so normal browsing/filtering isn't interrupted every
# 15 seconds for no reason.
# ============================================================
@st.fragment(run_every=15)
def poll_for_new_complaints():
    if not st.session_state.access_token:
        return  # not logged in yet, nothing to poll

    previous_count = (
        len(st.session_state.complaints_df)
        if st.session_state.complaints_df is not None
        else -1
    )

    ok, _ = fetch_complaints()  # updates st.session_state.complaints_df on success

    if ok and st.session_state.complaints_df is not None:
        new_count = len(st.session_state.complaints_df)
        if new_count != previous_count:
            st.rerun()


def update_complaint_status(complaint_id: str, new_status: str, admin_note: str = "") -> tuple[bool, str, dict]:
    """
    Returns (success, message, debug_info). debug_info always contains the
    raw status_code and response body so failures are never silent.
    """
    debug_info = {"request_status": new_status, "complaint_id": complaint_id}

    try:
        resp = requests.patch(
            f"{st.session_state.base_url}/api/admin/complaints/{complaint_id}",
            headers=api_headers(),
            json={"status": new_status, "admin_note": admin_note or None},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        debug_info["error"] = str(e)
        return False, f"Could not reach backend — {e}", debug_info

    debug_info["http_status_code"] = resp.status_code
    try:
        debug_info["response_body"] = resp.json()
    except Exception:
        debug_info["response_body"] = resp.text

    if resp.status_code != 200:
        detail = debug_info["response_body"].get("detail") if isinstance(debug_info["response_body"], dict) else resp.text
        return False, f"Update failed ({resp.status_code}): {detail}", debug_info

    returned_status = debug_info["response_body"].get("status") if isinstance(debug_info["response_body"], dict) else None
    debug_info["returned_status"] = returned_status
    if returned_status != new_status:
        return False, (
            f"Backend returned 200 but the complaint's status is '{returned_status}', "
            f"not the requested '{new_status}'. This points to a backend issue, not a "
            f"Streamlit refresh issue."
        ), debug_info

    return True, "Status updated.", debug_info


# ============================================================
# NEW — OFFICIAL RATE LIST UPLOAD
#
# Same (success, message, debug_info) convention as update_complaint_status
# above, so every API-calling function in this file behaves identically —
# one mental model for callers, and debug_info always available for the
# same kind of "🔍 API response details" expander pattern used elsewhere.
# ============================================================
def upload_official_rate_list(uploaded_file) -> tuple[bool, str, dict]:
    """
    Uploads a CSV/Excel official rate list to POST /api/admin/upload-rates.
    """
    debug_info = {"filename": uploaded_file.name}

    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }

    try:
        resp = requests.post(
            f"{st.session_state.base_url}/api/admin/upload-rates",
            headers=api_headers(),  # Authorization: Bearer <token> only — no Content-Type,
                                     # requests sets the multipart boundary itself for `files=`
            files=files,
            timeout=30,  # generous — parsing + a DB lookup per row can take a few seconds
        )
    except requests.exceptions.RequestException as e:
        debug_info["error"] = str(e)
        return False, f"Could not reach backend — {e}", debug_info

    debug_info["http_status_code"] = resp.status_code
    try:
        debug_info["response_body"] = resp.json()
    except Exception:
        debug_info["response_body"] = resp.text

    if resp.status_code == 401:
        st.session_state.access_token = None
        return False, "Session expired — please log in again.", debug_info

    if resp.status_code == 403:
        return False, "This account does not have admin privileges.", debug_info

    if resp.status_code != 200:
        body = debug_info["response_body"]
        detail = body.get("detail") if isinstance(body, dict) else resp.text
        return False, f"Upload rejected ({resp.status_code}): {detail}", debug_info

    body = debug_info["response_body"]
    total = body.get("total_rows_processed", 0)
    inserted = body.get("rates_inserted", 0)
    skipped = body.get("skipped_items", [])
    effective_date = body.get("effective_date", "today")

    message = f"Processed {total} row(s) — {inserted} rate(s) saved for {effective_date}."
    if skipped:
        message += f" {len(skipped)} row(s) skipped."
    debug_info["skipped_items"] = skipped

    return True, message, debug_info


# ============================================================
# LOGIN SCREEN
# ============================================================
def render_login():
    st.title("🛡️ PriceGuard Admin Dashboard")
    st.caption("Log in with an admin account to review and action complaints.")

    with st.form("login_form"):
        base_url = st.text_input("Backend URL", value=st.session_state.base_url)
        email = st.text_input("Admin email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", width='stretch')

    if submitted:
        st.session_state.base_url = base_url.rstrip("/")
        ok, msg = login(email, password)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


# ============================================================
# SIDEBAR (filters + session controls)
# ============================================================
def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("🛡️ PriceGuard Admin")
    st.sidebar.caption(f"Logged in as **{st.session_state.admin_email}**")

    if st.sidebar.button("🔄 Refresh Data", width='stretch'):
        ok, msg = fetch_complaints()
        st.sidebar.info(msg) if ok else st.sidebar.error(msg)
        st.rerun()

    if st.sidebar.button("Log Out", width='stretch'):
        st.session_state.access_token = None
        st.session_state.admin_email = None
        st.session_state.complaints_df = None
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Filters")

    if df.empty:
        st.sidebar.info("No data to filter yet.")
        return df

    status_options = sorted(df["status"].unique().tolist())
    selected_statuses = st.sidebar.multiselect(
        "Status", options=status_options, default=status_options
    )

    item_options = sorted(df["commodity_name"].unique().tolist())
    selected_items = st.sidebar.multiselect(
        "Item", options=item_options, default=item_options
    )

    min_date = df["created_at"].min().date()
    max_date = df["created_at"].max().date()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    filtered = df[
        df["status"].isin(selected_statuses) & df["commodity_name"].isin(selected_items)
    ]

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered["created_at"].dt.date >= start) & (filtered["created_at"].dt.date <= end)
        ]

    return filtered


# ============================================================
# TAB 1 — OVERVIEW & MAP
# ============================================================
def render_rate_upload_section():
    st.subheader("📤 Upload Official Rate List")
    st.caption(
        "File must be .csv or .xlsx with columns: **Item Name**, **Unit**, **Price**. "
        "Uploading today's rates again will update, not duplicate, existing entries."
    )

    with st.form("rate_upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader(
            "Select rate list file",
            type=["csv", "xlsx"],
            accept_multiple_files=False,
        )
        submitted = st.form_submit_button("Upload", width="stretch")

    if submitted:
        # ---- Negative test: Upload clicked with nothing selected ----
        if uploaded_file is None:
            st.warning("Please select a CSV or Excel file before clicking Upload.")
            return

        with st.spinner(f"Uploading and processing {uploaded_file.name}..."):
            ok, message, debug_info = upload_official_rate_list(uploaded_file)

        if ok:
            st.success(message)
            if debug_info.get("skipped_items"):
                with st.expander(f"⚠️ {len(debug_info['skipped_items'])} row(s) skipped — click to see why"):
                    for item in debug_info["skipped_items"]:
                        st.write(f"- {item}")
        else:
            # ---- Negative test: backend rejected the file (400/401/403/etc.) ----
            # Clean message only — no raw traceback ever reaches the screen.
            st.error(message)

    st.divider()


def render_overview_tab(full_df: pd.DataFrame, filtered_df: pd.DataFrame):
    st.subheader("Overview")

    render_rate_upload_section()   # NEW

    total = len(full_df)
    pending_count = (full_df["status_category"] == "Pending").sum()
    verified_count = (full_df["status_category"] == "Verified").sum()
    rejected_count = (full_df["status_category"] == "Rejected").sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Complaints", total)
    c2.metric("Pending / Needs Review", int(pending_count))
    c3.metric("Verified Violations", int(verified_count))
    c4.metric("Rejected", int(rejected_count))

    st.caption(
        "KPIs reflect **all** complaints regardless of sidebar filters. "
        "The map and table below respect your filters."
    )

    st.divider()
    st.subheader("Complaint Locations")

    if filtered_df.empty:
        st.info("No complaints match the current filters.")
        return

    map_df = filtered_df.copy()
    map_df["color"] = map_df["status_category"].map(STATUS_COLORS)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[map_longitude, map_latitude]",
        get_fill_color="color",
        get_radius=120,
        pickable=True,
        opacity=0.8,
        stroked=True,
        get_line_color=[0, 0, 0],
        line_width_min_pixels=1,
    )

    view_state = pdk.ViewState(
        latitude=map_df["map_latitude"].mean(),
        longitude=map_df["map_longitude"].mean(),
        zoom=11,
        pitch=0,
    )

    tooltip = {
        "html": (
            "<b>{shop_name}</b><br/>"
            "Item: {commodity_name}<br/>"
            "Status: {status}<br/>"
            "Reported: Rs. {reported_price} (Official: Rs. {official_price_at_submission})<br/>"
            "Location source: {location_source}"
        ),
        "style": {"backgroundColor": "steelblue", "color": "white"},
    }
    with st.container(border=True):
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))

    legend_col1, legend_col2, legend_col3 = st.columns(3)
    legend_col1.markdown("🔴 **Verified Overpricing**")
    legend_col2.markdown("🟡 **Pending / Needs Review**")
    legend_col3.markdown("⚪ **Rejected / Spam**")


# ============================================================
# TAB 2 — COMPLAINTS TABLE
# ============================================================
def render_table_tab(filtered_df: pd.DataFrame):
    st.subheader(f"Complaints ({len(filtered_df)})")

    if filtered_df.empty:
        st.info("No complaints match the current filters.")
        return

    display_cols = [
        "created_at", "shop_name", "commodity_name", "market_name",
        "reported_price", "official_price_at_submission", "ai_extracted_price",
        "status", "flags", "distance_from_market_km", "user_email",
    ]
    column_config = {
        "created_at": st.column_config.DatetimeColumn("Submitted", format="D MMM YYYY, h:mm a"),
        "reported_price": st.column_config.NumberColumn("Reported (Rs.)", format="%.0f"),
        "official_price_at_submission": st.column_config.NumberColumn("Official (Rs.)", format="%.0f"),
        "ai_extracted_price": st.column_config.NumberColumn("OCR Extracted (Rs.)", format="%.0f"),
        "distance_from_market_km": st.column_config.NumberColumn("Distance (km)", format="%.2f"),
    }

    verified_df = filtered_df[filtered_df["status"] == "verified"]
    other_df = filtered_df[filtered_df["status"] != "verified"]

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader(f"✅ Verified Complaints ({len(verified_df)})")
        if verified_df.empty:
            st.info("No verified complaints yet.")
        else:
            with st.container(border=True):
                st.dataframe(
                    verified_df[display_cols].sort_values("created_at", ascending=False),
                    width='stretch',
                    hide_index=True,
                    column_config=column_config,
                )

    with right_col:
        st.subheader(f"📋 Other Complaints ({len(other_df)})")
        if other_df.empty:
            st.info("No other complaints.")
        else:
            with st.container(border=True):
                st.dataframe(
                    other_df[display_cols].sort_values("created_at", ascending=False),
                    width='stretch',
                    hide_index=True,
                    column_config=column_config,
                )

    st.divider()
    csv = filtered_df[display_cols].sort_values("created_at", ascending=False).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export filtered data as CSV", csv, "priceguard_complaints.csv", "text/csv")


# ============================================================
# TAB 3 — DETAIL VIEW & ACTION PANEL
# ============================================================
def render_detail_tab(filtered_df: pd.DataFrame):
    st.subheader("Complaint Detail & Review")

    if filtered_df.empty:
        st.info("No complaints match the current filters.")
        return

    NEEDS_INITIAL_REVIEW = [
        "pending",
        "Suspicious: Price Mismatch",
        "Pending Manual Review (Handwritten)",
    ]
    ACTIONABLE_STATUSES = NEEDS_INITIAL_REVIEW + ["verified"]
    actionable_df = filtered_df[filtered_df["status"].isin(ACTIONABLE_STATUSES)]

    if actionable_df.empty:
        st.info(
            "No complaints currently need review — everything in the current "
            "filter is either Rejected/Spam/Auto-Rejected, or you've filtered "
            "them out in the sidebar."
        )
        return

    sorted_df = actionable_df.sort_values("created_at", ascending=False).reset_index(drop=True)
    options = {
        f"{row.created_at.strftime('%d %b %Y, %I:%M %p')} — {row.shop_name or 'Unknown Shop'} "
        f"— {row.commodity_name} — {row.status}": row.id
        for row in sorted_df.itertuples()
    }
    st.caption(
        f"Showing {len(sorted_df)} complaint(s) with status: "
        f"pending, Suspicious: Price Mismatch, Pending Manual Review (Handwritten), or verified. "
        f"Resolved complaints move out of this list into the 'Other Complaints' table."
    )
    st.markdown('<div id="complaint-select-marker"></div>', unsafe_allow_html=True)
    selected_label = st.selectbox("Select a complaint to review", options.keys())

    st.markdown('<div style="height: 260px;"></div>', unsafe_allow_html=True)
    complaint_id = options[selected_label]
    row = sorted_df[sorted_df["id"] == complaint_id].iloc[0]

    img_col, data_col = st.columns([1, 1.2])

    with img_col:
        st.markdown("**Receipt Image**")
        raw_url = row['receipt_image_url']
        image_url = raw_url if raw_url.startswith("http") else f"{st.session_state.base_url}{raw_url}"
        try:
            st.image(image_url, width='stretch')
        except Exception:
            st.warning(f"Could not load image from {image_url}")

    with data_col:
        st.markdown("**Price Comparison**")
        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Reported", f"Rs. {row['reported_price']:.0f}")
        pc2.metric(
            "Official",
            f"Rs. {row['official_price_at_submission']:.0f}"
            if pd.notnull(row["official_price_at_submission"]) else "N/A",
        )
        pc3.metric(
            "OCR Extracted",
            f"Rs. {row['ai_extracted_price']:.0f}" if pd.notnull(row["ai_extracted_price"]) else "N/A",
        )

        st.markdown("**Details**")
        st.write(f"**Shop:** {row['shop_name'] or 'N/A'}")
        st.write(f"**Item:** {row['commodity_name']}")
        st.write(f"**Market:** {row['market_name']}")
        st.write(f"**Submitted by:** {row['user_email']}")
        st.write(f"**Submitted at:** {row['created_at'].strftime('%d %b %Y, %I:%M %p')}")
        st.write(
            f"**Distance from market:** "
            f"{row['distance_from_market_km']:.2f} km" if pd.notnull(row["distance_from_market_km"]) else "N/A"
        )
        st.write(f"**Current status:** `{row['status']}`")

        st.markdown("**AI Flags**")
        if row["flags"]:
            for flag in str(row["flags"]).split(","):
                st.markdown(f"- {flag.strip()}")
        else:
            st.caption("No flags recorded.")

    st.divider()
    st.markdown("**Admin Actions**")

    note = st.text_input(
        "Optional note (recorded in the audit trail)",
        key=f"note_{complaint_id}",
        placeholder="e.g. Verified against receipt image, price genuinely higher than official rate.",
    )

    current_status = row["status"]

    if current_status in NEEDS_INITIAL_REVIEW:
        a1, a2 = st.columns(2)

        if a1.button("✅ Verify Violation", width="stretch", key=f"verify_{complaint_id}"):
            ok, msg, debug_info = update_complaint_status(str(complaint_id), "verified", note or "Verified by admin.")
            _handle_action_result(ok, msg, debug_info, complaint_id, "verified")

        if a2.button("❌ Reject as Spam", width="stretch", key=f"reject_{complaint_id}"):
            ok, msg, debug_info = update_complaint_status(str(complaint_id), "dismissed", note or "Rejected as spam/invalid by admin.")
            _handle_action_result(ok, msg, debug_info, complaint_id, "dismissed")

    elif current_status == "verified":
        st.info("This complaint has been verified. Once follow-up action is complete, mark it resolved.")
        if st.button("✔️ Mark Resolved", width="stretch", key=f"resolve_{complaint_id}"):
            ok, msg, debug_info = update_complaint_status(str(complaint_id), "Resolved", note or "Marked resolved by admin.")
            _handle_action_result(ok, msg, debug_info, complaint_id, "Resolved")

    st.markdown("---")
    st.markdown("**Manual override** (set any status directly)")
    all_statuses = sorted(filtered_df["status"].unique().tolist())
    override_status = st.selectbox("Status", options=all_statuses, key=f"override_{complaint_id}")
    if st.button("Apply Override", key=f"apply_override_{complaint_id}"):
        ok, msg, debug_info = update_complaint_status(str(complaint_id), override_status, note or "Manual override by admin.")
        _handle_action_result(ok, msg, debug_info, complaint_id, override_status)


def _handle_action_result(ok: bool, msg: str, debug_info: dict, complaint_id: str = None, expected_status: str = None):
    if ok:
        st.success(msg)
    else:
        st.error(msg)

    with st.expander("🔍 API response details (for debugging)"):
        st.json(debug_info)

    if not ok:
        return

    fetch_ok, fetch_msg = fetch_complaints()
    if not fetch_ok:
        st.warning(f"Update succeeded, but re-fetching the complaint list failed: {fetch_msg}")
        return

    if complaint_id is not None and expected_status is not None:
        refreshed_df = st.session_state.complaints_df
        match = refreshed_df[refreshed_df["id"] == complaint_id]
        if not match.empty:
            actual_status = match.iloc[0]["status"]
            if actual_status != expected_status:
                st.warning(
                    f"⚠️ The update API confirmed status='{expected_status}', but the "
                    f"re-fetched complaint list shows status='{actual_status}'. This is "
                    f"a backend/database read-after-write issue, not a Streamlit bug — "
                    f"worth checking your Neon connection pooling settings."
                )

    st.rerun()


# ============================================================
# TAB 4 — PREDICTIVE ANALYTICS & ALERTS
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_forecastable_items(base_url: str) -> list:
    """
    All 31 items the model can actually forecast — independent of which
    items happen to appear in the complaints table.
    """
    try:
        resp = requests.get(f"{base_url}/api/forecast/", timeout=15)
        if resp.status_code != 200:
            return []
        return resp.json().get("items", [])
    except requests.exceptions.RequestException:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def fetch_forecast(base_url: str, item_name: str, history_weeks: int = 12):
    """
    Returns the forecast API response for one item, or None on failure.
    Cached for 5 minutes per (base_url, item_name) combo.
    """
    try:
        resp = requests.get(
            f"{base_url}/api/forecast/{item_name}",
            params={"history_weeks": history_weeks},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.exceptions.RequestException:
        return None


def detect_hoarding_alerts(complaints_df: pd.DataFrame, base_url: str, threshold_pct: float) -> pd.DataFrame:
    """
    For every complaint currently needing review, compares its reported_price
    against the LSTM's near-term expected baseline price for that commodity.
    """
    review_statuses = [
        "pending",
        "Suspicious: Price Mismatch",
        "Pending Manual Review (Handwritten)",
    ]
    candidates = complaints_df[complaints_df["status"].isin(review_statuses)]

    if candidates.empty:
        return pd.DataFrame()

    alerts = []
    for row in candidates.itertuples():
        forecast_data = fetch_forecast(base_url, row.commodity_name)
        if not forecast_data or not forecast_data.get("forecast"):
            continue

        predicted_baseline = forecast_data["forecast"][0]["predicted_price"]
        if predicted_baseline <= 0:
            continue

        pct_diff = ((row.reported_price - predicted_baseline) / predicted_baseline) * 100

        if pct_diff > threshold_pct:
            alerts.append({
                "complaint_id": row.id,
                "item_name": row.commodity_name,
                "shop_name": row.shop_name or "Unknown",
                "market_name": row.market_name,
                "reported_price": row.reported_price,
                "predicted_baseline": round(predicted_baseline, 2),
                "pct_above_baseline": round(pct_diff, 1),
                "status": row.status,
                "submitted_by": row.user_email,
            })

    if not alerts:
        return pd.DataFrame()

    return pd.DataFrame(alerts).sort_values("pct_above_baseline", ascending=False)


def render_predictive_analytics_tab(full_df: pd.DataFrame):
    st.subheader("🔮 Predictive Analytics & Alerts")

    st.markdown("### 🚨 Hoarding Detection")

    threshold_pct = st.slider(
        "Alert threshold — flag complaints reported this much above the model's expected price",
        min_value=10, max_value=100, value=DEFAULT_HOARDING_THRESHOLD_PCT, step=5,
        format="%d%%",
    )

    with st.spinner("Scanning pending complaints against model forecasts..."):
        alerts_df = detect_hoarding_alerts(full_df, st.session_state.base_url, threshold_pct)

    if alerts_df.empty:
        st.success("✅ No pending complaints currently exceed the hoarding threshold.")
    else:
        for row in alerts_df.itertuples():
            st.error(
                f"🔴 **Potential Hoarding Detected** — **{row.item_name}** at "
                f"**{row.shop_name}** ({row.market_name}): reported **Rs. {row.reported_price:.0f}**, "
                f"model expected **Rs. {row.predicted_baseline:.0f}** "
                f"(**+{row.pct_above_baseline}%** above baseline). "
                f"Status: `{row.status}` — submitted by {row.submitted_by}."
            )

        with st.expander(f"View all {len(alerts_df)} flagged complaint(s) as a table"):
            st.dataframe(alerts_df, width="stretch", hide_index=True)

    st.caption(
        "Baseline = the model's predicted price for the upcoming week, refreshed every 5 minutes. "
        "This flags complaints for priority review — it doesn't auto-reject or auto-verify anything."
    )

    st.divider()

    st.markdown("### 📈 Forecast Explorer")

    item_options = fetch_forecastable_items(st.session_state.base_url)
    if not item_options:
        st.warning("Could not load the model's item list from the backend.")
        return
    default_index = item_options.index("Tomato") if "Tomato" in item_options else 0
    selected_item = st.selectbox("Select a commodity", options=item_options, index=default_index)

    forecast_data = fetch_forecast(st.session_state.base_url, selected_item, history_weeks=12)

    if not forecast_data:
        st.warning(
            f"Could not fetch a forecast for '{selected_item}' — either the backend is unreachable, "
            f"or this item isn't in the model's trained item list."
        )
        return

    history_df = pd.DataFrame(forecast_data["history"])
    history_df["type"] = "Historical"
    history_df = history_df.rename(columns={"price": "value"})

    forecast_df = pd.DataFrame(forecast_data["forecast"])
    forecast_df["type"] = "Forecast"
    forecast_df = forecast_df.rename(columns={"predicted_price": "value"})

    bridge_row = pd.DataFrame([{
        "date": forecast_data["last_known_date"],
        "value": forecast_data["last_known_price"],
        "type": "Forecast",
    }])
    forecast_df = pd.concat([bridge_row, forecast_df], ignore_index=True)

    combined = pd.concat([history_df, forecast_df], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])

    chart_df = combined.pivot(index="date", columns="type", values="value")

    with st.container(border=True):
        st.line_chart(chart_df, width="stretch")

    c1, c2, c3 = st.columns(3)
    c1.metric("Last Known Price", f"Rs. {forecast_data['last_known_price']:.0f}", help=forecast_data["last_known_date"])
    c2.metric("Next Week (Predicted)", f"Rs. {forecast_data['forecast'][0]['predicted_price']:.0f}")
    c3.metric("4 Weeks Out (Predicted)", f"Rs. {forecast_data['forecast'][-1]['predicted_price']:.0f}")

    st.caption(
        f"Category: {forecast_data['category']} • Unit: {forecast_data['unit']} • "
        f"Forecast generated: {forecast_data['generated_at']}"
    )


# ============================================================
# MAIN
# ============================================================
def main():
    inject_enterprise_theme()
    inject_complaint_selectbox_styling()
    poll_for_new_complaints()  # NEW — background auto-refresh, no reload/relogin needed

    if not st.session_state.access_token:
        render_login()
        return

    if st.session_state.complaints_df is None:
        with st.spinner("Loading complaints..."):
            ok, msg = fetch_complaints()
        if not ok:
            st.error(msg)
            if "Session expired" in msg:
                st.rerun()
            return

    full_df = st.session_state.complaints_df
    if full_df is None:
        full_df = pd.DataFrame()

    filtered_df = render_sidebar(full_df)

    st.title("🛡️ PriceGuard — Admin Dashboard")

    if full_df.empty:
        st.info("No complaints have been submitted yet.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview & Map", "📋 Complaints Table", "🔍 Detail & Actions", "🔮 Predictive Analytics & Alerts"
    ])
    with tab1:
        render_overview_tab(full_df, filtered_df)
    with tab2:
        render_table_tab(filtered_df)
    with tab3:
        render_detail_tab(filtered_df)
    with tab4:
        render_predictive_analytics_tab(full_df)


if __name__ == "__main__":
    main()