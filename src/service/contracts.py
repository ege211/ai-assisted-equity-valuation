"""
Data Transfer Objects (DTOs) and Service Contracts for the Platform Service Layer.

Defines strongly typed, frozen boundaries between core domain engines
(valuation, accounting normalization, filing intelligence, research) and future UI presentation layers.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.service.provenance import (
    SourceProvenanceDTO,
    LineageStepDTO,
    DataLineageDTO,
    QualitativeEvidenceLineageDTO,
    ValuationBridgeLineageDTO,
    FundamentalChangeDTO,
    WhatChangedResponse,
)


# ==============================================================================
# 1. SERVICE EXCEPTION HIERARCHY
# ==============================================================================

class PlatformServiceError(Exception):
    """Base exception for all service-layer failures."""
    pass


class InvalidRequestError(PlatformServiceError):
    """Raised when an incoming client request fails structural or business validation."""
    pass


class InvalidTickerError(InvalidRequestError):
    """Raised when a requested ticker is empty, malformed, or contains invalid characters."""
    pass


class UnsupportedModeError(InvalidRequestError):
    """Raised when a request specifies an unrecognized execution mode (not LIVE or HISTORICAL)."""
    pass


class MissingPITDateError(InvalidRequestError):
    """Raised when a HISTORICAL mode request fails to provide an as_of_date."""
    pass


class MissingCompanyError(PlatformServiceError):
    """Raised when the requested company is not present in the platform universe."""
    pass


class ValuationUnavailableError(PlatformServiceError):
    """Raised when deterministic valuation inputs are missing or cannot be computed as of the requested date."""
    pass


class FilingIntelligenceUnavailableError(PlatformServiceError):
    """Raised when qualitative disclosures are missing or unextractable for the requested period."""
    pass


class TemporalLeakageError(PlatformServiceError):
    """Raised when an information date violates strict point-in-time constraints (look-ahead leak)."""
    pass


# ==============================================================================
# 2. REQUEST CONTRACTS
# ==============================================================================

@dataclass(frozen=True)
class CompanyRequest:
    """Standardized user request to analyze an equity issuer."""
    ticker: str
    as_of_date: Optional[str] = None  # None indicates LIVE mode
    mode: str = "LIVE"  # "LIVE" or "HISTORICAL"

    def __post_init__(self) -> None:
        clean_ticker = self.ticker.strip().upper() if self.ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        object.__setattr__(self, "ticker", clean_ticker)

        clean_mode = self.mode.strip().upper() if self.mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported execution mode '{self.mode}'. Must be 'LIVE' or 'HISTORICAL'.")
        object.__setattr__(self, "mode", clean_mode)

        if clean_mode == "HISTORICAL" and not self.as_of_date:
            raise MissingPITDateError("Historical analysis requires an explicit as_of_date (YYYY-MM-DD).")


@dataclass(frozen=True)
class ValuationRequest:
    """Specific request to execute deterministic valuation on a covered enterprise."""
    ticker: str
    as_of_date: Optional[str] = None
    mode: str = "LIVE"
    persist: bool = False

    def __post_init__(self) -> None:
        clean_ticker = self.ticker.strip().upper() if self.ticker else ""
        if not clean_ticker:
            raise InvalidTickerError("Ticker symbol cannot be empty.")
        object.__setattr__(self, "ticker", clean_ticker)

        clean_mode = self.mode.strip().upper() if self.mode else "LIVE"
        if clean_mode not in ("LIVE", "HISTORICAL"):
            raise UnsupportedModeError(f"Unsupported execution mode '{self.mode}'. Must be 'LIVE' or 'HISTORICAL'.")
        object.__setattr__(self, "mode", clean_mode)

        if clean_mode == "HISTORICAL" and not self.as_of_date:
            raise MissingPITDateError("Historical valuation requires an explicit as_of_date (YYYY-MM-DD).")


# ==============================================================================
# 3. COMPANY PROFILE CONTRACT
# ==============================================================================

@dataclass(frozen=True)
class CompanyProfile:
    """Enterprise metadata and filing coverage snapshot."""
    ticker: str
    company_name: str
    cik: str
    sector: str
    fiscal_year_end_month: Optional[int] = None
    latest_filing_date: Optional[str] = None
    covered_filings_count: int = 0


# ==============================================================================
# 4. VALUATION CONTRACTS
# ==============================================================================

@dataclass(frozen=True)
class ForecastPeriodDTO:
    """Discrete 1-year operational forecast projection."""
    forecast_year_index: int
    fiscal_year: int
    revenue: float
    revenue_growth: float
    ebit_margin: float
    ebit: float
    tax_rate: float
    tax_expense: float
    nopat: float
    da: float
    capex: float
    delta_nwc: float
    fcff: float
    discount_factor: float
    pv_fcff: float


@dataclass(frozen=True)
class ValuationScenarioSummary:
    """Summary metrics for a specific forecast scenario (Base, Bull, or Bear)."""
    scenario_name: str
    fair_value_per_share: float
    enterprise_value: float
    equity_value: float
    wacc: float
    terminal_growth: float
    upside_downside: Optional[float] = None


@dataclass(frozen=True)
class SensitivityGridDTO:
    """Two-dimensional valuation sensitivity matrix."""
    parameter_1_name: str
    parameter_1_values: List[float]
    parameter_2_name: str
    parameter_2_values: List[float]
    matrix: List[List[Optional[float]]]


@dataclass(frozen=True)
class RelativeValuationSummary:
    """Relative multiples benchmarking against sector peers."""
    multiple_name: str
    company_multiple: Optional[float]
    peer_median_multiple: Optional[float]
    implied_equity_value: Optional[float]
    implied_fair_value_per_share: Optional[float]
    benchmark_source: str


@dataclass(frozen=True)
class ValuationResponse:
    """Complete, immutable output package from the Deterministic Valuation Engine."""
    ticker: str
    company_id: str
    valuation_date: str
    as_of_date: str
    valuation_mode: str
    current_share_price: Optional[float]
    fair_value_per_share: float  # Base scenario fair value
    enterprise_value: float
    equity_value: float
    total_debt: float
    cash: float
    net_debt: float
    diluted_shares: float
    upside_downside: Optional[float]
    wacc: float
    terminal_growth: float
    cost_of_equity: float
    cost_of_debt: float
    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    revenue_growth_summary: str
    ebit_margin_summary: str
    forecast_periods: List[ForecastPeriodDTO]
    scenarios: Dict[str, ValuationScenarioSummary]
    sensitivities: Dict[str, SensitivityGridDTO]
    relative_multiples: List[RelativeValuationSummary]
    lineage: str
    data_sources: str
    assumption_sources: str
    calculation_status: str
    status_reason: Optional[str] = None
    valuation_lineage: Optional[DataLineageDTO] = None
    wacc_lineage: Optional[DataLineageDTO] = None


# ==============================================================================
# 5. FILING INTELLIGENCE CONTRACTS
# ==============================================================================

@dataclass(frozen=True)
class FilingSignal:
    """Structured qualitative claim anchored to verbatim filing evidence."""
    signal_id: str
    category: str
    claim: str
    evidence_quote: str
    evidence_location: str
    source_identifier: str
    direction: str
    severity: str
    confidence: float
    materiality: str
    validation_status: str
    validation_reason: Optional[str] = None
    form: str = ""
    filing_date: str = ""
    acceptance_datetime: Optional[str] = None
    section_name: str = ""
    accession_number: str = ""


@dataclass(frozen=True)
class ChangeSignalDTO:
    """Period-over-period delta in qualitative disclosures."""
    signal_id: str
    ticker: str
    category: str
    change_type: str
    current_claim: Optional[str]
    previous_claim: Optional[str]
    direction_shift: Optional[str]
    severity_shift: Optional[str]
    materiality: str
    summary: str
    current_accession: str
    previous_accession: str
    current_filing_date: Optional[str] = None
    previous_filing_date: Optional[str] = None


@dataclass(frozen=True)
class ValuationBridgeRecordDTO:
    """Audited valuation bridge linkage connecting qualitative signals to DCF adjustments."""
    comparison_id: str
    ticker: str
    valuation_date: str
    primary_signal_category: str
    key_assumption_adjusted: str
    adjustment_magnitude: float
    evidence_citation: str
    baseline_fair_value: float
    enhanced_fair_value: float
    fair_value_pct_change: float


@dataclass(frozen=True)
class FilingIntelligenceResponse:
    """Complete qualitative disclosure intelligence package for an issuer."""
    ticker: str
    as_of_date: Optional[str]
    mode: str
    total_claims_retrieved: int
    validated_claims_count: int
    rejected_claims_count: int
    signals: List[FilingSignal]
    change_signals: List[ChangeSignalDTO]
    covered_accessions: List[str]
    evidence_status_summary: str
    valuation_bridge: Optional[ValuationBridgeRecordDTO] = None


# ==============================================================================
# 6. RESEARCH DISCLOSURE CONTRACT (PHASE 7 AUDITED BASELINE)
# ==============================================================================

@dataclass(frozen=True)
class ResearchDisclosure:
    """Audited empirical research baseline communicating Phase 7 findings and limitations."""
    experiment_name: str = "Phase 7 Chronological Walk-Forward Panel"
    primary_target: str = "forward_ebit_margin_change"
    sample_size_longitudinal: int = 46
    walk_forward_folds: int = 2
    baseline_mae: float = 0.0777
    enhanced_mae: float = 0.0781
    delta_mae_pct: float = -0.60
    p_value: float = 0.2335
    hypothesis_decision: str = "Fail to reject H0"
    key_takeaway: str = (
        "Under strict chronological out-of-sample validation, filing-derived qualitative features "
        "do not provide statistically significant incremental predictive power beyond conventional "
        "financial information in the current sample."
    )
    curse_of_dimensionality_finding: str = (
        "Model B Omnibus (22 features) degraded MAE by -13.14% (p = 0.0045), confirming parameter "
        "estimation variance in moderate samples."
    )
    filing_only_parity_finding: str = (
        "The filing-only specification performed approximately at parity with the fundamental baseline "
        "(MAE 0.0771 vs 0.0777, p = 0.8714), providing no statistically significant evidence of incremental value."
    )
    limitations: List[str] = field(default_factory=lambda: [
        "Small longitudinal sample size (N=46 shared complete cases across 2 annual cohorts).",
        "Two-fold walk-forward validation represents a proof-of-concept multi-period evaluation, not broad multi-cycle regime generalization.",
        "Fixed 30-company large-cap universe entails inherent survivorship bias.",
    ])


# ==============================================================================
# 7. AGGREGATE ANALYSIS RESPONSE CONTRACT
# ==============================================================================

@dataclass(frozen=True)
class AnalysisResponse:
    """Unified response package returned by PlatformService.analyze_company()."""
    request: CompanyRequest
    profile: CompanyProfile
    valuation: Optional[ValuationResponse] = None
    filing_intelligence: Optional[FilingIntelligenceResponse] = None
    research_disclosure: ResearchDisclosure = field(default_factory=ResearchDisclosure)
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    status: str = "SUCCESS"  # "SUCCESS", "PARTIAL", "ERROR"
    error_message: Optional[str] = None
    what_changed: Optional[WhatChangedResponse] = None


# ==============================================================================
# 8. PHASE 8C: FUNDAMENTALS & FILING EXPLORER CONTRACTS
# ==============================================================================

@dataclass(frozen=True)
class FinancialPeriodDTO:
    """Canonical normalized financial statement period record."""
    period_type: str  # "ANNUAL" or "QUARTERLY"
    fiscal_year: int
    fiscal_period: str  # "FY", "Q1", "Q2", "Q3", "Q4"
    period_end_date: str
    filing_date: str
    acceptance_datetime: str
    form: str
    accession_number: str
    revenue: Optional[float] = None
    cogs: Optional[float] = None
    gross_profit: Optional[float] = None
    sga: Optional[float] = None
    ebit: Optional[float] = None
    interest_expense: Optional[float] = None
    pretax_income: Optional[float] = None
    tax_expense: Optional[float] = None
    net_income: Optional[float] = None
    da: Optional[float] = None
    cash: Optional[float] = None
    current_assets: Optional[float] = None
    accounts_receivable: Optional[float] = None
    inventory: Optional[float] = None
    total_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    accounts_payable: Optional[float] = None
    total_debt: Optional[float] = None
    total_equity: Optional[float] = None
    cfo: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None
    source_provenance: Optional[SourceProvenanceDTO] = None


@dataclass(frozen=True)
class FinancialFeatureDTO:
    """Pre-computed accounting ratio or normalized feature from DuckDB."""
    feature_name: str
    feature_value: Optional[float] = None
    unit: str = "RATIO"
    fiscal_year: int = 0
    fiscal_period: str = ""
    period_end_date: str = ""
    calculation_method: str = ""
    source_concepts: str = ""
    source_accessions: str = ""
    source_provenance: Optional[SourceProvenanceDTO] = None


@dataclass(frozen=True)
class FundamentalsResponse:
    """Comprehensive multi-period fundamental statement and ratio package."""
    ticker: str
    as_of_date: Optional[str]
    mode: str
    annual_statements: List[FinancialPeriodDTO]
    quarterly_statements: List[FinancialPeriodDTO]
    features: List[FinancialFeatureDTO]
    as_of_cutoff_datetime: Optional[str] = None


@dataclass(frozen=True)
class FilingSectionDTO:
    """Detected item section within an SEC filing document."""
    section_id: str
    section_name: str
    section_title: str
    char_count: int
    detection_confidence: str
    section_preview: str


@dataclass(frozen=True)
class FilingSummaryDTO:
    """Metadata and section summary for an individual SEC filing."""
    accession_number: str
    ticker: str
    form: str
    filing_date: str
    report_date: Optional[str]
    acceptance_datetime: str
    section_count: int
    claim_count: int
    sections: List[FilingSectionDTO] = field(default_factory=list)


@dataclass(frozen=True)
class FilingExplorerResponse:
    """Filing catalog and document inspection payload."""
    ticker: str
    as_of_date: Optional[str]
    mode: str
    filings: List[FilingSummaryDTO]
    total_filings_count: int
    ten_k_count: int = 0
    ten_q_count: int = 0
    latest_filing_date: Optional[str] = None
    latest_acceptance_datetime: Optional[str] = None
    total_claims_count: int = 0
    validated_claims_count: int = 0
    rejected_claims_count: int = 0
    company_name: str = ""
    cik: str = ""
    excluded_future_filings_count: int = 0

