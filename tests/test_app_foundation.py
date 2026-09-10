"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8B — Application Foundation Verification Suite
File: tests/test_app_foundation.py

Comprehensive test suite verifying the Streamlit application shell:
1. App and module importability
2. UI isolation (Streamlit prohibited in src/)
3. Service layer independence
4. Company universe selector
5. LIVE request execution
6. HISTORICAL request execution with PIT enforcement
7. Rejection of HISTORICAL mode without date
8. Graceful handling of invalid tickers
9. AnalysisResponse immutability across UI renderers
10. Strict 'N/A' rendering for unavailable values (no synthetic data)
11. Verification that no valuation formulas exist in app/
12. Mocked UI Streamlit method invocations
13. Verbatim Phase 7 research disclosure rendering
14. Analytical taxonomy tags (Source Data, Analyst Assumption, Model Output)
15. Navigation view definitions
"""

import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service.contracts import (
    AnalysisResponse,
    CompanyProfile,
    CompanyRequest,
    FilingIntelligenceResponse,
    FilingSignal,
    ForecastPeriodDTO,
    InvalidRequestError,
    InvalidTickerError,
    MissingCompanyError,
    MissingPITDateError,
    ResearchDisclosure,
    ValuationResponse,
    ValuationScenarioSummary,
)
from src.service.platform_service import PlatformService
from app.state import (
    clear_fallback_state,
    get_state,
    init_session_state,
    reset_analysis_state,
    set_state,
)
from app.components import (
    format_count,
    format_currency,
    format_multiple,
    format_percent,
    render_company_selector,
    render_header,
    render_kpi_cards,
    render_navigation,
)
from app.components.company_selector import get_universe_list
from app.components.navigation import NAV_PAGES
from app.pages import (
    render_changes_page,
    render_evidence_page,
    render_filings_page,
    render_fundamentals_page,
    render_overview_page,
    render_valuation_page,
)
from app.main import run_app


class TestAppFoundation(unittest.TestCase):
    """Phase 8B verification test suite for the Streamlit application shell."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = PlatformService()

    def setUp(self) -> None:
        clear_fallback_state()
        init_session_state()

    def test_01_app_imports_successfully(self) -> None:
        """Verify all app modules, components, and pages import cleanly."""
        import app.main
        import app.state
        import app.components
        import app.components.header
        import app.components.company_selector
        import app.components.kpi_cards
        import app.components.navigation
        import app.pages
        import app.pages.overview
        import app.pages.valuation
        import app.pages.fundamentals
        import app.pages.filings
        import app.pages.evidence
        import app.pages.changes

        self.assertTrue(hasattr(app.main, "run_app"))
        self.assertTrue(hasattr(app.components, "render_kpi_cards"))
        self.assertTrue(hasattr(app.pages, "render_overview_page"))

    def test_02_streamlit_isolated_to_app_and_not_in_src(self) -> None:
        """
        Verify that Streamlit and Dash are NEVER imported anywhere in src/.
        UI frameworks must remain strictly isolated to app/.
        """
        src_dir = PROJECT_ROOT / "src"
        py_files = list(src_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 10, "Should inspect existing src/ Python files.")

        prohibited_modules = {"streamlit", "dash", "gradio"}

        for py_file in py_files:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_pkg = alias.name.split(".")[0]
                        self.assertNotIn(
                            top_pkg,
                            prohibited_modules,
                            f"Prohibited UI import '{top_pkg}' found in {py_file.name}",
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_pkg = node.module.split(".")[0]
                        self.assertNotIn(
                            top_pkg,
                            prohibited_modules,
                            f"Prohibited UI from-import '{top_pkg}' found in {py_file.name}",
                        )

    def test_03_service_layer_ui_independent(self) -> None:
        """Verify that src.service has no dependencies on app/ or UI packages."""
        service_dir = PROJECT_ROOT / "src" / "service"
        for py_file in service_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            self.assertNotIn("import app", content)
            self.assertNotIn("from app", content)
            self.assertNotIn("streamlit", content)

    def test_04_company_selector_returns_valid_universe(self) -> None:
        """Verify that the company selector retrieves the 30-company universe."""
        universe = get_universe_list(self.service)
        self.assertEqual(len(universe), 30)

        tickers = [c.ticker for c in universe]
        self.assertIn("MSFT", tickers)
        self.assertIn("AAPL", tickers)
        self.assertIn("NVDA", tickers)
        self.assertIn("XOM", tickers)
        self.assertIn("JNJ", tickers)

        # Check alphabetical sorting
        self.assertEqual(tickers, sorted(tickers))

    def test_05_live_request_works(self) -> None:
        """Verify that a LIVE analysis request executes and returns complete AnalysisResponse."""
        set_state("selected_ticker", "MSFT")
        set_state("mode", "LIVE")
        set_state("as_of_date", None)

        response = run_app(service=self.service)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, AnalysisResponse)
        self.assertEqual(response.profile.ticker, "MSFT")
        self.assertEqual(response.status, "SUCCESS")
        self.assertIsNotNone(response.valuation)
        self.assertGreater(response.valuation.fair_value_per_share, 0)
        self.assertEqual(response.valuation.valuation_mode, "LIVE")

    def test_06_historical_request_works(self) -> None:
        """Verify that a HISTORICAL analysis request executes with exact point-in-time propagation."""
        set_state("selected_ticker", "MSFT")
        set_state("mode", "HISTORICAL")
        set_state("as_of_date", "2024-12-31")

        response = run_app(service=self.service)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, AnalysisResponse)
        self.assertEqual(response.profile.ticker, "MSFT")
        self.assertIsNotNone(response.valuation)
        self.assertEqual(response.valuation.valuation_mode, "HISTORICAL")
        self.assertEqual(response.valuation.valuation_date, "2024-12-31")
        self.assertEqual(response.request.as_of_date, "2024-12-31")

    def test_07_historical_without_date_is_rejected(self) -> None:
        """Verify that HISTORICAL mode without an as_of_date is strictly rejected and handled gracefully."""
        # 1. Direct contract assertion
        with self.assertRaises(MissingPITDateError):
            CompanyRequest(ticker="MSFT", mode="HISTORICAL", as_of_date=None)

        # 2. App-level graceful error handling
        set_state("selected_ticker", "MSFT")
        set_state("mode", "HISTORICAL")
        set_state("as_of_date", None)

        # Simulating run_app catching the error
        mock_st = MagicMock()
        mock_st.sidebar.selectbox.return_value = "MSFT — Microsoft Corporation"
        mock_st.sidebar.radio.return_value = "HISTORICAL"
        mock_st.sidebar.text_input.return_value = ""
        mock_st.sidebar.button.return_value = True

        response = run_app(service=self.service, st_client=mock_st)
        self.assertIsNone(response)
        service_error = get_state("service_error", st_client=mock_st)
        self.assertIsNotNone(service_error)
        self.assertIn("Point-in-Time Error", service_error)

    def test_08_invalid_ticker_handled(self) -> None:
        """Verify that invalid or missing tickers raise structured errors and are caught gracefully."""
        # 1. Blank ticker
        with self.assertRaises(InvalidTickerError):
            CompanyRequest(ticker="", mode="LIVE")

        # 2. Unknown company
        with self.assertRaises(MissingCompanyError):
            self.service.analyze_company(CompanyRequest(ticker="UNKNOWN_TICKER_XYZ", mode="LIVE"))

        # 3. Graceful handling in app
        mock_st = MagicMock()
        mock_st.sidebar.selectbox.return_value = "MSFT — Microsoft Corporation"
        mock_st.sidebar.radio.return_value = "LIVE"
        mock_st.sidebar.button.return_value = True

        # Deliberately set state to an unknown ticker
        set_state("selected_ticker", "UNKNOWN_TICKER_XYZ", mock_st)
        set_state("_last_ticker", None, mock_st)

        # Mock service that raises MissingCompanyError
        mock_svc = MagicMock()
        mock_svc.list_covered_companies.return_value = self.service.list_covered_companies()
        mock_svc.analyze_company.side_effect = MissingCompanyError("Company 'UNKNOWN' not found.")

        response = run_app(service=mock_svc, st_client=mock_st)
        self.assertIsNone(response)
        err = get_state("service_error", st_client=mock_st)
        self.assertIn("Company Not Covered", err)

    def test_09_analysis_response_renders_without_mutation(self) -> None:
        """Verify that passing AnalysisResponse to UI components and pages never mutates the DTO."""
        req = CompanyRequest("MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)

        initial_fv = resp.valuation.fair_value_per_share
        initial_status = resp.status
        initial_ticker = resp.profile.ticker

        # Pass through all renderers
        render_header(resp.profile, "LIVE", None, resp.status, resp.warnings)
        render_kpi_cards(resp)
        render_overview_page(resp)
        render_valuation_page(resp)
        render_fundamentals_page(resp)
        render_filings_page(resp)
        render_evidence_page(resp)
        render_changes_page(resp)

        # Assert zero mutation
        self.assertEqual(resp.valuation.fair_value_per_share, initial_fv)
        self.assertEqual(resp.status, initial_status)
        self.assertEqual(resp.profile.ticker, initial_ticker)

    def test_10_unavailable_values_render_as_na(self) -> None:
        """Verify that when values are unavailable, formatting helpers render 'N/A' (never synthetic numbers)."""
        # 1. Format helpers
        self.assertEqual(format_currency(None), "N/A")
        self.assertEqual(format_percent(None), "N/A")
        self.assertEqual(format_multiple(None), "N/A")
        self.assertEqual(format_count(None), "N/A")

        # 2. None response in KPI cards
        kpis_none = render_kpi_cards(None)
        for k, v in kpis_none.items():
            self.assertEqual(v, "N/A", f"Key {k} should be 'N/A' when response is None")

        # 3. Partial response with missing valuation
        profile = self.service.get_company_profile("MSFT")
        disc = self.service.get_research_disclosure()
        partial_resp = AnalysisResponse(
            request=CompanyRequest("MSFT", mode="LIVE"),
            profile=profile,
            valuation=None,  # Missing valuation
            filing_intelligence=None,  # Missing filing intelligence
            research_disclosure=disc,
            status="PARTIAL",
            warnings=["Deterministic valuation unavailable."],
        )

        kpis_partial = render_kpi_cards(partial_resp)
        self.assertEqual(kpis_partial["fair_value_per_share"], "N/A")
        self.assertEqual(kpis_partial["enterprise_value"], "N/A")
        self.assertEqual(kpis_partial["wacc"], "N/A")
        self.assertEqual(kpis_partial["pe_multiple"], "N/A")
        self.assertEqual(kpis_partial["analysis_status"], "PARTIAL")

    def test_11_no_valuation_formulas_exist_in_app(self) -> None:
        """
        Verify that app/ contains NO mathematical valuation formulas or financial ratio derivations.
        All math must reside in src/valuation/ and src/normalization/.
        """
        app_dir = PROJECT_ROOT / "app"
        py_files = list(app_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 5)

        prohibited_formula_patterns = [
            "1 / (1 + wacc)",
            "1 / (1 + WACC)",
            "terminal_value =",
            "nopat = ebit",
            "rf + beta *",
            "cost_of_equity =",
        ]

        for py_file in py_files:
            text = py_file.read_text(encoding="utf-8").lower()
            for pattern in prohibited_formula_patterns:
                self.assertNotIn(
                    pattern.lower(),
                    text,
                    f"Prohibited valuation formula '{pattern}' found in {py_file.name}",
                )

    def test_12_mock_ui_rendering_calls(self) -> None:
        """Verify that components invoke Streamlit methods correctly when client is supplied."""
        mock_st = MagicMock()
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col] * 6

        req = CompanyRequest("MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)

        # 1. Header
        render_header(resp.profile, st_client=mock_st)
        mock_st.title.assert_called()

        # 2. KPI Cards
        render_kpi_cards(resp, st_client=mock_st)
        mock_col.metric.assert_called()

        # 3. Overview Page
        render_overview_page(resp, st_client=mock_st)
        mock_st.header.assert_called()

        # 4. Valuation Page
        render_valuation_page(resp, st_client=mock_st)
        mock_st.dataframe.assert_called()

        # 5. Evidence Page
        render_evidence_page(resp, st_client=mock_st)
        self.assertTrue(mock_st.expander.called or mock_st.markdown.called)

    def test_13_phase7_research_disclosure_verbatim(self) -> None:
        """Verify overview page contains the exact frozen Phase 7 research disclosure figures."""
        req = CompanyRequest("MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)
        page_data = render_overview_page(resp)

        disc = page_data["disclosure"]
        self.assertEqual(disc["sample_size"], 46)
        self.assertEqual(disc["walk_forward_folds"], 2)
        self.assertEqual(disc["baseline_mae"], 0.0777)
        self.assertEqual(disc["enhanced_mae"], 0.0781)
        self.assertEqual(disc["p_value"], 0.2335)
        self.assertEqual(disc["hypothesis_decision"], "Fail to reject H0")
        self.assertIn("do not provide statistically significant incremental predictive power", disc["key_takeaway"])

    def test_14_taxonomy_tags_present(self) -> None:
        """Verify that analytical taxonomy tags (Source Data, Analyst Assumption, Model Output) are rendered."""
        mock_st = MagicMock()
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col] * 6

        req = CompanyRequest("MSFT", mode="LIVE")
        resp = self.service.analyze_company(req)

        header_info = render_header(resp.profile, st_client=mock_st)
        self.assertIn("source_data", header_info["taxonomy"])
        self.assertIn("analyst_assumptions", header_info["taxonomy"])
        self.assertIn("model_output", header_info["taxonomy"])

        # Check call arguments for taxonomy markdown
        markdown_calls = [call[0][0] for call in mock_st.markdown.call_args_list if call[0]]
        taxonomy_rendered = any("ANALYTICAL TAXONOMY" in str(c) for c in markdown_calls)
        self.assertTrue(taxonomy_rendered, "Taxonomy bar must be rendered in header.")

    def test_15_navigation_options(self) -> None:
        """Verify that all 6 required analytical navigation pages are defined."""
        expected_pages = [
            "Overview",
            "Valuation",
            "Fundamentals",
            "Filing Intelligence",
            "Evidence",
            "What Changed",
        ]
        self.assertEqual(NAV_PAGES, expected_pages)


if __name__ == "__main__":
    unittest.main()
