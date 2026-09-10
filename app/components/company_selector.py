"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Company Selector Component
File: app/components/company_selector.py

Renders sidebar controls for selecting universe companies (30 covered enterprises),
toggling between LIVE and HISTORICAL modes, and providing point-in-time as_of_date input.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from src.service.contracts import CompanyProfile, CompanyRequest
from src.service.platform_service import PlatformService
from app.state import get_state, set_state

try:
    import streamlit as st
except ImportError:
    st = None


def validate_historical_date(date_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate that an as-of date string is present and conforms to YYYY-MM-DD.

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str]).
    """
    if not date_str or not str(date_str).strip():
        return False, "Historical mode requires an as-of date (YYYY-MM-DD). Cutoff date is mandatory."
    clean_date = str(date_str).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", clean_date):
        return False, "Invalid historical date format. Expected YYYY-MM-DD."
    try:
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
    except ValueError:
        return False, "Invalid calendar date. Please enter a valid YYYY-MM-DD date."
    if dt > datetime.now():
        return False, "Historical cutoff date cannot be in the future."
    if dt.year < 1990:
        return False, "Historical cutoff date cannot be before 1990 (prior to digital SEC EDGAR records)."
    return True, None


def get_universe_list(service: PlatformService) -> List[CompanyProfile]:
    """Retrieve universe companies sorted alphabetically by ticker."""
    companies = service.list_covered_companies()
    return sorted(companies, key=lambda c: c.ticker)


def render_company_selector(
    service: PlatformService,
    st_client: Any = None,
) -> Tuple[Optional[CompanyRequest], bool]:
    """
    Render company selection and point-in-time analysis controls in the sidebar.

    Args:
        service: PlatformService instance to query covered companies.
        st_client: Optional Streamlit module or mock.

    Returns:
        Tuple of (Optional[CompanyRequest], run_triggered: bool).
    """
    ctx = st_client or st
    universe = get_universe_list(service)
    ticker_options = [f"{c.ticker} — {c.company_name}" for c in universe]
    ticker_map = {f"{c.ticker} — {c.company_name}": c.ticker for c in universe}

    current_ticker = get_state("selected_ticker", "MSFT", ctx)
    if not isinstance(current_ticker, str):
        current_ticker = "MSFT"

    current_mode = get_state("mode", "LIVE", ctx)
    if not isinstance(current_mode, str):
        current_mode = "LIVE"

    current_date = get_state("as_of_date", None, ctx)
    if current_date is not None and not isinstance(current_date, str):
        current_date = str(current_date)

    # Find current index
    default_idx = 0
    for idx, opt in enumerate(ticker_options):
        if opt.startswith(current_ticker + " —"):
            default_idx = idx
            break

    run_analysis = False
    selected_ticker = current_ticker
    selected_mode = current_mode
    selected_date = current_date
    date_validation_error: Optional[str] = None

    if ctx is not None:
        ctx.sidebar.markdown("### Analysis Configuration")

        # 1. Company Selection Dropdown
        selected_option = ctx.sidebar.selectbox(
            "Select Company",
            options=ticker_options,
            index=default_idx,
            help="Choose from the 30 institutional coverage universe companies.",
        )
        if isinstance(selected_option, str):
            selected_ticker = ticker_map.get(selected_option, current_ticker)

        # 2. Mode Selection
        mode_idx = 0 if current_mode == "LIVE" else 1
        sel_mode = ctx.sidebar.radio(
            "Information Horizon Mode",
            options=["LIVE", "HISTORICAL"],
            index=mode_idx,
            help="LIVE uses the latest available filings. HISTORICAL enforces point-in-time acceptance date cutoff.",
        )
        if isinstance(sel_mode, str):
            selected_mode = sel_mode

        # 3. Point-in-Time Date (if HISTORICAL)
        if selected_mode == "HISTORICAL":
            sel_date = ctx.sidebar.text_input(
                "Point-in-Time Cutoff (YYYY-MM-DD)",
                value=current_date if current_date else "",
                help="Only filings accepted by the SEC on or before this date (23:59:59) will be included. Required.",
            )
            raw_date = sel_date.strip() if isinstance(sel_date, str) else ""
            is_valid, err_msg = validate_historical_date(raw_date)
            if not is_valid:
                date_validation_error = err_msg
                selected_date = None
                ctx.sidebar.error(f"⚠️ {err_msg}")
            else:
                selected_date = raw_date
        else:
            selected_date = None

        # 4. Action Button
        run_analysis = ctx.sidebar.button("Run Analysis", type="primary")

        # Update state
        set_state("selected_ticker", selected_ticker, ctx)
        set_state("mode", selected_mode, ctx)
        set_state("as_of_date", selected_date, ctx)

    # In headless / mock mode when selected_mode is HISTORICAL and date is set
    if selected_mode == "HISTORICAL" and selected_date:
        is_valid, err_msg = validate_historical_date(selected_date)
        if not is_valid:
            date_validation_error = err_msg
            selected_date = None

    # Build validated request, or return None if parameters are invalid
    if selected_mode == "HISTORICAL" and (not selected_date or date_validation_error):
        return None, run_analysis

    request = None
    try:
        request = CompanyRequest(
            ticker=selected_ticker,
            mode=selected_mode,
            as_of_date=selected_date,
        )
    except Exception:
        request = None

    return request, run_analysis
