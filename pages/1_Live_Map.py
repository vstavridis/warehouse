"""Live Warehouse Map - Area 1 (includes coil search / locate)."""

import json

import streamlit as st

import config
from backend.database import init_db
from backend import models
from backend.ui import apply_page_chrome
from backend.warehouse_map import build_map_figure
from backend.positioning import is_low_confidence

st.set_page_config(page_title="Live Map", page_icon="🗺️", layout="wide")
init_db()
apply_page_chrome()

if "selected_coil" not in st.session_state:
    st.session_state.selected_coil = None


def _format_value(value):
    """Numbers coming out of Excel formulas often carry long floating-point
    tails (e.g. 609.7664543524415 for a meters column); round those down
    to a plain whole number for display. Text values pass through as-is."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            return f"{round(value):,}"
        except (ValueError, OverflowError):
            return value
    return value


def _mark_dialog_dismissed():
    # Closing the dialog appears to make the underlying Plotly component
    # remount, which replays its last-known selection as if it were a
    # brand new click on the very next run - without this flag, that
    # phantom event would reopen the popup the moment it's closed. Set
    # here (an on_dismiss callback fires before the following rerun) so
    # that one replayed event can be told apart from a genuine click.
    st.session_state["_suppress_next_chart_event"] = True


@st.dialog("Coil Details", on_dismiss=_mark_dialog_dismissed, width="large")
def show_coil_dialog(coil_id: str):
    coil = models.get_coil(coil_id)
    if coil is None:
        st.error(f"{coil_id} not found.")
        return

    position = models.get_position(coil["current_position"]) if coil["current_position"] else None

    lock_badge = (
        ' <span style="color:#E53935; font-size:0.6em; vertical-align:middle;">🔒</span>'
        if coil["locked"] else ""
    )
    st.markdown(f"### {coil['coil_id']}{lock_badge}", unsafe_allow_html=True)

    if position is None:
        st.warning(f"{coil['coil_id']} is currently **{coil['status']}** and has no "
                   f"position in the warehouse (likely sent to production).")
        return

    status_icon = {
        config.COIL_STATUS_STATIONARY: "🟢",
        config.COIL_STATUS_MOVING: "🟠",
        config.COIL_STATUS_PRODUCTION: "⚪",
        config.COIL_STATUS_MISSING: "🔴",
    }.get(coil["status"], "⚪")

    extra_fields = json.loads(coil["extra_fields"]) if coil["extra_fields"] else {}

    def _core_details():
        st.markdown(f"**Status:** {status_icon} {coil['status']}")
        st.write(f"**Tag ID:** {coil['tag_id'] or '—'}")
        st.write(f"**Area:** {config.AREA_1}")
        st.write(f"**Column:** {position['column_name']}")
        st.write(f"**Position:** {position['position_id']}")
        st.write(f"**Level:** {position['level']}")
        st.write(f"**Last Movement:** {coil['last_movement'] or '—'}")
        st.write(f"**Last Seen:** {coil['last_seen'] or '—'}")
        conf = coil["location_confidence"]
        if conf is not None:
            st.write(f"**Location Confidence:** {conf}%")
            if is_low_confidence(conf):
                st.warning("Low location confidence")

    if extra_fields:
        # A vertical divider (instead of stacking the stock-list details
        # below everything) keeps the popup wide and short rather than
        # narrow and tall. st.columns has no built-in divider, so this
        # scopes a border-left onto the second column via CSS - scoped to
        # inside the dialog specifically, so it doesn't affect any other
        # two-column layout elsewhere in the app.
        st.markdown(
            """
            <style>
            div[data-testid="stDialog"] div[data-testid="stColumn"]:nth-of-type(2) {
                border-left: 1px solid rgba(150, 150, 150, 0.35);
                padding-left: 1.5rem;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        left, right = st.columns(2)
        with left:
            _core_details()
        with right:
            st.markdown("**Stock details**")
            for label, value in extra_fields.items():
                st.write(f"**{label}:** {_format_value(value)}")
    else:
        _core_details()


top = st.columns([6, 1])
with top[1]:
    st.page_link("app.py", label="🏠 Home", width="stretch")

SELECT_KEY = "coil_search_selectbox"


@st.fragment(run_every=config.LIVE_MAP_REFRESH_SECONDS)
def live_map_chart():
    # The search box has to stay inside this fragment (not hoisted out
    # next to the nav row below) so that a coil clicked directly on the
    # map - which only triggers a fragment-scoped rerun - immediately
    # updates the dropdown too, instead of waiting for a full page rerun.
    coils = models.get_active_coils()
    coil_ids = sorted(coils["coil_id"].tolist()) if not coils.empty else []

    # Sync the dropdown's displayed value FROM selected_coil (e.g. after a
    # map click) rather than the other way around. A plain `index=` based
    # on selected_coil doesn't work here: once a selectbox has its own
    # stored widget state, Streamlit keeps returning THAT on every rerun
    # regardless of `index`, which would silently reset selected_coil back
    # on every single tick - exactly the "click works once, never again"
    # bug this caused.
    desired = st.session_state.selected_coil if st.session_state.selected_coil in coil_ids else "-"
    if st.session_state.get(SELECT_KEY) != desired:
        st.session_state[SELECT_KEY] = desired

    chosen = st.selectbox("🔍 Search Coil", options=["-"] + coil_ids, key=SELECT_KEY)
    if chosen != desired:
        # The dropdown value changed because the user actually picked
        # something themselves, not because we just set it above.
        st.session_state.selected_coil = None if chosen == "-" else chosen

    # Only rebuild the figure when something that would actually change
    # its appearance has changed (a coil moved/changed status, or the
    # selection changed) - not on every single timer tick. This is the
    # only lever available from application code to reduce how often the
    # chart visibly redraws: Streamlit still re-sends the (identical,
    # cached) figure every tick so click events keep being delivered, but
    # an unchanged figure means the frontend has nothing new to draw.
    signature = (
        tuple(sorted(
            (r.coil_id, r.current_position, r.status, r.locked)
            for r in coils.itertuples()
        )),
        st.session_state.selected_coil,
    )
    if st.session_state.get("_map_signature") != signature:
        st.session_state["_map_fig"] = build_map_figure(selected_coil_id=st.session_state.selected_coil)
        st.session_state["_map_signature"] = signature
    fig = st.session_state["_map_fig"]

    event = st.plotly_chart(
        fig,
        width="stretch",
        theme=None,
        key="live_map_chart",
        on_select="rerun",
        selection_mode=["points"],
    )

    current_id = None
    if event and event.get("selection", {}).get("points"):
        for pt in event["selection"]["points"]:
            if pt.get("customdata"):
                current_id = pt["customdata"]
                break

    if st.session_state.pop("_suppress_next_chart_event", False):
        # The dialog was just dismissed and the chart likely remounted,
        # replaying its last selection as a phantom "new" event. Absorb
        # it silently instead of reopening the popup unprompted.
        st.session_state["_chart_had_selection"] = current_id is not None
    else:
        # Plotly's click-to-select TOGGLES: clicking an already-selected
        # point deselects it (an empty event on the very next click)
        # rather than re-reporting the same selection - there's no way to
        # disable that, it's how Plotly's own frontend handles clicks in
        # "points" selection mode. So instead of only reacting to "a point
        # is selected", track whether a point WAS selected on the last run
        # and react to the transition either way: newly-selected (or a
        # different coil than before) opens its popup, and
        # newly-DESELECTED (this run's empty event right after a selected
        # one) is read as "the user clicked that same coil again" and
        # reopens its popup too - so every genuine click, on any coil,
        # always opens something, regardless of Plotly's own toggle state.
        had_selection = st.session_state.get("_chart_had_selection", False)

        if current_id is not None:
            is_new_click = (current_id != st.session_state.get("_last_opened_for")) or not had_selection
            st.session_state.selected_coil = current_id
            if is_new_click:
                st.session_state["_last_opened_for"] = current_id
                show_coil_dialog(current_id)
        elif had_selection:
            prev = st.session_state.get("_last_opened_for")
            if prev:
                show_coil_dialog(prev)

        st.session_state["_chart_had_selection"] = current_id is not None


live_map_chart()

st.divider()
nav = st.columns(4)
with nav[0]:
    st.page_link("pages/2_Simulation_Control.py", label="🎮 Simulation", width="stretch")
with nav[1]:
    st.page_link("pages/3_Movement_History.py", label="📜 Movement", width="stretch")
with nav[2]:
    st.page_link("pages/4_Tag_Management.py", label="🏷️ Management", width="stretch")
with nav[3]:
    st.page_link("pages/5_System_Debug.py", label="🛠️ Debug", width="stretch")
