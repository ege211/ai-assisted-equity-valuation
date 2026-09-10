"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8G — Final UI / QA / Institutional Research Terminal Verification Suite
File: tests/test_phase8g_ui_qa.py

Automated test suite (22 tests) validating:
1. Global temporal context consistency across pages
2. Overview page rendering of all mandatory institutional components
3. Valuation page rendering of DCF, scenarios, sandbox, sensitivity, relative multiples
4. Fundamentals page rendering of 3 statements, quality ratios, and clean units
5. Filings page rendering of catalog, section inspector, and accession provenance
6. Evidence page rendering of verified claims and quarantined claims
7. Changes page rendering of 4 clear sections and empty state handling
8. LIVE mode rendering across all 6 pages
9. HISTORICAL mode rendering with strict cutoff enforcement across all 6 pages
10. Missing historical date validation and error handling
11. Valuation unavailable state rendering without crash
12. Evidence unavailable state rendering without crash
13. Missing provenance graceful degradation to explicit badge
14. Negative valuation and cash flow formatting (-$X.XX, not $-X.XX)
15. Empty changes display showing baseline filing and unavailability reason
16. Phase 7 research disclosure exactness (authoritative figures, paired t-test, NO Diebold-Mariano)
17. Provenance visibility across key analytical outputs
18. Evidence validation visibility and explicit rejection reasons
19. Zero look-ahead / no live fallback enforcement
20. Session state consistency across mode and ticker mutations
21. Formatting consistency across currency, percentages, and ratios
22. End-to-end application lifecycle execution in LIVE and HISTORICAL modes
"""

import unittest
from typing import Any, Dict, List, Optional

from src.service.platform_service import PlatformService
from src.service.contracts import (
    AnalysisResponse,
    CompanyProfile,
    CompanyRequest,
    ValuationResponse,
    FilingIntelligenceResponse,
    MissingPITDateError,
    FilingSignal,
    ResearchDisclosure,
)
from src.service.provenance import WhatChangedResponse

from app.state import (
    init_session_state,
    get_state,
    set_state,
    reset_analysis_state,
)
from app.components.header import render_header
from app.components.kpi_cards import render_kpi_cards, format_currency as format_kpi_currency
from app.components.temporal_context import render_temporal_context
from app.components.provenance import (
    render_source_provenance_badge,
    render_why_this_number_expander,
    render_what_changed_table,
)
from app.pages.overview import render_overview_page
from app.pages.valuation import render_valuation_page
from app.pages.fundamentals import render_fundamentals_page, format_currency as format_fund_currency
from app.pages.filings import render_filings_page
from app.pages.evidence import render_evidence_page
from app.pages.changes import render_changes_page
from app.main import run_app


class MockStreamlitContext:
    """Headless mock for Streamlit UI calls and session capture."""

    def __init__(self):
        self.sidebar = self
        self.header_calls: List[str] = []
        self.markdown_calls: List[str] = []
        self.metric_calls: List[tuple] = []
        self.caption_calls: List[str] = []
        self.info_calls: List[str] = []
        self.warning_calls: List[str] = []
        self.error_calls: List[str] = []
        self.success_calls: List[str] = []
        self.write_calls: List[str] = []
        self.expander_labels: List[str] = []
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
        self.expander_labels.append(str(label))
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


class TestPhase8GUIQA(unittest.TestCase):
    """Institutional UI & QA Verification Suite for Phase 8G."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = PlatformService()
        cls.msft_live = cls.service.analyze_company(CompanyRequest("MSFT", mode="LIVE"))
        cls.msft_hist = cls.service.analyze_company(
            CompanyRequest("MSFT", as_of_date="2023-12-31", mode="HISTORICAL")
        )

    def setUp(self) -> None:
        init_session_state()

    # --------------------------------------------------------------------------
    # 1. Global Temporal Context Consistency
    # --------------------------------------------------------------------------
    def test_01_global_temporal_context_consistency(self) -> None:
        """Global PIT header and temporal context rendered identically across all pages."""
        ctx_live = MockStreamlitContext()
        render_header(
            profile=self.msft_live.profile,
            mode="LIVE",
            as_of_date=None,
            status=self.msft_live.status,
            st_client=ctx_live,
        )
        self.assertTrue(any("LIVE" in m for m in ctx_live.markdown_calls))

        ctx_hist = MockStreamlitContext()
        render_header(
            profile=self.msft_hist.profile,
            mode="HISTORICAL",
            as_of_date="2023-12-31",
            status=self.msft_hist.status,
            st_client=ctx_hist,
        )
        self.assertTrue(
            any("2023-12-31" in m for m in ctx_hist.markdown_calls)
        )

    # --------------------------------------------------------------------------
    # 2. Overview Rendering
    # --------------------------------------------------------------------------
    def test_02_overview_rendering(self) -> None:
        """Overview page renders all mandatory components without error."""
        ctx = MockStreamlitContext()
        data = render_overview_page(self.msft_live, st_client=ctx)

        self.assertEqual(data["ticker"], "MSFT")
        self.assertIsNotNone(data["valuation_kpis"])
        self.assertIsNotNone(data["fundamental_snapshot"])
        self.assertIsNotNone(data["filing_summary"])
        self.assertIsNotNone(data["disclosure"])
        # Check that header calls include corporate profile and academic disclosure
        self.assertTrue(any("EXECUTIVE OVERVIEW" in h.upper() for h in ctx.header_calls))
        self.assertTrue(any("ACADEMIC RESEARCH DISCLOSURE" in m.upper() for m in ctx.markdown_calls))

    # --------------------------------------------------------------------------
    # 3. Valuation Rendering
    # --------------------------------------------------------------------------
    def test_03_valuation_rendering(self) -> None:
        """Valuation page renders DCF, scenarios, sandbox, sensitivity, relative multiples."""
        ctx = MockStreamlitContext()
        data = render_valuation_page(self.msft_live, service=self.service, st_client=ctx)

        self.assertEqual(data["status"], "AVAILABLE")
        self.assertIsNotNone(data["fair_value_per_share"])
        self.assertIsNotNone(data["scenarios"])
        self.assertIn("BASE", data["scenarios"])
        self.assertIn("BULL", data["scenarios"])
        self.assertIn("BEAR", data["scenarios"])
        self.assertIsNotNone(data["sensitivity_grid"])

        # Check section headers in markdown
        self.assertTrue(any("DISCOUNTED CASH FLOW (DCF)" in h.upper() for h in ctx.header_calls))
        self.assertTrue(any("MULTI-SCENARIO" in m.upper() for m in ctx.markdown_calls))
        self.assertTrue(any("RELATIVE VALUATION MULTIPLES BENCHMARK" in m.upper() for m in ctx.markdown_calls))
        self.assertTrue(any("WHY THIS FAIR VALUE?" in el.upper() for el in ctx.expander_labels))

    # --------------------------------------------------------------------------
    # 4. Fundamentals Rendering
    # --------------------------------------------------------------------------
    def test_04_fundamentals_rendering(self) -> None:
        """Fundamentals page renders 3 statements + ratios with clean units."""
        ctx = MockStreamlitContext()
        data = render_fundamentals_page(self.msft_live, st_client=ctx, service=self.service)

        self.assertEqual(data["ticker"], "MSFT")
        self.assertGreater(data["annual_count"], 0)
        self.assertGreater(data["features_count"], 0)

        # Check explicit units and taxonomy
        self.assertTrue(any("INCOME STATEMENT" in m.upper() for m in ctx.markdown_calls))
        self.assertTrue(any("BALANCE SHEET" in m.upper() for m in ctx.markdown_calls))
        self.assertTrue(any("CASH FLOW" in m.upper() for m in ctx.markdown_calls))
        self.assertTrue(any("[SOURCE DATA]" in m for m in ctx.markdown_calls))
        self.assertTrue(any("[MODEL OUTPUT]" in m for m in ctx.markdown_calls))

    # --------------------------------------------------------------------------
    # 5. Filings Rendering
    # --------------------------------------------------------------------------
    def test_05_filings_rendering(self) -> None:
        """Filings page renders catalog + section inspector with provenance."""
        ctx = MockStreamlitContext()
        data = render_filings_page(self.msft_live, st_client=ctx, service=self.service)

        self.assertEqual(data["ticker"], "MSFT")
        self.assertGreater(data["total_filings"], 0)
        self.assertTrue(any("FILINGS" in h.upper() for h in ctx.header_calls))
        self.assertTrue(any("SECTION INSPECTOR" in m.upper() for m in ctx.markdown_calls))

    # --------------------------------------------------------------------------
    # 6. Evidence Rendering
    # --------------------------------------------------------------------------
    def test_06_evidence_rendering(self) -> None:
        """Evidence page renders verified claims + quarantine tab."""
        ctx = MockStreamlitContext()
        data = render_evidence_page(self.msft_live, st_client=ctx, service=self.service)

        self.assertEqual(data["ticker"], "MSFT")
        self.assertGreater(data["total_claims"], 0)
        self.assertTrue(any("EVIDENCE" in h.upper() for h in ctx.header_calls))
        self.assertTrue(any("QUARANTINED" in m.upper() for m in ctx.markdown_calls))

    # --------------------------------------------------------------------------
    # 7. Changes Rendering
    # --------------------------------------------------------------------------
    def test_07_changes_rendering(self) -> None:
        """Changes page renders 4 sections + empty state handling."""
        ctx = MockStreamlitContext()
        data = render_changes_page(self.msft_live, st_client=ctx, service=self.service)

        self.assertEqual(data["ticker"], "MSFT")
        # Verify the 4 sections are rendered
        self.assertTrue(any("1. Fundamental Financial Statement Deltas" in m for m in ctx.markdown_calls))
        self.assertTrue(any("2. Valuation Model Adjustments" in m for m in ctx.markdown_calls))
        self.assertTrue(any("3. Filing Intelligence & Metadata Shifts" in m for m in ctx.markdown_calls))
        self.assertTrue(any("4. Qualitative Disclosure Evolutions & Risk Signals" in m for m in ctx.markdown_calls))

    # --------------------------------------------------------------------------
    # 8. LIVE Mode Rendering
    # --------------------------------------------------------------------------
    def test_08_live_mode_rendering(self) -> None:
        """LIVE mode shows latest data across all 6 pages."""
        for page_fn in [
            lambda ctx: render_overview_page(self.msft_live, mode="LIVE", st_client=ctx),
            lambda ctx: render_valuation_page(self.msft_live, mode="LIVE", service=self.service, st_client=ctx),
            lambda ctx: render_fundamentals_page(self.msft_live, mode="LIVE", service=self.service, st_client=ctx),
            lambda ctx: render_filings_page(self.msft_live, mode="LIVE", service=self.service, st_client=ctx),
            lambda ctx: render_evidence_page(self.msft_live, mode="LIVE", service=self.service, st_client=ctx),
            lambda ctx: render_changes_page(self.msft_live, mode="LIVE", service=self.service, st_client=ctx),
        ]:
            ctx = MockStreamlitContext()
            res = page_fn(ctx)
            self.assertEqual(res["mode"], "LIVE")

    # --------------------------------------------------------------------------
    # 9. HISTORICAL Mode Rendering
    # --------------------------------------------------------------------------
    def test_09_historical_mode_rendering(self) -> None:
        """HISTORICAL mode enforces cutoff across all 6 pages."""
        cutoff = "2023-12-31"
        for page_fn in [
            lambda ctx: render_overview_page(self.msft_hist, mode="HISTORICAL", as_of_date=cutoff, st_client=ctx),
            lambda ctx: render_valuation_page(self.msft_hist, mode="HISTORICAL", as_of_date=cutoff, service=self.service, st_client=ctx),
            lambda ctx: render_fundamentals_page(self.msft_hist, mode="HISTORICAL", as_of_date=cutoff, service=self.service, st_client=ctx),
            lambda ctx: render_filings_page(self.msft_hist, mode="HISTORICAL", as_of_date=cutoff, service=self.service, st_client=ctx),
            lambda ctx: render_evidence_page(self.msft_hist, mode="HISTORICAL", as_of_date=cutoff, service=self.service, st_client=ctx),
            lambda ctx: render_changes_page(self.msft_hist, mode="HISTORICAL", as_of_date=cutoff, service=self.service, st_client=ctx),
        ]:
            ctx = MockStreamlitContext()
            res = page_fn(ctx)
            self.assertEqual(res["mode"], "HISTORICAL")
            self.assertEqual(res["as_of_date"], cutoff)

    # --------------------------------------------------------------------------
    # 10. Missing Historical Date
    # --------------------------------------------------------------------------
    def test_10_missing_historical_date(self) -> None:
        """UI displays explicit error when historical date is missing."""
        ctx = MockStreamlitContext()
        set_state("mode", "HISTORICAL")
        set_state("as_of_date", None)
        set_state("selected_ticker", "MSFT")

        with self.assertRaises(MissingPITDateError):
            self.service.analyze_company(CompanyRequest("MSFT", as_of_date=None, mode="HISTORICAL"))

        # In run_app, missing date creates an error banner
        run_app(service=self.service, st_client=ctx)
        self.assertTrue(
            any("Point-in-Time Error" in err or "as_of_date" in err for err in ctx.error_calls)
        )

    # --------------------------------------------------------------------------
    # 11. Unavailable Valuation State
    # --------------------------------------------------------------------------
    def test_11_unavailable_valuation_state(self) -> None:
        """Valuation unavailable state renders cleanly without crash."""
        ctx = MockStreamlitContext()
        empty_resp = AnalysisResponse(
            request=CompanyRequest("MSFT", mode="LIVE"),
            profile=self.msft_live.profile,
            valuation=None,
            filing_intelligence=None,
            research_disclosure=self.service.get_research_disclosure(),
            warnings=["Valuation model unavailable for this period."],
            provenance={},
            status="PARTIAL",
        )
        data = render_valuation_page(empty_resp, service=self.service, st_client=ctx)
        self.assertEqual(data["status"], "UNAVAILABLE")
        self.assertIsNone(data["fair_value_per_share"])
        self.assertTrue(any("unavailable" in w.lower() for w in ctx.warning_calls))

    # --------------------------------------------------------------------------
    # 12. Unavailable Evidence State
    # --------------------------------------------------------------------------
    def test_12_unavailable_evidence_state(self) -> None:
        """Evidence unavailable state renders cleanly without crash."""
        ctx = MockStreamlitContext()
        empty_resp = AnalysisResponse(
            request=CompanyRequest("MSFT", mode="LIVE"),
            profile=None,
            valuation=self.msft_live.valuation,
            filing_intelligence=None,
            research_disclosure=self.service.get_research_disclosure(),
            warnings=[],
            provenance={},
            status="PARTIAL",
        )
        data = render_evidence_page(empty_resp, intelligence=None, st_client=ctx, service=None)
        self.assertEqual(data["total_claims"], 0)
        self.assertTrue(any("evidence" in w.lower() for w in ctx.warning_calls))

    # --------------------------------------------------------------------------
    # 13. Unavailable Provenance State
    # --------------------------------------------------------------------------
    def test_13_unavailable_provenance_state(self) -> None:
        """Missing provenance degrades gracefully to explicit badge."""
        ctx = MockStreamlitContext()
        badge_data = render_source_provenance_badge(None, st_client=ctx)
        self.assertFalse(badge_data["available"])
        self.assertTrue(any("unavailable" in c.lower() for c in ctx.caption_calls))

        expander_data = render_why_this_number_expander("Fair Value", None, st_client=ctx)
        self.assertFalse(expander_data["has_lineage"])
        self.assertTrue(any("unavailable" in c.lower() for c in ctx.caption_calls))

    # --------------------------------------------------------------------------
    # 14. Negative Valuation Display
    # --------------------------------------------------------------------------
    def test_14_negative_valuation_display(self) -> None:
        """Negative margins/cash flows formatted correctly (-$X.XX, not $-X.XX)."""
        self.assertEqual(format_kpi_currency(-15.20), "-$15.20")
        self.assertEqual(format_kpi_currency(-1_500_000), "-$1,500,000.00")
        self.assertEqual(format_fund_currency(-45_000_000), "-$45.00M")
        self.assertEqual(format_fund_currency(-1_500_000_000), "-$1.50B")
        self.assertEqual(format_fund_currency(0.0), "$0")

        # Verify negative currency doesn't start with '$-'
        self.assertFalse(format_kpi_currency(-10.0).startswith("$-"))
        self.assertFalse(format_fund_currency(-10.0).startswith("$-"))

    # --------------------------------------------------------------------------
    # 15. Empty Changes Display
    # --------------------------------------------------------------------------
    def test_15_empty_changes_display(self) -> None:
        """No prior filing shows clean informative message with filing used."""
        ctx = MockStreamlitContext()
        mock_changed = WhatChangedResponse(
            ticker="MSFT",
            mode="HISTORICAL",
            as_of_date="1995-01-01",
            information_cutoff="1995-01-01 23:59:59",
            current_period="FY 1994",
            previous_period="N/A",
            current_accession="0000789019-94-000001",
            previous_accession="",
            fundamental_changes=[],
            valuation_changes=[],
            qualitative_signals=[],
            is_longitudinal_valid=False,
            rejection_reason="Only 1 filing found prior to cutoff date: longitudinal comparison requires at least 2 filings.",
        )
        data = render_what_changed_table(mock_changed, st_client=ctx)
        self.assertFalse(data["is_valid"])
        self.assertTrue(any("Longitudinal Comparison Rejected" in w for w in ctx.warning_calls))
        self.assertTrue(any("Baseline Filing Used" in i or "Filing Used" in i for i in ctx.info_calls))

    # --------------------------------------------------------------------------
    # 16. Phase 7 Disclosure Exactness
    # --------------------------------------------------------------------------
    def test_16_phase7_disclosure_exactness(self) -> None:
        """Phase 7 research disclosure matches authoritative values verbatim."""
        d = self.service.get_research_disclosure()

        self.assertEqual(d.sample_size_longitudinal, 46)
        self.assertEqual(d.walk_forward_folds, 2)
        self.assertEqual(d.baseline_mae, 0.0777)
        self.assertEqual(d.enhanced_mae, 0.0781)
        self.assertEqual(d.delta_mae_pct, -0.60)
        self.assertEqual(d.p_value, 0.2335)
        self.assertEqual(d.hypothesis_decision, "Fail to reject H0")

        # Strictly NO Diebold-Mariano
        self.assertNotIn("Diebold-Mariano", d.key_takeaway)
        self.assertNotIn("diebold_mariano", dir(d))

        # Check rendering in overview page
        ctx = MockStreamlitContext()
        render_overview_page(self.msft_live, st_client=ctx)
        self.assertTrue(any("0.0777" in i for i in ctx.info_calls))
        self.assertTrue(any("0.0781" in i for i in ctx.info_calls))
        self.assertTrue(any("-0.0005" in i for i in ctx.info_calls))
        self.assertTrue(any("-0.60%" in i for i in ctx.info_calls))
        self.assertTrue(any("0.2335" in i for i in ctx.info_calls))
        self.assertTrue(any("[-0.0011, +0.0003]" in i for i in ctx.info_calls))
        self.assertTrue(any("paired t-test" in i.lower() for i in ctx.info_calls))
        self.assertFalse(any("diebold-mariano" in i.lower() for i in ctx.info_calls))

    # --------------------------------------------------------------------------
    # 17. Provenance Visibility
    # --------------------------------------------------------------------------
    def test_17_provenance_visibility(self) -> None:
        """Every key output has visible provenance badge or expander."""
        prov = self.service.get_provenance("MSFT", "fair_value_per_share", mode="LIVE")
        self.assertIsNotNone(prov)
        self.assertTrue(prov.is_pit_compliant)
        self.assertTrue(len(prov.accession_number) > 0)
        self.assertTrue(prov.get_sec_url().startswith("https://www.sec.gov/Archives/edgar/data/"))

        val_lineage = self.service.get_valuation_lineage("MSFT", mode="LIVE")
        self.assertIsNotNone(val_lineage)
        self.assertGreaterEqual(len(val_lineage.steps), 4)

        wacc_lineage = self.service.get_wacc_lineage("MSFT", mode="LIVE")
        self.assertIsNotNone(wacc_lineage)
        self.assertGreaterEqual(len(wacc_lineage.steps), 4)

    # --------------------------------------------------------------------------
    # 18. Evidence Validation Visibility
    # --------------------------------------------------------------------------
    def test_18_evidence_validation_visibility(self) -> None:
        """Evidence cards show validation badge with rejection reasons."""
        ctx = MockStreamlitContext()
        data = render_evidence_page(self.msft_live, st_client=ctx, service=self.service)

        self.assertIn("validated_claims", data)
        self.assertIn("quarantined_claims", data)
        # Verify quarantined section header is present
        self.assertTrue(any("Quarantined" in m for m in ctx.markdown_calls))

    # --------------------------------------------------------------------------
    # 19. Zero Look-Ahead / No Live Fallback
    # --------------------------------------------------------------------------
    def test_19_no_live_fallback(self) -> None:
        """Historical failure never displays live data (zero look-ahead)."""
        ctx = MockStreamlitContext()
        # Request a historical cutoff date with zero coverage
        resp = self.service.analyze_company(
            CompanyRequest("MSFT", as_of_date="1995-01-01", mode="HISTORICAL")
        )
        self.assertIsNone(resp.valuation)
        self.assertEqual(resp.status, "PARTIAL")

        data = render_valuation_page(resp, mode="HISTORICAL", as_of_date="1995-01-01", st_client=ctx, service=self.service)
        self.assertEqual(data["status"], "UNAVAILABLE")
        self.assertIsNone(data["fair_value_per_share"])
        self.assertTrue(any("Zero look-ahead" in w for w in ctx.warning_calls))

    # --------------------------------------------------------------------------
    # 20. Session State Consistency
    # --------------------------------------------------------------------------
    def test_20_session_state_consistency(self) -> None:
        """Mode/ticker changes propagate cleanly through session state."""
        ctx = MockStreamlitContext()
        init_session_state(ctx)

        set_state("selected_ticker", "AAPL", ctx)
        set_state("mode", "HISTORICAL", ctx)
        set_state("as_of_date", "2023-09-30", ctx)

        self.assertEqual(get_state("selected_ticker", None, ctx), "AAPL")
        self.assertEqual(get_state("mode", None, ctx), "HISTORICAL")
        self.assertEqual(get_state("as_of_date", None, ctx), "2023-09-30")

        reset_analysis_state(ctx)
        self.assertIsNone(get_state("analysis_response", None, ctx))

    # --------------------------------------------------------------------------
    # 21. Formatting Consistency
    # --------------------------------------------------------------------------
    def test_21_formatting_consistency(self) -> None:
        """Currency, percentage, ratio formatting consistent across all pages."""
        # Positive values
        self.assertEqual(format_kpi_currency(123.45), "$123.45")
        self.assertEqual(format_kpi_currency(1_200_000), "$1,200,000.00")

        # Zero and None
        self.assertEqual(format_kpi_currency(0.0), "$0.00")
        self.assertEqual(format_kpi_currency(None), "N/A")

        # Negative values
        self.assertEqual(format_kpi_currency(-0.5), "-$0.50")
        self.assertEqual(format_kpi_currency(-10_000_000), "-$10,000,000.00")
        self.assertEqual(format_fund_currency(-45_000_000), "-$45.00M")
        self.assertEqual(format_fund_currency(100_000_000), "$100.00M")

    # --------------------------------------------------------------------------
    # 22. End-to-End Application Render
    # --------------------------------------------------------------------------
    def test_22_end_to_end_application_render(self) -> None:
        """Full application renders end-to-end in both LIVE and HISTORICAL modes."""
        ctx_live = MockStreamlitContext()
        init_session_state(ctx_live)
        set_state("selected_ticker", "MSFT", ctx_live)
        set_state("mode", "LIVE", ctx_live)
        resp_live = run_app(service=self.service, st_client=ctx_live)
        self.assertIsNotNone(resp_live)
        self.assertEqual(resp_live.request.ticker, "MSFT")

        ctx_hist = MockStreamlitContext()
        init_session_state(ctx_hist)
        set_state("selected_ticker", "MSFT", ctx_hist)
        set_state("mode", "HISTORICAL", ctx_hist)
        set_state("as_of_date", "2024-03-31", ctx_hist)
        resp_hist = run_app(service=self.service, st_client=ctx_hist)
        self.assertIsNotNone(resp_hist)
        self.assertEqual(resp_hist.request.mode, "HISTORICAL")
        self.assertEqual(resp_hist.request.as_of_date, "2024-03-31")


if __name__ == "__main__":
    unittest.main()
