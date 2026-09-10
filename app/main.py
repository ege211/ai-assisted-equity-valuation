"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Streamlit Application Main Entry Point
File: app/main.py

The main application shell orchestrating:
1. Streamlit layout and session state management
2. Sidebar company selection and point-in-time configuration
3. PlatformService invocation (analyze_company)
4. Graceful handling of structured service exceptions
5. Top-level institutional header and real DTO KPI cards
6. Tab-based dispatching across the 6 core analytical views
"""

import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path so 'src' and 'app' packages are discoverable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service.platform_service import PlatformService
from src.service.contracts import (
    AnalysisResponse,
    CompanyRequest,
    PlatformServiceError,
    InvalidTickerError,
    MissingCompanyError,
    MissingPITDateError,
    UnsupportedModeError,
)

from app.state import (
    init_session_state,
    get_state,
    set_state,
    reset_analysis_state,
)
from app.components import (
    render_header,
    render_company_selector,
    render_kpi_cards,
    render_navigation,
)
from app.pages import (
    render_overview_page,
    render_valuation_page,
    render_fundamentals_page,
    render_filings_page,
    render_evidence_page,
    render_changes_page,
)

try:
    import streamlit as st
except ImportError:
    st = None


def get_default_service() -> PlatformService:
    """Instantiate and return the production PlatformService."""
    return PlatformService()


def run_app(service: Optional[PlatformService] = None, st_client: Any = None) -> Optional[AnalysisResponse]:
    """
    Execute the application lifecycle.

    Args:
        service: Optional PlatformService instance (defaults to production instance).
        st_client: Optional Streamlit module or mock.

    Returns:
        The resulting AnalysisResponse DTO, or None if an error occurred.
    """
    ctx = st_client or st
    svc = service or get_default_service()

    # 1. Page Configuration (if Streamlit is available)
    if ctx is not None and hasattr(ctx, "set_page_config"):
        try:
            ctx.set_page_config(
                page_title="Equity Intelligence Terminal",
                page_icon="📈",
                layout="wide",
                initial_sidebar_state="expanded",
            )
        except Exception:
            pass

    # 2. State Initialization
    init_session_state(ctx)

    # 3. Sidebar Controls
    request, run_triggered = render_company_selector(svc, ctx)
    active_page = render_navigation(ctx)

    # 4. Analysis Execution
    cached_response: Optional[AnalysisResponse] = get_state("analysis_response", None, ctx)
    response: Optional[AnalysisResponse] = cached_response
    service_error_msg: Optional[str] = None

    if request is None:
        service_error_msg = "Point-in-Time Error: Historical analysis requires an explicit as_of_date (YYYY-MM-DD)."
        reset_analysis_state(ctx)
        set_state("service_error", service_error_msg, ctx)
        response = None
    else:
        last_ticker = get_state("_last_ticker", None, ctx)
        last_mode = get_state("_last_mode", None, ctx)
        last_date = get_state("_last_date", None, ctx)

        params_changed = (
            request.ticker != last_ticker
            or request.mode != last_mode
            or request.as_of_date != last_date
        )

        should_execute = run_triggered or cached_response is None or params_changed

        if should_execute:
            try:
                response = svc.analyze_company(request)
                set_state("analysis_response", response, ctx)
                set_state("service_error", None, ctx)
                set_state("_last_ticker", request.ticker, ctx)
                set_state("_last_mode", request.mode, ctx)
                set_state("_last_date", request.as_of_date, ctx)
            except MissingPITDateError as e:
                service_error_msg = f"Point-in-Time Error: {str(e)}"
                reset_analysis_state(ctx)
                set_state("service_error", service_error_msg, ctx)
                response = None
            except InvalidTickerError as e:
                service_error_msg = f"Invalid Ticker Symbol: {str(e)}"
                reset_analysis_state(ctx)
                set_state("service_error", service_error_msg, ctx)
                response = None
            except MissingCompanyError as e:
                service_error_msg = f"Company Not Covered: {str(e)}"
                reset_analysis_state(ctx)
                set_state("service_error", service_error_msg, ctx)
                response = None
            except UnsupportedModeError as e:
                service_error_msg = f"Unsupported Mode: {str(e)}"
                reset_analysis_state(ctx)
                set_state("service_error", service_error_msg, ctx)
                response = None
            except PlatformServiceError as e:
                service_error_msg = f"Platform Service Error: {str(e)}"
                reset_analysis_state(ctx)
                set_state("service_error", service_error_msg, ctx)
                response = None
            except Exception as e:
                service_error_msg = f"System Error: {str(e)}"
                reset_analysis_state(ctx)
                set_state("service_error", service_error_msg, ctx)
                response = None

    # 5. Render Header & Error Banner
    if service_error_msg and ctx is not None:
        ctx.error(f"⚠️ {service_error_msg}")

    render_header(
        profile=response.profile if response else None,
        mode=request.mode if request else get_state("mode", "LIVE", ctx),
        as_of_date=request.as_of_date if request else get_state("as_of_date", None, ctx),
        status=response.status if response else "ERROR" if service_error_msg else "IDLE",
        warnings=response.warnings if response else None,
        st_client=ctx,
    )

    if ctx is not None:
        ctx.markdown("---")

    # 6. Render KPI Cards
    render_kpi_cards(response, ctx)

    if ctx is not None:
        ctx.markdown("---")

    # 7. Render Active Page View
    curr_mode = request.mode if request else get_state("mode", "LIVE", ctx)
    curr_date = request.as_of_date if request else get_state("as_of_date", None, ctx)

    if active_page == "Overview":
        render_overview_page(response, mode=curr_mode, as_of_date=curr_date, st_client=ctx)
    elif active_page == "Valuation":
        render_valuation_page(response, service=svc, mode=curr_mode, as_of_date=curr_date, st_client=ctx)
    elif active_page == "Fundamentals":
        render_fundamentals_page(response, mode=curr_mode, as_of_date=curr_date, st_client=ctx, service=svc)
    elif active_page == "Filing Intelligence":
        render_filings_page(response, mode=curr_mode, as_of_date=curr_date, st_client=ctx, service=svc)
    elif active_page == "Evidence":
        render_evidence_page(response, mode=curr_mode, as_of_date=curr_date, st_client=ctx, service=svc)
    elif active_page == "What Changed":
        render_changes_page(response, mode=curr_mode, as_of_date=curr_date, st_client=ctx, service=svc)

    return response


def main():
    """Main script entry point."""
    if st is None:
        print("=" * 70)
        print("AI-Assisted Equity Valuation & Investment Intelligence Platform")
        print("=" * 70)
        print("Streamlit is not installed in the current environment.")
        print("To launch the interactive dashboard, install Streamlit and run:")
        print("    streamlit run app/main.py")
        print("\nVerifying PlatformService integration:")
        svc = get_default_service()
        companies = svc.list_covered_companies()
        print(f"PlatformService connected. Covered universe: {len(companies)} companies.")
        print("Sample analysis for MSFT (LIVE):")
        resp = svc.analyze_company(CompanyRequest("MSFT", mode="LIVE"))
        fv = resp.valuation.fair_value_per_share if resp.valuation else None
        print(f"Status: {resp.status} | Base Fair Value: {('$' + f'{fv:.2f}') if fv is not None else 'N/A'}")
        print("=" * 70)
    else:
        run_app()


if __name__ == "__main__":
    main()
