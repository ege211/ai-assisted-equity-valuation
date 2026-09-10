"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8F — Provenance, Lineage & "What Changed?" UI Components
File: app/components/provenance.py

Institutional presentation components for auditable provenance and data lineage:
1. render_source_provenance_badge: SEC accession, acceptance timestamp, EDGAR link, or fallback.
2. render_lineage_pipeline: 4-stage numerical or qualitative calculation pipeline.
3. render_why_this_number_expander: "Why this Number?" drilldown expander for DCF and WACC.
4. render_what_changed_table: Longitudinal fundamental deltas with noise filtering and dual-accession lock.
"""

from typing import Any, Dict, List, Optional
from src.service.provenance import (
    SourceProvenanceDTO,
    DataLineageDTO,
    LineageStepDTO,
    FundamentalChangeDTO,
    WhatChangedResponse,
)

try:
    import streamlit as st
except ImportError:
    st = None


def _format_curr(val: Optional[float]) -> str:
    """Format currency values in billions/millions with sign."""
    if val is None:
        return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9:
        return f"${val / 1e9:,.2f}B"
    if abs_v >= 1e6:
        return f"${val / 1e6:,.2f}M"
    return f"${val:,.0f}"


def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generate a clean GitHub-flavored markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, separator_line] + row_lines)


def render_source_provenance_badge(
    prov: Optional[SourceProvenanceDTO],
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render a standardized SEC source provenance badge or fallback notice.
    """
    ctx = st_client or st
    if prov is None:
        if ctx is not None:
            ctx.caption("Source provenance unavailable")
        return {"available": False, "is_pit_compliant": False}

    badge_data: Dict[str, Any] = {
        "available": True,
        "source_type": prov.source_type,
        "primary_source": prov.primary_source,
        "accession_number": prov.accession_number,
        "filing_date": prov.filing_date,
        "acceptance_datetime": prov.acceptance_datetime,
        "sec_url": prov.sec_url,
        "is_pit_compliant": prov.is_pit_compliant,
        "pit_rejection_reason": prov.pit_rejection_reason,
    }

    if ctx is not None:
        if prov.is_pit_compliant:
            acc_str = prov.accession_number or "N/A"
            adt_str = prov.acceptance_datetime or "N/A"
            edgar_link = f" | [View on SEC EDGAR]({prov.sec_url})" if prov.sec_url else ""
            ctx.caption(
                f"🛡️ **[SOURCE DATA]** `{prov.primary_source}` | "
                f"**Accession:** `{acc_str}` | **Accepted:** `{adt_str}`{edgar_link}"
            )
        else:
            ctx.warning(
                f"⚠️ **[POINT-IN-TIME EXCLUSION]** {prov.pit_rejection_reason or 'Filing rejected under historical cutoff'}"
            )

    return badge_data


def render_lineage_pipeline(
    lineage: Optional[DataLineageDTO],
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render a multi-stage step-by-step transformation pipeline.
    """
    ctx = st_client or st
    if lineage is None:
        if ctx is not None:
            ctx.info("Data lineage information unavailable.")
        return {"available": False, "steps": []}

    pipeline_data: Dict[str, Any] = {
        "available": True,
        "metric_name": lineage.metric_name,
        "final_value": lineage.final_value,
        "unit": lineage.unit,
        "calculation_summary": lineage.calculation_summary,
        "steps": [
            {
                "step_number": s.step_number,
                "step_name": s.step_name,
                "description": s.description,
                "input_values": s.input_values,
                "output_value": s.output_value,
                "transformation_rule": s.transformation_rule,
            }
            for s in lineage.steps
        ],
    }

    if ctx is not None:
        ctx.markdown(f"**Calculation Methodology:** {lineage.calculation_summary}")
        ctx.markdown(f"**Final Output:** `{lineage.final_value}` ({lineage.unit})")

        for s in lineage.steps:
            ctx.markdown(f"#### Step {s.step_number}: `{s.step_name}`")
            ctx.write(f"*{s.description}*")
            ctx.write(f"• **Rule:** `{s.transformation_rule}`")
            ctx.write(f"• **Inputs:** `{s.input_values}`")
            ctx.write(f"• **Output:** `{s.output_value}`")

    return pipeline_data


def render_why_this_number_expander(
    title: str,
    lineage: Optional[DataLineageDTO],
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render an institutional 'Why this Number?' lineage expander.
    """
    ctx = st_client or st
    result_data: Dict[str, Any] = {
        "title": title,
        "has_lineage": lineage is not None,
    }

    if lineage is None:
        if ctx is not None:
            with ctx.expander(title):
                ctx.caption("Source provenance and calculation lineage unavailable.")
        return result_data

    if ctx is not None:
        with ctx.expander(title):
            render_source_provenance_badge(lineage.source_provenance, st_client=ctx)
            ctx.markdown("---")
            render_lineage_pipeline(lineage, st_client=ctx)

    result_data["metric_name"] = lineage.metric_name
    result_data["final_value"] = lineage.final_value
    return result_data


def render_what_changed_table(
    changes: Optional[WhatChangedResponse],
    st_client: Any = None,
) -> Dict[str, Any]:
    """
    Render structured multi-period changes across fundamental financials and qualitative disclosures.
    """
    ctx = st_client or st
    if changes is None:
        if ctx is not None:
            ctx.info("Multi-period change analysis unavailable.")
        return {"available": False, "is_valid": False}

    if not changes.is_longitudinal_valid:
        if ctx is not None:
            ctx.warning(f"⚠️ **Longitudinal Comparison Rejected:** {changes.rejection_reason or 'No prior filing available for longitudinal comparison at this cutoff.'}")
            if changes.current_accession or changes.current_period:
                ctx.info(
                    f"**Filing Used:** Accession `{changes.current_accession or 'N/A'}` "
                    f"(Period: `{changes.current_period or 'N/A'}`). "
                    f"Longitudinal comparison requires at least one preceding historical filing accepted prior to cutoff."
                )
        return {
            "available": True,
            "is_valid": False,
            "rejection_reason": changes.rejection_reason,
        }

    output_data: Dict[str, Any] = {
        "available": True,
        "is_valid": True,
        "current_period": changes.current_period,
        "previous_period": changes.previous_period,
        "current_accession": changes.current_accession,
        "previous_accession": changes.previous_accession,
        "fundamental_changes_count": len(changes.fundamental_changes),
        "qualitative_signals_count": len(changes.qualitative_signals),
    }

    if ctx is not None:
        ctx.markdown(
            f"### Longitudinal Delta Analysis: `{changes.current_period}` vs `{changes.previous_period}`"
        )
        ctx.caption(
            f"🔒 **Dual-Accession Point-in-Time Lock:** Verified | "
            f"Current Accession: `{changes.current_accession}` | Prior Accession: `{changes.previous_accession}`"
        )

        # 1. Fundamental Financial Deltas Table
        ctx.markdown("#### 1. Fundamental Financial Statement Deltas `[SOURCE DATA]`")
        ctx.caption(
            "Noise Filter Active: Changes with |pct_change| < 0.1% or |delta| < $1,000 are flagged as noise/flat."
        )

        if changes.fundamental_changes:
            table_headers = [
                "Financial Metric",
                f"Prior ({changes.previous_period})",
                f"Current ({changes.current_period})",
                "Absolute Delta",
                "Delta (%)",
                "Meaningful?",
                "Interpretation",
            ]
            table_rows = []
            for fc in changes.fundamental_changes:
                meaningful_badge = "✅ YES" if fc.is_meaningful else "⚪ Noise"
                table_rows.append(
                    [
                        f"**{fc.metric_name}**",
                        _format_curr(fc.previous_value),
                        _format_curr(fc.current_value),
                        _format_curr(fc.absolute_change),
                        f"{fc.percentage_change:+.1f}%",
                        meaningful_badge,
                        fc.interpretation,
                    ]
                )
            ctx.markdown(_build_markdown_table(table_headers, table_rows))
        else:
            ctx.info("No fundamental financial statement deltas detected between the comparison periods.")

        # 2. Valuation Bridge Changes
        ctx.markdown("---")
        ctx.markdown("#### 2. Valuation Model Adjustments `[MODEL OUTPUT]`")
        if changes.valuation_changes:
            val_headers = [
                "Valuation Metric",
                "Baseline Model (Model A)",
                "Enhanced Model (Model B)",
                "Difference",
                "Impact (%)",
                "Analytical Driver",
            ]
            val_rows = []
            for vc in changes.valuation_changes:
                val_rows.append(
                    [
                        f"**{vc.metric_name}**",
                        f"${vc.previous_value:.2f}",
                        f"${vc.current_value:.2f}",
                        f"${vc.absolute_change:+.2f}",
                        f"{vc.percentage_change:+.2f}%",
                        vc.interpretation,
                    ]
                )
            ctx.markdown(_build_markdown_table(val_headers, val_rows))
        else:
            ctx.info("No valuation model adjustments or scenario shifts detected between the comparison periods.")

    return output_data
