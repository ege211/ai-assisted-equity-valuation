"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Top-Level KPI Cards Component
File: app/components/kpi_cards.py

Renders top-level financial KPI metrics using real DTO values from AnalysisResponse.
Explicitly distinguishes Source Data, Analyst Assumption, and Model Output.
Enforces the core requirement: If a value is unavailable, renders 'N/A' (never synthetic data).
"""

from typing import Any, Dict, Optional
from src.service.contracts import AnalysisResponse

try:
    import streamlit as st
except ImportError:
    st = None


def format_currency(val: Optional[float], decimals: int = 2) -> str:
    """Format floating point currency, or 'N/A' if None."""
    if val is None:
        return "N/A"
    if val < 0:
        return f"-${abs(val):,.{decimals}f}"
    return f"${val:,.{decimals}f}"


def format_percent(val: Optional[float], decimals: int = 2) -> str:
    """Format decimal percentage, or 'N/A' if None."""
    if val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def format_multiple(val: Optional[float], decimals: int = 2) -> str:
    """Format multiple (e.g. 25.4x), or 'N/A' if None."""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}x"


def format_count(val: Optional[int]) -> str:
    """Format integer count, or 'N/A' if None."""
    if val is None:
        return "N/A"
    return str(val)


def render_kpi_cards(
    response: Optional[AnalysisResponse],
    st_client: Any = None,
) -> Dict[str, str]:
    """
    Render top-level executive KPI cards from an AnalysisResponse.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        st_client: Optional Streamlit module or mock.

    Returns:
        Dictionary of formatted KPI strings.
    """
    ctx = st_client or st

    # Default all KPIs to "N/A"
    kpis = {
        "fair_value_per_share": "N/A",
        "enterprise_value": "N/A",
        "wacc": "N/A",
        "pe_multiple": "N/A",
        "verified_claims_count": "N/A",
        "analysis_status": "N/A",
    }

    if response is not None:
        kpis["analysis_status"] = response.status

        # Valuation outputs
        if response.valuation is not None:
            val = response.valuation
            kpis["fair_value_per_share"] = format_currency(val.fair_value_per_share)
            if val.enterprise_value is not None:
                ev_b = val.enterprise_value / 1e9
                prefix = "-$" if ev_b < 0 else "$"
                kpis["enterprise_value"] = f"{prefix}{abs(ev_b):,.1f}B"
            else:
                kpis["enterprise_value"] = "N/A"
            kpis["wacc"] = format_percent(val.wacc)

            # Relative valuation
            if val.relative_multiples:
                pe_summary = next(
                    (m for m in val.relative_multiples if "PE" in m.multiple_name.upper()),
                    None,
                )
                if pe_summary and pe_summary.company_multiple is not None:
                    kpis["pe_multiple"] = format_multiple(pe_summary.company_multiple)

        # Filing intelligence outputs
        if response.filing_intelligence is not None:
            fi = response.filing_intelligence
            kpis["verified_claims_count"] = format_count(fi.validated_claims_count)

    if ctx is not None:
        cols = ctx.columns(6)
        if isinstance(cols, (list, tuple)) and len(cols) == 6:
            c1, c2, c3, c4, c5, c6 = cols
        else:
            c1 = c2 = c3 = c4 = c5 = c6 = ctx

        c1.metric(
            label="Base Fair Value",
            value=kpis["fair_value_per_share"],
            help="[MODEL OUTPUT] Base-case DCF fair value per share from deterministic valuation engine.",
        )
        c2.metric(
            label="Enterprise Value",
            value=kpis["enterprise_value"],
            help="[MODEL OUTPUT] Implied enterprise value from discounted cash flows.",
        )
        c3.metric(
            label="Base WACC",
            value=kpis["wacc"],
            help="[ANALYST ASSUMPTION] Cost of capital calibrated from static risk-free rate, beta, and equity risk premium.",
        )
        c4.metric(
            label="LTM P/E Multiple",
            value=kpis["pe_multiple"],
            help="[SOURCE DATA] Trailing Twelve Months Price-to-Earnings multiple computed from audited financials.",
        )
        c5.metric(
            label="Verified Claims",
            value=kpis["verified_claims_count"],
            help="[SOURCE DATA] Count of qualitative disclosures anchored to verbatim SEC primary source text.",
        )
        c6.metric(
            label="Engine Status",
            value=kpis["analysis_status"],
            help="[PLATFORM] Execution integrity status (SUCCESS indicates complete valuation and evidence suite).",
        )

    return kpis
