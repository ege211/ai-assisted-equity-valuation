"""
Strongly-Typed Schemas and Controlled Vocabularies for SEC Filing Intelligence.

Defines:
- 12 Qualitative Categories
- Controlled vocabularies (Direction, Severity, Materiality, ValidationStatus, ChangeType)
- Data contracts for documents, sections, passages, claims, evidence, and change signals
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QualitativeCategory(str, Enum):
    """12 Standard Qualitative Analytical Categories."""
    REGULATORY_RISK = "REGULATORY_RISK"
    LITIGATION_RISK = "LITIGATION_RISK"
    DEMAND_UNCERTAINTY = "DEMAND_UNCERTAINTY"
    MARGIN_PRESSURE = "MARGIN_PRESSURE"
    STRATEGIC_CHANGE = "STRATEGIC_CHANGE"
    CAPITAL_ALLOCATION_CHANGE = "CAPITAL_ALLOCATION_CHANGE"
    GUIDANCE_DIRECTION = "GUIDANCE_DIRECTION"
    LIQUIDITY_RISK = "LIQUIDITY_RISK"
    SUPPLY_CHAIN_RISK = "SUPPLY_CHAIN_RISK"
    COMPETITIVE_PRESSURE = "COMPETITIVE_PRESSURE"
    MATERIAL_BUSINESS_CHANGE = "MATERIAL_BUSINESS_CHANGE"
    MANAGEMENT_OUTLOOK = "MANAGEMENT_OUTLOOK"


class Direction(str, Enum):
    """Controlled directional polarity of a disclosure or sentiment."""
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    """Assessed risk or operational severity level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class Materiality(str, Enum):
    """Analytical assessment of economic and financial materiality."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ValidationStatus(str, Enum):
    """Status of evidence quote verification against source filing text."""
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NO_EVIDENCE = "NO_EVIDENCE"


class ChangeType(str, Enum):
    """Period-over-period delta category for disclosure change detection."""
    NEW = "NEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    PERSISTENT = "PERSISTENT"
    MODIFIED = "MODIFIED"


@dataclass
class FilingDocument:
    """Primary SEC filing document metadata and body content."""
    document_id: str
    accession_number: str
    cik: str
    ticker: str
    form: str
    filing_date: str
    acceptance_datetime: Optional[str]
    primary_document: str
    content_hash: str
    char_count: int
    word_count: int
    file_path: Optional[str] = None
    clean_text: Optional[str] = None


@dataclass
class FilingSection:
    """Identified structural section within a filing."""
    section_id: str
    document_id: str
    accession_number: str
    ticker: str
    section_name: str
    section_title: str
    start_char: int
    end_char: int
    char_count: int
    detection_confidence: str  # HIGH, UNCERTAIN, MISSING
    section_text: Optional[str] = None


@dataclass
class FilingPassage:
    """Discrete, identifiable text passage chunk for retrieval."""
    passage_id: str
    section_id: str
    document_id: str
    accession_number: str
    ticker: str
    section_name: str
    category_hint: str
    passage_index: int
    start_char: int
    end_char: int
    passage_text: str


@dataclass
class ValidationResult:
    """Outcome of evidence quote verification."""
    is_valid: bool
    status: ValidationStatus
    reason: Optional[str] = None
    matched_quote: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    match_score: float = 0.0


@dataclass
class ExtractedClaim:
    """Structured qualitative intelligence item with verified evidence."""
    extraction_id: str
    document_id: str
    accession_number: str
    company_id: str
    ticker: str
    cik: str
    form: str
    filing_date: str
    acceptance_datetime: Optional[str]
    filing_period_end: Optional[str]
    section_name: str
    passage_id: str
    category: str
    claim: str
    evidence_quote: str
    evidence_location: str
    source_identifier: str
    direction: str
    severity: str
    confidence: float
    materiality: str
    extraction_model: str
    prompt_version: str
    schema_version: str
    extraction_timestamp: str
    validation_status: str
    validation_reason: Optional[str] = None


@dataclass
class ChangeSignal:
    """Structured delta between two filing periods."""
    signal_id: str
    ticker: str
    current_accession: str
    previous_accession: str
    category: str
    change_type: str
    current_claim: Optional[str]
    previous_claim: Optional[str]
    direction_shift: Optional[str]
    severity_shift: Optional[str]
    materiality: str
    summary: str


@dataclass
class ExtractionRunMetadata:
    """Audit record of an LLM extraction execution run."""
    run_id: str
    run_timestamp: str
    model_name: str
    provider_name: str
    prompt_version: str
    schema_version: str
    temperature: Optional[float]
    total_passages_processed: int
    total_extractions_generated: int
    total_validated: int
    total_rejected: int
    execution_duration_sec: float
