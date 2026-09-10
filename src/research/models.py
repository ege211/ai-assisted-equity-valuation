"""
Data models and structured schemas for Phase 6 Research Integration & Empirical Evaluation.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TargetType(str, Enum):
    FORWARD_EBIT_MARGIN_CHANGE = "forward_ebit_margin_change"
    FORWARD_REVENUE_GROWTH = "forward_revenue_growth"
    EARNINGS_DETERIORATION = "earnings_deterioration"


class ModelRole(str, Enum):
    BASELINE = "BASELINE"
    ENHANCED = "ENHANCED"


class ValidationMethod(str, Enum):
    LEAVE_ONE_OUT = "leave_one_out"
    WALK_FORWARD = "walk_forward"
    K_FOLD = "k_fold"


@dataclass
class ResearchObservation:
    """Represents a point-in-time cross-sectional research observation."""
    observation_id: str
    company_id: str
    ticker: str
    sector: str
    observation_date: str  # YYYY-MM-DD
    data_as_of_date: str   # ISO timestamp
    fiscal_year: int
    latest_eligible_filing: str
    latest_filing_accession: str
    financial_feature_version: str = "features_phase3_v1.0"
    filing_intelligence_version: str = "filing_phase5_v1.0"


@dataclass
class BaselineFeatures:
    """Conventional fundamental and market features as of information date T."""
    ticker: str
    fiscal_year: int
    revenue_growth_yoy: float = 0.0
    ebit_margin: float = 0.0
    gross_margin: float = 0.0
    roic: float = 0.0
    fcf_margin: float = 0.0
    net_debt_to_revenue: float = 0.0
    owc_to_revenue: float = 0.0
    beta: float = 1.0
    wacc: float = 0.08

    def to_dict(self) -> Dict[str, float]:
        return {
            "revenue_growth_yoy": self.revenue_growth_yoy,
            "ebit_margin": self.ebit_margin,
            "gross_margin": self.gross_margin,
            "roic": self.roic,
            "fcf_margin": self.fcf_margin,
            "net_debt_to_revenue": self.net_debt_to_revenue,
            "owc_to_revenue": self.owc_to_revenue,
            "beta": self.beta,
            "wacc": self.wacc,
        }

    def to_vector(self, feature_names: Optional[List[str]] = None) -> List[float]:
        d = self.to_dict()
        if feature_names is None:
            return list(d.values())
        return [d.get(f, 0.0) for f in feature_names]


@dataclass
class FilingFeatures:
    """Aggregated qualitative features extracted from SEC filings as of T."""
    ticker: str
    fiscal_year: int
    accession_number: str
    margin_pressure_score: float = 0.0
    supply_chain_risk_score: float = 0.0
    regulatory_risk_score: float = 0.0
    litigation_risk_score: float = 0.0
    demand_uncertainty_score: float = 0.0
    guidance_sentiment_score: float = 0.0
    capital_allocation_score: float = 0.0
    total_risk_claims: float = 0.0
    high_materiality_risk_count: float = 0.0
    escalated_risk_count: float = 0.0
    net_qualitative_sentiment: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "margin_pressure_score": self.margin_pressure_score,
            "supply_chain_risk_score": self.supply_chain_risk_score,
            "regulatory_risk_score": self.regulatory_risk_score,
            "litigation_risk_score": self.litigation_risk_score,
            "demand_uncertainty_score": self.demand_uncertainty_score,
            "guidance_sentiment_score": self.guidance_sentiment_score,
            "capital_allocation_score": self.capital_allocation_score,
            "total_risk_claims": self.total_risk_claims,
            "high_materiality_risk_count": self.high_materiality_risk_count,
            "escalated_risk_count": self.escalated_risk_count,
            "net_qualitative_sentiment": self.net_qualitative_sentiment,
        }

    def to_vector(self, feature_names: Optional[List[str]] = None) -> List[float]:
        d = self.to_dict()
        if feature_names is None:
            return list(d.values())
        return [d.get(f, 0.0) for f in feature_names]


@dataclass
class ResearchTargetSet:
    """Forward financial realization targets occurring strictly after information date T."""
    ticker: str
    fiscal_year: int
    forward_ebit_margin_change: Optional[float] = None
    forward_revenue_growth: Optional[float] = None
    earnings_deterioration: Optional[float] = None
    realization_date: str = ""
    source_statement_id: Optional[str] = None
    is_valid: bool = True


@dataclass
class ModelEvaluationMetrics:
    """Standardized empirical evaluation metrics."""
    mae: float
    rmse: float
    r2: float
    accuracy: Optional[float] = None
    roc_auc: Optional[float] = None
    brier_score: Optional[float] = None
    sample_size: int = 0


@dataclass
class ModelComparisonResult:
    """Controlled comparison between Model A (Baseline) and Model B (Enhanced)."""
    experiment_id: str
    target_name: str
    baseline_metrics: ModelEvaluationMetrics
    enhanced_metrics: ModelEvaluationMetrics
    delta_mae: float                    # MAE_baseline - MAE_enhanced (positive = improvement)
    delta_rmse: float                   # RMSE_baseline - RMSE_enhanced
    delta_r2: float                     # R2_enhanced - R2_baseline
    p_value_paired_t: float
    p_value_permutation: float
    bootstrap_ci_delta_mae: Tuple[float, float]
    is_statistically_significant: bool  # p < 0.05 on primary test


@dataclass
class AblationResult:
    """Performance metrics for an individual qualitative feature group."""
    ablation_group: str
    feature_count: int
    mae: float
    rmse: float
    r2: float
    delta_mae_vs_baseline: float
    delta_rmse_vs_baseline: float
    sample_size: int


@dataclass
class RobustnessResult:
    """Result of cross-sector or parameter robustness checks."""
    test_type: str
    stratum: str
    sample_size: int
    baseline_mae: float
    enhanced_mae: float
    delta_mae: float
    baseline_rmse: float
    enhanced_rmse: float
    delta_rmse: float


@dataclass
class ValuationComparisonRecord:
    """Bridge comparison between Baseline DCF and Filing-Informed Scenario DCF."""
    ticker: str
    company_name: str
    sector: str
    valuation_date: str
    baseline_fair_value: float
    enhanced_fair_value: float
    fair_value_difference: float
    fair_value_pct_change: float
    market_price: float
    baseline_upside: float
    enhanced_upside: float
    primary_signal_category: str
    signal_intensity: float
    key_assumption_adjusted: str
    adjustment_magnitude: float
    evidence_citation: str


@dataclass
class ExperimentConfig:
    """Specification of an empirical experiment run."""
    experiment_id: str
    experiment_name: str
    target_name: str
    horizon_months: int = 12
    baseline_model_type: str = "RidgeRegression"
    enhanced_model_type: str = "RidgeRegression"
    validation_method: str = "leave_one_out"
    alpha_ridge: float = 1.0
    baseline_features: List[str] = field(default_factory=lambda: [
        "revenue_growth_yoy", "ebit_margin", "gross_margin", "roic",
        "fcf_margin", "net_debt_to_revenue", "owc_to_revenue", "beta", "wacc"
    ])
    enhanced_features: List[str] = field(default_factory=lambda: [
        "revenue_growth_yoy", "ebit_margin", "gross_margin", "roic",
        "fcf_margin", "net_debt_to_revenue", "owc_to_revenue", "beta", "wacc",
        "margin_pressure_score", "supply_chain_risk_score", "regulatory_risk_score",
        "litigation_risk_score", "demand_uncertainty_score", "guidance_sentiment_score",
        "capital_allocation_score", "total_risk_claims", "high_materiality_risk_count",
        "escalated_risk_count", "net_qualitative_sentiment"
    ])
