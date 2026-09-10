"""
Phase 6 Research Integration & Empirical Evaluation Package.
"""
from src.research.ablation import ABLATION_GROUPS, run_ablation_study
from src.research.baseline_model import BaselineModel
from src.research.dataset_builder import ResearchDatasetBuilder
from src.research.enhanced_model import EnhancedModel
from src.research.evaluation import compare_models, run_cross_validation
from src.research.experiment import ResearchExperimentOrchestrator
from src.research.feature_alignment import aggregate_filing_claims, extract_baseline_features
from src.research.math_utils import (
    LinearRegressionOLS,
    LogisticRegression,
    RidgeRegression,
    accuracy_score,
    bootstrap_ci,
    brier_score,
    mean_absolute_error,
    paired_t_test,
    permutation_test,
    r2_score,
    roc_auc_score,
    root_mean_squared_error,
)
from src.research.models import (
    AblationResult,
    BaselineFeatures,
    ExperimentConfig,
    FilingFeatures,
    ModelComparisonResult,
    ModelEvaluationMetrics,
    ModelRole,
    ResearchObservation,
    ResearchTargetSet,
    RobustnessResult,
    TargetType,
    ValidationMethod,
    ValuationComparisonRecord,
)
from src.research.robustness import run_regularization_sensitivity, run_sector_robustness
from src.research.target_builder import build_forward_targets
from src.research.valuation_bridge import (
    BRIDGE_VERSION,
    bridge_filing_to_valuation,
    run_universe_valuation_bridge,
)

__all__ = [
    "ABLATION_GROUPS",
    "BRIDGE_VERSION",
    "AblationResult",
    "BaselineFeatures",
    "BaselineModel",
    "EnhancedModel",
    "ExperimentConfig",
    "FilingFeatures",
    "LinearRegressionOLS",
    "LogisticRegression",
    "ModelComparisonResult",
    "ModelEvaluationMetrics",
    "ModelRole",
    "ResearchDatasetBuilder",
    "ResearchExperimentOrchestrator",
    "ResearchObservation",
    "ResearchTargetSet",
    "RidgeRegression",
    "RobustnessResult",
    "TargetType",
    "ValidationMethod",
    "ValuationComparisonRecord",
    "accuracy_score",
    "aggregate_filing_claims",
    "bootstrap_ci",
    "brier_score",
    "bridge_filing_to_valuation",
    "build_forward_targets",
    "compare_models",
    "extract_baseline_features",
    "mean_absolute_error",
    "paired_t_test",
    "permutation_test",
    "r2_score",
    "roc_auc_score",
    "root_mean_squared_error",
    "run_ablation_study",
    "run_cross_validation",
    "run_regularization_sensitivity",
    "run_sector_robustness",
    "run_universe_valuation_bridge",
]
