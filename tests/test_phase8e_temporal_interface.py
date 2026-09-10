"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8E — Historical / Live Mode & Point-in-Time Research Interface Verification Suite
File: tests/test_phase8e_temporal_interface.py

Comprehensive test suite verifying the Phase 8E specifications (23 required tests):
1. test_01_temporal_component_live
2. test_02_temporal_component_historical
3. test_03_temporal_component_missing_historical_date
4. test_04_format_temporal_label
5. test_05_company_selector_validate_historical_date_valid
6. test_06_company_selector_validate_historical_date_missing
7. test_07_company_selector_validate_historical_date_invalid_format
8. test_08_company_selector_validate_historical_date_future
9. test_09_company_selector_validate_historical_date_ancient
10. test_10_synthetic_anti_leakage_cutoff
11. test_11_platform_service_filing_intelligence_pit_cutoff
12. test_12_platform_service_filings_explorer_pit_cutoff
13. test_13_platform_service_fundamentals_pit_cutoff
14. test_14_platform_service_missing_pit_date_error
15. test_15_zero_lookahead_no_live_fallback
16. test_16_overview_page_historical_mode
17. test_17_valuation_page_historical_mode
18. test_18_valuation_page_zero_fallback
19. test_19_fundamentals_page_historical_mode
20. test_20_filings_page_historical_mode
21. test_21_evidence_page_historical_mode
22. test_22_changes_page_historical_mode
23. test_23_main_run_app_historical_mode
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
from src.service.contracts import (
    CompanyRequest,
    ValuationRequest,
    AnalysisResponse,
    CompanyProfile,
    ResearchDisclosure,
    MissingPITDateError,
    ValuationUnavailableError,
)
from src.service.platform_service import PlatformService
from app.components.temporal_context import render_temporal_context, format_temporal_label
from app.components.company_selector import validate_historical_date
from app.pages.overview import render_overview_page
from app.pages.valuation import render_valuation_page
from app.pages.fundamentals import render_fundamentals_page
from app.pages.filings import render_filings_page
from app.pages.evidence import render_evidence_page
from app.pages.changes import render_changes_page
from app.main import run_app
from app.state import init_session_state, set_state


class MockStreamlitContext:
    """Mock Streamlit object capturing calls for headless verification."""
    def __init__(self):
        self.sidebar = self
        self.markdown_calls: List[str] = []
        self.metric_calls: List[tuple] = []
        self.header_calls: List[str] = []
        self.caption_calls: List[str] = []
        self.info_calls: List[str] = []
        self.warning_calls: List[str] = []
        self.error_calls: List[str] = []
        self.success_calls: List[str] = []
        self.write_calls: List[str] = []
        self.radio_returns: Dict[str, Any] = {}
        self.selectbox_returns: Dict[str, Any] = {}
        self.text_input_returns: Dict[str, Any] = {}
        self.button_returns: Dict[str, bool] = {}
        self.slider_returns: Dict[str, float] = {}

    def title(self, text, *args, **kwargs):
        self.header_calls.append(str(text))

    def header(self, text, *args, **kwargs):
        self.header_calls.append(str(text))

    def subheader(self, text, *args, **kwargs):
        self.header_calls.append(str(text))

    def caption(self, text, *args, **kwargs):
        self.caption_calls.append(str(text))

    def markdown(self, text, *args, **kwargs):
        self.markdown_calls.append(str(text))

    def metric(self, label, value, delta=None, *args, **kwargs):
        self.metric_calls.append((str(label), str(value), str(delta) if delta else None))

    def info(self, text, *args, **kwargs):
        self.info_calls.append(str(text))

    def warning(self, text, *args, **kwargs):
        self.warning_calls.append(str(text))

    def error(self, text, *args, **kwargs):
        self.error_calls.append(str(text))

    def success(self, text, *args, **kwargs):
        self.success_calls.append(str(text))

    def write(self, text, *args, **kwargs):
        self.write_calls.append(str(text))

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [self] * n

    def expander(self, label, expanded=False):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def radio(self, label, options, index=0, *args, **kwargs):
        if label in self.radio_returns:
            return self.radio_returns[label]
        return options[index] if options else None

    def selectbox(self, label, options, index=0, *args, **kwargs):
        if label in self.selectbox_returns:
            return self.selectbox_returns[label]
        return options[index] if options else None

    def text_input(self, label, value="", *args, **kwargs):
        if label in self.text_input_returns:
            return self.text_input_returns[label]
        return value

    def button(self, label, *args, **kwargs):
        return self.button_returns.get(label, False)

    def slider(self, label, min_value=0.0, max_value=1.0, value=0.5, *args, **kwargs):
        if label in self.slider_returns:
            return self.slider_returns[label]
        return value

    def dataframe(self, data, *args, **kwargs):
        pass

    def set_page_config(self, *args, **kwargs):
        pass


class TestPhase8ETemporalInterface(unittest.TestCase):
    """Complete 23-point verification suite for Phase 8E Point-in-Time Temporal Interface."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = PlatformService()

    # ==========================================================================
    # 1. TEMPORAL CONTEXT COMPONENT TESTS
    # ==========================================================================

    def test_01_temporal_component_live(self):
        """Test render_temporal_context in LIVE mode renders LIVE banner without cutoff."""
        ctx = MockStreamlitContext()
        res = render_temporal_context(mode="LIVE", st_client=ctx)

        self.assertEqual(res["mode"], "LIVE")
        self.assertIsNone(res["as_of_date"])
        self.assertEqual(res["cutoff_label"], "None (Latest Available Data)")
        self.assertTrue(any("LIVE MODE" in call for call in ctx.caption_calls))

    def test_02_temporal_component_historical(self):
        """Test render_temporal_context in HISTORICAL mode renders AS OF: YYYY-MM-DD (23:59:59 cutoff)."""
        ctx = MockStreamlitContext()
        res = render_temporal_context(mode="HISTORICAL", as_of_date="2024-03-31", st_client=ctx)

        self.assertEqual(res["mode"], "HISTORICAL")
        self.assertEqual(res["as_of_date"], "2024-03-31")
        self.assertTrue(any("2024-03-31" in call and "23:59:59 cutoff" in call for call in ctx.info_calls))

    def test_03_temporal_component_missing_historical_date(self):
        """Test render_temporal_context in HISTORICAL mode with missing date produces a warning."""
        ctx = MockStreamlitContext()
        res = render_temporal_context(mode="HISTORICAL", as_of_date=None, st_client=ctx)

        self.assertEqual(res["mode"], "HISTORICAL")
        self.assertIsNone(res["as_of_date"])
        self.assertTrue(any("Point-in-Time Cutoff Date Missing" in call for call in ctx.warning_calls))

    def test_04_format_temporal_label(self):
        """Test format_temporal_label produces standardized labels across modes."""
        live_label = format_temporal_label("LIVE")
        self.assertEqual(live_label, "LIVE (Latest Available)")

        hist_label = format_temporal_label("HISTORICAL", "2024-03-31")
        self.assertEqual(hist_label, "HISTORICAL (Point-in-Time: 2024-03-31 23:59:59)")

        missing_label = format_temporal_label("HISTORICAL", None)
        self.assertEqual(missing_label, "HISTORICAL (Cutoff Unspecified)")

    # ==========================================================================
    # 2. COMPANY SELECTOR & DATE VALIDATION TESTS
    # ==========================================================================

    def test_05_company_selector_validate_historical_date_valid(self):
        """Test validate_historical_date accepts valid past YYYY-MM-DD dates."""
        valid, err = validate_historical_date("2024-03-31")
        self.assertTrue(valid)
        self.assertIsNone(err)

        valid2, err2 = validate_historical_date("2020-12-31")
        self.assertTrue(valid2)
        self.assertIsNone(err2)

    def test_06_company_selector_validate_historical_date_missing(self):
        """Test validate_historical_date rejects empty or None input."""
        valid1, err1 = validate_historical_date("")
        self.assertFalse(valid1)
        self.assertIn("mandatory", err1.lower())

        valid2, err2 = validate_historical_date(None)
        self.assertFalse(valid2)
        self.assertIn("mandatory", err2.lower())

    def test_07_company_selector_validate_historical_date_invalid_format(self):
        """Test validate_historical_date rejects malformed date strings."""
        invalid_inputs = ["03-31-2024", "2024/03/31", "not-a-date", "2024-02-30", "2024-13-01"]
        for inp in invalid_inputs:
            valid, err = validate_historical_date(inp)
            self.assertFalse(valid, f"Expected {inp} to be invalid")
            self.assertIn("YYYY-MM-DD", err)

    def test_08_company_selector_validate_historical_date_future(self):
        """Test validate_historical_date rejects dates after today (future dates)."""
        future_date = "2099-01-01"
        valid, err = validate_historical_date(future_date)
        self.assertFalse(valid)
        self.assertIn("future", err.lower())

    def test_09_company_selector_validate_historical_date_ancient(self):
        """Test validate_historical_date rejects dates before digital SEC EDGAR era (1990)."""
        ancient_date = "1985-06-15"
        valid, err = validate_historical_date(ancient_date)
        self.assertFalse(valid)
        self.assertIn("1990", err)

    # ==========================================================================
    # 3. SYNTHETIC ANTI-LEAKAGE PIT CUTOFF TEST
    # ==========================================================================

    def test_10_synthetic_anti_leakage_cutoff(self):
        """
        Verify authoritative acceptance_datetime filtering on synthetic records:
        Given cutoff 2024-01-01:
        Record A: acceptance_datetime = '2023-12-20 18:30:00+00' -> VISIBLE
        Record B: acceptance_datetime = '2024-02-01 09:15:00+00' -> EXCLUDED
        """
        con = duckdb.connect(":memory:")
        con.execute("""
            CREATE TABLE test_filings (
                accession_number VARCHAR PRIMARY KEY,
                ticker VARCHAR,
                acceptance_datetime TIMESTAMP WITH TIME ZONE
            );
            INSERT INTO test_filings VALUES
                ('0001-A', 'TEST', '2023-12-20 18:30:00+00'::TIMESTAMPTZ),
                ('0002-B', 'TEST', '2024-02-01 09:15:00+00'::TIMESTAMPTZ);
        """)

        cutoff_date = "2024-01-01"
        cutoff_dt = f"{cutoff_date} 23:59:59"

        rows = con.execute(
            "SELECT accession_number FROM test_filings WHERE acceptance_datetime <= ?::TIMESTAMPTZ",
            [cutoff_dt]
        ).fetchall()

        accessions = [r[0] for r in rows]
        self.assertIn("0001-A", accessions, "Record A (2023-12-20) must be included before 2024-01-01 cutoff.")
        self.assertNotIn("0002-B", accessions, "Record B (2024-02-01) must be strictly excluded by 2024-01-01 cutoff.")
        self.assertEqual(len(accessions), 1)

    # ==========================================================================
    # 4. PLATFORM SERVICE TEMPORAL ENFORCEMENT TESTS
    # ==========================================================================

    def test_11_platform_service_filing_intelligence_pit_cutoff(self):
        """Verify PlatformService.get_filing_intelligence excludes future disclosures under historical cutoff."""
        hist_intel = self.service.get_filing_intelligence(ticker="MSFT", as_of_date="2023-01-01", mode="HISTORICAL")

        self.assertEqual(hist_intel.mode, "HISTORICAL")
        self.assertEqual(hist_intel.as_of_date, "2023-01-01")

        # Every signal in historical intelligence must satisfy acceptance cutoff
        cutoff_ts = datetime.strptime("2023-01-01 23:59:59", "%Y-%m-%d %H:%M:%S")
        for s in hist_intel.signals:
            if s.acceptance_datetime:
                clean_acc = s.acceptance_datetime[:19].replace("T", " ")
                acc_dt = datetime.strptime(clean_acc, "%Y-%m-%d %H:%M:%S")
                self.assertLessEqual(acc_dt, cutoff_ts)

    def test_12_platform_service_filings_explorer_pit_cutoff(self):
        """Verify PlatformService.get_filing_explorer_data filters filings and counts excluded future filings."""
        hist_explorer = self.service.get_filing_explorer_data(ticker="MSFT", as_of_date="2023-01-01", mode="HISTORICAL")

        self.assertEqual(hist_explorer.mode, "HISTORICAL")
        self.assertEqual(hist_explorer.as_of_date, "2023-01-01")

        cutoff_ts = datetime.strptime("2023-01-01 23:59:59", "%Y-%m-%d %H:%M:%S")
        for f in hist_explorer.filings:
            if f.acceptance_datetime:
                clean_acc = f.acceptance_datetime[:19].replace("T", " ")
                acc_dt = datetime.strptime(clean_acc, "%Y-%m-%d %H:%M:%S")
                self.assertLessEqual(acc_dt, cutoff_ts)

        # There are filings submitted after 2023-01-01 in the database, so excluded count must be > 0
        self.assertGreater(hist_explorer.excluded_future_filings_count, 0)

    def test_13_platform_service_fundamentals_pit_cutoff(self):
        """Verify PlatformService.get_fundamentals filters statements and sets as_of_cutoff_datetime."""
        hist_fund = self.service.get_fundamentals(ticker="MSFT", as_of_date="2022-12-31", mode="HISTORICAL")

        self.assertEqual(hist_fund.mode, "HISTORICAL")
        self.assertEqual(hist_fund.as_of_date, "2022-12-31")
        self.assertEqual(hist_fund.as_of_cutoff_datetime, "2022-12-31 23:59:59")

        cutoff_ts = datetime.strptime("2022-12-31 23:59:59", "%Y-%m-%d %H:%M:%S")
        for ann in hist_fund.annual_statements:
            if ann.acceptance_datetime:
                clean_acc = ann.acceptance_datetime[:19].replace("T", " ")
                acc_dt = datetime.strptime(clean_acc, "%Y-%m-%d %H:%M:%S")
                self.assertLessEqual(acc_dt, cutoff_ts)

    def test_14_platform_service_missing_pit_date_error(self):
        """Verify MissingPITDateError is raised when HISTORICAL mode lacks as_of_date."""
        with self.assertRaises(MissingPITDateError):
            CompanyRequest(ticker="MSFT", mode="HISTORICAL", as_of_date=None)

        with self.assertRaises(MissingPITDateError):
            ValuationRequest(ticker="MSFT", mode="HISTORICAL", as_of_date=None)

        with self.assertRaises(MissingPITDateError):
            self.service.get_filing_intelligence("MSFT", mode="HISTORICAL", as_of_date=None)

        with self.assertRaises(MissingPITDateError):
            self.service.get_fundamentals("MSFT", mode="HISTORICAL", as_of_date=None)

        with self.assertRaises(MissingPITDateError):
            self.service.get_filing_explorer_data("MSFT", mode="HISTORICAL", as_of_date=None)

    def test_15_zero_lookahead_no_live_fallback(self):
        """Verify that when historical data is missing, zero look-ahead prevents fallback to live data."""
        ancient_req = CompanyRequest(ticker="MSFT", mode="HISTORICAL", as_of_date="1995-01-01")
        resp = self.service.analyze_company(ancient_req)

        # No valuation should exist as of 1995
        self.assertIsNone(resp.valuation)
        self.assertIn(resp.status, ("PARTIAL", "ERROR"))
        self.assertTrue(any("Valuation unavailable" in w for w in resp.warnings))

        # ValuationRequest directly should fail cleanly with ValuationUnavailableError
        val_req = ValuationRequest(ticker="MSFT", mode="HISTORICAL", as_of_date="1995-01-01")
        with self.assertRaises(ValuationUnavailableError):
            self.service.get_valuation(val_req)

    # ==========================================================================
    # 5. UI PAGE INTEGRATION TESTS
    # ==========================================================================

    def test_16_overview_page_historical_mode(self):
        """Test overview page displays temporal context and historical coverage notice."""
        ctx = MockStreamlitContext()
        req = CompanyRequest("MSFT", as_of_date="2023-12-31", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        data = render_overview_page(resp, mode="HISTORICAL", as_of_date="2023-12-31", st_client=ctx)

        self.assertEqual(data["mode"], "HISTORICAL")
        self.assertEqual(data["as_of_date"], "2023-12-31")
        self.assertTrue(any("HISTORICAL POINT-IN-TIME (Cutoff: 2023-12-31 23:59:59)" in call for call in ctx.write_calls))
        self.assertTrue(any("Some historical data may be unavailable" in call for call in ctx.warning_calls))

    def test_17_valuation_page_historical_mode(self):
        """Test valuation page renders temporal context and explicit cutoff."""
        ctx = MockStreamlitContext()
        req = CompanyRequest("MSFT", as_of_date="2024-03-31", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        data = render_valuation_page(resp, service=self.service, mode="HISTORICAL", as_of_date="2024-03-31", st_client=ctx)

        self.assertEqual(data["mode"], "HISTORICAL")
        self.assertEqual(data["as_of_date"], "2024-03-31")
        self.assertEqual(data["information_cutoff"], "2024-03-31 23:59:59")
        self.assertTrue(any("Information Cutoff" in call and "2024-03-31 23:59:59" in call for call in ctx.write_calls))

    def test_18_valuation_page_zero_fallback(self):
        """Test valuation page displays unavailable status and never shows live data when historical valuation missing."""
        ctx = MockStreamlitContext()
        dummy_profile = CompanyProfile(
            ticker="MSFT",
            company_name="Microsoft Corp",
            cik="0000789019",
            sector="Technology",
        )
        empty_resp = AnalysisResponse(
            request=CompanyRequest("MSFT", as_of_date="1995-01-01", mode="HISTORICAL"),
            profile=dummy_profile,
            valuation=None,
            filing_intelligence=None,
            research_disclosure=self.service.get_research_disclosure(),
            warnings=["Valuation unavailable as of 1995-01-01."],
            provenance={},
            status="PARTIAL",
        )

        data = render_valuation_page(empty_resp, service=self.service, mode="HISTORICAL", as_of_date="1995-01-01", st_client=ctx)

        self.assertEqual(data["status"], "UNAVAILABLE")
        self.assertIsNone(data["fair_value_per_share"])
        self.assertTrue(any("Zero look-ahead fallback enforced" in call for call in ctx.warning_calls))

    def test_19_fundamentals_page_historical_mode(self):
        """Test fundamentals page renders temporal context and information cutoff."""
        ctx = MockStreamlitContext()
        req = CompanyRequest("MSFT", as_of_date="2023-12-31", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        data = render_fundamentals_page(resp, mode="HISTORICAL", as_of_date="2023-12-31", st_client=ctx, service=self.service)

        self.assertEqual(data["mode"], "HISTORICAL")
        self.assertEqual(data["as_of_date"], "2023-12-31")
        self.assertEqual(data["information_cutoff"], "2023-12-31 23:59:59")
        self.assertTrue(any("Information Cutoff" in call and "2023-12-31 23:59:59" in call for call in ctx.markdown_calls))

    def test_20_filings_page_historical_mode(self):
        """Test filings page displays cutoff, reports excluded future filings count, and renders temporal context."""
        ctx = MockStreamlitContext()
        req = CompanyRequest("MSFT", as_of_date="2023-01-01", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        data = render_filings_page(resp, mode="HISTORICAL", as_of_date="2023-01-01", st_client=ctx, service=self.service)

        self.assertEqual(data["mode"], "HISTORICAL")
        self.assertEqual(data["as_of_date"], "2023-01-01")
        self.assertGreater(data["excluded_future_filings_count"], 0)
        self.assertTrue(any("Point-in-Time Lock" in call and "excluded" in call for call in ctx.info_calls))

    def test_21_evidence_page_historical_mode(self):
        """Test evidence page displays temporal context and eligibility notice."""
        ctx = MockStreamlitContext()
        req = CompanyRequest("MSFT", as_of_date="2023-12-31", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        data = render_evidence_page(resp, mode="HISTORICAL", as_of_date="2023-12-31", st_client=ctx, service=self.service)

        self.assertEqual(data["mode"], "HISTORICAL")
        self.assertEqual(data["as_of_date"], "2023-12-31")
        self.assertEqual(data["information_cutoff"], "2023-12-31 23:59:59")
        self.assertTrue(any("Point-in-Time Eligibility" in call for call in ctx.info_calls))

    def test_22_changes_page_historical_mode(self):
        """Test changes page displays temporal context and delta verification notice."""
        ctx = MockStreamlitContext()
        req = CompanyRequest("MSFT", as_of_date="2023-12-31", mode="HISTORICAL")
        resp = self.service.analyze_company(req)

        data = render_changes_page(resp, mode="HISTORICAL", as_of_date="2023-12-31", st_client=ctx, service=self.service)

        self.assertEqual(data["mode"], "HISTORICAL")
        self.assertEqual(data["as_of_date"], "2023-12-31")
        self.assertEqual(data["information_cutoff"], "2023-12-31 23:59:59")
        self.assertTrue(any("Point-in-Time Delta Verification" in call for call in ctx.info_calls))

    def test_23_main_run_app_historical_mode(self):
        """Test end-to-end run_app execution in HISTORICAL mode."""
        ctx = MockStreamlitContext()
        init_session_state(ctx)
        set_state("selected_ticker", "MSFT", ctx)
        set_state("mode", "HISTORICAL", ctx)
        set_state("as_of_date", "2024-03-31", ctx)
        set_state("active_page", "Overview", ctx)

        # Mock selector to return historical request
        ctx.radio_returns["Analysis Mode"] = "HISTORICAL"
        ctx.text_input_returns["Point-in-Time Cutoff Date (YYYY-MM-DD)"] = "2024-03-31"

        resp = run_app(service=self.service, st_client=ctx)

        self.assertIsNotNone(resp)
        self.assertEqual(resp.request.mode, "HISTORICAL")
        self.assertEqual(resp.request.as_of_date, "2024-03-31")


if __name__ == "__main__":
    unittest.main()
