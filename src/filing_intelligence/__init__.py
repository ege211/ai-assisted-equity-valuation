"""
SEC Filing Qualitative Intelligence & Structured Extraction Package.

Transforms SEC 10-K, 10-Q, and amendment filings into evidence-grounded,
auditable qualitative intelligence features without hallucinations.
"""
from src.filing_intelligence.change_detector import ChangeDetector
from src.filing_intelligence.document_fetcher import DocumentFetcher
from src.filing_intelligence.document_parser import parse_sec_html
from src.filing_intelligence.engine import FilingIntelligenceEngine
from src.filing_intelligence.evidence_validator import EvidenceValidator
from src.filing_intelligence.extractor import Extractor
from src.filing_intelligence.llm_provider import (
    DeterministicRuleBasedLLMProvider,
    LLMProvider,
    MockLLMProvider,
)
from src.filing_intelligence.retrieval import (
    CATEGORY_SIGNATURES,
    chunk_section_into_passages,
    retrieve_relevant_passages,
)
from src.filing_intelligence.schemas import (
    ChangeSignal,
    ChangeType,
    Direction,
    ExtractedClaim,
    ExtractionRunMetadata,
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

__all__ = [
    "FilingIntelligenceEngine",
    "DocumentFetcher",
    "parse_sec_html",
    "parse_sections",
    "chunk_section_into_passages",
    "retrieve_relevant_passages",
    "CATEGORY_SIGNATURES",
    "EvidenceValidator",
    "calculate_confidence_score",
    "classify_materiality",
    "ChangeDetector",
    "Extractor",
    "LLMProvider",
    "DeterministicRuleBasedLLMProvider",
    "MockLLMProvider",
    "QualitativeCategory",
    "Direction",
    "Severity",
    "Materiality",
    "ValidationStatus",
    "ChangeType",
    "FilingDocument",
    "FilingSection",
    "FilingPassage",
    "ExtractedClaim",
    "ChangeSignal",
    "ValidationResult",
    "ExtractionRunMetadata",
]
