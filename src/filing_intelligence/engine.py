"""
Filing Intelligence Engine Orchestrator.

Integrates:
- Document fetching and local caching
- HTML text normalization
- Structural section detection
- Relevance passage retrieval
- LLM structured extraction
- Exact evidence verification
- Confidence and materiality scoring
- Period-over-period change detection
- Relational DuckDB persistence
"""
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.filing_intelligence.change_detector import ChangeDetector
from src.filing_intelligence.document_fetcher import DocumentFetcher
from src.filing_intelligence.document_parser import parse_sec_html
from src.filing_intelligence.evidence_validator import EvidenceValidator
from src.filing_intelligence.extractor import Extractor
from src.filing_intelligence.llm_provider import (
    DeterministicRuleBasedLLMProvider,
    LLMProvider,
)
from src.filing_intelligence.retrieval import retrieve_relevant_passages
from src.filing_intelligence.schemas import (
    ChangeSignal,
    ExtractedClaim,
    FilingDocument,
    FilingPassage,
    FilingSection,
)
from src.filing_intelligence.section_parser import parse_sections

logger = logging.getLogger(__name__)


class FilingIntelligenceEngine:
    """Production SEC Filing Qualitative Intelligence Engine."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        db_path: str = DEFAULT_DB_PATH,
        llm_provider: Optional[LLMProvider] = None,
        fetcher: Optional[DocumentFetcher] = None,
    ) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)
        self.provider = llm_provider or DeterministicRuleBasedLLMProvider()
        self.fetcher = fetcher or DocumentFetcher()
        self.validator = EvidenceValidator()
        self.extractor = Extractor(provider=self.provider, validator=self.validator)
        self.change_detector = ChangeDetector()

    def process_filing(
        self,
        ticker: str,
        form: str,
        accession_number: str,
        primary_document: str,
        filing_date: str,
        acceptance_datetime: Optional[str] = None,
        as_of_date: Optional[str] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end extraction pipeline on a single SEC filing.
        """
        start_time = time.time()
        ticker = ticker.upper()

        # 1. Company Metadata
        with self.db.get_connection() as conn:
            comp = conn.execute(
                "SELECT company_id, cik, sector FROM companies WHERE ticker = ?",
                [ticker],
            ).fetchone()
            if not comp:
                raise ValueError(f"Ticker {ticker} not found in companies table.")
            company_id, cik, sector = comp

        # 2. Fetch Document with Point-in-Time Enforcement
        raw_html, file_path, content_hash = self.fetcher.fetch_document(
            cik=cik,
            accession_number=accession_number,
            primary_document=primary_document,
            filing_date=filing_date,
            acceptance_datetime=acceptance_datetime,
            as_of_date=as_of_date,
        )

        # 3. Clean and Normalize Text
        clean_text, char_count, word_count = parse_sec_html(raw_html)
        doc_id = f"doc_{ticker}_{accession_number.replace('-', '')[:14]}"

        doc = FilingDocument(
            document_id=doc_id,
            accession_number=accession_number,
            cik=cik,
            ticker=ticker,
            form=form,
            filing_date=filing_date,
            acceptance_datetime=acceptance_datetime,
            primary_document=primary_document,
            content_hash=content_hash,
            char_count=char_count,
            word_count=word_count,
            file_path=file_path,
            clean_text=clean_text,
        )

        # 4. Parse Structural Sections
        sections = parse_sections(
            clean_text=clean_text,
            form=form,
            document_id=doc_id,
            accession_number=accession_number,
            ticker=ticker,
        )

        # 5. Retrieve Targeted Category Passages
        passages = retrieve_relevant_passages(sections)

        # 6. Extract Claims & Validate Evidence
        extractions: List[ExtractedClaim] = []
        for p in passages:
            claim = self.extractor.extract_from_passage(
                passage=p,
                document=doc,
                company_id=company_id,
            )
            if claim:
                extractions.append(claim)

        # Deduplicate extractions by (category, evidence_quote)
        unique_extractions: List[ExtractedClaim] = []
        seen_quotes = set()
        for e in extractions:
            key = (e.category, e.evidence_quote.strip().lower()[:60])
            if key not in seen_quotes:
                seen_quotes.add(key)
                unique_extractions.append(e)

        duration = time.time() - start_time

        # 7. Database Persistence
        if persist:
            self._persist_filing(doc, sections, passages, unique_extractions, duration)

        validated_count = sum(1 for e in unique_extractions if e.validation_status == "VALIDATED")
        rejected_count = sum(1 for e in unique_extractions if e.validation_status == "REJECTED")

        return {
            "document": doc,
            "sections": sections,
            "passages": passages,
            "extractions": unique_extractions,
            "total_passages": len(passages),
            "total_extractions": len(unique_extractions),
            "validated_count": validated_count,
            "rejected_count": rejected_count,
            "duration_sec": duration,
        }

    def _persist_filing(
        self,
        doc: FilingDocument,
        sections: List[FilingSection],
        passages: List[FilingPassage],
        extractions: List[ExtractedClaim],
        duration_sec: float,
    ) -> None:
        """Store extraction and document artifacts into DuckDB."""
        # 1. Document Record
        doc_record = [{
            "document_id": doc.document_id,
            "accession_number": doc.accession_number,
            "cik": doc.cik,
            "ticker": doc.ticker,
            "form": doc.form,
            "filing_date": doc.filing_date,
            "acceptance_datetime": doc.acceptance_datetime,
            "primary_document": doc.primary_document,
            "file_path": doc.file_path,
            "content_hash": doc.content_hash,
            "char_count": doc.char_count,
            "word_count": doc.word_count,
        }]
        self.db.insert_filing_documents(doc_record)

        # 2. Section Records
        sec_records = [
            {
                "section_id": s.section_id,
                "document_id": s.document_id,
                "accession_number": s.accession_number,
                "ticker": s.ticker,
                "section_name": s.section_name,
                "section_title": s.section_title,
                "start_char": s.start_char,
                "end_char": s.end_char,
                "char_count": s.char_count,
                "detection_confidence": s.detection_confidence,
                "section_text": s.section_text[:1000] if s.section_text else None,
            }
            for s in sections
        ]
        self.db.insert_filing_sections(sec_records)

        # 3. Passage Records
        pass_records = [
            {
                "passage_id": p.passage_id,
                "section_id": p.section_id,
                "document_id": p.document_id,
                "accession_number": p.accession_number,
                "ticker": p.ticker,
                "section_name": p.section_name,
                "category_hint": p.category_hint,
                "passage_index": p.passage_index,
                "start_char": p.start_char,
                "end_char": p.end_char,
                "passage_text": p.passage_text,
            }
            for p in passages
        ]
        self.db.insert_filing_passages(pass_records)

        # 4. Extraction Records
        ext_records = [
            {
                "extraction_id": e.extraction_id,
                "document_id": e.document_id,
                "accession_number": e.accession_number,
                "company_id": e.company_id,
                "ticker": e.ticker,
                "cik": e.cik,
                "form": e.form,
                "filing_date": e.filing_date,
                "acceptance_datetime": e.acceptance_datetime,
                "filing_period_end": e.filing_period_end,
                "section_name": e.section_name,
                "passage_id": e.passage_id,
                "category": e.category,
                "claim": e.claim,
                "evidence_quote": e.evidence_quote,
                "evidence_location": e.evidence_location,
                "source_identifier": e.source_identifier,
                "direction": e.direction,
                "severity": e.severity,
                "confidence": e.confidence,
                "materiality": e.materiality,
                "extraction_model": e.extraction_model,
                "prompt_version": e.prompt_version,
                "schema_version": e.schema_version,
                "extraction_timestamp": e.extraction_timestamp,
                "validation_status": e.validation_status,
                "validation_reason": e.validation_reason,
            }
            for e in extractions
        ]
        self.db.insert_filing_extractions(ext_records)

        # 5. Execution Run Log
        val_count = sum(1 for e in extractions if e.validation_status == "VALIDATED")
        rej_count = sum(1 for e in extractions if e.validation_status == "REJECTED")
        now_str = datetime.now(timezone.utc).isoformat()
        run_record = [{
            "run_id": f"run_{doc.ticker}_{uuid.uuid4().hex[:8]}",
            "run_timestamp": now_str,
            "model_name": self.provider.model_name,
            "provider_name": self.provider.provider_name,
            "prompt_version": self.extractor.prompt_version,
            "schema_version": self.extractor.schema_version,
            "temperature": 0.0,
            "total_passages_processed": len(passages),
            "total_extractions_generated": len(extractions),
            "total_validated": val_count,
            "total_rejected": rej_count,
            "execution_duration_sec": round(duration_sec, 3),
        }]
        self.db.insert_llm_extraction_runs(run_record)

    def compare_filings(
        self,
        current_accession: str,
        previous_accession: str,
        ticker: str,
        persist: bool = True,
    ) -> List[ChangeSignal]:
        """
        Compare qualitative disclosures between two filings.
        """
        curr_claims_raw = self.db.query_filing_extractions(ticker=ticker, validation_status="VALIDATED")
        curr_claims = [
            ExtractedClaim(**c) for c in curr_claims_raw if c["accession_number"] == current_accession
        ]
        prev_claims = [
            ExtractedClaim(**c) for c in curr_claims_raw if c["accession_number"] == previous_accession
        ]

        signals = self.change_detector.detect_changes(
            current_claims=curr_claims,
            previous_claims=prev_claims,
            current_accession=current_accession,
            previous_accession=previous_accession,
            ticker=ticker,
        )

        if persist and signals:
            sig_records = [
                {
                    "signal_id": s.signal_id,
                    "ticker": s.ticker,
                    "current_accession": s.current_accession,
                    "previous_accession": s.previous_accession,
                    "category": s.category,
                    "change_type": s.change_type,
                    "current_claim": s.current_claim,
                    "previous_claim": s.previous_claim,
                    "direction_shift": s.direction_shift,
                    "severity_shift": s.severity_shift,
                    "materiality": s.materiality,
                    "summary": s.summary,
                }
                for s in signals
            ]
            self.db.insert_filing_change_signals(sig_records)

        return signals

    def process_company_pair(
        self,
        ticker: str,
        as_of_date: Optional[str] = "2024-12-31",
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Process the latest two comparable 10-K filings for a company and detect changes.
        """
        ticker = ticker.upper()

        query = """
        SELECT
            ticker, form, filing_date::VARCHAR, acceptance_datetime::VARCHAR,
            accession_number, primary_document
        FROM filings
        WHERE ticker = ? AND form IN ('10-K', '10-K/A')
        """
        params: List[Any] = [ticker]
        if as_of_date:
            query += " AND (acceptance_datetime::VARCHAR <= (? || ' 23:59:59') OR filing_date <= ?::DATE)"
            params.append(as_of_date)
            params.append(as_of_date)

        query += " ORDER BY filing_date DESC, acceptance_datetime DESC LIMIT 2;"

        with self.db.get_connection() as conn:
            filings = conn.execute(query, params).fetchall()

        if not filings:
            return {"ticker": ticker, "status": "NO_FILINGS_FOUND"}

        # Process Current Filing
        curr_row = filings[0]
        curr_res = self.process_filing(
            ticker=curr_row[0],
            form=curr_row[1],
            accession_number=curr_row[4],
            primary_document=curr_row[5],
            filing_date=curr_row[2],
            acceptance_datetime=curr_row[3],
            as_of_date=as_of_date,
            persist=persist,
        )

        signals: List[ChangeSignal] = []

        # Process Previous Filing if available
        prev_res = None
        if len(filings) > 1:
            prev_row = filings[1]
            prev_res = self.process_filing(
                ticker=prev_row[0],
                form=prev_row[1],
                accession_number=prev_row[4],
                primary_document=prev_row[5],
                filing_date=prev_row[2],
                acceptance_datetime=prev_row[3],
                as_of_date=as_of_date,
                persist=persist,
            )

            # Detect Changes
            signals = self.compare_filings(
                current_accession=curr_row[4],
                previous_accession=prev_row[4],
                ticker=ticker,
                persist=persist,
            )

        return {
            "ticker": ticker,
            "current_filing": curr_res,
            "previous_filing": prev_res,
            "change_signals": signals,
            "status": "SUCCESS",
        }
