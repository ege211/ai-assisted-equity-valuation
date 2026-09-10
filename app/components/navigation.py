"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Navigation Component
File: app/components/navigation.py

Renders the multi-tab navigation bar for the platform's core views:
1. Overview
2. Valuation
3. Fundamentals
4. Filing Intelligence
5. Evidence
6. What Changed
"""

from typing import Any, List
from app.state import get_state, set_state

try:
    import streamlit as st
except ImportError:
    st = None

NAV_PAGES: List[str] = [
    "Overview",
    "Valuation",
    "Fundamentals",
    "Filing Intelligence",
    "Evidence",
    "What Changed",
]


def render_navigation(st_client: Any = None) -> str:
    """
    Render horizontal or sidebar navigation controls.

    Args:
        st_client: Optional Streamlit module or mock.

    Returns:
        The active page name string.
    """
    ctx = st_client or st
    current_page = get_state("active_page", "Overview", ctx)

    default_idx = 0
    if current_page in NAV_PAGES:
        default_idx = NAV_PAGES.index(current_page)

    selected_page = current_page

    if ctx is not None:
        # Render clean radio selector in sidebar or tab selector
        ctx.sidebar.markdown("---")
        ctx.sidebar.markdown("### Platform Navigation")
        selected_page = ctx.sidebar.radio(
            "Go to View",
            options=NAV_PAGES,
            index=default_idx,
            label_visibility="collapsed",
        )
        set_state("active_page", selected_page, ctx)

    return selected_page
