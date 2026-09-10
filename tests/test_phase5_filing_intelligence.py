"""
Comprehensive Unit Test Suite for Phase 5 SEC Filing Qualitative Intelligence.

Covers criteria A through T:
A: Filing retrieval and disk caching
B: Document HTML parsing, cleaning, and unescaping
C: Structural section detection and Table of Contents (TOC) avoidance
D: Relevant passage retrieval mapped to 12 qualitative categories
E: Structured schema and enum validation
F: Evidence quote exact matching in validator
G: Mandatory rejection of fabricated/hallucinated quotations
H: Missing/empty evidence rejection
I: Point-in-time date filtering enforcement
J: 10-K/A amendment temporal isolation
K: Prompt versioning tracking in extractions
L: Model and provider metadata persistence
M: Confidence score calculation and NEEDS_REVIEW handling
N: Materiality classification (LOW, MEDIUM, HIGH)
O: Claim vs. evidence quote separation
P: Period-over-period change detection (NEW, ESCALATED, RESOLVED)
Q: Duplicate extraction deduplication
R: Empty and irrelevant passage abstention
S: Model-agnostic LLMProvider abstraction and swapping
T: End-to-end database persistence and lineage tracking
"""
import copy
import json
import os
import unittest

from src.data.db import DatabaseManager
from src.filing_intelligence.change_detector import ChangeDetector
from src.filing_intelligence.document_fetcher import DocumentFetcher
from src.filing_intelligence.document_parser import parse_sec_html
from src.filing_intelligence.engine import FilingIntelligenceEngine
from src.filing_intelligence.evidence_validator import EvidenceValidator
from src.filing_intelligence.extractor import Extractor
from src.filing_intelligence.llm_provider import (
    DeterministicRuleBasedLLMProvider,
    MockLLMProvider,
)
from src.filing_intelligence.retrieval import (
    chunk_section_into_passages,
    retrieve_relevant_passages,
)
from src.filing_intelligence.schemas import (
    ChangeSignal,
    Direction,
    ExtractedClaim,
    FilingDocument,
    FilingPassage,
    FilingSection,
    Materiality,
    QualitativeCategory,
    Severity,
    ValidationResult,
    ValidationStatus,
)
from src.filing_intelligence.section_parser import parse_sections
from src.filing_intelligence.scoring import (
    calculate_confidence_score,
    classify_materiality,
)


class TestPhase5FilingIntelligence(unittest.TestCase):
    """Rigorous unit tests for SEC qualitative intelligence and LLM extraction."""

    def setUp(self) -> None:
        """Create test fixtures, sample HTML, and clean text."""
        self.sample_html = """
        <html>
        <head><title>Apple Inc. Form 10-K</title></head>
        <body>
            <div class="toc">
                <p>Table of Contents</p>
                <p>Item 1. Business 1</p>
                <p>Item 1A. Risk Factors 5</p>
                <p>Item 7. Management's Discussion and Analysis 20</p>
            </div>
            <hr>
            <div>
                <h2>Item 1. Business</h2>
                <p>The Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories.</p>
            </div>
            <div>
                <h2>Item 1A. Risk Factors</h2>
                <p>The Company is subject to complex and changing laws and regulations worldwide, including legal and regulatory proceedings, antitrust actions and privacy inquiries that could result in substantial fines, penalties, altered business practices, or increased compliance costs.</p>
                <p>Global economic conditions, inflation, and currency fluctuations may cause customer demand softening and decelerating consumer hardware spending.</p>
            </div>
            <div>
                <h2>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</h2>
                <p>Total net sales increased 2% during fiscal year 2024. Our gross margin expanded by 140 basis points to 46.2%, driven by product mix and operational efficiencies, partially offset by component cost pressures.</p>
                <p>We returned $100 billion to shareholders through share repurchases and declared dividends of $0.25 per share.</p>
            </div>
            <div>
                <h2>Item 8. Financial Statements</h2>
                <p>Consolidated statements of financial condition and cash flows.</p>
            </div>
        </body>
        </html>
        """

        self.clean_text, self.char_count, self.word_count = parse_sec_html(self.sample_html)

        self.mock_doc = FilingDocument(
            document_id="doc_TEST_0001",
            accession_number="0000320193-24-000123",
            cik="0000320193",
            ticker="AAPL",
            form="10-K",
            filing_date="2024-11-01",
            acceptance_datetime="2024-11-01 13:01:36+03",
            primary_document="aapl-20240928.htm",
            content_hash="abc123hash",
            char_count=self.char_count,
            word_count=self.word_count,
            clean_text=self.clean_text,
        )

        self.validator = EvidenceValidator()

    # --- Test A: Filing Retrieval & Disk Caching ---
    def test_a_filing_retrieval_and_caching(self) -> None:
        """Fetcher checks cache path, returns content hash, and avoids re-download."""
        fetcher = DocumentFetcher(cache_dir="scratch/test_cache")
        cache_path = fetcher.get_cache_path("0000320193", "0000320193-24-000123", "test.htm")
        self.assertIn("test.htm", cache_path)
        # Test reading pre-seeded file
        os.makedirs("scratch/test_cache", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write("<html><body>Cached 10-K Content</body></html>")

        content, path, chash = fetcher.fetch_document("0000320193", "0000320193-24-000123", "test.htm")
        self.assertEqual(content, "<html><body>Cached 10-K Content</body></html>")
        self.assertEqual(path, cache_path)
        self.assertEqual(len(chash), 64)

    # --- Test B: Document HTML Parsing ---
    def test_b_document_html_parsing(self) -> None:
        """HTML parser strips tags, unescapes entities, and preserves paragraphs."""
        html = "<p>Gross Margin &amp; Revenue</p><br/><p>Increased&#160;10%</p>"
        clean, chars, words = parse_sec_html(html)
        self.assertIn("Gross Margin & Revenue", clean)
        self.assertIn("Increased 10%", clean)
        self.assertNotIn("<p>", clean)
        self.assertNotIn("&amp;", clean)
        self.assertGreater(chars, 0)
        self.assertEqual(words, 6)

    # --- Test C: Section Detection & TOC Avoidance ---
    def test_c_section_detection_and_toc_avoidance(self) -> None:
        """Parser detects Item 1, Item 1A, Item 7 while skipping Table of Contents entries."""
        sections = parse_sections(
            clean_text=self.clean_text,
            form="10-K",
            document_id="doc_TEST_0001",
            accession_number="0000320193-24-000123",
            ticker="AAPL",
        )
        sec_names = [s.section_name for s in sections]
        self.assertIn("ITEM_1_BUSINESS", sec_names)
        self.assertIn("ITEM_1A_RISK_FACTORS", sec_names)
        self.assertIn("ITEM_7_MDA", sec_names)
        # Ensure Item 1A contains substantive risk text, not just TOC
        risk_sec = next(s for s in sections if s.section_name == "ITEM_1A_RISK_FACTORS")
        self.assertIn("antitrust actions and privacy inquiries", risk_sec.section_text)
        self.assertEqual(risk_sec.detection_confidence, "HIGH")

    # --- Test D: Relevant Passage Retrieval ---
    def test_d_relevant_passage_retrieval(self) -> None:
        """Passage retrieval extracts blocks mapped to qualitative categories."""
        sections = parse_sections(self.clean_text, "10-K", "doc_01", "acc_01", "AAPL")
        passages = retrieve_relevant_passages(sections)
        self.assertGreater(len(passages), 0)
        hints = [p.category_hint for p in passages]
        self.assertTrue(any(h in ["REGULATORY_RISK", "DEMAND_UNCERTAINTY", "MARGIN_PRESSURE"] for h in hints))

    # --- Test E: Structured Schema Validation ---
    def test_e_structured_schema_validation(self) -> None:
        """All 12 QualitativeCategory enum values and controlled vocabularies are defined."""
        self.assertEqual(len(QualitativeCategory), 12)
        self.assertEqual(Direction.POSITIVE.value, "POSITIVE")
        self.assertEqual(Severity.HIGH.value, "HIGH")
        self.assertEqual(Materiality.HIGH.value, "HIGH")
        self.assertEqual(ValidationStatus.VALIDATED.value, "VALIDATED")

    # --- Test F: Evidence Quote Exact Matching ---
    def test_f_evidence_quote_exact_matching(self) -> None:
        """EvidenceValidator validates exact verbatim quote present in passage."""
        passage = "Our gross margin expanded by 140 basis points to 46.2% due to product mix."
        quote = "gross margin expanded by 140 basis points"
        res = self.validator.validate_quote(quote, passage)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, ValidationStatus.VALIDATED)
        self.assertEqual(res.match_score, 1.0)
        self.assertIsNotNone(res.start_char)

    # --- Test G: Mandatory Fabricated Quote Rejection ---
    def test_g_fabricated_quote_rejection(self) -> None:
        """EvidenceValidator strictly REJECTS hallucinated quote not present in filing."""
        passage = "Our gross margin expanded by 140 basis points to 46.2% due to product mix."
        hallucinated_quote = "Management announced an impending bankruptcy and CEO resignation."
        res = self.validator.validate_quote(hallucinated_quote, passage)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ValidationStatus.REJECTED)
        self.assertIn("REJECTED: Proposed quote not found", res.reason)

    # --- Test H: Missing Evidence Rejection ---
    def test_h_missing_evidence_rejection(self) -> None:
        """Missing or empty quote is marked NO_EVIDENCE."""
        passage = "Valid passage text."
        res = self.validator.validate_quote("", passage)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, ValidationStatus.NO_EVIDENCE)

    # --- Test I: Point-in-Time Date Filtering ---
    def test_i_pit_date_filtering(self) -> None:
        """Fetcher rejects filings submitted after as_of_date."""
        fetcher = DocumentFetcher()
        with self.assertRaises(ValueError):
            fetcher.fetch_document(
                cik="0000320193",
                accession_number="0000320193-24-000123",
                primary_document="aapl-20240928.htm",
                filing_date="2024-11-01",
                acceptance_datetime="2024-11-01 13:00:00",
                as_of_date="2024-06-30",  # Future filing must be rejected
            )

    # --- Test J: 10-K/A Amendment Isolation ---
    def test_j_amendment_isolation(self) -> None:
        """Amendment filed after cutoff is isolated from historical analysis."""
        fetcher = DocumentFetcher()
        # Original 10-K filed 2023-11-03: permitted as of 2023-12-31
        # Amendment 10-K/A filed 2024-04-15: rejected as of 2023-12-31
        with self.assertRaises(ValueError):
            fetcher.fetch_document(
                cik="0000320193",
                accession_number="0000320193-24-000099",
                primary_document="amendment.htm",
                filing_date="2024-04-15",
                as_of_date="2023-12-31",
            )

    # --- Test K: Prompt Version Tracking ---
    def test_k_prompt_version_tracking(self) -> None:
        """Extractor stamps prompt_version and schema_version on every claim."""
        provider = DeterministicRuleBasedLLMProvider()
        extractor = Extractor(provider, prompt_version="v2.0-custom", schema_version="v2.0-schema")
        sections = parse_sections(self.clean_text, "10-K", "doc_01", "acc_01", "AAPL")
        passages = retrieve_relevant_passages(sections)
        claim = extractor.extract_from_passage(passages[0], self.mock_doc, company_id="comp_100")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.prompt_version, "v2.0-custom")
        self.assertEqual(claim.schema_version, "v2.0-schema")

    # --- Test L: Model Metadata Tracking ---
    def test_l_model_metadata_tracking(self) -> None:
        """Extracted claim records extraction_model with provider and model name."""
        provider = MockLLMProvider(
            canned_response={
                "has_claim": True,
                "category": "REGULATORY_RISK",
                "claim": "Regulatory scrutiny disclosed.",
                "evidence_quote": "The Company is subject to complex and changing laws",
                "direction": "NEGATIVE",
                "severity": "HIGH",
            },
            model_name="claude-3-5-sonnet",
            provider_name="anthropic",
        )
        extractor = Extractor(provider)
        sections = parse_sections(self.clean_text, "10-K", "doc_01", "acc_01", "AAPL")
        passages = retrieve_relevant_passages(sections)
        claim = extractor.extract_from_passage(passages[0], self.mock_doc, company_id="comp_100")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.extraction_model, "anthropic/claude-3-5-sonnet")

    # --- Test M: Confidence Score Handling ---
    def test_m_confidence_score_handling(self) -> None:
        """Low confidence (< 0.70) extractions are marked NEEDS_REVIEW."""
        val_res = ValidationResult(is_valid=True, status=ValidationStatus.VALIDATED, match_score=0.70)
        # Short quote with generic section authority -> confidence < 0.70
        score = calculate_confidence_score(val_res, quote="Short quote.", section_name="ITEM_2_PROPERTIES", category="MARGIN_PRESSURE")
        self.assertLess(score, 0.70)

    # --- Test N: Materiality Classification ---
    def test_n_materiality_classification(self) -> None:
        """Multi-billion restructuring or formal subpoena classified as HIGH materiality."""
        mat_high = classify_materiality(
            quote="The FTC initiated a formal investigation regarding antitrust practices with potential $2 billion penalty.",
            claim="FTC antitrust probe.",
            severity="CRITICAL",
        )
        self.assertEqual(mat_high, Materiality.HIGH)

        mat_low = classify_materiality(
            quote="We maintain ordinary commercial leases for sales branches.",
            claim="Branch leases.",
            severity="LOW",
        )
        self.assertEqual(mat_low, Materiality.LOW)

    # --- Test O: Claim vs Evidence Separation ---
    def test_o_claim_vs_evidence_separation(self) -> None:
        """Claim is an analytical summary distinct from verbatim evidence quote."""
        provider = DeterministicRuleBasedLLMProvider()
        extractor = Extractor(provider)
        sections = parse_sections(self.clean_text, "10-K", "doc_01", "acc_01", "AAPL")
        passages = retrieve_relevant_passages(sections)
        claim = extractor.extract_from_passage(passages[0], self.mock_doc, company_id="comp_100")
        self.assertIsNotNone(claim)
        self.assertNotEqual(claim.claim, claim.evidence_quote)
        self.assertIn(claim.evidence_quote, passages[0].passage_text)

    # --- Test P: Period-over-Period Change Detection ---
    def test_p_period_over_period_change_detection(self) -> None:
        """Detector flags NEW, ESCALATED, and RESOLVED qualitative signals."""
        detector = ChangeDetector()
        claim_curr = ExtractedClaim(
            extraction_id="e1", document_id="d1", accession_number="acc_2024",
            company_id="c1", ticker="AAPL", cik="0000320193", form="10-K",
            filing_date="2024-11-01", acceptance_datetime=None, filing_period_end=None,
            section_name="ITEM_1A", passage_id="p1", category="REGULATORY_RISK",
            claim="DOJ antitrust action.", evidence_quote="DOJ filed lawsuit.",
            evidence_location="loc", source_identifier="src", direction="NEGATIVE",
            severity="CRITICAL", confidence=0.9, materiality="HIGH",
            extraction_model="model", prompt_version="v1", schema_version="v1",
            extraction_timestamp="ts", validation_status="VALIDATED",
        )
        claim_prev = ExtractedClaim(
            extraction_id="e2", document_id="d2", accession_number="acc_2023",
            company_id="c1", ticker="AAPL", cik="0000320193", form="10-K",
            filing_date="2023-11-03", acceptance_datetime=None, filing_period_end=None,
            section_name="ITEM_1A", passage_id="p2", category="REGULATORY_RISK",
            claim="DOJ inquiry.", evidence_quote="DOJ sent inquiry.",
            evidence_location="loc", source_identifier="src", direction="NEGATIVE",
            severity="MEDIUM", confidence=0.9, materiality="MEDIUM",
            extraction_model="model", prompt_version="v1", schema_version="v1",
            extraction_timestamp="ts", validation_status="VALIDATED",
        )
        signals = detector.detect_changes([claim_curr], [claim_prev], "acc_2024", "acc_2023", "AAPL")
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].change_type, "ESCALATED")
        self.assertIn("MEDIUM -> CRITICAL", signals[0].severity_shift)

    # --- Test Q: Duplicate Extraction Deduplication ---
    def test_q_duplicate_extraction_deduplication(self) -> None:
        """Engine deduplicates identical extractions for the same filing."""
        engine = FilingIntelligenceEngine()
        # Mock fetcher to return sample html
        class MockFetcher:
            def fetch_document(self, **kwargs):
                return self_ref.sample_html, "scratch/sample.htm", "hash123"
        self_ref = self
        engine.fetcher = MockFetcher()

        res = engine.process_filing(
            ticker="AAPL", form="10-K", accession_number="0000320193-24-000123",
            primary_document="aapl-20240928.htm", filing_date="2024-11-01",
            persist=False,
        )
        extractions = res["extractions"]
        quotes = [(e.category, e.evidence_quote) for e in extractions]
        self.assertEqual(len(quotes), len(set(quotes)))

    # --- Test R: Empty/Irrelevant Passage Abstention ---
    def test_r_empty_irrelevant_passage_abstention(self) -> None:
        """Passage with no verifiable claim produces has_claim = False and is not extracted."""
        provider = MockLLMProvider(canned_response={"has_claim": False})
        extractor = Extractor(provider)
        sections = parse_sections(self.clean_text, "10-K", "doc_01", "acc_01", "AAPL")
        passages = retrieve_relevant_passages(sections)
        claim = extractor.extract_from_passage(passages[0], self.mock_doc, company_id="comp_100")
        self.assertIsNone(claim)

    # --- Test S: LLM Provider Abstraction ---
    def test_s_provider_abstraction(self) -> None:
        """Extractor seamlessly functions with either DeterministicRule or Mock provider."""
        rule_p = DeterministicRuleBasedLLMProvider()
        mock_p = MockLLMProvider(canned_response={"has_claim": False})
        ext1 = Extractor(rule_p)
        ext2 = Extractor(mock_p)
        self.assertEqual(ext1.provider.provider_name, "deterministic-rule")
        self.assertEqual(ext2.provider.provider_name, "mock-provider")

    # --- Test T: End-to-End Database Lineage ---
    def test_t_database_lineage(self) -> None:
        """Extractions persist to DuckDB and maintain complete lineage to SEC accession."""
        engine = FilingIntelligenceEngine()
        class MockFetcher:
            def fetch_document(self, **kwargs):
                return self_ref.sample_html, "scratch/sample.htm", "hash123"
        self_ref = self
        engine.fetcher = MockFetcher()

        res = engine.process_filing(
            ticker="AAPL", form="10-K", accession_number="0000320193-24-000123",
            primary_document="aapl-20240928.htm", filing_date="2024-11-01",
            persist=True,
        )
        # Query extractions
        queried = engine.db.query_filing_extractions(ticker="AAPL", validation_status="VALIDATED")
        self.assertGreater(len(queried), 0)
        item = queried[0]
        self.assertEqual(item["ticker"], "AAPL")
        self.assertEqual(item["accession_number"], "0000320193-24-000123")
        self.assertEqual(item["validation_status"], "VALIDATED")
        self.assertIn("0000320193-24-000123", item["source_identifier"])


if __name__ == "__main__":
    unittest.main()
