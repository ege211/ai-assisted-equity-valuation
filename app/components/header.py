"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Institutional Header Component
File: app/components/header.py

Renders the top institutional research terminal banner, company profile badge,
and explicit analytical taxonomy tags (Source Data, Analyst Assumption, Model Output).
"""

from typing import Any, Dict, List, Optional
from src.service.contracts import CompanyProfile

try:
    import streamlit as st
except ImportError:
    st = None


def render_header(
    profile: Optional[CompanyProfile] = None,
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    status: str = "SUCCESS",
    warnings: Optional[List[str]] = None,
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render the institutional terminal header and taxonomy banner.

    Args:
        profile: Optional CompanyProfile DTO from PlatformService.
        mode: Valuation mode ('LIVE' or 'HISTORICAL').
        as_of_date: Cutoff date string (if HISTORICAL).
        status: Analysis status ('SUCCESS' or 'PARTIAL').
        warnings: List of diagnostic warning strings if partial.
        st_client: Optional Streamlit module or mock.

    Returns:
        Structured dictionary summarizing rendered header elements.
    """
    ctx = st_client or st
    warnings = warnings or []

    # Format header metadata
    date_display = as_of_date if (mode == "HISTORICAL" and as_of_date) else "Latest Available"
    company_title = (
        f"{profile.company_name.upper()} ({profile.ticker}) · {profile.sector}"
        if profile is not None
        else "Equity Intelligence Terminal"
    )

    header_data = {
        "title": company_title,
        "mode": mode,
        "date_display": date_display,
        "sector": profile.sector if profile else "N/A",
        "cik": profile.cik if profile else "N/A",
        "fy_end": str(profile.fiscal_year_end_month) if (profile and profile.fiscal_year_end_month) else "N/A",
        "status": status,
        "warnings": warnings,
        "taxonomy": {
            "source_data": "SEC EDGAR XBRL & 10-K/10-Q Primary Filings",
            "analyst_assumptions": "Static Market Registry (Rf, Beta, ERP)",
            "model_output": "Deterministic Discounted Cash Flow & Relative Multiples",
        },
    }

    if ctx is not None:
        # Title and institutional subtitle
        ctx.title("AI-Assisted Equity Valuation & Investment Intelligence")
        ctx.caption(
            "Institutional Research Terminal | Deterministic Valuation & Verified SEC Filing Intelligence"
        )

        # Company profile banner
        if profile is not None:
            ctx.subheader(company_title)
            cols = ctx.columns(4)
            if isinstance(cols, (list, tuple)) and len(cols) == 4:
                c1, c2, c3, c4 = cols
            else:
                c1 = c2 = c3 = c4 = ctx
            c1.markdown(f"**Entity:** `{profile.ticker}` · {profile.company_name}")
            c2.markdown(f"**SEC CIK:** `{profile.cik}` | **Sector:** {profile.sector}")
            c3.markdown(f"**Analysis Mode:** `{mode}`")
            if mode == "HISTORICAL":
                c4.markdown(f"**PIT Cutoff:** `AS OF {as_of_date} · 23:59:59`")
            else:
                c4.markdown("**PIT Cutoff:** `LIVE · Latest Available Information`")

        # Explicit Analytical Taxonomy Bar
        ctx.markdown(
            "> **ANALYTICAL TAXONOMY:** "
            "`[SOURCE DATA]` SEC EDGAR Facts & Primary Disclosures | "
            "`[ANALYST ASSUMPTION]` Static Market Registry Parameters | "
            "`[MODEL OUTPUT]` Deterministic Valuation Engine"
        )

        # Partial status notification
        if status == "PARTIAL":
            ctx.warning(
                "Notice: Analysis completed with partial data availability. "
                "Certain valuation or qualitative modules could not be computed for this period."
            )
            if warnings:
                with ctx.expander("Diagnostic Warnings", expanded=False):
                    for w in warnings:
                        ctx.write(f"- {w}")

    return header_data
