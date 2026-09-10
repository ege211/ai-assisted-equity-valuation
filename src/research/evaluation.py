"""
Controlled Evaluation Protocol and Statistical Comparison for Phase 6.

Executes cross-validation across models, computes out-of-sample performance metrics,
and performs rigorous statistical significance tests (paired t-test, permutation test, bootstrap CI).
"""
from typing import Any, Dict, List, Optional, Tuple

from src.research.baseline_model import BaselineModel
from src.research.enhanced_model import EnhancedModel
from src.research.math_utils import (
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
    ExperimentConfig,
    ModelComparisonResult,
    ModelEvaluationMetrics,
)


def run_cross_validation(
    X: List[List[float]],
    y: List[float],
    model_class: Any,
    model_type: str = "RidgeRegression",
    alpha: float = 1.0,
    is_classification: bool = False,
    validation_method: str = "leave_one_out",
) -> Tuple[List[float], ModelEvaluationMetrics]:
    """
    Perform out-of-sample cross-validation and return out-of-sample predictions
    along with aggregate evaluation metrics.
    """
    n_samples = len(X)
    if n_samples < 3:
        raise ValueError(f"Insufficient sample size for cross-validation: {n_samples}")

    predictions: List[float] = [0.0] * n_samples

    # Leave-One-Out Cross-Validation (LOOCV)
    for i in range(n_samples):
        X_train = [X[j] for j in range(n_samples) if j != i]
        y_train = [y[j] for j in range(n_samples) if j != i]
        X_val = [X[i]]

        model = model_class(model_type=model_type, alpha=alpha, is_classification=is_classification)
        model.fit(X_train, y_train)
        pred = model.predict(X_val)
        predictions[i] = float(pred[0])

    mae = mean_absolute_error(y, predictions)
    rmse = root_mean_squared_error(y, predictions)
    r2 = r2_score(y, predictions)

    acc = None
    auc = None
    brier = None
    if is_classification:
        acc = accuracy_score(y, [1.0 if p >= 0.5 else 0.0 for p in predictions])
        auc = roc_auc_score(y, predictions)
        brier = brier_score(y, predictions)

    metrics = ModelEvaluationMetrics(
        mae=mae,
        rmse=rmse,
        r2=r2,
        accuracy=acc,
        roc_auc=auc,
        brier_score=brier,
        sample_size=n_samples,
    )
    return predictions, metrics


def compare_models(
    experiment_id: str,
    target_name: str,
    X_baseline: List[List[float]],
    X_enhanced: List[List[float]],
    y: List[float],
    tickers: List[str],
    observation_ids: List[str],
    config: ExperimentConfig,
) -> Tuple[ModelComparisonResult, List[Dict[str, Any]]]:
    """
    Execute controlled comparison between Model A (Baseline) and Model B (Enhanced)
    under strictly identical CV splits.
    """
    is_classification = config.target_name == "earnings_deterioration"

    preds_a, metrics_a = run_cross_validation(
        X=X_baseline,
        y=y,
        model_class=BaselineModel,
        model_type=config.baseline_model_type,
        alpha=config.alpha_ridge,
        is_classification=is_classification,
        validation_method=config.validation_method,
    )

    preds_b, metrics_b = run_cross_validation(
        X=X_enhanced,
        y=y,
        model_class=EnhancedModel,
        model_type=config.enhanced_model_type,
        alpha=config.alpha_ridge,
        is_classification=is_classification,
        validation_method=config.validation_method,
    )

    # Compute errors for statistical testing
    errors_a = [abs(yi - pi) for yi, pi in zip(y, preds_a)]
    errors_b = [abs(yi - pi) for yi, pi in zip(y, preds_b)]

    delta_mae = metrics_a.mae - metrics_b.mae
    delta_rmse = metrics_a.rmse - metrics_b.rmse
    delta_r2 = metrics_b.r2 - metrics_a.r2

    t_stat, p_val_t = paired_t_test(errors_a, errors_b)
    p_val_perm = permutation_test(errors_a, errors_b, n_permutations=2000, seed=42)
    ci_low, ci_high = bootstrap_ci(errors_a, errors_b, n_bootstraps=2000, alpha=0.05, seed=42)

    is_sig = p_val_perm < 0.05 and delta_mae > 0.0

    comparison_result = ModelComparisonResult(
        experiment_id=experiment_id,
        target_name=target_name,
        baseline_metrics=metrics_a,
        enhanced_metrics=metrics_b,
        delta_mae=delta_mae,
        delta_rmse=delta_rmse,
        delta_r2=delta_r2,
        p_value_paired_t=p_val_t,
        p_value_permutation=p_val_perm,
        bootstrap_ci_delta_mae=(ci_low, ci_high),
        is_statistically_significant=is_sig,
    )

    # Detailed row-by-row prediction logs for research_model_results
    result_rows: List[Dict[str, Any]] = []
    for i in range(len(y)):
        obs_id = observation_ids[i]
        tick = tickers[i]
        actual = y[i]

        # Model A row
        pred_a = preds_a[i]
        res_a = actual - pred_a
        result_rows.append({
            "result_id": f"res_{experiment_id}_base_{tick}",
            "experiment_id": experiment_id,
            "model_role": "BASELINE",
            "observation_id": obs_id,
            "ticker": tick,
            "target_name": target_name,
            "actual_value": actual,
            "predicted_value": pred_a,
            "residual": res_a,
            "absolute_error": abs(res_a),
            "squared_error": res_a ** 2,
            "validation_fold": f"loocv_{tick}",
        })

        # Model B row
        pred_b = preds_b[i]
        res_b = actual - pred_b
        result_rows.append({
            "result_id": f"res_{experiment_id}_enh_{tick}",
            "experiment_id": experiment_id,
            "model_role": "ENHANCED",
            "observation_id": obs_id,
            "ticker": tick,
            "target_name": target_name,
            "actual_value": actual,
            "predicted_value": pred_b,
            "residual": res_b,
            "absolute_error": abs(res_b),
            "squared_error": res_b ** 2,
            "validation_fold": f"loocv_{tick}",
        })

    return comparison_result, result_rows
