"""
Ablation Study Module for Phase 6.

Evaluates the incremental predictive contribution of distinct qualitative
information categories (Operational Risks, Regulatory/Litigation, Guidance/Capital Allocation, All).
"""
from typing import Any, Dict, List, Tuple

from src.research.enhanced_model import EnhancedModel
from src.research.evaluation import run_cross_validation
from src.research.models import AblationResult, ExperimentConfig


# Predefined feature groupings
ABLATION_GROUPS = {
    "1_Baseline_Only": [],
    "2_Operational_Risks": [
        "margin_pressure_score",
        "supply_chain_risk_score",
    ],
    "3_Legal_and_Regulatory": [
        "regulatory_risk_score",
        "litigation_risk_score",
    ],
    "4_Guidance_and_Capital": [
        "guidance_sentiment_score",
        "capital_allocation_score",
    ],
    "5_Macro_and_Intensity": [
        "demand_uncertainty_score",
        "total_risk_claims",
        "high_materiality_risk_count",
        "escalated_risk_count",
        "net_qualitative_sentiment",
    ],
    "6_All_Filing_Features": [
        "margin_pressure_score",
        "supply_chain_risk_score",
        "regulatory_risk_score",
        "litigation_risk_score",
        "demand_uncertainty_score",
        "guidance_sentiment_score",
        "capital_allocation_score",
        "total_risk_claims",
        "high_materiality_risk_count",
        "escalated_risk_count",
        "net_qualitative_sentiment",
    ],
}


def run_ablation_study(
    experiment_id: str,
    base_features_matrix: List[List[float]],
    filing_feature_dict_list: List[Dict[str, float]],
    y: List[float],
    config: ExperimentConfig,
    baseline_mae: float,
    baseline_rmse: float,
) -> List[AblationResult]:
    """
    Execute ablation runs across predefined feature subsets and calculate delta vs baseline.
    """
    results: List[AblationResult] = []
    is_classification = config.target_name == "earnings_deterioration"

    for group_name, feat_names in ABLATION_GROUPS.items():
        # Build feature matrix for this ablation group
        if not feat_names:
            # Baseline only
            X_group = [row[:] for row in base_features_matrix]
        else:
            X_group = []
            for i, base_row in enumerate(base_features_matrix):
                f_dict = filing_feature_dict_list[i]
                group_feats = [f_dict.get(fn, 0.0) for fn in feat_names]
                X_group.append(base_row + group_feats)

        # Run CV
        _, metrics = run_cross_validation(
            X=X_group,
            y=y,
            model_class=EnhancedModel,
            model_type=config.enhanced_model_type,
            alpha=config.alpha_ridge,
            is_classification=is_classification,
            validation_method=config.validation_method,
        )

        delta_mae = baseline_mae - metrics.mae
        delta_rmse = baseline_rmse - metrics.rmse

        results.append(
            AblationResult(
                ablation_group=group_name,
                feature_count=len(X_group[0]),
                mae=metrics.mae,
                rmse=metrics.rmse,
                r2=metrics.r2,
                delta_mae_vs_baseline=delta_mae,
                delta_rmse_vs_baseline=delta_rmse,
                sample_size=len(y),
            )
        )

    return results
