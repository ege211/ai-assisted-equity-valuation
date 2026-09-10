"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8E — Temporal Context UI Component
File: app/components/temporal_context.py

Standardized, reusable UI component displaying temporal research context:
1. Explicit mode banner (LIVE vs HISTORICAL).
2. Authoritative information cutoff date and 23:59:59 timestamp.
3. Informational guidance on SEC EDGAR acceptance_datetime availability rules.
4. Clean presentation-only formatting across all analytical views.
"""

from typing import Any, Dict, Optional

try:
    import streamlit as st
except ImportError:
    st = None


def format_temporal_label(mode: str = "LIVE", as_of_date: Optional[str] = None) -> str:
    """
    Generate a standardized text label representing the active temporal horizon.
    """
    clean_mode = str(mode).strip().upper() if mode else "LIVE"
    if clean_mode == "HISTORICAL":
        if as_of_date:
            date_str = str(as_of_date).strip()
            return f"HISTORICAL (Point-in-Time: {date_str} 23:59:59)"
        return "HISTORICAL (Cutoff Unspecified)"
    return "LIVE (Latest Available)"


def render_temporal_context(
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
    show_box: bool = True,
) -> Dict[str, Any]:
    """
    Render the institutional temporal context banner.

    Args:
        mode: Execution mode ('LIVE' or 'HISTORICAL').
        as_of_date: Optional cutoff date string (YYYY-MM-DD).
        st_client: Optional Streamlit module or mock.
        show_box: Whether to render a visual info banner in Streamlit.

    Returns:
        Dictionary summarizing the active temporal parameters.
    """
    ctx = st_client or st
    clean_mode = str(mode).strip().upper() if mode else "LIVE"
    is_hist = clean_mode == "HISTORICAL"
    date_str = str(as_of_date).strip() if (as_of_date and is_hist) else None

    cutoff_display = f"{date_str} 23:59:59" if (is_hist and date_str) else "None (Latest Available Data)"
    label = format_temporal_label(clean_mode, date_str)

    context_data: Dict[str, Any] = {
        "mode": clean_mode,
        "is_historical": is_hist,
        "as_of_date": date_str,
        "cutoff_timestamp": cutoff_display,
        "cutoff_label": cutoff_display,
        "label": label,
        "rule": (
            f"SEC EDGAR acceptance_datetime <= {cutoff_display}"
            if is_hist
            else "Latest available SEC EDGAR submissions across universe"
        ),
    }

    if ctx is not None and show_box:
        if is_hist:
            if not date_str:
                ctx.warning("⚠️ **Point-in-Time Cutoff Date Missing:** Historical research mode requires an explicit cutoff date (YYYY-MM-DD).")
            else:
                ctx.info(
                    f"⏳ **RESEARCH HORIZON: HISTORICAL** | **AS OF:** `{date_str}` (23:59:59 cutoff) | "
                    f"**Information Availability Rule:** `acceptance_datetime <= {cutoff_display}`\n\n"
                    f"*Strict Point-in-Time Lock: Future filings, disclosures, and accounting revisions post-dating {cutoff_display} are physically excluded.*"
                )
        else:
            ctx.caption(
                "🟢 **RESEARCH HORIZON: LIVE MODE** | **Information Availability Rule:** Latest available SEC EDGAR submissions across universe.\n\n"
                "*Live Evaluation: Incorporates all audited primary filings and quantitative observations currently ingested.*"
            )

    return context_data
