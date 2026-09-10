"""
Shared page chrome: hides Streamlit's auto-generated sidebar (this app
uses its own nav row instead), disables the Plotly chart "Fullscreen"
modebar button, and kicks off the OneDrive auto-sync check.

The fullscreen button uses the browser's native Fullscreen API on the
chart's own DOM node. When a background auto-refresh (st.fragment) sends
a new Plotly figure while that element is in native fullscreen, the
browser does not reliably repaint it until fullscreen is exited - a
known interaction issue between Streamlit/Plotly and the Fullscreen API,
not something app code can fix from the Python side. Removing the button
is the most reliable way to keep the live map from ever getting stuck.
"""

import streamlit as st

from backend.onedrive_sync import maybe_auto_sync

PAGES = [
    ("app.py", "🏠 Home"),
    ("pages/1_Live_Map.py", "🗺️ Live Map"),
    ("pages/2_Simulation_Control.py", "🎮 Simulation"),
    ("pages/3_Movement_History.py", "📜 Movement"),
    ("pages/4_Tag_Management.py", "🏷️ Management"),
    ("pages/5_System_Debug.py", "🛠️ Debug"),
    ("pages/6_Import_Stock.py", "📥 Import Stock"),
]


def apply_page_chrome():
    """Hide the default sidebar/page-nav and the Plotly fullscreen button,
    and check whether a OneDrive auto-sync is due. Call once near the top
    of every page."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        button[data-title="Fullscreen"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    try:
        maybe_auto_sync()
    except Exception:
        pass  # never let a sync hiccup break page rendering


def render_nav(current: str):
    """A row of navigation buttons replacing the hidden sidebar. `current`
    is the page path (matching the second element of a PAGES tuple's
    first element) to skip linking to itself."""
    targets = [p for p in PAGES if p[0] != current]
    cols = st.columns(len(targets))
    for col, (path, label) in zip(cols, targets):
        with col:
            st.page_link(path, label=label, width="stretch")
