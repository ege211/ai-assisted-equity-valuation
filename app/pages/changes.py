"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8C — Longitudinal Disclosure Delta Timeline View
File: app/pages/changes.py

Renders the longitudinal filing disclosure change view:
1. Multi-period disclosure deltas (NEW, ESCALATED, RESOLVED, MODIFIED, PERSISTENT)
2. Interactive change type filter (ALL, NEW, ESCALATED, RESOLVED, MODIFIED, PERSISTENT)
3. Chronological timeline table with direction/severity shifts and materiality
4. Current vs Prior accession provenance
5. Strict Point-in-Time compliance via PlatformService
"""

from typing import Any, Dict, List, Optional
from src.service.contracts import AnalysisResponse, FilingIntelligenceResponse, ChangeSignalDTO
from src.service.provenance import WhatChangedResponse
from src.service.platform_service import PlatformService
from app.components.temporal_context import render_temporal_context
from app.components.provenance import render_what_changed_table

try:
    import streamlit as st
except ImportError:
    st = None


def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generate a clean GitHub-flavored markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, separator_line] + row_lines)


def render_changes_page(
    response: Optional[AnalysisResponse] = None,
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
    service: Optional[Any] = None,
    intelligence: Optional[FilingIntelligenceResponse] = None,
    change_type_filter: Optional[str] = None,
    what_changed: Optional[WhatChangedResponse] = None,
) -> Dict[str, Any]:
    """
    Render the 'What Changed' longitudinal research and disclosure delta page view.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        st_client: Optional Streamlit module or mock.
        service: Optional PlatformService instance for fetching intelligence.
        intelligence: Optional pre-loaded FilingIntelligenceResponse DTO.
        change_type_filter: Optional change type filter override for headless testing.
        what_changed: Optional pre-loaded WhatChangedResponse DTO.

    Returns:
        Structured data dictionary for testing/headless execution.
    """
    ctx = st_client or st
    changes_data: Dict[str, Any] = {
        "ticker": None,
        "mode": None,
        "as_of_date": None,
        "total_signals": 0,
        "change_signals": [],
        "active_change_type": "ALL",
        "by_change_type_count": {},
        "what_changed": None,
        "is_longitudinal_valid": False,
        "rejection_reason": None,
        "fundamental_changes": [],
        "valuation_changes": [],
    }

    state_ticker, state_mode, state_date = None, None, None
    try:
        from app.state import get_state
        state_ticker = get_state("selected_ticker")
        state_mode = get_state("mode")
        state_date = get_state("as_of_date")
    except Exception:
        pass

    eff_mode = (intelligence.mode if intelligence else (response.request.mode if (response and response.request) else (mode or state_mode or "LIVE"))).upper()
    eff_as_of_date = intelligence.as_of_date if intelligence else (response.request.as_of_date if (response and response.request) else (as_of_date or state_date))
    cutoff_str = f"{eff_as_of_date} 23:59:59" if eff_mode == "HISTORICAL" else "LIVE (LATEST)"
    changes_data["mode"] = eff_mode
    changes_data["as_of_date"] = eff_as_of_date
    changes_data["information_cutoff"] = cutoff_str

    ticker = None
    if response and response.profile:
        ticker = response.profile.ticker
    elif intelligence:
        ticker = intelligence.ticker
    else:
        ticker = state_ticker

    # 1. Resolve WhatChangedResponse
    if what_changed is None:
        if response is not None and response.what_changed is not None:
            what_changed = response.what_changed
        elif ticker:
            svc = service or PlatformService()
            try:
                what_changed = svc.get_company_changes(ticker=ticker, as_of_date=eff_as_of_date, mode=eff_mode)
            except Exception as e:
                what_changed = None

    if what_changed is not None:
        changes_data["what_changed"] = what_changed
        changes_data["is_longitudinal_valid"] = what_changed.is_longitudinal_valid
        changes_data["rejection_reason"] = what_changed.rejection_reason
        changes_data["fundamental_changes"] = what_changed.fundamental_changes
        changes_data["valuation_changes"] = what_changed.valuation_changes

    # 2. Resolve FilingIntelligence
    if intelligence is None:
        if response is not None and response.profile is not None:
            svc = service or PlatformService()
            try:
                intelligence = svc.get_filing_intelligence(ticker=ticker, as_of_date=eff_as_of_date, mode=eff_mode)
            except Exception as e:
                if ctx is not None:
                    ctx.error(f"Failed to load disclosure change signals: {e}")
                return changes_data
        elif response is not None and response.filing_intelligence is not None:
            intelligence = response.filing_intelligence

    if intelligence is None and what_changed is None:
        if ctx is not None:
            render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
            ctx.warning("Please select a company to inspect longitudinal disclosure changes.")
        return changes_data

    raw_signals: List[ChangeSignalDTO] = (
        what_changed.qualitative_signals
        if (what_changed and what_changed.qualitative_signals)
        else (intelligence.change_signals if intelligence else [])
    )
    changes_data["ticker"] = ticker or (intelligence.ticker if intelligence else "")
    changes_data["total_signals"] = len(raw_signals)

    # Compute breakdown counts
    counts: Dict[str, int] = {}
    for s in raw_signals:
        ct = s.change_type.upper()
        counts[ct] = counts.get(ct, 0) + 1
    changes_data["by_change_type_count"] = counts

    # 3. Interactive Change Type Filter
    type_options = ["ALL", "NEW", "ESCALATED", "RESOLVED", "MODIFIED", "PERSISTENT"]
    chosen_type = "ALL"
    if change_type_filter and change_type_filter.upper() in type_options:
        chosen_type = change_type_filter.upper()
    elif ctx is not None and hasattr(ctx, "selectbox"):
        chosen_type = ctx.selectbox(
            "Filter by Disclosure Delta Type",
            options=type_options,
            index=0,
            format_func=lambda t: f"{t} ({counts.get(t, len(raw_signals) if t == 'ALL' else 0)})",
            help="Filter longitudinal shifts by mutation category.",
        )

    changes_data["active_change_type"] = chosen_type

    # Filter signals
    if chosen_type == "ALL":
        filtered_signals = raw_signals
    else:
        filtered_signals = [s for s in raw_signals if s.change_type.upper() == chosen_type]

    changes_data["change_signals"] = filtered_signals

    if ctx is not None:
        ctx.header("What Changed — Research & Disclosure Intelligence `[AUDITABLE COMPARISON]`")
        render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
        ctx.caption(
            "Longitudinal Financial Statement Diffing | Dual-Accession PIT Lock | Semantic Disclosure Escalations"
        )

        # 1 & 2: Fundamental Deltas and Valuation Adjustments
        render_what_changed_table(what_changed, st_client=ctx)
        ctx.markdown("---")

        # 3. Filing Intelligence & Metadata Shifts
        ctx.markdown("### 3. Filing Intelligence & Metadata Shifts `[SOURCE DATA]`")
        ctx.caption("Form-over-form filing metadata, accession chronology, and semantic shift volume.")

        mcols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
        mcols[0].metric("Total Disclosure Deltas", str(len(raw_signals)))
        mcols[1].metric("New Disclosures", str(counts.get("NEW", 0)))
        mcols[2].metric("Escalations", str(counts.get("ESCALATED", 0)))
        mcols[3].metric("Resolved / Removed", str(counts.get("RESOLVED", 0)))

        ctx.markdown(
            f"**Reporting Entity:** `{changes_data['ticker']}` | "
            f"**Mode:** `{changes_data['mode']}` | "
            f"**Information Cutoff:** `{cutoff_str}`"
        )
        if eff_mode == "HISTORICAL":
            ctx.info(f"Point-in-Time Delta Verification: Both current and prior filings in change comparisons have acceptance_datetime <= {cutoff_str}.")

        if what_changed and not what_changed.is_longitudinal_valid:
            ctx.warning(
                f"**Longitudinal Comparison Unavailable:** {what_changed.rejection_reason or 'No prior filing available for longitudinal comparison at this cutoff.'}"
            )
            ctx.info(
                f"**Baseline Filing Used:** Accession `{what_changed.current_accession or 'N/A'}` "
                f"(Period: `{what_changed.current_period or 'N/A'}`). "
                f"Longitudinal comparison requires at least one preceding historical filing accepted prior to cutoff."
            )

        ctx.markdown("---")

        # 4. Qualitative Disclosure Evolutions & Risk Signals
        ctx.markdown(f"### 4. Qualitative Disclosure Evolutions & Risk Signals (`{chosen_type}`) `[SOURCE DATA]`")
        ctx.caption("Form-over-form comparison tracking shifts in qualitative management disclosures and risk factors.")

        if not raw_signals:
            ctx.info("No longitudinal change signals recorded prior to the specified point-in-time cutoff.")
            return changes_data

        if not filtered_signals:
            ctx.info(f"No disclosure changes found for category `{chosen_type}`.")
        else:
            table_headers = [
                "Category / Topic",
                "Delta Type",
                "Direction Shift",
                "Severity Shift",
                "Materiality",
                "Current Filing Date",
                "Prior Filing Date",
                "Summary",
            ]
            table_rows = [
                [
                    f"**{s.category}**",
                    f"`{s.change_type}`",
                    f"`{s.direction_shift or 'UNCHANGED'}`",
                    f"`{s.severity_shift or 'UNCHANGED'}`",
                    f"`{s.materiality}`",
                    s.current_filing_date or "N/A",
                    s.previous_filing_date or "N/A",
                    s.summary,
                ]
                for s in filtered_signals
            ]
            ctx.markdown(_build_markdown_table(table_headers, table_rows))

            ctx.markdown("---")

            # Detailed Delta Inspector Cards
            ctx.markdown("#### Disclosure Delta Inspection & Accession Lineage")
            for idx, sig in enumerate(filtered_signals, 1):
                badge = f"[{sig.change_type.upper()}]"
                with ctx.expander(
                    f"{badge} #{idx}: {sig.category} — Shift: {sig.direction_shift or 'N/A'} (Materiality: {sig.materiality})",
                    expanded=(idx <= 2),
                ):
                    pcols = ctx.columns(2) if hasattr(ctx, "columns") else (ctx, ctx)
                    pcols[0].write(
                        f"**Prior Filing:** `{sig.previous_filing_date or 'N/A'}`\n\n"
                        f"**Prior Accession:** `{sig.previous_accession or 'INITIAL'}`"
                    )
                    pcols[1].write(
                        f"**Current Filing:** `{sig.current_filing_date or 'N/A'}`\n\n"
                        f"**Current Accession:** `{sig.current_accession}`"
                    )

                    if sig.previous_claim:
                        ctx.markdown(f"**Prior Disclosure Claim:**\n> {sig.previous_claim}")
                    if sig.current_claim:
                        ctx.markdown(f"**Current Disclosure Claim:**\n> {sig.current_claim}")

                    ctx.markdown(f"**Analytical Summary:** {sig.summary}")

    return changes_data

