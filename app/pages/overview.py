"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8G — Executive Research Terminal Overview
File: app/pages/overview.py

Renders the executive research terminal dashboard:
1. Corporate Identity & Point-in-Time Context
2. Key Valuation KPIs (Market Price, Fair Value, Upside/Downside, WACC, Terminal Growth)
3. Fundamental Snapshot (Revenue, EBIT Margin, FCF, Net Debt, Cash)
4. Filing Intelligence Summary (Covered Filings, Validated Disclosures, Quarantined Claims)
5. Frozen Phase 7 Academic Research Disclosure
6. Source Provenance & Lineage Badge
7. Foundational System Axioms
"""

from typing import Any, Dict, Optional
from src.service.contracts import AnalysisResponse
from app.components.temporal_context import render_temporal_context
from app.components.provenance import render_source_provenance_badge

try:
    import streamlit as st
except ImportError:
    st = None


def _format_currency(val: Optional[float], decimals: int = 2) -> str:
    """Format currency values with sign preservation."""
    if val is None:
        return "N/A"
    prefix = "-$" if val < 0 else "$"
    return f"{prefix}{abs(val):,.{decimals}f}"


def _format_large_currency(val: Optional[float], decimals: int = 1) -> str:
    """Format large currency values in Billions/Millions."""
    if val is None:
        return "N/A"
    abs_v = abs(val)
    prefix = "-$" if val < 0 else "$"
    if abs_v >= 1e9:
        return f"{prefix}{abs_v / 1e9:,.{decimals}f}B"
    if abs_v >= 1e6:
        return f"{prefix}{abs_v / 1e6:,.{decimals}f}M"
    return f"{prefix}{abs_v:,.{decimals}f}"


def _format_pct(val: Optional[float], decimals: int = 1) -> str:
    """Format percentage values."""
    if val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def render_overview_page(
    response: Optional[AnalysisResponse],
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render the executive overview research terminal page.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        mode: Valuation mode ('LIVE' or 'HISTORICAL').
        as_of_date: Point-in-time cutoff date string (if HISTORICAL).
        st_client: Optional Streamlit module or mock.

    Returns:
        Structured data dictionary for testing/headless execution.
    """
    ctx = st_client or st

    profile_data: Dict[str, Any] = {}
    disclosure_data: Dict[str, Any] = {}
    valuation_kpis: Dict[str, Any] = {}
    fundamental_snapshot: Dict[str, Any] = {}
    filing_summary: Dict[str, Any] = {}

    if response is not None:
        p = response.profile
        profile_data = {
            "ticker": p.ticker,
            "company_name": p.company_name,
            "cik": p.cik,
            "sector": p.sector,
            "fiscal_year_end_month": p.fiscal_year_end_month,
            "covered_filings_count": p.covered_filings_count,
            "latest_filing_date": p.latest_filing_date,
        }

        d = response.research_disclosure
        disclosure_data = {
            "primary_target": d.primary_target,
            "sample_size": d.sample_size_longitudinal,
            "walk_forward_folds": d.walk_forward_folds,
            "baseline_mae": d.baseline_mae,
            "enhanced_mae": d.enhanced_mae,
            "p_value": d.p_value,
            "hypothesis_decision": d.hypothesis_decision,
            "key_takeaway": d.key_takeaway,
            "curse_of_dimensionality": d.curse_of_dimensionality_finding,
            "filing_only_parity": d.filing_only_parity_finding,
            "limitations": d.limitations,
        }

        # 1. Valuation KPIs
        if response.valuation is not None:
            v = response.valuation
            valuation_kpis = {
                "market_price": v.current_share_price,
                "fair_value_per_share": v.fair_value_per_share,
                "upside_downside": v.upside_downside,
                "wacc": v.wacc,
                "terminal_growth": v.terminal_growth,
                "enterprise_value": v.enterprise_value,
                "equity_value": v.equity_value,
            }

            # 2. Fundamental Snapshot from Valuation LTM / Balance Sheet
            fundamental_snapshot = {
                "net_debt": v.net_debt,
                "cash": v.cash,
                "total_debt": v.total_debt,
                "diluted_shares": v.diluted_shares,
                "revenue_growth_summary": v.revenue_growth_summary,
                "ebit_margin_summary": v.ebit_margin_summary,
            }

            # If forecast periods are available, capture Year 1 revenue/EBIT/FCF
            if v.forecast_periods:
                p1 = v.forecast_periods[0]
                fundamental_snapshot["year1_revenue"] = p1.revenue
                fundamental_snapshot["year1_ebit"] = p1.ebit
                fundamental_snapshot["year1_ebit_margin"] = p1.ebit_margin
                fundamental_snapshot["year1_fcff"] = p1.fcff

        # 3. Filing Intelligence Summary
        if response.filing_intelligence is not None:
            fi = response.filing_intelligence
            filing_summary = {
                "total_claims": fi.total_claims_retrieved,
                "validated_claims": fi.validated_claims_count,
                "quarantined_claims": fi.rejected_claims_count,
                "covered_accessions_count": len(fi.covered_accessions),
            }

    eff_mode = (response.request.mode if (response and response.request) else mode).upper()
    eff_as_of_date = response.request.as_of_date if (response and response.request) else as_of_date

    page_data: Dict[str, Any] = {
        "ticker": profile_data.get("ticker"),
        "profile": profile_data,
        "disclosure": disclosure_data,
        "valuation_kpis": valuation_kpis,
        "fundamental_snapshot": fundamental_snapshot,
        "filing_summary": filing_summary,
        "mode": eff_mode,
        "as_of_date": eff_as_of_date,
    }

    if ctx is not None:
        ctx.header("Executive Overview & Company Profile")
        render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)

        if response is None:
            ctx.info("Select a company from the sidebar to load the institutional research profile.")
            return page_data

        # ======================================================================
        # 1. CORPORATE PROFILE & HISTORICAL COVERAGE
        # ======================================================================
        cols = ctx.columns(2)
        c1, c2 = cols if (isinstance(cols, (list, tuple)) and len(cols) == 2) else (ctx, ctx)
        with c1:
            ctx.markdown("#### Corporate Profile")
            ctx.write(f"**Entity Name:** {profile_data.get('company_name', 'N/A')}")
            ctx.write(f"**Ticker:** `{profile_data.get('ticker', 'N/A')}`")
            ctx.write(f"**SEC CIK:** `{profile_data.get('cik', 'N/A')}`")
            ctx.write(f"**GICS Sector:** {profile_data.get('sector', 'N/A')}")
            ctx.write(f"**FY End Month:** {profile_data.get('fiscal_year_end_month', 'N/A')}")

        with c2:
            ctx.markdown("#### Filing Coverage & Data Status")
            ctx.write(f"**Audited Filings in Database:** {profile_data.get('covered_filings_count', 'N/A')}")
            ctx.write(f"**Latest Filing Date:** `{profile_data.get('latest_filing_date', 'N/A')}`")
            if eff_mode == "HISTORICAL":
                ctx.write(f"**Coverage Status:** `HISTORICAL POINT-IN-TIME (Cutoff: {eff_as_of_date} 23:59:59)`")
                ctx.warning(f"Some historical data may be unavailable for cutoff {eff_as_of_date}.")
            else:
                ctx.write("**Coverage Status:** `ACTIVE (LIVE / LATEST AVAILABLE)`")

        # Provenance Lineage Badge
        prov = (
            response.valuation.valuation_lineage.source_provenance
            if (response.valuation and response.valuation.valuation_lineage)
            else None
        )
        render_source_provenance_badge(prov, st_client=ctx)

        ctx.markdown("---")

        # ======================================================================
        # 2. KEY VALUATION KPIS
        # ======================================================================
        ctx.markdown("### Executive Valuation Dashboard `[MODEL OUTPUT]`")
        k_cols = ctx.columns(5) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx, ctx)
        if isinstance(k_cols, (list, tuple)) and len(k_cols) == 5:
            fv_val = valuation_kpis.get("fair_value_per_share")
            mp_val = valuation_kpis.get("market_price")
            up_val = valuation_kpis.get("upside_downside")
            wacc_val = valuation_kpis.get("wacc")
            g_val = valuation_kpis.get("terminal_growth")

            k_cols[0].metric(
                "DCF Fair Value",
                _format_currency(fv_val),
                help="[MODEL OUTPUT] Base DCF intrinsic value per share.",
            )
            k_cols[1].metric(
                "Market Price",
                _format_currency(mp_val),
                help="[MARKET PRICE] Observed trading price at valuation date.",
            )
            delta_str = f"{up_val * 100:+.1f}%" if up_val is not None else None
            k_cols[2].metric(
                "Implied Upside / (Downside)",
                delta_str or "N/A",
                delta=delta_str,
                help="[MODEL OUTPUT] Relative difference between DCF fair value and market price.",
            )
            k_cols[3].metric(
                "Cost of Capital (WACC)",
                _format_pct(wacc_val),
                help="[ANALYST ASSUMPTION] Calibrated Weighted Average Cost of Capital.",
            )
            k_cols[4].metric(
                "Terminal Growth (g)",
                _format_pct(g_val),
                help="[ANALYST ASSUMPTION] Perpetual growth rate for Gordon Growth terminal value.",
            )

        ctx.markdown("---")

        # ======================================================================
        # 3. FUNDAMENTAL SNAPSHOT & CAPITAL STRUCTURE
        # ======================================================================
        ctx.markdown("### Fundamental Snapshot & Capital Structure `[SOURCE DATA]`")
        f_cols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
        if isinstance(f_cols, (list, tuple)) and len(f_cols) == 4:
            f_cols[0].metric(
                "Net Debt",
                _format_large_currency(fundamental_snapshot.get("net_debt")),
                help="[SOURCE DATA] Total Debt minus Cash & Cash Equivalents.",
            )
            f_cols[1].metric(
                "Cash & Equivalents",
                _format_large_currency(fundamental_snapshot.get("cash")),
                help="[SOURCE DATA] Balance sheet liquid reserves.",
            )
            f_cols[2].metric(
                "Total Debt",
                _format_large_currency(fundamental_snapshot.get("total_debt")),
                help="[SOURCE DATA] Short-term plus long-term debt obligations.",
            )
            shares = fundamental_snapshot.get("diluted_shares")
            f_cols[3].metric(
                "Diluted Shares",
                f"{shares / 1e6:,.1f}M" if shares else "N/A",
                help="[SOURCE DATA] Weighted average diluted shares outstanding.",
            )

        ctx.markdown("---")

        # ======================================================================
        # 4. FILING INTELLIGENCE & AUDIT SUMMARY
        # ======================================================================
        ctx.markdown("### Filing Intelligence & Evidence Grounding `[SOURCE DATA]`")
        fi_cols = ctx.columns(3) if hasattr(ctx, "columns") else (ctx, ctx, ctx)
        if isinstance(fi_cols, (list, tuple)) and len(fi_cols) == 3:
            fi_cols[0].metric(
                "Total Claims Retrieved",
                str(filing_summary.get("total_claims", "N/A")),
                help="[SOURCE DATA] Total qualitative disclosure claims extracted from SEC filings.",
            )
            fi_cols[1].metric(
                "Validated Disclosures",
                str(filing_summary.get("validated_claims", "N/A")),
                help="[EVIDENCE] Claims passing exact verbatim quote validation against SEC filings.",
            )
            fi_cols[2].metric(
                "Quarantined Claims",
                str(filing_summary.get("quarantined_claims", "N/A")),
                help="[GOVERNANCE] Unverified claims quarantined and excluded from analysis.",
            )

        ctx.markdown("---")

        # ======================================================================
        # 5. FROZEN PHASE 7 ACADEMIC RESEARCH DISCLOSURE
        # ======================================================================
        ctx.markdown("### Academic Research Disclosure (Phase 7 Longitudinal Audit)")
        if disclosure_data:
            ctx.info(
                f"**Methodological Benchmark:** {disclosure_data.get('key_takeaway')}\n\n"
                f"- **Primary Target:** `{disclosure_data.get('primary_target')}`\n"
                f"- **Sample Size:** $N = {disclosure_data.get('sample_size')}$ complete cases across 30 companies\n"
                f"- **Validation Scheme:** {disclosure_data.get('walk_forward_folds')}-fold expanding-window chronological walk-forward\n"
                f"- **Model A Baseline (Fundamental Only):** MAE = {disclosure_data.get('baseline_mae', 0.0777):.4f}\n"
                f"- **Model B Operational (Pre-Specified):** MAE = {disclosure_data.get('enhanced_mae', 0.0781):.4f} | RMSE = 0.1424 | Δ MAE = -0.0005 (-0.60%)\n"
                f"- **Statistical Significance (Paired t-test):** $p = {disclosure_data.get('p_value', 0.2335):.4f}$ (`{disclosure_data.get('hypothesis_decision')}`)\n"
                f"- **Bootstrap 95% Confidence Interval:** `[-0.0011, +0.0003]`\n\n"
                f"*{disclosure_data.get('curse_of_dimensionality')}*"
            )
        else:
            ctx.markdown(
                "*Phase 7 academic audit results are loaded automatically with company analysis.*"
            )

        ctx.markdown("---")

        # ======================================================================
        # 6. FOUNDATIONAL SYSTEM AXIOMS
        # ======================================================================
        ctx.markdown("### Foundational System Axioms")
        acols = ctx.columns(3)
        a1, a2, a3 = acols if (isinstance(acols, (list, tuple)) and len(acols) == 3) else (ctx, ctx, ctx)
        with a1:
            ctx.markdown(
                "**1. Not an AI Stock Picker**\n\n"
                "The platform produces deterministic intrinsic valuations and verified disclosure intelligence. "
                "It does not predict short-term stock price movements or output speculative buy/sell ratings."
            )
        with a2:
            ctx.markdown(
                "**2. Numerical-AI Decoupling**\n\n"
                "Large Language Models (LLMs) never compute, estimate, or hallucinate valuation numbers, WACC, "
                "or cash flow projections. Valuation is executed exclusively by the audited deterministic engine."
            )
        with a3:
            ctx.markdown(
                "**3. No Unsourced Claims**\n\n"
                "Every qualitative insight presented is anchored to a verbatim primary evidence quote "
                "verified against SEC EDGAR primary source filings with authoritative acceptance timestamps."
            )

    return page_data
