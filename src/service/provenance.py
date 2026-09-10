"""
AI-Assisted Equity Valuation & Investment Intelligence Platform
Phase 8F — Provenance, Lineage & Change Intelligence Contracts
File: src/service/provenance.py

Structured data contracts representing:
1. SourceProvenanceDTO: Canonical source identification and SEC EDGAR metadata.
2. LineageStepDTO & DataLineageDTO: Step-by-step mathematical lineage pipelines.
3. QualitativeEvidenceLineageDTO: 6-stage qualitative disclosure lineage.
4. ValuationBridgeLineageDTO: Traceability from qualitative signal to valuation delta.
5. FundamentalChangeDTO & WhatChangedResponse: Structured form-over-form change intelligence.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SourceProvenanceDTO:
    """Detailed attribution for any data point ingested into the platform."""
    source_name: str = "SEC EDGAR"
    source_type: str = "FILING_XBRL"  # FILING_XBRL, FILING_NARRATIVE, MACRO_TREASURY, MARKET_PRICE, DERIVED_MODEL, SEC_FILING, DERIVED
    source_identifier: str = ""
    accession_number: Optional[str] = None
    form: Optional[str] = None
    filing_date: Optional[str] = None
    acceptance_datetime: Optional[str] = None
    fiscal_period: Optional[str] = None
    fiscal_year: Optional[int] = None
    section_name: Optional[str] = None
    concept: Optional[str] = None
    unit: Optional[str] = None
    observation_date: Optional[str] = None
    pit_cutoff: Optional[str] = None
    is_pit_compliant: bool = True
    provenance_note: Optional[str] = None

    # Unified Phase 8F Aliases & Extended Fields
    primary_source: Optional[str] = None
    sec_url: Optional[str] = None
    calculation_method: Optional[str] = None
    source_concepts: List[str] = field(default_factory=list)
    as_of_date: Optional[str] = None
    mode: str = "LIVE"
    pit_rejection_reason: Optional[str] = None

    def get_primary_source(self) -> str:
        if self.primary_source:
            return self.primary_source
        return f"{self.source_name} Form {self.form or 'N/A'} / Accession {self.accession_number or 'N/A'}"

    def get_sec_url(self) -> Optional[str]:
        if self.sec_url:
            return self.sec_url
        if self.accession_number:
            acc_clean = self.accession_number.replace("-", "")
            return f"https://www.sec.gov/Archives/edgar/data/{acc_clean}/{self.accession_number}.txt"
        return None


@dataclass(frozen=True)
class LineageStepDTO:
    """A discrete transformation or dependency step in a numerical lineage chain."""
    step_index: int = 1
    stage_name: str = ""  # e.g., "1. PRIMARY SOURCE", "2. NORMALIZED STATEMENT", etc.
    metric_name: str = ""
    input_values: Dict[str, Any] = field(default_factory=dict)
    output_value: Any = None
    transformation_description: str = ""
    source_provenance: Optional[SourceProvenanceDTO] = None

    # Unified Phase 8F Aliases
    step_number: Optional[int] = None
    step_name: Optional[str] = None
    description: Optional[str] = None
    transformation_rule: Optional[str] = None


@dataclass(frozen=True)
class DataLineageDTO:
    """Complete mathematical lineage pipeline for a key valuation or accounting metric."""
    entity_ticker: str = ""
    target_metric: str = ""  # e.g., "DCF Fair Value per Share", "Cost of Capital (WACC)"
    final_value: Any = None
    unit: str = ""
    as_of_date: Optional[str] = None
    mode: str = "LIVE"
    steps: List[LineageStepDTO] = field(default_factory=list)
    summary_explanation: str = ""

    # Unified Phase 8F Aliases
    metric_name: Optional[str] = None
    calculation_summary: Optional[str] = None
    source_provenance: Optional[SourceProvenanceDTO] = None


@dataclass(frozen=True)
class QualitativeEvidenceLineageDTO:
    """Full 6-stage trace for an individual qualitative disclosure."""
    ticker: str = ""
    claim_id: str = ""
    company_name: str = ""
    cik: str = ""
    form: str = ""
    accession_number: str = ""
    filing_date: str = ""
    acceptance_datetime: str = ""
    section_name: str = ""
    passage_id: str = ""
    verbatim_quote: str = ""
    extraction_category: str = ""
    direction: str = ""  # POSITIVE, NEGATIVE, NEUTRAL
    severity: str = ""   # LOW, MEDIUM, HIGH
    materiality: str = "" # HIGH, MEDIUM, LOW
    confidence: float = 1.0
    validation_status: str = "VALIDATED"  # VALIDATED, REJECTED, QUARANTINED
    validation_reason: Optional[str] = None
    valuation_bridge_link: Optional[str] = None

    # Unified Phase 8F 6-Stage Mapping Dictionaries
    category: Optional[str] = None
    filing_stage: Dict[str, Any] = field(default_factory=dict)
    section_stage: Dict[str, Any] = field(default_factory=dict)
    passage_stage: Dict[str, Any] = field(default_factory=dict)
    extraction_stage: Dict[str, Any] = field(default_factory=dict)
    validation_stage: Dict[str, Any] = field(default_factory=dict)
    signal_stage: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValuationBridgeLineageDTO:
    """Detailed provenance linking a qualitative disclosure to a valuation model adjustment."""
    ticker: str = ""
    comparison_id: str = ""
    valuation_date: str = ""
    primary_signal_category: str = ""
    key_assumption_adjusted: str = ""
    adjustment_magnitude: float = 0.0
    baseline_fair_value: float = 0.0
    enhanced_fair_value: float = 0.0
    fair_value_pct_change: float = 0.0
    rationale: str = ""
    supporting_evidence_quote: str = ""
    accession_number: str = ""
    filing_date: str = ""
    acceptance_datetime: Optional[str] = None
    validation_status: str = "VALIDATED"

    # Unified Phase 8F Aliases
    evidence_citation: Optional[str] = None
    is_pit_valid: bool = True


@dataclass(frozen=True)
class FundamentalChangeDTO:
    """Deterministic comparison of a financial metric between two reporting periods."""
    metric_name: str = ""
    category: str = "FINANCIAL"  # "REVENUE", "PROFITABILITY", "CASH_FLOW", "LIQUIDITY_DEBT", "VALUATION_ASSUMPTION"
    current_period: str = ""
    current_value: Optional[float] = None
    previous_period: str = ""
    previous_value: Optional[float] = None
    absolute_change: Optional[float] = None
    percent_change: Optional[float] = None
    unit: str = "$"
    direction: str = "UNCHANGED"  # "INCREASED", "DECREASED", "UNCHANGED"
    is_meaningful: bool = True  # Exceeds deterministic noise threshold
    explanation: str = ""
    source_provenance: Optional[SourceProvenanceDTO] = None

    # Unified Phase 8F Aliases
    percentage_change: Optional[float] = None
    interpretation: Optional[str] = None


@dataclass(frozen=True)
class WhatChangedResponse:
    """Comprehensive form-over-form change intelligence report."""
    ticker: str = ""
    mode: str = "LIVE"
    as_of_date: Optional[str] = None
    information_cutoff: str = "LIVE"
    current_period_label: str = ""
    previous_period_label: str = ""
    fundamental_changes: List[FundamentalChangeDTO] = field(default_factory=list)
    qualitative_changes: List[Any] = field(default_factory=list)  # ChangeSignalDTO
    valuation_assumption_changes: List[FundamentalChangeDTO] = field(default_factory=list)
    summary_narrative: str = ""
    is_pit_valid: bool = True

    # Unified Phase 8F Aliases
    current_period: Optional[str] = None
    previous_period: Optional[str] = None
    current_accession: Optional[str] = None
    previous_accession: Optional[str] = None
    valuation_changes: List[FundamentalChangeDTO] = field(default_factory=list)
    qualitative_signals: List[Any] = field(default_factory=list)
    is_longitudinal_valid: Optional[bool] = None
    rejection_reason: Optional[str] = None
