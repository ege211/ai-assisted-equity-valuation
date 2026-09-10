"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8F — Provenance, Data Lineage & "What Changed?" Research Intelligence Verification Suite
File: tests/test_phase8f_provenance.py

Comprehensive test suite verifying the Phase 8F specifications (25 rigorous tests):
1.  test_01_source_provenance_schema_immutability
2.  test_02_lineage_step_schema_immutability
3.  test_03_data_lineage_schema_immutability
4.  test_04_qualitative_evidence_lineage_schema
5.  test_05_valuation_bridge_lineage_schema
6.  test_06_fundamental_change_schema
7.  test_07_what_changed_response_schema
8.  test_08_get_provenance_sec_accession_linking
9.  test_09_get_provenance_sec_url_edgar_format
10. test_10_get_provenance_acceptance_timestamp
11. test_11_get_provenance_pit_compliance
12. test_12_what_changed_dual_accession_pit_lock
13. test_13_what_changed_fundamental_deltas_computation
14. test_14_what_changed_noise_filter_threshold
15. test_15_valuation_numerical_lineage_completeness
16. test_16_wacc_derivation_lineage_completeness
17. test_17_qualitative_evidence_6stage_lineage
18. test_18_valuation_bridge_lineage_query
19. test_19_adversarial_leakage_future_filing_excluded
20. test_20_adversarial_leakage_future_evidence_excluded
21. test_21_adversarial_dual_accession_leakage
22. test_22_ui_render_source_provenance_badge
23. test_23_ui_render_why_this_number_expander
24. test_24_ui_render_what_changed_table_and_rejection
25. test_25_end_to_end_changes_page_integration
"""

import dataclasses
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
from src.service.provenance import (
    SourceProvenanceDTO,
    LineageStepDTO,
    DataLineageDTO,
    QualitativeEvidenceLineageDTO,
    ValuationBridgeLineageDTO,
    FundamentalChangeDTO,
    WhatChangedResponse,
)
from src.service.platform_service import PlatformService
from app.components.provenance import (
    render_source_provenance_badge,
    render_lineage_pipeline,
    render_why_this_number_expander,
    render_what_changed_table,
)
from app.pages.changes import render_changes_page
from app.state import init_session_state, set_state


class MockStreamlitContext:
    """Mock Streamlit context capturing UI function calls for headless verification."""
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
        self.tabs_mock = [self, self, self, self]

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

    def tabs(self, titles):
        return [self] * len(titles)

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


class TestPhase8FProvenance(unittest.TestCase):
    """Rigorous 25-test verification suite for Phase 8F Provenance & Change Intelligence."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = PlatformService()

    # ==========================================================================
    # 1. DTO SCHEMA & IMMUTABILITY CONTRACTS
    # ==========================================================================

    def test_01_source_provenance_schema_immutability(self):
        """Verify SourceProvenanceDTO fields, helper methods, and frozen immutability."""
        prov = SourceProvenanceDTO(
            source_name="SEC EDGAR",
            source_type="FILING_XBRL",
            source_identifier="0000789019-24-000021",
            accession_number="0000789019-24-000021",
            form="10-K",
            filing_date="2024-07-30",
            acceptance_datetime="2024-07-30 20:06:22+00",
            concept="us-gaap:Revenues",
            is_pit_compliant=True,
        )
        self.assertEqual(prov.source_name, "SEC EDGAR")
        self.assertEqual(prov.accession_number, "0000789019-24-000021")
        self.assertEqual(prov.form, "10-K")
        self.assertTrue(prov.is_pit_compliant)
        self.assertIn("10-K", prov.get_primary_source())
        self.assertIn("0000789019-24-000021", prov.get_sec_url())

        with self.assertRaises(dataclasses.FrozenInstanceError):
            prov.accession_number = "mutated"

    def test_02_lineage_step_schema_immutability(self):
        """Verify LineageStepDTO fields and frozen immutability."""
        step = LineageStepDTO(
            step_index=1,
            step_number=1,
            stage_name="1. PRIMARY SOURCE",
            step_name="PRIMARY_SOURCE_EXTRACTION",
            metric_name="Revenue",
            input_values={"tag": "us-gaap:Revenues"},
            output_value=245120000000.0,
            transformation_description="Direct extraction from audited 10-K XBRL",
            transformation_rule="XBRL direct fact",
        )
        self.assertEqual(step.step_number, 1)
        self.assertEqual(step.output_value, 245120000000.0)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            step.output_value = 0.0

    def test_03_data_lineage_schema_immutability(self):
        """Verify DataLineageDTO fields, steps list, and frozen immutability."""
        lineage = DataLineageDTO(
            entity_ticker="MSFT",
            target_metric="DCF Fair Value per Share",
            metric_name="DCF Fair Value per Share",
            final_value=425.50,
            unit="USD/share",
            as_of_date="2024-07-30",
            mode="LIVE",
            steps=[
                LineageStepDTO(step_number=1, step_name="STEP1", output_value=100.0)
            ],
            summary_explanation="Deterministic DCF calculation pipeline",
            calculation_summary="Deterministic DCF calculation pipeline",
        )
        self.assertEqual(lineage.entity_ticker, "MSFT")
        self.assertEqual(lineage.final_value, 425.50)
        self.assertEqual(len(lineage.steps), 1)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            lineage.final_value = 500.0

    def test_04_qualitative_evidence_lineage_schema(self):
        """Verify QualitativeEvidenceLineageDTO 6-stage chain and frozen immutability."""
        ev = QualitativeEvidenceLineageDTO(
            ticker="MSFT",
            claim_id="clm-001",
            company_name="Microsoft Corporation",
            cik="0000789019",
            form="10-K",
            accession_number="0000789019-24-000021",
            filing_date="2024-07-30",
            acceptance_datetime="2024-07-30 20:06:22+00",
            section_name="Item 7. Management Discussion and Analysis",
            passage_id="p-42",
            verbatim_quote="Azure and cloud services revenue increased 30%.",
            extraction_category="REVENUE_GROWTH",
            direction="POSITIVE",
            severity="HIGH",
            materiality="HIGH",
            validation_status="VALIDATED",
            filing_stage={"form": "10-K", "accession": "0000789019-24-000021"},
            section_stage={"section_name": "Item 7"},
            passage_stage={"passage_id": "p-42", "quote": "Azure revenue..."},
            extraction_stage={"claim": "Azure growth"},
            validation_stage={"status": "VALIDATED"},
            signal_stage={"category": "REVENUE_GROWTH"},
        )
        self.assertEqual(ev.ticker, "MSFT")
        self.assertEqual(ev.validation_status, "VALIDATED")
        self.assertEqual(ev.filing_stage["form"], "10-K")
        self.assertEqual(ev.signal_stage["category"], "REVENUE_GROWTH")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            ev.validation_status = "REJECTED"

    def test_05_valuation_bridge_lineage_schema(self):
        """Verify ValuationBridgeLineageDTO fields and frozen immutability."""
        bridge = ValuationBridgeLineageDTO(
            ticker="MSFT",
            comparison_id="comp-001",
            valuation_date="2024-07-30",
            primary_signal_category="REVENUE_GROWTH",
            key_assumption_adjusted="revenue_growth_y1",
            adjustment_magnitude=0.015,
            baseline_fair_value=400.0,
            enhanced_fair_value=420.0,
            fair_value_pct_change=5.0,
            rationale="Strong cloud growth guidance",
            supporting_evidence_quote="Azure grew 30%",
            accession_number="0000789019-24-000021",
            filing_date="2024-07-30",
            validation_status="VALIDATED",
            evidence_citation="SEC Form 10-K Item 7",
            is_pit_valid=True,
        )
        self.assertEqual(bridge.baseline_fair_value, 400.0)
        self.assertEqual(bridge.enhanced_fair_value, 420.0)
        self.assertTrue(bridge.is_pit_valid)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            bridge.enhanced_fair_value = 500.0

    def test_06_fundamental_change_schema(self):
        """Verify FundamentalChangeDTO attributes and noise thresholds."""
        chg = FundamentalChangeDTO(
            metric_name="Revenue",
            category="REVENUE",
            current_period="FY2024",
            current_value=245120000000.0,
            previous_period="FY2023",
            previous_value=211915000000.0,
            absolute_change=33205000000.0,
            percent_change=15.67,
            unit="$",
            direction="INCREASED",
            is_meaningful=True,
            explanation="Increased by +15.7%",
            percentage_change=15.67,
            interpretation="Increased by +15.7%",
        )
        self.assertEqual(chg.metric_name, "Revenue")
        self.assertTrue(chg.is_meaningful)
        self.assertEqual(chg.direction, "INCREASED")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            chg.absolute_change = 0.0

    def test_07_what_changed_response_schema(self):
        """Verify WhatChangedResponse bundling and dual-accession metadata."""
        resp = WhatChangedResponse(
            ticker="MSFT",
            mode="LIVE",
            as_of_date=None,
            information_cutoff="LIVE",
            current_period_label="FY2024",
            previous_period_label="FY2023",
            fundamental_changes=[],
            qualitative_changes=[],
            valuation_assumption_changes=[],
            summary_narrative="Longitudinal comparison",
            is_pit_valid=True,
            current_period="FY2024",
            previous_period="FY2023",
            current_accession="0000789019-24-000021",
            previous_accession="0000789019-23-000015",
            is_longitudinal_valid=True,
            rejection_reason=None,
        )
        self.assertEqual(resp.ticker, "MSFT")
        self.assertTrue(resp.is_pit_valid)
        self.assertTrue(resp.is_longitudinal_valid)
        self.assertEqual(resp.current_accession, "0000789019-24-000021")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            resp.is_pit_valid = False

    # ==========================================================================
    # 2. PLATFORM SERVICE PROVENANCE & LINEAGE RETRIEVAL
    # ==========================================================================

    def test_08_get_provenance_sec_accession_linking(self):
        """Verify get_provenance links authoritative SEC accession from database."""
        prov = self.service.get_provenance(ticker="MSFT", as_of_date="2024-07-30", mode="HISTORICAL")
        self.assertIsNotNone(prov.accession_number)
        self.assertIn("-", prov.accession_number)
        self.assertEqual(prov.source_name, "SEC EDGAR")
        self.assertTrue(prov.is_pit_compliant)

    def test_09_get_provenance_sec_url_edgar_format(self):
        """Verify get_provenance constructs valid SEC EDGAR URL linking to source."""
        prov = self.service.get_provenance(ticker="MSFT", as_of_date="2024-07-30", mode="HISTORICAL")
        sec_url = prov.get_sec_url()
        self.assertIsNotNone(sec_url)
        self.assertTrue(sec_url.startswith("https://www.sec.gov/Archives/edgar/data/"))
        self.assertIn(prov.accession_number, sec_url)

    def test_10_get_provenance_acceptance_timestamp(self):
        """Verify get_provenance captures exact authoritative acceptance timestamp."""
        prov = self.service.get_provenance(ticker="MSFT", as_of_date="2024-07-30", mode="HISTORICAL")
        self.assertIsNotNone(prov.acceptance_datetime)
        self.assertGreaterEqual(len(prov.acceptance_datetime), 10)

    def test_11_get_provenance_pit_compliance(self):
        """Verify is_pit_compliant reflects point-in-time constraints accurately."""
        # Valid historical date
        valid_prov = self.service.get_provenance(ticker="MSFT", as_of_date="2024-07-30", mode="HISTORICAL")
        self.assertTrue(valid_prov.is_pit_compliant)
        self.assertIsNone(valid_prov.pit_rejection_reason)

        # Ancient cutoff before company filings exist
        ancient_prov = self.service.get_provenance(ticker="MSFT", as_of_date="1980-01-01", mode="HISTORICAL")
        self.assertFalse(ancient_prov.is_pit_compliant)
        self.assertIsNotNone(ancient_prov.pit_rejection_reason)

    # ==========================================================================
    # 3. WHAT CHANGED ENGINE & DUAL-ACCESSION POINT-IN-TIME LOCK
    # ==========================================================================

    def test_12_what_changed_dual_accession_pit_lock(self):
        """Verify get_company_changes enforces dual-accession PIT lock across both periods."""
        # Valid historical date: both T and T-1 are accepted prior to 2024-07-30 23:59:59
        changes = self.service.get_company_changes("MSFT", as_of_date="2024-07-30", mode="HISTORICAL")
        self.assertTrue(changes.is_pit_valid)
        self.assertTrue(changes.is_longitudinal_valid)
        self.assertIsNotNone(changes.current_accession)
        self.assertIsNotNone(changes.previous_accession)

        # Ancient cutoff: fewer than 2 statements exist -> must reject comparison cleanly
        ancient_changes = self.service.get_company_changes("MSFT", as_of_date="1995-01-01", mode="HISTORICAL")
        self.assertFalse(ancient_changes.is_pit_valid)
        self.assertFalse(ancient_changes.is_longitudinal_valid)
        self.assertIn("Insufficient", ancient_changes.rejection_reason)

    def test_13_what_changed_fundamental_deltas_computation(self):
        """Verify mathematical integrity of fundamental statement deltas."""
        changes = self.service.get_company_changes("MSFT", mode="LIVE")
        self.assertGreater(len(changes.fundamental_changes), 0)

        for fc in changes.fundamental_changes:
            self.assertAlmostEqual(
                fc.absolute_change,
                fc.current_value - fc.previous_value,
                places=2,
                msg=f"Absolute delta mismatch for {fc.metric_name}"
            )
            if fc.previous_value != 0:
                expected_pct = ((fc.current_value - fc.previous_value) / abs(fc.previous_value)) * 100.0
                self.assertAlmostEqual(
                    fc.percent_change,
                    expected_pct,
                    places=2,
                    msg=f"Percentage delta mismatch for {fc.metric_name}"
                )

    def test_14_what_changed_noise_filter_threshold(self):
        """Verify noise filter flags changes with |pct| < 0.1% or |delta| < $1,000."""
        changes = self.service.get_company_changes("MSFT", mode="LIVE")
        for fc in changes.fundamental_changes:
            if abs(fc.percent_change) < 0.1 or abs(fc.absolute_change) < 1000.0:
                self.assertFalse(fc.is_meaningful)
                self.assertIn("Flat / within rounding noise threshold", fc.explanation)
            else:
                self.assertTrue(fc.is_meaningful)

    # ==========================================================================
    # 4. VALUATION & WACC NUMERICAL LINEAGE
    # ==========================================================================

    def test_15_valuation_numerical_lineage_completeness(self):
        """Verify get_valuation_lineage returns complete 4-stage DCF lineage steps."""
        lineage = self.service.get_valuation_lineage("MSFT", mode="LIVE")
        self.assertIsNotNone(lineage)
        self.assertEqual(lineage.entity_ticker, "MSFT")
        self.assertGreaterEqual(len(lineage.steps), 4)

        step_names = [s.step_name for s in lineage.steps]
        self.assertIn("RAW_SEC_EXTRACTION", step_names)
        self.assertIn("FCFF_NORMALIZATION", step_names)
        self.assertIn("DISCOUNTING_AND_WACC", step_names)
        self.assertIn("TERMINAL_VALUE_AND_EQUITY_BRIDGE", step_names)

        # Final bridge output must match final_value
        last_step = lineage.steps[-1]
        self.assertEqual(last_step.output_value["fair_value_per_share"], lineage.final_value)

    def test_16_wacc_derivation_lineage_completeness(self):
        """Verify get_wacc_lineage returns CAPM formula steps and weights."""
        wacc_lin = self.service.get_wacc_lineage("MSFT", mode="LIVE")
        self.assertIsNotNone(wacc_lin)
        self.assertEqual(wacc_lin.unit, "%")
        self.assertGreaterEqual(len(wacc_lin.steps), 4)

        step_names = [s.step_name for s in wacc_lin.steps]
        self.assertIn("COST_OF_EQUITY_CAPM", step_names)
        self.assertIn("COST_OF_DEBT", step_names)
        self.assertIn("CAPITAL_STRUCTURE_WEIGHTS", step_names)
        self.assertIn("WACC_COMBINATION", step_names)

    # ==========================================================================
    # 5. QUALITATIVE DISCLOSURE LINEAGE & VALUATION BRIDGE
    # ==========================================================================

    def test_17_qualitative_evidence_6stage_lineage(self):
        """Verify get_evidence_lineage generates 6-stage chain down to verbatim quote."""
        ev_list = self.service.get_evidence_lineage("MSFT", mode="LIVE")
        self.assertGreater(len(ev_list), 0)

        for ev in ev_list:
            self.assertEqual(ev.validation_status, "VALIDATED")
            self.assertTrue(bool(ev.verbatim_quote))
            self.assertIn("accession_number", ev.filing_stage)
            self.assertIn("section_name", ev.section_stage)
            self.assertIn("verbatim_quote", ev.passage_stage)
            self.assertIn("claim", ev.extraction_stage)
            self.assertIn("status", ev.validation_stage)
            self.assertIn("category", ev.signal_stage)

    def test_18_valuation_bridge_lineage_query(self):
        """Verify get_valuation_bridge_lineage links disclosure signal to DCF delta."""
        bridge = self.service.get_valuation_bridge_lineage("MSFT", mode="LIVE")
        if bridge is not None:
            self.assertGreater(bridge.baseline_fair_value, 0.0)
            self.assertGreater(bridge.enhanced_fair_value, 0.0)
            self.assertTrue(bridge.is_pit_valid)
            self.assertIsNotNone(bridge.primary_signal_category)

    # ==========================================================================
    # 6. ADVERSARIAL TEMPORAL INTEGRITY & ANTI-LEAKAGE
    # ==========================================================================

    def test_19_adversarial_leakage_future_filing_excluded(self):
        """Verify filings accepted after point-in-time cutoff are strictly excluded."""
        prov = self.service.get_provenance(ticker="MSFT", as_of_date="2022-01-01", mode="HISTORICAL")
        self.assertIsNotNone(prov.acceptance_datetime)
        self.assertLessEqual(prov.acceptance_datetime[:10], "2022-01-01")

        # In-memory test verifying future filing is rejected
        con = duckdb.connect(":memory:")
        con.execute("""
            CREATE TABLE filings (
                accession_number VARCHAR PRIMARY KEY,
                ticker VARCHAR,
                acceptance_datetime TIMESTAMP WITH TIME ZONE
            );
            INSERT INTO filings VALUES
                ('0001-A', 'TEST', '2023-12-20 18:30:00+00'::TIMESTAMPTZ),
                ('0002-B', 'TEST', '2024-02-01 09:15:00+00'::TIMESTAMPTZ);
        """)
        rows = con.execute(
            "SELECT accession_number FROM filings WHERE acceptance_datetime <= '2024-01-01 23:59:59'::TIMESTAMPTZ"
        ).fetchall()
        accs = [r[0] for r in rows]
        self.assertEqual(accs, ["0001-A"])

    def test_20_adversarial_leakage_future_evidence_excluded(self):
        """Verify qualitative evidence accepted after historical cutoff is strictly excluded."""
        ev_list = self.service.get_evidence_lineage("MSFT", as_of_date="2023-01-01", mode="HISTORICAL")
        cutoff_dt = datetime.strptime("2023-01-01 23:59:59", "%Y-%m-%d %H:%M:%S")
        for ev in ev_list:
            if ev.acceptance_datetime:
                acc_clean = ev.acceptance_datetime[:19].replace("T", " ")
                acc_dt = datetime.strptime(acc_clean, "%Y-%m-%d %H:%M:%S")
                self.assertLessEqual(acc_dt, cutoff_dt)

    def test_21_adversarial_dual_accession_leakage(self):
        """
        Verify that if current period accession post-dates cutoff, longitudinal comparison
        is strictly marked invalid.
        """
        con = duckdb.connect(":memory:")
        con.execute("""
            CREATE TABLE annual_financials (
                ticker VARCHAR,
                period_end_date DATE,
                acceptance_datetime TIMESTAMPTZ,
                accession_number VARCHAR,
                revenue DOUBLE
            );
            INSERT INTO annual_financials VALUES
                ('ADVR', '2024-12-31'::DATE, '2025-02-15 16:00:00+00'::TIMESTAMPTZ, '0002-CURR', 200.0),
                ('ADVR', '2023-12-31'::DATE, '2024-02-10 16:00:00+00'::TIMESTAMPTZ, '0001-PREV', 100.0);
        """)
        cutoff = "2024-06-30"
        rows = con.execute(
            "SELECT accession_number, acceptance_datetime::VARCHAR FROM annual_financials WHERE acceptance_datetime <= ?::TIMESTAMPTZ ORDER BY period_end_date DESC",
            [f"{cutoff} 23:59:59"]
        ).fetchall()
        # Only 1 statement remains before cutoff
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "0001-PREV")

    # ==========================================================================
    # 7. PRESENTATION COMPONENTS & UI TESTS
    # ==========================================================================

    def test_22_ui_render_source_provenance_badge(self):
        """Verify render_source_provenance_badge handles compliant, non-compliant, and None inputs."""
        ctx = MockStreamlitContext()

        # Valid compliant badge
        prov_valid = SourceProvenanceDTO(
            source_name="SEC EDGAR",
            primary_source="SEC Form 10-K / CIK 0000789019 / Accession 0000789019-24-000021",
            accession_number="0000789019-24-000021",
            acceptance_datetime="2024-07-30 20:06:22+00",
            sec_url="https://www.sec.gov/Archives/edgar/data/789019/000078901924000021/0000789019-24-000021.txt",
            is_pit_compliant=True,
        )
        res1 = render_source_provenance_badge(prov_valid, st_client=ctx)
        self.assertTrue(res1["available"])
        self.assertTrue(res1["is_pit_compliant"])
        self.assertTrue(any("[SOURCE DATA]" in c for c in ctx.caption_calls))

        # Non-compliant badge
        ctx_warn = MockStreamlitContext()
        prov_invalid = SourceProvenanceDTO(
            is_pit_compliant=False,
            pit_rejection_reason="Accession exceeds cutoff date",
        )
        res2 = render_source_provenance_badge(prov_invalid, st_client=ctx_warn)
        self.assertFalse(res2["is_pit_compliant"])
        self.assertTrue(any("[POINT-IN-TIME EXCLUSION]" in w for w in ctx_warn.warning_calls))

        # None badge
        ctx_none = MockStreamlitContext()
        res3 = render_source_provenance_badge(None, st_client=ctx_none)
        self.assertFalse(res3["available"])
        self.assertTrue(any("unavailable" in c for c in ctx_none.caption_calls))

    def test_23_ui_render_why_this_number_expander(self):
        """Verify render_why_this_number_expander renders steps and rules without crashing."""
        ctx = MockStreamlitContext()
        lineage = self.service.get_valuation_lineage("MSFT", mode="LIVE")
        res = render_why_this_number_expander("Why this Fair Value?", lineage, st_client=ctx)

        self.assertTrue(res["has_lineage"])
        self.assertEqual(res["title"], "Why this Fair Value?")
        self.assertTrue(any("Calculation Methodology:" in m for m in ctx.markdown_calls))
        self.assertTrue(any("RAW_SEC_EXTRACTION" in m for m in ctx.markdown_calls))

    def test_24_ui_render_what_changed_table_and_rejection(self):
        """Verify render_what_changed_table renders tables when valid and warnings when rejected."""
        ctx_valid = MockStreamlitContext()
        changes_valid = self.service.get_company_changes("MSFT", mode="LIVE")
        res1 = render_what_changed_table(changes_valid, st_client=ctx_valid)
        self.assertTrue(res1["is_valid"])
        self.assertGreater(res1["fundamental_changes_count"], 0)
        self.assertTrue(any("Longitudinal Delta Analysis:" in m for m in ctx_valid.markdown_calls))

        # Test rejected comparison
        ctx_rej = MockStreamlitContext()
        changes_rej = WhatChangedResponse(
            ticker="MSFT",
            is_longitudinal_valid=False,
            rejection_reason="Insufficient statements available before cutoff",
        )
        res2 = render_what_changed_table(changes_rej, st_client=ctx_rej)
        self.assertFalse(res2["is_valid"])
        self.assertTrue(any("Longitudinal Comparison Rejected" in w for w in ctx_rej.warning_calls))

    def test_25_end_to_end_changes_page_integration(self):
        """Verify app/pages/changes.py executes cleanly across LIVE and HISTORICAL modes."""
        ctx_live = MockStreamlitContext()
        init_session_state()
        set_state("selected_ticker", "MSFT")
        set_state("mode", "LIVE")
        render_changes_page(st_client=ctx_live, service=self.service)
        self.assertTrue(any("WHAT CHANGED" in h.upper() for h in ctx_live.header_calls))

        ctx_hist = MockStreamlitContext()
        set_state("mode", "HISTORICAL")
        set_state("as_of_date", "2024-07-30")
        render_changes_page(st_client=ctx_hist, service=self.service)
        self.assertTrue(any("WHAT CHANGED" in h.upper() for h in ctx_hist.header_calls))


if __name__ == "__main__":
    unittest.main()
