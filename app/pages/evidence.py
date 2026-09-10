"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8D — Verified Qualitative Evidence & Evidence Audit Interface
File: app/pages/evidence.py

Upgraded Institutional Evidence Grounding & Audit Interface:
1. Strict validation governance: Only VALIDATED claims in main view; REJECTED / unknown
   quarantined with prominent disclaimer: "Quarantined claims are not used as verified evidence".
2. Verbatim quotes only: Exact primary source EDGAR passages, zero paraphrasing.
3. Multi-filter controls: Category, Direction, Severity, Materiality, Form, plus in-memory
   keyword search across claims, categories, and quotes (without NLP).
4. Evidence -> Valuation bridge traceability: Direct linkage to valuation_comparison_results
   when category matches, otherwise explicitly marked "Informational disclosure only — not linked to valuation adjustment".
5. 4-part audit view: SOURCE, EXTRACTION, EVIDENCE, VALIDATION for every claim.
6. Presentation-only layer; no raw math, no custom parsing.
"""

from typing import Any, Dict, List, Optional
from src.service.contracts import (
    AnalysisResponse,
    FilingIntelligenceResponse,
    FilingSignal,
    ValuationBridgeRecordDTO,
)
from src.service.platform_service import PlatformService
from app.components.temporal_context import render_temporal_context

try:
    import streamlit as st
except ImportError:
    st = None


def render_evidence_page(
    response: Optional[AnalysisResponse] = None,
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
    service: Optional[Any] = None,
    intelligence: Optional[FilingIntelligenceResponse] = None,
    category_filter: Optional[str] = None,
    direction_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    materiality_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
    keyword_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Render the upgraded verified qualitative evidence grounding and audit page view.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        st_client: Optional Streamlit module or mock.
        service: Optional PlatformService instance for fetching intelligence.
        intelligence: Optional pre-loaded FilingIntelligenceResponse DTO.
        category_filter: Optional category filter override.
        direction_filter: Optional direction filter override (POSITIVE, NEGATIVE, NEUTRAL).
        severity_filter: Optional severity filter override (LOW, MEDIUM, HIGH).
        materiality_filter: Optional materiality filter override.
        form_filter: Optional form filter override (10-K, 10-Q).
        keyword_query: Optional in-memory search keyword.

    Returns:
        Structured data dictionary for testing/headless execution.
    """
    ctx = st_client or st
    evidence_data: Dict[str, Any] = {
        "ticker": None,
        "mode": None,
        "as_of_date": None,
        "total_claims": 0,
        "validated_claims": [],
        "quarantined_claims": [],
        "rejected_count": 0,
        "validated_count": 0,
        "active_category": "All Categories",
        "active_direction": "ALL",
        "active_severity": "ALL",
        "active_materiality": "ALL",
        "active_form": "ALL",
        "keyword_query": keyword_query or "",
        "valuation_bridge": None,
        "linked_claims_count": 0,
        "unlinked_claims_count": 0,
    }

    eff_mode = (intelligence.mode if intelligence else (response.request.mode if (response and response.request) else mode)).upper()
    eff_as_of_date = intelligence.as_of_date if intelligence else (response.request.as_of_date if (response and response.request) else as_of_date)
    cutoff_str = f"{eff_as_of_date} 23:59:59" if eff_mode == "HISTORICAL" else "LIVE (LATEST)"
    evidence_data["mode"] = eff_mode
    evidence_data["as_of_date"] = eff_as_of_date
    evidence_data["information_cutoff"] = cutoff_str

    # 1. Resolve FilingIntelligenceResponse (always query with include_rejected=True for complete audit)
    if intelligence is None:
        if response is not None and response.profile is not None:
            svc = service or PlatformService()
            ticker = response.profile.ticker
            try:
                intelligence = svc.get_filing_intelligence(
                    ticker=ticker,
                    as_of_date=eff_as_of_date,
                    mode=eff_mode,
                    include_rejected=True,
                )
            except Exception as e:
                if ctx is not None:
                    ctx.error(f"Failed to load filing qualitative intelligence: {e}")
                return evidence_data
        elif response is not None and response.filing_intelligence is not None:
            intelligence = response.filing_intelligence

    if intelligence is None:
        if ctx is not None:
            render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
            ctx.warning("Please select a company to inspect verified qualitative evidence.")
        return evidence_data

    bridge: Optional[ValuationBridgeRecordDTO] = getattr(intelligence, "valuation_bridge", None)

    evidence_data["ticker"] = intelligence.ticker
    evidence_data["mode"] = intelligence.mode
    evidence_data["as_of_date"] = intelligence.as_of_date
    evidence_data["total_claims"] = intelligence.total_claims_retrieved
    evidence_data["valuation_bridge"] = bridge

    # Strict Validation Governance: Only VALIDATED in main list; all others quarantined
    validated_signals: List[FilingSignal] = []
    quarantined_signals: List[FilingSignal] = []

    for sig in intelligence.signals:
        if (sig.validation_status or "").strip().upper() == "VALIDATED":
            validated_signals.append(sig)
        else:
            quarantined_signals.append(sig)

    evidence_data["validated_count"] = len(validated_signals)
    evidence_data["rejected_count"] = len(quarantined_signals) if quarantined_signals else intelligence.rejected_claims_count

    # 2. Multi-Filter Controls
    all_categories = sorted(list(set(s.category for s in intelligence.signals if s.category)))
    cat_options = ["All Categories"] + all_categories

    chosen_cat = cat_options[0]
    if category_filter:
        match = next((c for c in cat_options if c.upper() == category_filter.upper()), None)
        chosen_cat = match if match else category_filter
    elif ctx is not None and hasattr(ctx, "selectbox") and len(cat_options) > 1:
        chosen_cat = ctx.selectbox(
            "Filter by Disclosure Category",
            options=cat_options,
            index=0,
            help="Filter qualitative claims by disclosure topic / category.",
        )

    # Direction Filter
    direction_options = ["ALL", "POSITIVE", "NEGATIVE", "NEUTRAL"]
    chosen_direction = direction_filter.upper() if direction_filter and direction_filter.upper() in direction_options else "ALL"
    if direction_filter is None and ctx is not None and hasattr(ctx, "selectbox"):
        chosen_direction = ctx.selectbox(
            "Filter by Direction",
            options=direction_options,
            index=0,
            help="Filter by disclosure sentiment / operational direction.",
        )

    # Severity Filter
    severity_options = ["ALL", "LOW", "MEDIUM", "HIGH"]
    chosen_severity = severity_filter.upper() if severity_filter and severity_filter.upper() in severity_options else "ALL"
    if severity_filter is None and ctx is not None and hasattr(ctx, "selectbox"):
        chosen_severity = ctx.selectbox(
            "Filter by Severity",
            options=severity_options,
            index=0,
            help="Filter by extracted risk / operational severity level.",
        )

    # Materiality Filter
    all_mat = sorted(list(set(s.materiality.upper() for s in intelligence.signals if s.materiality)))
    mat_options = ["ALL"] + all_mat
    chosen_materiality = materiality_filter.upper() if materiality_filter else "ALL"
    if materiality_filter is None and ctx is not None and hasattr(ctx, "selectbox") and len(mat_options) > 2:
        chosen_materiality = ctx.selectbox(
            "Filter by Materiality",
            options=mat_options,
            index=0,
            help="Filter by legal / economic materiality tier.",
        )

    # Form Filter
    all_forms = sorted(list(set(s.form.upper() for s in intelligence.signals if s.form)))
    form_options = ["ALL"] + (all_forms if all_forms else ["10-K", "10-Q"])
    chosen_form = form_filter.upper() if form_filter and form_filter.upper() in form_options else "ALL"
    if form_filter is None and ctx is not None and hasattr(ctx, "selectbox") and len(form_options) > 2:
        chosen_form = ctx.selectbox(
            "Filter by Filing Form",
            options=form_options,
            index=0,
            help="Filter by source SEC document type.",
        )

    # In-memory keyword search
    search_query = keyword_query or ""
    if not keyword_query and ctx is not None and hasattr(ctx, "text_input"):
        search_query = ctx.text_input(
            "Search Disclosures & Verbatim Quotes",
            value="",
            help="In-memory substring search across claims, categories, and verbatim quotes (no external NLP).",
        ).strip()

    evidence_data["active_category"] = chosen_cat
    evidence_data["active_direction"] = chosen_direction
    evidence_data["active_severity"] = chosen_severity
    evidence_data["active_materiality"] = chosen_materiality
    evidence_data["active_form"] = chosen_form
    evidence_data["keyword_query"] = search_query

    # Apply multi-filter predicate function
    def _matches_filters(signal: FilingSignal) -> bool:
        if chosen_cat != "All Categories" and signal.category.upper() != chosen_cat.upper():
            return False
        if chosen_direction != "ALL" and signal.direction.upper() != chosen_direction:
            return False
        if chosen_severity != "ALL" and signal.severity.upper() != chosen_severity:
            return False
        if chosen_materiality != "ALL" and signal.materiality.upper() != chosen_materiality:
            return False
        if chosen_form != "ALL" and signal.form.upper() != chosen_form:
            return False
        if search_query:
            kw = search_query.lower()
            text_match = (
                kw in (signal.claim or "").lower()
                or kw in (signal.category or "").lower()
                or kw in (signal.evidence_quote or "").lower()
                or kw in (signal.source_identifier or "").lower()
            )
            if not text_match:
                return False
        return True

    display_validated = [s for s in validated_signals if _matches_filters(s)]
    display_quarantined = [s for s in quarantined_signals if _matches_filters(s)]

    # Calculate valuation bridge linkages
    linked_count = 0
    unlinked_count = 0
    for s in display_validated:
        if bridge and s.category.strip().upper() == bridge.primary_signal_category.strip().upper():
            linked_count += 1
        else:
            unlinked_count += 1

    evidence_data["validated_claims"] = display_validated
    evidence_data["quarantined_claims"] = display_quarantined
    evidence_data["linked_claims_count"] = linked_count
    evidence_data["unlinked_claims_count"] = unlinked_count

    if ctx is not None:
        ctx.header("Verified Qualitative Disclosures & Evidence Grounding `[SOURCE DATA]`")
        render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
        ctx.caption(
            "Evidence Grounding Engine | Exact String Matching & Substring Anchoring | Primary SEC Sources Only"
        )

        mcols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
        mcols[0].metric("Total Claims Processed", str(intelligence.total_claims_retrieved))
        mcols[1].metric("Verified Claims", str(len(validated_signals)))
        mcols[2].metric("Quarantined (Excluded)", str(evidence_data["rejected_count"]))
        mcols[3].metric("Filtered View Count", str(len(display_validated)))

        ev_summary = getattr(intelligence, "evidence_status_summary", "")
        ctx.markdown(
            f"**Reporting Entity:** `{intelligence.ticker}` | "
            f"**Mode:** `{intelligence.mode}` | "
            f"**Information Cutoff:** `{cutoff_str}` | "
            f"**Validation Status:** `{ev_summary}`"
        )
        if eff_mode == "HISTORICAL":
            ctx.info(f"Point-in-Time Eligibility: All evidence passages are strictly anchored to filings accepted on or before {cutoff_str}.")
        ctx.markdown("---")

        # 3. Verified Evidence Catalog
        ctx.markdown("### 1. Verified Evidence Grounding Catalog")
        ctx.caption(
            "Each claim below is mathematically anchored to an exact verbatim passage in the cited SEC filing."
        )

        if not display_validated:
            ctx.info("No verified claims match the current filter criteria.")
        else:
            for idx, c in enumerate(display_validated, 1):
                dir_icon = "🟢" if c.direction == "POSITIVE" else "🔴" if c.direction == "NEGATIVE" else "⚪"
                is_linked = bridge is not None and c.category.strip().upper() == bridge.primary_signal_category.strip().upper()
                link_badge = " [LINKED TO VALUATION]" if is_linked else ""

                with ctx.expander(
                    f"[VERIFIED EVIDENCE] #{idx}: {dir_icon} {c.category.upper()} | "
                    f"{c.form} ({c.filing_date}) — Materiality: {c.materiality}{link_badge}",
                    expanded=(idx <= 3),
                ):
                    bcols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
                    bcols[0].write(f"**Direction:** `{c.direction}`")
                    bcols[1].write(f"**Severity:** `{c.severity}`")
                    bcols[2].write(f"**Materiality:** `{c.materiality}`")
                    bcols[3].write(f"**Confidence:** `{c.confidence:.1%}`")

                    # Evidence -> Valuation Bridge Linkage
                    if is_linked and bridge:
                        ctx.success(
                            f"🔗 **VALUATION BRIDGE LINKAGE ACTIVE:**\n\n"
                            f"- **Primary Signal Category:** `{bridge.primary_signal_category}`\n"
                            f"- **Key Assumption Adjusted:** `{bridge.key_assumption_adjusted}`\n"
                            f"- **Adjustment Magnitude:** `{bridge.adjustment_magnitude:+.4f}`\n"
                            f"- **Fair Value Impact:** Baseline ${bridge.baseline_fair_value:.2f} ➔ "
                            f"Enhanced ${bridge.enhanced_fair_value:.2f} ({bridge.fair_value_pct_change:+.2f}%)\n"
                            f"- **Evidence Citation:** `{bridge.evidence_citation}`"
                        )
                    else:
                        ctx.caption(
                            "ℹ️ *Informational disclosure only — not linked to valuation adjustment.*"
                        )

                    # Proposition and Verbatim Quote
                    ctx.markdown(f"**Extracted Proposition:** {c.claim}")
                    ctx.markdown("**Verbatim SEC EDGAR Evidence Passage:**")
                    ctx.info(f"\"{c.evidence_quote}\"")

                    # 4-Part Audit Expander
                    ctx.caption(
                        f"🔗 **Qualitative Lineage Pipeline:** Filing (`{c.form}`) ➔ Section (`{c.section_name or 'N/A'}`) ➔ Passage (`{c.source_identifier or 'N/A'}`) ➔ NLP Extraction ➔ Deterministic Validation (`{c.validation_status}`) ➔ Signal (`{c.category}`)"
                    )
                    ctx.markdown("#### Evidence Audit Trail")
                    acols = ctx.columns(2) if hasattr(ctx, "columns") else (ctx, ctx)
                    
                    with acols[0]:
                        ctx.markdown("**[1. SOURCE PROVENANCE]**")
                        ctx.caption(
                            f"- **Accession Number:** `{c.accession_number}`\n"
                            f"- **Filing Form:** `{c.form}`\n"
                            f"- **Filing Date:** `{c.filing_date}`\n"
                            f"- **Acceptance Datetime:** `{c.acceptance_datetime or 'N/A'}`\n"
                            f"- **Section Name:** `{c.section_name or 'N/A'}`"
                        )
                        ctx.markdown("**[2. EXTRACTION METADATA]**")
                        ctx.caption(
                            f"- **Source Identifier:** `{c.source_identifier}`\n"
                            f"- **Direction / Severity:** `{c.direction}` / `{c.severity}`\n"
                            f"- **Legal Materiality:** `{c.materiality}`"
                        )

                    with acols[1]:
                        ctx.markdown("**[3. VERBATIM EVIDENCE]**")
                        ctx.caption(
                            f"- **Location Identifier:** `{c.evidence_location}`\n"
                            f"- **Confidence Score:** `{c.confidence:.1%}`\n"
                            f"- **Quote Length:** {len(c.evidence_quote)} characters"
                        )
                        ctx.markdown("**[4. VALIDATION GOVERNANCE]**")
                        ctx.caption(
                            f"- **Validation Status:** `{c.validation_status}`\n"
                            f"- **Verification Rule:** Exact string match against primary EDGAR text\n"
                            f"- **Audit Detail:** {c.validation_reason or 'Deterministic substring match confirmed.'}"
                        )

        ctx.markdown("---")

        # 4. Quarantined Claims Section
        ctx.markdown("### 2. Quarantined / Unverified Disclosures `[REJECTED]`")
        ctx.caption(
            "Propositions failing exact string matching or provenance audit are strictly quarantined."
        )

        if not display_quarantined:
            ctx.success(
                "✅ No quarantined claims in current view. All displayed claims successfully passed deterministic string-matching verification."
            )
        else:
            ctx.warning(
                "⚠️ **QUARANTINE GOVERNANCE NOTICE:** Quarantined claims are not used as verified evidence. "
                "The following propositions failed deterministic verification against primary SEC filing text "
                "and are strictly quarantined from valuation, feature engineering, and statistical modeling."
            )

            for idx, qc in enumerate(display_quarantined, 1):
                with ctx.expander(
                    f"[QUARANTINED] #{idx}: {qc.category.upper()} — Status: {qc.validation_status}",
                    expanded=False,
                ):
                    ctx.error(
                        f"**Verification Failure Reason:** {qc.validation_reason or 'Exact substring not located in primary source filing.'}"
                    )
                    ctx.markdown(f"**Proposed Claim:** {qc.claim}")
                    ctx.caption(
                        f"Target Accession: `{qc.accession_number}` | Section: `{qc.section_name}` | "
                        f"Validation Status: `{qc.validation_status}`"
                    )

    return evidence_data


