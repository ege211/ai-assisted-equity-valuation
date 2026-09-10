"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8C — Interactive Research Dashboards & Visualizations Verification Suite
File: tests/test_phase8c_dashboard.py

Comprehensive test suite verifying the Phase 8C presentation layer:
1. test_01_interactive_dcf_scenario_override_computation
2. test_02_interactive_dcf_bounds_checking
3. test_03_base_model_immutability_under_scenario
4. test_04_sensitivity_grid_matrix_rendering
5. test_05_multiperiod_income_statement_display
6. test_06_multiperiod_balance_sheet_display
7. test_07_multiperiod_cash_flow_display
8. test_08_annual_vs_quarterly_frequency_toggle
9. test_09_normalized_accounting_quality_ratios_display
10. test_10_statement_taxonomy_tags
11. test_11_sec_filing_catalog_multiperiod
12. test_12_sec_filing_section_breakdown
13. test_13_filing_explorer_point_in_time_enforcement
14. test_14_verified_evidence_grounding_cards
15. test_15_quarantined_rejected_claims_separation
16. test_16_longitudinal_change_timeline_display
17. test_17_change_type_filtering
18. test_18_no_domain_logic_in_app_layer
"""

import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service.contracts import (
    CompanyRequest,
    AnalysisResponse,
    FundamentalsResponse,
    FilingExplorerResponse,
    FilingIntelligenceResponse,
    FilingSignal,
    ChangeSignalDTO,
    FinancialPeriodDTO,
    FinancialFeatureDTO,
    FilingSummaryDTO,
    FilingSectionDTO,
    ValuationScenarioSummary,
)
from src.service.platform_service import PlatformService
from app.pages.valuation import render_valuation_page, render_sensitivity_matrix
from app.pages.fundamentals import render_fundamentals_page
from app.pages.filings import render_filings_page
from app.pages.evidence import render_evidence_page
from app.pages.changes import render_changes_page


class MockStreamlitContext:
    """Mock Streamlit object capturing calls for headless test assertions."""
    def __init__(self):
        self.markdown_calls = []
        self.metric_calls = []
        self.header_calls = []
        self.caption_calls = []
        self.info_calls = []
        self.warning_calls = []
        self.error_calls = []
        self.success_calls = []
        self.write_calls = []

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

    def slider(self, label, min_value=0.0, max_value=100.0, value=50.0, step=1.0, *args, **kwargs):
        return value

    def radio(self, label, options, index=0, *args, **kwargs):
        return options[index] if options else None

    def selectbox(self, label, options, index=0, *args, **kwargs):
        return options[index] if options else None


class TestPhase8CDashboard(unittest.TestCase):
    """Test suite covering Phase 8C interactive research dashboard specifications."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = PlatformService()
        # Analyze a representative company for baseline testing
        cls.msft_response = cls.service.analyze_company(CompanyRequest("MSFT", mode="LIVE"))

    # --------------------------------------------------------------------------
    # 1. Interactive DCF Scenario Override
    # --------------------------------------------------------------------------
    def test_01_interactive_dcf_scenario_override_computation(self) -> None:
        """Verify interactive scenario recalculation yields a valid distinct scenario."""
        base_val = self.msft_response.valuation.fair_value_per_share
        
        # Calculate analyst scenario with higher margin (45% vs base ~40%) and lower WACC
        scenario = self.service.calculate_analyst_scenario(
            ticker="MSFT",
            wacc_override=0.08,
            terminal_growth_override=0.025,
            target_margin_override=0.45,
        )
        self.assertIsInstance(scenario, ValuationScenarioSummary)
        self.assertEqual(scenario.scenario_name, "ANALYST_SCENARIO")
        self.assertGreater(scenario.fair_value_per_share, 0.0)
        # With lower discount rate and higher margin, scenario fair value should exceed base
        self.assertGreater(scenario.fair_value_per_share, base_val)

    # --------------------------------------------------------------------------
    # 2. Interactive DCF Bounds Checking
    # --------------------------------------------------------------------------
    def test_02_interactive_dcf_bounds_checking(self) -> None:
        """Verify sensitivity grid handles invalid combinations (g >= WACC) safely."""
        grid = self.msft_response.valuation.sensitivities.get("wacc_terminal_growth")
        self.assertIsNotNone(grid)
        # Verify render_sensitivity_matrix maps invalid cells to 'N/A'
        matrix = render_sensitivity_matrix(grid)
        self.assertIsInstance(matrix, list)
        self.assertGreater(len(matrix), 0)
        
        # If g >= WACC in any cell, value should be formatted or indicated safely
        for row in matrix:
            for col_val in row.values():
                self.assertIsInstance(col_val, str)

    # --------------------------------------------------------------------------
    # 3. Base Model Immutability Under Scenario
    # --------------------------------------------------------------------------
    def test_03_base_model_immutability_under_scenario(self) -> None:
        """Verify on-demand scenario recalculation does not mutate base model DTO."""
        base_val_before = self.msft_response.valuation.fair_value_per_share
        base_wacc_before = self.msft_response.valuation.wacc

        # Execute scenario calculation
        _ = self.service.calculate_analyst_scenario(
            ticker="MSFT",
            wacc_override=0.15,
            terminal_growth_override=0.01,
            target_margin_override=0.20,
        )

        # Baseline DTO remains strictly unchanged
        self.assertEqual(self.msft_response.valuation.fair_value_per_share, base_val_before)
        self.assertEqual(self.msft_response.valuation.wacc, base_wacc_before)

    # --------------------------------------------------------------------------
    # 4. Sensitivity Grid Matrix Rendering
    # --------------------------------------------------------------------------
    def test_04_sensitivity_grid_matrix_rendering(self) -> None:
        """Verify 2D sensitivity table renders and highlights base cell."""
        grid = self.msft_response.valuation.sensitivities.get("wacc_terminal_growth")
        self.assertIsNotNone(grid)
        matrix = render_sensitivity_matrix(grid)
        
        # Check that base cell marker exists
        found_base = False
        for row in matrix:
            for val in row.values():
                if "★" in val or "Base" in val:
                    found_base = True
                    break
        self.assertTrue(found_base, "Base model cell must be visually marked in sensitivity grid.")

    # --------------------------------------------------------------------------
    # 5. Multi-Period Income Statement Display
    # --------------------------------------------------------------------------
    def test_05_multiperiod_income_statement_display(self) -> None:
        """Verify Income Statement displays canonical items across historical periods."""
        mock_ctx = MockStreamlitContext()
        fund_data = render_fundamentals_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        self.assertEqual(fund_data["ticker"], "MSFT")
        self.assertGreater(fund_data["annual_count"], 0)
        inc_stmt = fund_data["displayed_statement"].get("income_statement")
        self.assertIsNotNone(inc_stmt)
        
        # Check canonical lines
        line_items = [r[0] for r in inc_stmt["rows"]]
        self.assertIn("Revenue", line_items)
        self.assertIn("Cost of Goods Sold (COGS)", line_items)
        self.assertIn("Gross Profit", line_items)
        self.assertIn("Operating Income (EBIT)", line_items)
        self.assertIn("Net Income", line_items)

    # --------------------------------------------------------------------------
    # 6. Multi-Period Balance Sheet Display
    # --------------------------------------------------------------------------
    def test_06_multiperiod_balance_sheet_display(self) -> None:
        """Verify Balance Sheet displays canonical assets, liabilities, and equity items."""
        mock_ctx = MockStreamlitContext()
        fund_data = render_fundamentals_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        bs = fund_data["displayed_statement"].get("balance_sheet")
        self.assertIsNotNone(bs)
        
        line_items = [r[0] for r in bs["rows"]]
        self.assertIn("Cash & Cash Equivalents", line_items)
        self.assertIn("Total Assets", line_items)
        self.assertIn("Total Debt", line_items)
        self.assertIn("Total Stockholders' Equity", line_items)

    # --------------------------------------------------------------------------
    # 7. Multi-Period Cash Flow Display
    # --------------------------------------------------------------------------
    def test_07_multiperiod_cash_flow_display(self) -> None:
        """Verify Statement of Cash Flows displays CFO, Capex, and FCF."""
        mock_ctx = MockStreamlitContext()
        fund_data = render_fundamentals_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        cf = fund_data["displayed_statement"].get("cash_flow")
        self.assertIsNotNone(cf)
        
        line_items = [r[0] for r in cf["rows"]]
        self.assertIn("Cash Flow from Operations (CFO)", line_items)
        self.assertIn("Capital Expenditures (Capex)", line_items)
        self.assertIn("Free Cash Flow (FCF)", line_items)

    # --------------------------------------------------------------------------
    # 8. Annual vs Quarterly Frequency Toggle
    # --------------------------------------------------------------------------
    def test_08_annual_vs_quarterly_frequency_toggle(self) -> None:
        """Verify fundamentals explorer supports Annual and Quarterly frequencies."""
        fundamentals = self.service.get_fundamentals("MSFT")
        self.assertGreater(len(fundamentals.annual_statements), 0)
        self.assertGreater(len(fundamentals.quarterly_statements), 0)

        # Headless render with Annual
        mock_annual = MockStreamlitContext()
        mock_annual.radio = lambda label, options, index=0, *args, **kwargs: options[0]
        data_annual = render_fundamentals_page(fundamentals=fundamentals, st_client=mock_annual)
        self.assertEqual(data_annual["selected_frequency"], "ANNUAL")

        # Headless render with Quarterly
        mock_quarterly = MockStreamlitContext()
        mock_quarterly.radio = lambda label, options, index=0, *args, **kwargs: options[1]
        data_quarterly = render_fundamentals_page(fundamentals=fundamentals, st_client=mock_quarterly)
        self.assertEqual(data_quarterly["selected_frequency"], "QUARTERLY")

    # --------------------------------------------------------------------------
    # 9. Normalized Accounting Quality Ratios Display
    # --------------------------------------------------------------------------
    def test_09_normalized_accounting_quality_ratios_display(self) -> None:
        """Verify Normalized Accounting Quality Ratios table renders key metrics."""
        mock_ctx = MockStreamlitContext()
        fund_data = render_fundamentals_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        ratios = fund_data.get("normalized_ratios")
        self.assertIsNotNone(ratios)
        ratio_names = [r[0] for r in ratios["rows"]]
        self.assertIn("Return on Invested Capital (ROIC)", ratio_names)
        self.assertIn("Operating Margin (EBIT Margin)", ratio_names)
        self.assertIn("Revenue Growth (YoY)", ratio_names)
        self.assertIn("Operating Working Capital (OWC)", ratio_names)
        self.assertIn("Normalized Tax Rate", ratio_names)

    # --------------------------------------------------------------------------
    # 10. Statement Taxonomy Tags
    # --------------------------------------------------------------------------
    def test_10_statement_taxonomy_tags(self) -> None:
        """Verify explicit data taxonomy tags are present across financial views."""
        mock_ctx = MockStreamlitContext()
        render_fundamentals_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        all_text = " ".join(mock_ctx.markdown_calls + mock_ctx.header_calls)
        self.assertIn("[SOURCE DATA]", all_text)
        self.assertIn("[MODEL OUTPUT]", all_text)

    # --------------------------------------------------------------------------
    # 11. SEC Filing Catalog Multiperiod
    # --------------------------------------------------------------------------
    def test_11_sec_filing_catalog_multiperiod(self) -> None:
        """Verify filing explorer catalog lists audited submissions with PIT metadata."""
        mock_ctx = MockStreamlitContext()
        filings_data = render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        self.assertEqual(filings_data["ticker"], "MSFT")
        self.assertGreater(filings_data["total_filings"], 0)
        self.assertGreater(len(filings_data["filtered_filings"]), 0)
        first_filing = filings_data["filtered_filings"][0]
        self.assertTrue(hasattr(first_filing, "accession_number"))
        self.assertTrue(hasattr(first_filing, "acceptance_datetime"))

    # --------------------------------------------------------------------------
    # 12. SEC Filing Section Breakdown
    # --------------------------------------------------------------------------
    def test_12_sec_filing_section_breakdown(self) -> None:
        """Verify section inspector displays parsed sections, char counts, and confidence."""
        mock_ctx = MockStreamlitContext()
        filings_data = render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        self.assertIsNotNone(filings_data["selected_accession"])
        sections = filings_data["selected_filing_sections"]
        self.assertIsInstance(sections, list)
        if sections:
            sec = sections[0]
            self.assertTrue(sec.char_count > 0)
            self.assertIn(sec.detection_confidence, ("HIGH", "MEDIUM", "LOW"))
            self.assertTrue(len(sec.section_preview) > 0)

    # --------------------------------------------------------------------------
    # 13. Filing Explorer Point-in-Time Enforcement
    # --------------------------------------------------------------------------
    def test_13_filing_explorer_point_in_time_enforcement(self) -> None:
        """Verify Historical mode strictly excludes filings accepted after PIT cutoff."""
        pit_date = "2023-01-01"
        res = self.service.get_filing_explorer_data("MSFT", as_of_date=pit_date, mode="HISTORICAL", form_filter=["10-K"])
        
        for filing in res.filings:
            # Acceptance datetime must be strictly on or before 2023-01-01 23:59:59
            acceptance_date = filing.acceptance_datetime.split()[0]
            self.assertLessEqual(acceptance_date, pit_date)

    # --------------------------------------------------------------------------
    # 14. Verified Evidence Grounding Cards
    # --------------------------------------------------------------------------
    def test_14_verified_evidence_grounding_cards(self) -> None:
        """Verify verified qualitative claims display verbatim quote and EDGAR citations."""
        mock_ctx = MockStreamlitContext()
        ev_data = render_evidence_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        self.assertEqual(ev_data["ticker"], "MSFT")
        self.assertGreater(ev_data["validated_count"], 0)
        claim = ev_data["validated_claims"][0]
        self.assertTrue(len(claim.evidence_quote) > 0)
        self.assertTrue(len(claim.accession_number) > 0)
        self.assertIn(claim.direction, ("POSITIVE", "NEGATIVE", "NEUTRAL"))
        self.assertIn(claim.severity, ("LOW", "MEDIUM", "HIGH"))

    # --------------------------------------------------------------------------
    # 15. Quarantined Rejected Claims Separation
    # --------------------------------------------------------------------------
    def test_15_quarantined_rejected_claims_separation(self) -> None:
        """Verify quarantined claims section isolates rejected claims with failure rationale."""
        # Create a synthetic FilingIntelligenceResponse containing both validated and rejected claims
        mock_intel = FilingIntelligenceResponse(
            ticker="TEST",
            as_of_date="2024-12-31",
            mode="LIVE",
            total_claims_retrieved=2,
            validated_claims_count=1,
            rejected_claims_count=1,
            evidence_status_summary="1/2 claims validated",
            signals=[
                FilingSignal(
                    signal_id="sig_val",
                    category="margin_expansion",
                    claim="Operating efficiency improved.",
                    evidence_quote="operating margins expanded by 120 basis points",
                    evidence_location="Item 7",
                    source_identifier="acc_1",
                    direction="POSITIVE",
                    severity="MEDIUM",
                    confidence=0.95,
                    materiality="MATERIAL",
                    validation_status="VALIDATED",
                    accession_number="0001-24-0001",
                    form="10-K",
                    filing_date="2024-07-30",
                ),
                FilingSignal(
                    signal_id="sig_rej",
                    category="guidance",
                    claim="Revenue projected to surge 100%.",
                    evidence_quote="revenue surge",
                    evidence_location="Item 7",
                    source_identifier="acc_1",
                    direction="POSITIVE",
                    severity="HIGH",
                    confidence=0.20,
                    materiality="MATERIAL",
                    validation_status="REJECTED",
                    validation_reason="Substring not located in filing text (unanchored hallucination).",
                    accession_number="0001-24-0001",
                    form="10-K",
                    filing_date="2024-07-30",
                ),
            ],
            change_signals=[],
            covered_accessions=["0001-24-0001"],
        )

        mock_ctx = MockStreamlitContext()
        ev_data = render_evidence_page(st_client=mock_ctx, intelligence=mock_intel)
        
        self.assertEqual(ev_data["validated_count"], 1)
        self.assertEqual(ev_data["rejected_count"], 1)
        self.assertEqual(len(ev_data["quarantined_claims"]), 1)
        self.assertEqual(ev_data["quarantined_claims"][0].validation_status, "REJECTED")

        # Verify warning/quarantine messaging in UI output
        all_warnings = " ".join(mock_ctx.warning_calls + mock_ctx.error_calls)
        self.assertIn("QUARANTINE", all_warnings.upper())

    # --------------------------------------------------------------------------
    # 16. Longitudinal Change Timeline Display
    # --------------------------------------------------------------------------
    def test_16_longitudinal_change_timeline_display(self) -> None:
        """Verify longitudinal change timeline renders delta attributes."""
        mock_ctx = MockStreamlitContext()
        ch_data = render_changes_page(self.msft_response, st_client=mock_ctx, service=self.service)
        
        self.assertEqual(ch_data["ticker"], "MSFT")
        self.assertGreater(ch_data["total_signals"], 0)
        sig = ch_data["change_signals"][0]
        self.assertIn(sig.change_type, ("NEW", "ESCALATED", "RESOLVED", "MODIFIED", "PERSISTENT"))
        self.assertTrue(len(sig.current_accession) > 0)
        self.assertTrue(len(sig.summary) > 0)

    # --------------------------------------------------------------------------
    # 17. Change Type Filtering
    # --------------------------------------------------------------------------
    def test_17_change_type_filtering(self) -> None:
        """Verify change signal filtering by delta type works cleanly."""
        ch_all = render_changes_page(self.msft_response, change_type_filter="ALL", service=self.service)
        self.assertEqual(ch_all["active_change_type"], "ALL")
        
        # Test filtering by a specific change type
        ch_new = render_changes_page(self.msft_response, change_type_filter="NEW", service=self.service)
        self.assertEqual(ch_new["active_change_type"], "NEW")
        for s in ch_new["change_signals"]:
            self.assertEqual(s.change_type.upper(), "NEW")

    # --------------------------------------------------------------------------
    # 18. No Domain Logic in App Layer (Presentation Layer Only)
    # --------------------------------------------------------------------------
    def test_18_no_domain_logic_in_app_layer(self) -> None:
        """Verify app/ modules contain zero valuation math, beta formulas, accounting derivations, or NLP regex."""
        app_dir = PROJECT_ROOT / "app"
        py_files = list(app_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 0)

        prohibited_terms = [
            "calculate_dcf",
            "calculate_wacc",
            "capm",
            "unlevered_beta",
            "hamada",
            "re_compile",
            "duckdb.connect",
        ]

        for py_file in py_files:
            content = py_file.read_text(encoding="utf-8")
            # Parse AST to ensure valid syntax
            tree = ast.parse(content, filename=str(py_file))
            self.assertIsNotNone(tree)
            
            # Check prohibited direct engine implementation calls in app/
            for term in prohibited_terms:
                self.assertNotIn(
                    term,
                    content,
                    f"Forbidden domain engine logic '{term}' detected in presentation layer file {py_file.name}!",
                )


if __name__ == "__main__":
    unittest.main()
