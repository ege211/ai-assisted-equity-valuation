"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8D — Filing Intelligence & Evidence Audit Interface Verification Suite
File: tests/test_phase8d_filing_interface.py

Comprehensive test suite verifying the Phase 8D specifications:
1. test_01_filing_overview_header_metrics
2. test_02_filing_catalog_newest_to_oldest_order
3. test_03_filing_catalog_form_filtering
4. test_04_filing_catalog_column_completeness
5. test_05_section_inspector_key_items_highlighted
6. test_06_section_inspector_metadata_and_preview
7. test_07_filing_explorer_strict_pit_cutoff
8. test_08_evidence_validation_governance_main_list
9. test_09_evidence_quarantine_isolation_of_unverified_claims
10. test_10_evidence_quarantine_governance_disclaimer
11. test_11_evidence_verbatim_quote_integrity
12. test_12_evidence_category_filtering
13. test_13_evidence_direction_filtering
14. test_14_evidence_severity_filtering
15. test_15_evidence_materiality_filtering
16. test_16_evidence_form_filtering
17. test_17_evidence_in_memory_keyword_search
18_test_18_evidence_to_valuation_bridge_matched_linkage
19. test_19_evidence_to_valuation_bridge_unmatched_handling
20. test_20_four_part_audit_expander_sections
21. test_21_longitudinal_changes_filing_date_provenance
22. test_22_longitudinal_changes_mutation_filter_and_provenance
"""

import sys
import unittest
from pathlib import Path
from typing import Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service.contracts import (
    CompanyRequest,
    AnalysisResponse,
    FilingExplorerResponse,
    FilingIntelligenceResponse,
    FilingSignal,
    ChangeSignalDTO,
    FilingSummaryDTO,
    FilingSectionDTO,
    ValuationBridgeRecordDTO,
)
from src.service.platform_service import PlatformService
from app.pages.filings import render_filings_page, is_key_section
from app.pages.evidence import render_evidence_page
from app.pages.changes import render_changes_page


class MockStreamlitContext:
    """Mock Streamlit object capturing calls for headless verification."""
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

    def selectbox(self, label, options, index=0, *args, **kwargs):
        return options[index] if options else None

    def text_input(self, label, value="", *args, **kwargs):
        return value


class TestPhase8DFilingInterface(unittest.TestCase):
    """Complete verification suite for Phase 8D Filing Intelligence & Evidence Interface."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = PlatformService()
        cls.msft_response = cls.service.analyze_company(CompanyRequest("MSFT", mode="LIVE"))

    # --------------------------------------------------------------------------
    # 1. Filing Overview Header Metrics
    # --------------------------------------------------------------------------
    def test_01_filing_overview_header_metrics(self) -> None:
        """Verify overview metrics: ticker, CIK, mode, filing counts, 10-K, 10-Q, claims."""
        mock_ctx = MockStreamlitContext()
        data = render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)

        self.assertEqual(data["ticker"], "MSFT")
        self.assertTrue(len(data["company_name"]) > 0)
        self.assertTrue(len(data["cik"]) > 0)
        self.assertGreater(data["total_filings"], 0)
        self.assertGreater(data["ten_k_count"], 0)
        self.assertGreater(data["ten_q_count"], 0)
        self.assertIsNotNone(data["latest_filing_date"])
        self.assertIsNotNone(data["latest_acceptance_datetime"])
        self.assertGreater(data["total_claims_count"], 0)
        self.assertGreater(data["validated_claims_count"], 0)

        # Check metric card labels in UI output
        labels = [m[0] for m in mock_ctx.metric_calls]
        self.assertIn("Company / Ticker", labels)
        self.assertIn("Total Ingested Filings", labels)
        self.assertIn("10-K / 10-Q Submissions", labels)
        self.assertIn("Extracted Disclosures", labels)

    # --------------------------------------------------------------------------
    # 2. Dense Filing Catalog Newest to Oldest Sort
    # --------------------------------------------------------------------------
    def test_02_filing_catalog_newest_to_oldest_order(self) -> None:
        """Verify dense catalog filings are sorted chronologically newest to oldest."""
        mock_ctx = MockStreamlitContext()
        data = render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)

        filings = data["filtered_filings"]
        self.assertGreater(len(filings), 1)
        for i in range(len(filings) - 1):
            cur_dt = filings[i].acceptance_datetime or filings[i].filing_date
            next_dt = filings[i + 1].acceptance_datetime or filings[i + 1].filing_date
            self.assertGreaterEqual(cur_dt, next_dt)

    # --------------------------------------------------------------------------
    # 3. Filing Catalog Form Filtering
    # --------------------------------------------------------------------------
    def test_03_filing_catalog_form_filtering(self) -> None:
        """Verify catalog form filtering for All, 10-K, and 10-Q."""
        mock_ctx = MockStreamlitContext()
        data_10k = render_filings_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            form_filter_override="10-K",
        )
        for f in data_10k["filtered_filings"]:
            self.assertEqual(f.form, "10-K")

        data_10q = render_filings_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            form_filter_override="10-Q",
        )
        for f in data_10q["filtered_filings"]:
            self.assertEqual(f.form, "10-Q")

    # --------------------------------------------------------------------------
    # 4. Filing Catalog Column Completeness
    # --------------------------------------------------------------------------
    def test_04_filing_catalog_column_completeness(self) -> None:
        """Verify catalog table markdown rendering includes all mandatory column headers."""
        mock_ctx = MockStreamlitContext()
        render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)

        all_md = " ".join(mock_ctx.markdown_calls)
        self.assertIn("Form", all_md)
        self.assertIn("Filing Date", all_md)
        self.assertIn("Acceptance Datetime (PIT)", all_md)
        self.assertIn("Report Date", all_md)
        self.assertIn("Accession Number", all_md)
        self.assertIn("Audited Sections", all_md)
        self.assertIn("Extracted Claims", all_md)

    # --------------------------------------------------------------------------
    # 5. Section Inspector Key Items Highlighted
    # --------------------------------------------------------------------------
    def test_05_section_inspector_key_items_highlighted(self) -> None:
        """Verify key institutional narrative sections are highlighted."""
        self.assertTrue(is_key_section("ITEM_1A_RISK_FACTORS"))
        self.assertTrue(is_key_section("ITEM_7_MDA"))
        self.assertTrue(is_key_section("ITEM_7A_MARKET_RISK"))
        self.assertTrue(is_key_section("ITEM_8_FINANCIAL_STATEMENTS"))
        self.assertFalse(is_key_section("ITEM_99_RANDOM"))

        mock_ctx = MockStreamlitContext()
        data = render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)
        self.assertIsInstance(data["highlighted_sections"], list)
        self.assertGreater(len(data["highlighted_sections"]), 0)
        self.assertIn("ITEM_1A_RISK_FACTORS", data["highlighted_sections"])

    # --------------------------------------------------------------------------
    # 6. Section Inspector Metadata & Preview
    # --------------------------------------------------------------------------
    def test_06_section_inspector_metadata_and_preview(self) -> None:
        """Verify character count, detection confidence, and non-empty verbatim preview."""
        mock_ctx = MockStreamlitContext()
        data = render_filings_page(self.msft_response, st_client=mock_ctx, service=self.service)

        sections = data["selected_filing_sections"]
        self.assertGreater(len(sections), 0)
        sec = sections[0]
        self.assertGreater(sec.char_count, 0)
        self.assertIn(sec.detection_confidence, ("HIGH", "MEDIUM", "LOW"))
        self.assertTrue(len(sec.section_preview) > 0)

    # --------------------------------------------------------------------------
    # 7. Filing Explorer Strict PIT Cutoff Enforcement
    # --------------------------------------------------------------------------
    def test_07_filing_explorer_strict_pit_cutoff(self) -> None:
        """Verify Historical mode strictly excludes filings accepted after PIT cutoff."""
        pit_date = "2023-01-01"
        res = self.service.get_filing_explorer_data("MSFT", as_of_date=pit_date, mode="HISTORICAL")

        for f in res.filings:
            acceptance_date = f.acceptance_datetime.split()[0]
            self.assertLessEqual(acceptance_date, pit_date)

    # --------------------------------------------------------------------------
    # 8. Evidence Validation Governance - Only Validated in Main List
    # --------------------------------------------------------------------------
    def test_08_evidence_validation_governance_main_list(self) -> None:
        """Verify only VALIDATED claims appear in the main validated_claims list."""
        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(self.msft_response, st_client=mock_ctx, service=self.service)

        self.assertGreater(len(data["validated_claims"]), 0)
        for c in data["validated_claims"]:
            self.assertEqual(c.validation_status.upper(), "VALIDATED")

    # --------------------------------------------------------------------------
    # 9. Evidence Quarantine Isolation of Unverified Claims
    # --------------------------------------------------------------------------
    def test_09_evidence_quarantine_isolation_of_unverified_claims(self) -> None:
        """Verify any claims with validation_status != VALIDATED are isolated in quarantine."""
        synthetic_intel = FilingIntelligenceResponse(
            ticker="MOCK",
            as_of_date="2024-12-31",
            mode="LIVE",
            total_claims_retrieved=3,
            validated_claims_count=1,
            rejected_claims_count=2,
            evidence_status_summary="1/3 validated",
            signals=[
                FilingSignal(
                    signal_id="s1", category="risk", claim="Valid claim",
                    evidence_quote="exact match quote", evidence_location="p1",
                    source_identifier="acc1", direction="NEGATIVE", severity="LOW",
                    confidence=0.9, materiality="MATERIAL", validation_status="VALIDATED",
                ),
                FilingSignal(
                    signal_id="s2", category="risk", claim="Rejected claim",
                    evidence_quote="quote 2", evidence_location="p2",
                    source_identifier="acc1", direction="NEGATIVE", severity="HIGH",
                    confidence=0.1, materiality="MATERIAL", validation_status="REJECTED",
                    validation_reason="Substring missing",
                ),
                FilingSignal(
                    signal_id="s3", category="risk", claim="Pending unknown claim",
                    evidence_quote="quote 3", evidence_location="p3",
                    source_identifier="acc1", direction="NEUTRAL", severity="LOW",
                    confidence=0.5, materiality="MATERIAL", validation_status="UNKNOWN_STATUS",
                ),
            ],
            change_signals=[],
            covered_accessions=["acc1"],
        )

        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(st_client=mock_ctx, intelligence=synthetic_intel)

        self.assertEqual(len(data["validated_claims"]), 1)
        self.assertEqual(data["validated_claims"][0].signal_id, "s1")
        self.assertEqual(len(data["quarantined_claims"]), 2)
        quarantined_ids = {q.signal_id for q in data["quarantined_claims"]}
        self.assertEqual(quarantined_ids, {"s2", "s3"})

    # --------------------------------------------------------------------------
    # 10. Evidence Quarantine Governance Disclaimer
    # --------------------------------------------------------------------------
    def test_10_evidence_quarantine_governance_disclaimer(self) -> None:
        """Verify UI displays mandatory notice: Quarantined claims are not used as verified evidence."""
        synthetic_intel = FilingIntelligenceResponse(
            ticker="MOCK",
            as_of_date="2024-12-31",
            mode="LIVE",
            total_claims_retrieved=2,
            validated_claims_count=1,
            rejected_claims_count=1,
            evidence_status_summary="1/2 validated",
            signals=[
                FilingSignal(
                    signal_id="s1", category="margin", claim="Valid",
                    evidence_quote="quote", evidence_location="p1",
                    source_identifier="acc1", direction="POSITIVE", severity="LOW",
                    confidence=0.9, materiality="MATERIAL", validation_status="VALIDATED",
                ),
                FilingSignal(
                    signal_id="s2", category="margin", claim="Unverified",
                    evidence_quote="quote bad", evidence_location="p2",
                    source_identifier="acc1", direction="POSITIVE", severity="HIGH",
                    confidence=0.1, materiality="MATERIAL", validation_status="REJECTED",
                ),
            ],
            change_signals=[],
            covered_accessions=["acc1"],
        )

        mock_ctx = MockStreamlitContext()
        render_evidence_page(st_client=mock_ctx, intelligence=synthetic_intel)

        all_warnings = " ".join(mock_ctx.warning_calls)
        self.assertIn("Quarantined claims are not used as verified evidence", all_warnings)

    # --------------------------------------------------------------------------
    # 11. Evidence Verbatim Quote Integrity
    # --------------------------------------------------------------------------
    def test_11_evidence_verbatim_quote_integrity(self) -> None:
        """Verify claims display verbatim quote strings without paraphrasing."""
        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(self.msft_response, st_client=mock_ctx, service=self.service)

        for c in data["validated_claims"][:5]:
            self.assertTrue(len(c.evidence_quote) > 10)
            self.assertIn(c.evidence_quote, " ".join(mock_ctx.info_calls))

    # --------------------------------------------------------------------------
    # 12. Evidence Category Filtering
    # --------------------------------------------------------------------------
    def test_12_evidence_category_filtering(self) -> None:
        """Verify category filtering isolates claims matching the chosen category."""
        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            category_filter="MARGIN_PRESSURE",
        )

        self.assertEqual(data["active_category"], "MARGIN_PRESSURE")
        self.assertGreater(len(data["validated_claims"]), 0)
        for c in data["validated_claims"]:
            self.assertEqual(c.category.upper(), "MARGIN_PRESSURE")

    # --------------------------------------------------------------------------
    # 13. Evidence Direction Filtering
    # --------------------------------------------------------------------------
    def test_13_evidence_direction_filtering(self) -> None:
        """Verify filtering by direction (POSITIVE, NEGATIVE, NEUTRAL)."""
        mock_ctx = MockStreamlitContext()
        data_neg = render_evidence_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            direction_filter="NEGATIVE",
        )

        for c in data_neg["validated_claims"]:
            self.assertEqual(c.direction.upper(), "NEGATIVE")

    # --------------------------------------------------------------------------
    # 14. Evidence Severity Filtering
    # --------------------------------------------------------------------------
    def test_14_evidence_severity_filtering(self) -> None:
        """Verify filtering by severity (LOW, MEDIUM, HIGH)."""
        mock_ctx = MockStreamlitContext()
        data_med = render_evidence_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            severity_filter="MEDIUM",
        )

        for c in data_med["validated_claims"]:
            self.assertEqual(c.severity.upper(), "MEDIUM")

    # --------------------------------------------------------------------------
    # 15. Evidence Materiality Filtering
    # --------------------------------------------------------------------------
    def test_15_evidence_materiality_filtering(self) -> None:
        """Verify filtering by materiality."""
        mock_ctx = MockStreamlitContext()
        data_mat = render_evidence_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            materiality_filter="HIGH",
        )

        self.assertGreater(len(data_mat["validated_claims"]), 0)
        for c in data_mat["validated_claims"]:
            self.assertEqual(c.materiality.upper(), "HIGH")

    # --------------------------------------------------------------------------
    # 16. Evidence Form Filtering
    # --------------------------------------------------------------------------
    def test_16_evidence_form_filtering(self) -> None:
        """Verify filtering qualitative disclosures by source form (10-K)."""
        mock_ctx = MockStreamlitContext()
        data_10k = render_evidence_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            form_filter="10-K",
        )

        for c in data_10k["validated_claims"]:
            self.assertEqual(c.form.upper(), "10-K")

    # --------------------------------------------------------------------------
    # 17. Evidence In-Memory Keyword Search
    # --------------------------------------------------------------------------
    def test_17_evidence_in_memory_keyword_search(self) -> None:
        """Verify in-memory substring search across claims, categories, and quotes."""
        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            keyword_query="cloud",
        )

        for c in data["validated_claims"]:
            match = (
                "cloud" in c.claim.lower()
                or "cloud" in c.category.lower()
                or "cloud" in c.evidence_quote.lower()
            )
            self.assertTrue(match)

    # --------------------------------------------------------------------------
    # 18. Evidence -> Valuation Bridge Matched Linkage
    # --------------------------------------------------------------------------
    def test_18_evidence_to_valuation_bridge_matched_linkage(self) -> None:
        """Verify that matched claims display the complete valuation bridge impact chain."""
        bridge = ValuationBridgeRecordDTO(
            comparison_id="comp_test",
            ticker="MSFT",
            valuation_date="2024-12-31",
            primary_signal_category="MARGIN_PRESSURE",
            key_assumption_adjusted="ebit_margins",
            adjustment_magnitude=-0.005,
            evidence_citation="operating margin compression in Intelligent Cloud",
            baseline_fair_value=410.0,
            enhanced_fair_value=398.0,
            fair_value_pct_change=-2.93,
        )
        intel = FilingIntelligenceResponse(
            ticker="MSFT",
            as_of_date="2024-12-31",
            mode="LIVE",
            total_claims_retrieved=1,
            validated_claims_count=1,
            rejected_claims_count=0,
            evidence_status_summary="1/1 validated",
            signals=[
                FilingSignal(
                    signal_id="sig_bridge",
                    category="MARGIN_PRESSURE",
                    claim="Cloud infrastructure costs are expanding.",
                    evidence_quote="higher infrastructure scaling costs pressured gross margins",
                    evidence_location="Item 7",
                    source_identifier="0001-24-01",
                    direction="NEGATIVE",
                    severity="HIGH",
                    confidence=0.95,
                    materiality="MATERIAL",
                    validation_status="VALIDATED",
                    form="10-K",
                    filing_date="2024-07-30",
                    accession_number="0001-24-01",
                )
            ],
            change_signals=[],
            covered_accessions=["0001-24-01"],
            valuation_bridge=bridge,
        )

        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(st_client=mock_ctx, intelligence=intel)

        self.assertEqual(data["linked_claims_count"], 1)
        all_success = " ".join(mock_ctx.success_calls)
        self.assertIn("VALUATION BRIDGE LINKAGE ACTIVE", all_success)
        self.assertIn("ebit_margins", all_success)
        self.assertIn("-0.0050", all_success)

    # --------------------------------------------------------------------------
    # 19. Evidence -> Valuation Bridge Unmatched Handling
    # --------------------------------------------------------------------------
    def test_19_evidence_to_valuation_bridge_unmatched_handling(self) -> None:
        """Verify unmatched claims explicitly render Informational disclosure only notice."""
        bridge = ValuationBridgeRecordDTO(
            comparison_id="comp_test",
            ticker="MSFT",
            valuation_date="2024-12-31",
            primary_signal_category="MARGIN_PRESSURE",
            key_assumption_adjusted="ebit_margins",
            adjustment_magnitude=-0.005,
            evidence_citation="margin compression",
            baseline_fair_value=410.0,
            enhanced_fair_value=398.0,
            fair_value_pct_change=-2.93,
        )
        intel = FilingIntelligenceResponse(
            ticker="MSFT",
            as_of_date="2024-12-31",
            mode="LIVE",
            total_claims_retrieved=1,
            validated_claims_count=1,
            rejected_claims_count=0,
            evidence_status_summary="1/1 validated",
            signals=[
                FilingSignal(
                    signal_id="sig_unlinked",
                    category="CYBERSECURITY_RISKS",
                    claim="Cyber defense posture remains vigilant.",
                    evidence_quote="we maintain robust network defensive measures",
                    evidence_location="Item 1A",
                    source_identifier="0001-24-01",
                    direction="NEUTRAL",
                    severity="LOW",
                    confidence=0.85,
                    materiality="MATERIAL",
                    validation_status="VALIDATED",
                    form="10-K",
                    filing_date="2024-07-30",
                    accession_number="0001-24-01",
                )
            ],
            change_signals=[],
            covered_accessions=["0001-24-01"],
            valuation_bridge=bridge,
        )

        mock_ctx = MockStreamlitContext()
        data = render_evidence_page(st_client=mock_ctx, intelligence=intel)

        self.assertEqual(data["unlinked_claims_count"], 1)
        all_captions = " ".join(mock_ctx.caption_calls)
        self.assertIn("Informational disclosure only — not linked to valuation adjustment", all_captions)

    # --------------------------------------------------------------------------
    # 20. 4-Part Audit Expander Sections
    # --------------------------------------------------------------------------
    def test_20_four_part_audit_expander_sections(self) -> None:
        """Verify 4-part audit trail contains SOURCE, EXTRACTION, EVIDENCE, VALIDATION."""
        mock_ctx = MockStreamlitContext()
        render_evidence_page(self.msft_response, st_client=mock_ctx, service=self.service)

        all_md = " ".join(mock_ctx.markdown_calls)
        self.assertIn("[1. SOURCE PROVENANCE]", all_md)
        self.assertIn("[2. EXTRACTION METADATA]", all_md)
        self.assertIn("[3. VERBATIM EVIDENCE]", all_md)
        self.assertIn("[4. VALIDATION GOVERNANCE]", all_md)

    # --------------------------------------------------------------------------
    # 21. Longitudinal Changes Filing Date Provenance
    # --------------------------------------------------------------------------
    def test_21_longitudinal_changes_filing_date_provenance(self) -> None:
        """Verify longitudinal change timeline includes current and prior filing dates."""
        mock_ctx = MockStreamlitContext()
        data = render_changes_page(self.msft_response, st_client=mock_ctx, service=self.service)

        self.assertGreater(data["total_signals"], 0)
        first_sig = data["change_signals"][0]
        self.assertTrue(hasattr(first_sig, "current_filing_date"))
        self.assertTrue(hasattr(first_sig, "previous_filing_date"))

        # Check table headers rendered in UI
        all_md = " ".join(mock_ctx.markdown_calls)
        self.assertIn("Current Filing Date", all_md)
        self.assertIn("Prior Filing Date", all_md)

    # --------------------------------------------------------------------------
    # 22. Longitudinal Changes Mutation Filter & Provenance
    # --------------------------------------------------------------------------
    def test_22_longitudinal_changes_mutation_filter_and_provenance(self) -> None:
        """Verify longitudinal change signals filter by delta type and display accession lineage."""
        mock_ctx = MockStreamlitContext()
        data = render_changes_page(
            self.msft_response,
            st_client=mock_ctx,
            service=self.service,
            change_type_filter="MODIFIED",
        )

        self.assertEqual(data["active_change_type"], "MODIFIED")
        self.assertGreater(len(data["change_signals"]), 0)
        for s in data["change_signals"]:
            self.assertEqual(s.change_type.upper(), "MODIFIED")

        # Verify prior and current accession displayed
        all_writes = " ".join(mock_ctx.write_calls)
        self.assertIn("Prior Accession", all_writes)
        self.assertIn("Current Accession", all_writes)


if __name__ == "__main__":
    unittest.main()
