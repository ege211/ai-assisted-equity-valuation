"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8C — Canonical Fundamentals & Accounting Explorer View
File: app/pages/fundamentals.py

Renders canonical multi-period financial statements and normalized accounting features:
1. Multi-period Income Statement ([SOURCE DATA])
2. Multi-period Balance Sheet ([SOURCE DATA])
3. Multi-period Cash Flow Statement ([SOURCE DATA])
4. Normalized Accounting Quality Ratios & Features ([MODEL OUTPUT])
5. Period toggle (Annual 10-K vs Quarterly 10-Q)
6. Strict Point-in-Time compliance (via PlatformService.get_fundamentals)
7. Explicit taxonomy labels ([SOURCE DATA], [MODEL OUTPUT], [ANALYST ASSUMPTION])
"""

from typing import Any, Dict, List, Optional
from src.service.contracts import AnalysisResponse, FundamentalsResponse, FinancialPeriodDTO, FinancialFeatureDTO
from src.service.platform_service import PlatformService
from app.components.temporal_context import render_temporal_context
from app.components.provenance import render_source_provenance_badge

try:
    import streamlit as st
except ImportError:
    st = None


def format_currency(val: Optional[float]) -> str:
    """Format currency values in billions/millions with clean negative signs."""
    if val is None:
        return "N/A"
    prefix = "-$" if val < 0 else "$"
    abs_val = abs(val)
    if abs_val >= 1e9:
        return f"{prefix}{abs_val / 1e9:,.2f}B"
    if abs_val >= 1e6:
        return f"{prefix}{abs_val / 1e6:,.2f}M"
    return f"{prefix}{abs_val:,.0f}"


def format_ratio(val: Optional[float]) -> str:
    """Format ratio values as percentages."""
    if val is None:
        return "N/A"
    return f"{val * 100:.2f}%"


def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generate a clean GitHub-flavored markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, separator_line] + row_lines)


def render_fundamentals_page(
    response: Optional[AnalysisResponse] = None,
    mode: str = "LIVE",
    as_of_date: Optional[str] = None,
    st_client: Any = None,
    service: Optional[Any] = None,
    fundamentals: Optional[FundamentalsResponse] = None,
) -> Dict[str, Any]:
    """
    Render the canonical fundamental financial statement and normalized feature view.

    Args:
        response: Optional AnalysisResponse DTO from PlatformService.
        st_client: Optional Streamlit module or mock.
        service: Optional PlatformService instance for fetching data.
        fundamentals: Optional pre-loaded FundamentalsResponse DTO (for testing/caching).

    Returns:
        Structured data dictionary for testing/headless execution.
    """
    ctx = st_client or st
    fund_data: Dict[str, Any] = {
        "ticker": None,
        "mode": None,
        "as_of_date": None,
        "annual_count": 0,
        "quarterly_count": 0,
        "features_count": 0,
        "selected_frequency": "ANNUAL",
        "displayed_statement": {},
        "normalized_ratios": {},
    }

    eff_mode = (fundamentals.mode if fundamentals else (response.request.mode if (response and response.request) else mode)).upper()
    eff_as_of_date = fundamentals.as_of_date if fundamentals else (response.request.as_of_date if (response and response.request) else as_of_date)
    cutoff_str = f"{eff_as_of_date} 23:59:59" if eff_mode == "HISTORICAL" else "LIVE (LATEST)"

    # 1. Resolve Fundamentals data
    if fundamentals is None:
        if response is not None and response.profile is not None:
            svc = service or PlatformService()
            ticker = response.profile.ticker
            try:
                fundamentals = svc.get_fundamentals(ticker=ticker, as_of_date=eff_as_of_date, mode=eff_mode)
            except Exception as e:
                if ctx is not None:
                    ctx.error(f"Failed to load fundamental financial statements: {e}")
                return fund_data
        elif service is not None and hasattr(service, "get_fundamentals"):
            pass

    if fundamentals is None:
        if ctx is not None:
            render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
            ctx.warning("Please select a company to display fundamental statements.")
        return fund_data

    # Populate summary metadata
    fund_data["ticker"] = fundamentals.ticker
    fund_data["mode"] = fundamentals.mode
    fund_data["as_of_date"] = fundamentals.as_of_date
    fund_data["information_cutoff"] = cutoff_str
    fund_data["annual_count"] = len(fundamentals.annual_statements)
    fund_data["quarterly_count"] = len(fundamentals.quarterly_statements)
    fund_data["features_count"] = len(fundamentals.features)
    fund_data["annual_statements"] = fundamentals.annual_statements
    fund_data["quarterly_statements"] = fundamentals.quarterly_statements
    fund_data["features"] = fundamentals.features

    if ctx is not None:
        ctx.header("Financial Statements & Normalized Accounting Features")
        render_temporal_context(mode=eff_mode, as_of_date=eff_as_of_date, st_client=ctx)
        ctx.caption(
            "Point-in-Time Audited SEC Data | Standardized XBRL Concept Cascades | Multi-Period Historical Exploration"
        )

        ctx.markdown(
            f"**Reporting Entity:** `{fundamentals.ticker}` | "
            f"**Mode:** `{fundamentals.mode}` | "
            f"**Information Cutoff:** `{cutoff_str}` | "
            f"**Audited Annuals:** `{len(fundamentals.annual_statements)}` | "
            f"**Audited Quarterlies:** `{len(fundamentals.quarterly_statements)}`"
        )
        ctx.markdown("---")

        # 2. Frequency Selector Controls
        freq_choice = "Annual (Form 10-K)"
        if hasattr(ctx, "radio"):
            freq_choice = ctx.radio(
                "Statement Frequency",
                options=["Annual (Form 10-K)", "Quarterly (Form 10-Q)"],
                index=0,
                horizontal=True,
                help="Select reporting periodicity for primary statements.",
            )

        is_annual = "Annual" in str(freq_choice)
        active_stmts = fundamentals.annual_statements if is_annual else fundamentals.quarterly_statements
        fund_data["selected_frequency"] = "ANNUAL" if is_annual else "QUARTERLY"

        if not active_stmts:
            if eff_mode == "HISTORICAL":
                ctx.warning(f"N/A — fundamental financial statements unavailable as of point-in-time cutoff {cutoff_str}.")
            else:
                ctx.info(f"No {fund_data['selected_frequency'].lower()} statements found prior to point-in-time cutoff.")
            return fund_data

        # Limit to 5 most recent periods for tabular clarity
        display_periods: List[FinancialPeriodDTO] = active_stmts[:5]

        latest_p = display_periods[0] if display_periods else None
        latest_prov = latest_p.source_provenance if latest_p else None
        fund_data["latest_provenance"] = latest_prov

        # Column headers
        def make_col_header(p: FinancialPeriodDTO) -> str:
            if p.period_type == "ANNUAL":
                return f"FY {p.fiscal_year} ({p.period_end_date})"
            return f"{p.fiscal_period} {p.fiscal_year} ({p.period_end_date})"

        period_headers = [make_col_header(p) for p in display_periods]
        table_headers = ["Line Item"] + period_headers

        # Render Statement Provenance
        render_source_provenance_badge(latest_prov, st_client=ctx)

        # 3. Canonical Income Statement
        ctx.markdown("### 1. Consolidated Income Statement `[SOURCE DATA]`")
        ctx.caption("Authoritative SEC EDGAR primary line items from audited filings.")

        income_rows_def = [
            ("Revenue", lambda p: format_currency(p.revenue)),
            ("Cost of Goods Sold (COGS)", lambda p: format_currency(p.cogs)),
            ("Gross Profit", lambda p: format_currency(p.gross_profit)),
            ("Selling, General & Administrative (SG&A)", lambda p: format_currency(p.sga)),
            ("Operating Income (EBIT)", lambda p: format_currency(p.ebit)),
            ("Interest Expense", lambda p: format_currency(p.interest_expense)),
            ("Income Before Taxes", lambda p: format_currency(p.pretax_income)),
            ("Income Tax Expense", lambda p: format_currency(p.tax_expense)),
            ("Net Income", lambda p: format_currency(p.net_income)),
            ("Depreciation & Amortization (D&A)", lambda p: format_currency(p.da)),
        ]

        income_table_rows = []
        for label, getter in income_rows_def:
            row_vals = [label] + [getter(p) for p in display_periods]
            income_table_rows.append(row_vals)

        income_md = _build_markdown_table(table_headers, income_table_rows)
        ctx.markdown(income_md)
        fund_data["displayed_statement"]["income_statement"] = {
            "headers": table_headers,
            "rows": income_table_rows,
        }

        ctx.markdown("---")

        # 4. Canonical Balance Sheet
        ctx.markdown("### 2. Consolidated Balance Sheet `[SOURCE DATA]`")
        ctx.caption("Point-in-time balance sheet snapshots reported at period end.")

        bs_rows_def = [
            ("Cash & Cash Equivalents", lambda p: format_currency(p.cash)),
            ("Current Assets", lambda p: format_currency(p.current_assets)),
            ("Accounts Receivable", lambda p: format_currency(p.accounts_receivable)),
            ("Inventories", lambda p: format_currency(p.inventory)),
            ("Total Assets", lambda p: format_currency(p.total_assets)),
            ("Current Liabilities", lambda p: format_currency(p.current_liabilities)),
            ("Accounts Payable", lambda p: format_currency(p.accounts_payable)),
            ("Total Debt", lambda p: format_currency(p.total_debt)),
            ("Total Stockholders' Equity", lambda p: format_currency(p.total_equity)),
        ]

        bs_table_rows = []
        for label, getter in bs_rows_def:
            row_vals = [label] + [getter(p) for p in display_periods]
            bs_table_rows.append(row_vals)

        bs_md = _build_markdown_table(table_headers, bs_table_rows)
        ctx.markdown(bs_md)
        fund_data["displayed_statement"]["balance_sheet"] = {
            "headers": table_headers,
            "rows": bs_table_rows,
        }

        ctx.markdown("---")

        # 5. Canonical Cash Flow Statement
        ctx.markdown("### 3. Consolidated Statement of Cash Flows `[SOURCE DATA]`")
        ctx.caption("Audited operating cash generation and capital reinvestment.")

        cf_rows_def = [
            ("Cash Flow from Operations (CFO)", lambda p: format_currency(p.cfo)),
            ("Capital Expenditures (Capex)", lambda p: format_currency(p.capex)),
            ("Free Cash Flow (FCF)", lambda p: format_currency(p.fcf)),
        ]

        cf_table_rows = []
        for label, getter in cf_rows_def:
            row_vals = [label] + [getter(p) for p in display_periods]
            cf_table_rows.append(row_vals)

        cf_md = _build_markdown_table(table_headers, cf_table_rows)
        ctx.markdown(cf_md)
        fund_data["displayed_statement"]["cash_flow"] = {
            "headers": table_headers,
            "rows": cf_table_rows,
        }

        ctx.markdown("---")

        # 6. Normalized Accounting Quality Ratios
        ctx.markdown("### 4. Normalized Accounting Quality Ratios `[MODEL OUTPUT]`")
        ctx.caption(
            "Phase 3 Deterministic Accounting Normalization Engine | Clean Capital Returns & Margin Trajectory"
        )

        target_dates = [p.period_end_date for p in display_periods]
        feat_by_date_and_name: Dict[str, Dict[str, FinancialFeatureDTO]] = {}
        for f in fundamentals.features:
            if f.period_end_date in target_dates:
                feat_by_date_and_name.setdefault(f.period_end_date, {})[f.feature_name] = f

        ratio_defs = [
            ("Return on Invested Capital (ROIC)", "roic", format_ratio),
            ("Operating Margin (EBIT Margin)", "ebit_margin", format_ratio),
            ("Gross Margin", "gross_margin", format_ratio),
            ("Net Profit Margin", "net_margin", format_ratio),
            ("Revenue Growth (YoY)", "revenue_growth_yoy", format_ratio),
            ("Operating Working Capital (OWC)", "operating_working_capital", format_currency),
            ("OWC to Revenue Ratio", "owc_to_revenue", format_ratio),
            ("Normalized Tax Rate", "normalized_tax_rate", format_ratio),
            ("Invested Capital", "invested_capital", format_currency),
            ("Net Debt", "net_debt", format_currency),
        ]

        ratio_table_rows = []
        for label, feat_key, formatter in ratio_defs:
            row_vals = [label]
            for p in display_periods:
                feat = feat_by_date_and_name.get(p.period_end_date, {}).get(feat_key)
                val_str = formatter(feat.feature_value) if feat else "N/A"
                row_vals.append(val_str)
            ratio_table_rows.append(row_vals)

        ratio_md = _build_markdown_table(table_headers, ratio_table_rows)
        ctx.markdown(ratio_md)
        fund_data["normalized_ratios"] = {
            "headers": table_headers,
            "rows": ratio_table_rows,
        }

    return fund_data

