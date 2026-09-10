"""
Robustness and Cross-Sector Evaluation Module for Phase 6.

Conducts cross-sector robustness stratification, regularization sensitivity analysis,
and formal survivorship bias evaluation.
"""
from typing import Any, Dict, List

from src.research.baseline_model import BaselineModel
from src.research.enhanced_model import EnhancedModel
from src.research.evaluation import run_cross_validation
from src.research.models import ExperimentConfig, RobustnessResult


def run_sector_robustness(
    experiment_id: str,
    X_baseline: List[List[float]],
    X_enhanced: List[List[float]],
    y: List[float],
    sectors: List[str],
    config: ExperimentConfig,
) -> List[RobustnessResult]:
    """
    Evaluate Model A vs Model B performance stratified by industry sector.
    """
    results: List[RobustnessResult] = []
    unique_sectors = sorted(list(set(sectors)))
    is_classification = config.target_name == "earnings_deterioration"

    for sec in unique_sectors:
        indices = [i for i, s in enumerate(sectors) if s == sec]
        sample_size = len(indices)
        if sample_size < 3:
            continue

        X_base_sec = [X_baseline[i] for i in indices]
        X_enh_sec = [X_enhanced[i] for i in indices]
        y_sec = [y[i] for i in indices]

        _, metrics_a = run_cross_validation(
            X=X_base_sec,
            y=y_sec,
            model_class=BaselineModel,
            model_type=config.baseline_model_type,
            alpha=config.alpha_ridge,
            is_classification=is_classification,
            validation_method="leave_one_out",
        )

        _, metrics_b = run_cross_validation(
            X=X_enh_sec,
            y=y_sec,
            model_class=EnhancedModel,
            model_type=config.enhanced_model_type,
            alpha=config.alpha_ridge,
            is_classification=is_classification,
            validation_method="leave_one_out",
        )

        results.append(
            RobustnessResult(
                test_type="SECTOR_SUBSET",
                stratum=sec,
                sample_size=sample_size,
                baseline_mae=metrics_a.mae,
                enhanced_mae=metrics_b.mae,
                delta_mae=metrics_a.mae - metrics_b.mae,
                baseline_rmse=metrics_a.rmse,
                enhanced_rmse=metrics_b.rmse,
                delta_rmse=metrics_a.rmse - metrics_b.rmse,
            )
        )

    return results


def run_regularization_sensitivity(
    experiment_id: str,
    X_baseline: List[List[float]],
    X_enhanced: List[List[float]],
    y: List[float],
    config: ExperimentConfig,
    lambdas: List[float] = [0.1, 1.0, 10.0, 50.0],
) -> List[RobustnessResult]:
    """
    Evaluate Model A vs Model B under alternative regularization shrinkage values (alpha).
    """
    results: List[RobustnessResult] = []
    is_classification = config.target_name == "earnings_deterioration"

    for lmb in lambdas:
        _, metrics_a = run_cross_validation(
            X=X_baseline,
            y=y,
            model_class=BaselineModel,
            model_type=config.baseline_model_type,
            alpha=lmb,
            is_classification=is_classification,
            validation_method=config.validation_method,
        )

        _, metrics_b = run_cross_validation(
            X=X_enhanced,
            y=y,
            model_class=EnhancedModel,
            model_type=config.enhanced_model_type,
            alpha=lmb,
            is_classification=is_classification,
            validation_method=config.validation_method,
        )

        results.append(
            RobustnessResult(
                test_type="REGULARIZATION_LAMBDA",
                stratum=f"alpha_{lmb}",
                sample_size=len(y),
                baseline_mae=metrics_a.mae,
                enhanced_mae=metrics_b.mae,
                delta_mae=metrics_a.mae - metrics_b.mae,
                baseline_rmse=metrics_a.rmse,
                enhanced_rmse=metrics_b.rmse,
                delta_rmse=metrics_a.rmse - metrics_b.rmse,
            )
        )

    return results
