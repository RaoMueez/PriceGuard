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
DEFAULT_BASE_URL = "http://localhost:8000"

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
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["reviewed_at"] = pd.to_datetime(df["reviewed_at"])
    df["status_category"] = df["status"].apply(categorize_status)

    # Fall back to market coordinates for the map when device GPS wasn't
    # captured (e.g. location permission denied) — flagged via location_source
    # so it's clear in the map tooltip which one is being shown.
    df["map_latitude"] = df["device_latitude"].fillna(df["market_latitude"])
    df["map_longitude"] = df["device_longitude"].fillna(df["market_longitude"])
    df["location_source"] = df["device_latitude"].apply(
        lambda v: "Device GPS" if pd.notnull(v) else "Market (fallback)"
    )

    st.session_state.complaints_df = df
    return True, f"Loaded {len(df)} complaints."


def update_complaint_status(complaint_id: str, new_status: str, admin_note: str = "") -> tuple[bool, str, dict]:
    """
    Returns (success, message, debug_info). debug_info always contains the
    raw status_code and response body so failures are never silent — if this
    fails again, the expander in the UI will show exactly why (401 = token
    expired, 422 = bad payload, 404 = wrong id, 500 = server-side error, etc.)
    instead of just "it didn't work."
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

    # The PATCH endpoint returns the updated complaint — confirm the status
    # in that response actually matches what we asked for. If it doesn't,
    # that's a backend logic bug, not a frontend refresh issue.
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
# LOGIN SCREEN
# ============================================================
def render_login():
    st.title("🛡️ PriceGuard Admin Dashboard")
    st.caption("Log in with an admin account to review and action complaints.")

    with st.form("login_form"):
        base_url = st.text_input("Backend URL", value=st.session_state.base_url)
        email = st.text_input("Admin email", value="admin@priceguard.com")
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

    # date_input returns a single date until the user picks a second one —
    # guard against that instead of crashing on unpacking.
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered["created_at"].dt.date >= start) & (filtered["created_at"].dt.date <= end)
        ]

    return filtered


# ============================================================
# TAB 1 — OVERVIEW & MAP
# ============================================================
def render_overview_tab(full_df: pd.DataFrame, filtered_df: pd.DataFrame):
    st.subheader("Overview")

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

    # "verified" is the exact enum value set when an admin confirms a violation
    # (via the Verify Violation button / manual override) — everything else,
    # including pending/mismatch/handwritten/location-mismatch/rejected/spam,
    # lands in the right-hand "Other" column.
    verified_df = filtered_df[filtered_df["status"] == "verified"]
    other_df = filtered_df[filtered_df["status"] != "verified"]

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader(f"✅ Verified Complaints ({len(verified_df)})")
        if verified_df.empty:
            st.info("No verified complaints yet.")
        else:
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

    # Whitelist now includes "verified" too — without it, an admin who just
    # verified a complaint has no way to come back and mark it resolved,
    # since it would vanish from this dropdown immediately after verifying.
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

    # Layout fix for Goal 3: gives the dropdown genuine room to open downward
    # instead of fighting the library's auto-flip logic with CSS. Only
    # matters when this selectbox is near the bottom of the visible viewport
    # (e.g. sidebar filters collapsed a lot of content above it); harmless
    # otherwise.
    st.markdown('<div style="height: 260px;"></div>', unsafe_allow_html=True)
    complaint_id = options[selected_label]
    row = sorted_df[sorted_df["id"] == complaint_id].iloc[0]

    img_col, data_col = st.columns([1, 1.2])

    with img_col:
        st.markdown("**Receipt Image**")
        image_url = f"{st.session_state.base_url}{row['receipt_image_url']}"
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
        # Not yet verified — offer the first-pass decision.
        a1, a2 = st.columns(2)

        if a1.button("✅ Verify Violation", width="stretch", key=f"verify_{complaint_id}"):
            ok, msg, debug_info = update_complaint_status(str(complaint_id), "verified", note or "Verified by admin.")
            _handle_action_result(ok, msg, debug_info, complaint_id, "verified")

        if a2.button("❌ Reject as Spam", width="stretch", key=f"reject_{complaint_id}"):
            ok, msg, debug_info = update_complaint_status(str(complaint_id), "dismissed", note or "Rejected as spam/invalid by admin.")
            _handle_action_result(ok, msg, debug_info, complaint_id, "dismissed")

    elif current_status == "verified":
        # Already confirmed as a genuine violation — the only remaining step
        # is closing it out once whatever action was taken (fine issued,
        # shop warned, etc.) is done.
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
        # Don't refetch/rerun on failure — let the admin see the error and
        # the expander above instead of it flashing away on an immediate rerun.
        return

    fetch_ok, fetch_msg = fetch_complaints()
    if not fetch_ok:
        st.warning(f"Update succeeded, but re-fetching the complaint list failed: {fetch_msg}")
        return

    # Cross-check: does the freshly re-fetched data actually show the new status
    # for this specific complaint? If the PATCH confirmed success but this check
    # fails, that's evidence of a backend read-after-write issue (e.g. Neon
    # pooled-connection staleness) rather than a Streamlit-side bug.
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
# MAIN
# ============================================================
# ============================================================
# CUSTOM SELECTBOX BEHAVIOR (Details & Actions dropdown only)
#
# CAVEATS — read before relying on this for a live demo:
#   - Streamlit's selectbox is built on an internal library (BaseWeb) with
#     no supported customization API. This works on Streamlit 1.51.0 by
#     targeting its current DOM structure; a future Streamlit upgrade could
#     change that structure and silently break this.
#   - Goal 1 (disable typing) requires actual JavaScript — CSS cannot
#     prevent keyboard input. This uses a small script that finds the
#     dropdown's input field and sets it read-only, while leaving click-to-
#     open working normally.
#   - Goal 3 (force downward) is a genuine layout fix (extra space below,
#     which is your own suggested approach) rather than fighting the
#     library's position calculation — forcing it via CSS override risks
#     the menu rendering off-screen if the viewport truly has no room.
# ============================================================
def inject_complaint_selectbox_styling():
    st.markdown(
        """
        <style>
        /* Scoped via the marker element placed right before the selectbox
           in render_detail_tab — targets only that one widget, not every
           selectbox/multiselect in the app. */
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

    # JS: make the underlying <input> read-only so typing/searching is
    # blocked, while the element remains clickable to open the dropdown.
    # Runs inside an iframe (components.html), so it reaches into the
    # parent document — this is the standard workaround for Streamlit,
    # not an officially supported pattern.
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
        // Streamlit re-renders on every interaction, so keep checking
        // rather than running once.
        setInterval(lockComplaintSelectbox, 400);
        </script>
        """,
        height=0,
    )


def main():
    inject_complaint_selectbox_styling()

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

    tab1, tab2, tab3 = st.tabs(["📊 Overview & Map", "📋 Complaints Table", "🔍 Detail & Actions"])
    with tab1:
        render_overview_tab(full_df, filtered_df)
    with tab2:
        render_table_tab(filtered_df)
    with tab3:
        render_detail_tab(filtered_df)


if __name__ == "__main__":
    main()