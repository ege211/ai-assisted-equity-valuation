"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8D — SEC Filing & Document Explorer Interface
File: app/pages/filings.py

Upgraded Institutional SEC Filing and Section Explorer:
1. Institutional overview header & KPI metrics (Company, Ticker, CIK, Mode, PIT Cutoff,
   Filing counts, 10-K/10-Q breakdown, Claims breakdown: Extracted, Validated, Quarantined).
2. Dense multi-period filing catalog (newest -> oldest sort, All/10-K/10-Q filters,
   Form, Filing Date, Acceptance Datetime, Report Date, Accession, Sections, Claims).
3. Section inspector highlighting key narrative sections:
   ITEM_1A_RISK_FACTORS, ITEM_7_MDA, ITEM_7A_MARKET_RISK, ITEM_8_FINANCIAL_STATEMENTS.
4. Strict Point-in-Time compliance via PlatformService.get_filing_explorer_data.
5. Presentation-only layer; no raw math, no custom parsing.
"""

from typing import Any, Dict, List, Optional, Set
from src.service.contracts import (
    AnalysisResponse,
    FilingExplorerResponse,
    FilingSummaryDTO,
    FilingSectionDTO,
)
from src.service.provenance import SourceProvenanceDTO
from src.service.platform_service import PlatformService
from app.components.temporal_context import render_temporal_context
from app.components.provenance import render_source_provenance_badge

try:
    import streamlit as st
except ImportError:
    st = None


KEY_ITEM_SECTIONS: Set[str] = {
    "ITEM_1A_RISK_FACTORS",
    "ITEM_7_MDA",
    "ITEM_7A_MARKET_RISK",
    "ITEM_8_FINANCIAL_STATEMENTS",
}


def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generate a clean GitHub-flavored markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, separator_line] + row_lines)


def is_key_section(section_name: str) -> bool:
    """Check if a section identifier matches canonical institutional key items."""
    s_clean = (section_name or "").strip().upper()
    if s_clean in KEY_ITEM_SECTIONS:
        return True
    if "ITEM_1A" in s_clean or "RISK_FACTOR" in s_clean:
        return True
    if "ITEM_7A" in s_clean:
        return True
    if "ITEM_7" in s_clean or "MDA" in s_clean:
        return True
    if "ITEM_8" in s_clean or "FINANCIAL_STATEMENT" in s_clean:
        return True
    return False


def render_filings_page(
    response: Optional[AnalysisResponse] = None,
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
    service: Optional[Any] = None,
    filings_explorer: Optional[FilingExplorerResponse] = None,
    selected_accession: Optional[str] = None,
    form_filter_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Render the upgraded institutional SEC filings and section exploration view.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        mode: Execution mode ('LIVE' or 'HISTORICAL').
        as_of_date: Optional historical cutoff date (YYYY-MM-DD).
        st_client: Optional Streamlit module or mock.
        service: Optional PlatformService instance for querying data.
        filings_explorer: Optional pre-loaded FilingExplorerResponse DTO.
        selected_accession: Optional accession number override for headless testing.
        form_filter_override: Optional form filter override for headless testing.

    Returns:
        Structured data dictionary for testing/headless execution.
    """
    ctx = st_client or st
    filings_data: Dict[str, Any] = {
        "ticker": None,
        "company_name": "",
        "cik": "",
        "mode": None,
        "as_of_date": None,
        "information_cutoff": None,
        "total_filings": 0,
        "excluded_future_filings_count": 0,
        "ten_k_count": 0,
        "ten_q_count": 0,
        "latest_filing_date": None,
        "latest_acceptance_datetime": None,
        "total_claims_count": 0,
        "validated_claims_count": 0,
        "rejected_claims_count": 0,
        "filtered_filings": [],
        "selected_accession": None,
        "selected_filing_sections": [],
        "highlighted_sections": [],
    }

    eff_mode = (filings_explorer.mode if filings_explorer else (response.request.mode if (response and response.request) else mode)).upper()
    eff_as_of_date = filings_explorer.as_of_date if filings_explorer else (response.request.as_of_date if (response and response.request) else as_of_date)
    cutoff_str = f"{eff_as_of_date} 23:59:59" if eff_mode == "HISTORICAL" else "LIVE (LATEST)"
    filings_data["mode"] = eff_mode
    filings_data["as_of_date"] = eff_as_of_date
    filings_data["information_cutoff"] = cutoff_str

    # 1. Resolve FilingExplorerResponse
    if filings_explorer is None:
        if response is not None and response.profile is not None:
            svc = service or PlatformService()
            ticker = response.profile.ticker
            try:
                filings_explorer = svc.get_filing_explorer_data(
                    ticker=ticker,
                    as_of_date=eff_as_of_date,
                    mode=eff_mode,
                )
            except Exception as e:
                if ctx is not None:
                    ctx.error(f"Failed to load SEC filing catalog: {e}")
                return filings_data
        elif service is not None and hasattr(service, "get_filing_explorer_data"):
            pass

    if filings_explorer is None:
        if ctx is not None:
            render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
            ctx.warning("Please select a company to inspect SEC filing coverage.")
        return filings_data

    # Extract metadata
    company_name = getattr(filings_explorer, "company_name", "")
    cik = getattr(filings_explorer, "cik", "")
    if not company_name and response and response.profile:
        company_name = response.profile.company_name
        cik = response.profile.cik

    # Calculate form counts if not pre-populated
    ten_k_cnt = getattr(filings_explorer, "ten_k_count", 0)
    ten_q_cnt = getattr(filings_explorer, "ten_q_count", 0)
    if ten_k_cnt == 0 and filings_explorer.filings:
        ten_k_cnt = sum(1 for f in filings_explorer.filings if f.form == "10-K")
    if ten_q_cnt == 0 and filings_explorer.filings:
        ten_q_cnt = sum(1 for f in filings_explorer.filings if f.form == "10-Q")

    latest_filing = getattr(filings_explorer, "latest_filing_date", None)
    latest_acc = getattr(filings_explorer, "latest_acceptance_datetime", None)
    if not latest_filing and filings_explorer.filings:
        latest_filing = filings_explorer.filings[0].filing_date
    if not latest_acc and filings_explorer.filings:
        latest_acc = filings_explorer.filings[0].acceptance_datetime

    total_claims = getattr(filings_explorer, "total_claims_count", 0)
    val_claims = getattr(filings_explorer, "validated_claims_count", 0)
    rej_claims = getattr(filings_explorer, "rejected_claims_count", 0)

    # Populate filings_data
    filings_data["ticker"] = filings_explorer.ticker
    filings_data["company_name"] = company_name
    filings_data["cik"] = cik
    filings_data["mode"] = filings_explorer.mode
    filings_data["as_of_date"] = filings_explorer.as_of_date
    filings_data["total_filings"] = filings_explorer.total_filings_count
    filings_data["ten_k_count"] = ten_k_cnt
    filings_data["ten_q_count"] = ten_q_cnt
    filings_data["latest_filing_date"] = latest_filing
    filings_data["latest_acceptance_datetime"] = latest_acc
    filings_data["total_claims_count"] = total_claims
    filings_data["validated_claims_count"] = val_claims
    filings_data["rejected_claims_count"] = rej_claims

    excluded_cnt = getattr(filings_explorer, "excluded_future_filings_count", 0)
    filings_data["excluded_future_filings_count"] = excluded_cnt

    if ctx is not None:
        ctx.header("SEC Filings & Document Explorer `[SOURCE DATA]`")
        render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
        ctx.caption(
            "Authoritative SEC EDGAR Primary Source Catalog | Strict Point-in-Time Acceptance Verification"
        )

        # 1. Institutional Overview Metric Cards
        overview_cols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
        overview_cols[0].metric("Company / Ticker", f"{company_name or filings_explorer.ticker} ({filings_explorer.ticker})")
        overview_cols[1].metric("CIK / Mode", f"{cik or 'N/A'} | {filings_explorer.mode}")
        overview_cols[2].metric("Total Ingested Filings", str(filings_explorer.total_filings_count))
        overview_cols[3].metric("10-K / 10-Q Submissions", f"{ten_k_cnt} 10-Ks | {ten_q_cnt} 10-Qs")

        stat_cols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
        stat_cols[0].metric("Latest Filing Date", latest_filing or "N/A")
        stat_cols[1].metric("PIT Acceptance Cutoff", cutoff_str)
        stat_cols[2].metric("Extracted Disclosures", str(total_claims))
        stat_cols[3].metric("Verified / Quarantined", f"{val_claims} Verified | {rej_claims} Quarantined")

        if eff_mode == "HISTORICAL" and excluded_cnt > 0:
            ctx.info(f"Point-in-Time Lock: {excluded_cnt} future filings submitted after {cutoff_str} are excluded from this analysis.")

        ctx.caption(
            f"**Authoritative Timestamp Lineage:** Latest SEC Acceptance Datetime: `{latest_acc or 'N/A'}` | "
            f"Mode: `{filings_explorer.mode}` | Cutoff: `{cutoff_str}`"
        )
        ctx.markdown("---")

        if not filings_explorer.filings:
            ctx.info("No SEC filings found matching the specified point-in-time constraints.")
            return filings_data

        # 2. Form Type Filtering (All, 10-K, 10-Q)
        available_forms = sorted(list(set(f.form for f in filings_explorer.filings)))
        form_filter_options = ["All Primary Forms (10-K, 10-Q)"] + available_forms

        selected_form_filter = form_filter_options[0]
        if form_filter_override and form_filter_override in form_filter_options:
            selected_form_filter = form_filter_override
        elif hasattr(ctx, "selectbox"):
            selected_form_filter = ctx.selectbox(
                "Filter by Filing Form",
                options=form_filter_options,
                index=0,
                help="Filter filing catalog by SEC form category (Form 10-K Annual, Form 10-Q Quarterly).",
            )

        # Apply filtering
        if "All Primary" in selected_form_filter:
            filtered = [f for f in filings_explorer.filings if f.form in ("10-K", "10-Q")]
            if not filtered:
                filtered = filings_explorer.filings
        else:
            filtered = [f for f in filings_explorer.filings if f.form == selected_form_filter]

        # Enforce newest -> oldest sort order by acceptance_datetime / filing_date
        filtered = sorted(
            filtered,
            key=lambda x: (x.acceptance_datetime or "", x.filing_date or ""),
            reverse=True,
        )
        filings_data["filtered_filings"] = filtered

        # 3. Dense Multi-Filing Catalog Table
        ctx.markdown("### 1. Dense SEC Filing Ingestion Catalog")
        ctx.caption("Chronologically ordered newest-to-oldest with strict EDGAR acceptance timestamps.")

        catalog_headers = [
            "Form",
            "Filing Date",
            "Acceptance Datetime (PIT)",
            "Report Date",
            "Accession Number",
            "Audited Sections",
            "Extracted Claims",
        ]
        catalog_rows = [
            [
                f"`{f.form}`",
                f.filing_date,
                f.acceptance_datetime,
                f.report_date or "N/A",
                f"`{f.accession_number}`",
                str(f.section_count),
                str(f.claim_count),
            ]
            for f in filtered[:25]
        ]

        if catalog_rows:
            ctx.markdown(_build_markdown_table(catalog_headers, catalog_rows))
        else:
            ctx.info("No filings match the current form filter.")
            return filings_data

        ctx.markdown("---")

        # 4. Interactive Section Inspector & Text Preview
        ctx.markdown("### 2. Narrative Section Inspector & Text Preview")
        ctx.caption(
            "Institutional section parser highlighting core items: Item 1A (Risk Factors), "
            "Item 7 (MD&A), Item 7A (Market Risk), and Item 8 (Financial Statements)."
        )

        filings_with_sections = [f for f in filtered if f.section_count > 0]
        filing_candidates = filings_with_sections if filings_with_sections else filtered

        acc_options = [f.accession_number for f in filing_candidates]
        default_acc = selected_accession if selected_accession in acc_options else acc_options[0]

        chosen_acc = default_acc
        if selected_accession and selected_accession in acc_options:
            chosen_acc = selected_accession
        elif hasattr(ctx, "selectbox") and len(acc_options) > 1:
            chosen_acc = ctx.selectbox(
                "Select Filing to Inspect Sections",
                options=acc_options,
                index=acc_options.index(default_acc) if default_acc in acc_options else 0,
                format_func=lambda acc: next(
                    (f"{f.form} ({f.filing_date}) — Accession: {f.accession_number}" for f in filing_candidates if f.accession_number == acc),
                    acc,
                ),
            )

        filings_data["selected_accession"] = chosen_acc
        target_filing = next((f for f in filings_explorer.filings if f.accession_number == chosen_acc), None)

        if target_filing is not None:
            filings_data["selected_filing_sections"] = target_filing.sections

            mcols = ctx.columns(4) if hasattr(ctx, "columns") else (ctx, ctx, ctx, ctx)
            mcols[0].metric("Target Form", target_filing.form)
            mcols[1].metric("Filing Date", target_filing.filing_date)
            mcols[2].metric("Audited Sections", str(target_filing.section_count))
            mcols[3].metric("Extracted Disclosures", str(target_filing.claim_count))

            ctx.caption(
                f"**SEC EDGAR Accession:** `{target_filing.accession_number}` | "
                f"**Acceptance Datetime:** `{target_filing.acceptance_datetime}`"
            )

            cik_clean = filings_explorer.cik.lstrip("0") if filings_explorer.cik else ""
            acc_clean = target_filing.accession_number.replace("-", "") if target_filing.accession_number else ""
            f_prov = SourceProvenanceDTO(
                source_type="SEC_FILING",
                primary_source=f"SEC Form {target_filing.form} / CIK {filings_explorer.cik} / Accession {target_filing.accession_number}",
                accession_number=target_filing.accession_number,
                filing_date=target_filing.filing_date,
                acceptance_datetime=target_filing.acceptance_datetime,
                sec_url=f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{target_filing.accession_number}.txt" if target_filing.accession_number else None,
                calculation_method="Direct primary extraction from SEC EDGAR XBRL / HTML disclosure",
                source_concepts=[],
                as_of_date=filings_explorer.as_of_date,
                mode=filings_explorer.mode,
                is_pit_compliant=True,
                pit_rejection_reason=None,
            )
            render_source_provenance_badge(f_prov, st_client=ctx)

            if not target_filing.sections:
                ctx.info(
                    f"Filing `{target_filing.accession_number}` does not have partitioned narrative sections in the database. "
                    "Section parsing is currently executed for primary Form 10-K filings."
                )
            else:
                highlighted: List[str] = []
                for idx, sec in enumerate(target_filing.sections, 1):
                    key_item = is_key_section(sec.section_name)
                    if key_item:
                        highlighted.append(sec.section_name)
                        badge = "⭐ [KEY INSTITUTIONAL SECTION]"
                    else:
                        badge = "[NARRATIVE SECTION]"

                    with ctx.expander(
                        f"{badge} #{idx}: {sec.section_title or sec.section_name} "
                        f"({sec.char_count:,} characters | Confidence: {sec.detection_confidence})",
                        expanded=(key_item or idx == 1),
                    ):
                        if key_item:
                            ctx.markdown(f"**Institutional Priority:** `HIGH — {sec.section_name}`")
                        ctx.markdown(f"**Section Identifier:** `{sec.section_name}`")
                        ctx.markdown(f"**Character Count:** `{sec.char_count:,}` characters")
                        ctx.markdown(f"**Detection Confidence:** `{sec.detection_confidence}`")
                        ctx.markdown("**Verbatim Text Preview:**")
                        preview_text = sec.section_preview.strip() if sec.section_preview else "N/A"
                        ctx.info(f"\"{preview_text}...\"")

                filings_data["highlighted_sections"] = highlighted

    return filings_data


