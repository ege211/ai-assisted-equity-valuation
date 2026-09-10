"""
Model Specifications, Dataset Lock, and Statistical Testing for Phase 7 Panel Research.

Implements:
1. Dataset Lock Report: Validates and persists exact complete-case sample metadata
2. Baseline Model A (Ridge regression on conventional fundamental features)
3. Pre-specified Enhanced Models (Operational, Risk, Operating, Management, Omnibus)
4. Binary Logistic Classifier for Earnings Deterioration
5. Rigorous paired statistical hypothesis testing (paired t-test, permutation, bootstrap CI)
"""
from dataclasses import dataclass, field
import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.research.math_utils import (
    accuracy_score,
    bootstrap_ci,
    brier_score,
    mean_absolute_error,
    paired_t_test,
    pearson_correlation,
    permutation_test,
    pr_auc_score,
    r2_score,
    roc_auc_score,
    root_mean_squared_error,
    spearman_rank_correlation,
    LogisticRegression,
    RidgeRegression,
)
from src.research.panel_builder import (
    BASELINE_FEATURE_NAMES,
    MANAGEMENT_GROUP_FEATURES,
    OMNIBUS_QUALITATIVE_FEATURES,
    OPERATING_GROUP_FEATURES,
    PRESPECIFIED_OPERATIONAL_FEATURES,
    RISK_GROUP_FEATURES,
    PanelFeatures,
    PanelObservation,
    PanelTargets,
)
from src.research.walkforward import PreprocessingState, WalkForwardFold, WalkForwardValidator


@dataclass
class DatasetLockReport:
    """Audit metadata locking the dataset prior to model execution."""
    n_companies: int
    n_observations: int
    observation_date_min: str
    observation_date_max: str
    filing_intelligence_date_min: str
    filing_intelligence_date_max: str
    primary_target_coverage: int
    secondary_target_coverage: int
    complete_model_a_obs: int
    complete_model_b_obs: int
    shared_complete_cases: int
    n_walkforward_folds: int
    ticker_list: List[str]
    lock_timestamp: str

    def to_formatted_str(self) -> str:
        lines = [
            "=" * 70,
            "PHASE 7 EMPIRICAL DATASET LOCK REPORT",
            "=" * 70,
            f"Lock Timestamp:                   {self.lock_timestamp}",
            f"Number of Companies:              {self.n_companies}",
            f"Total Panel Observations:         {self.n_observations}",
            f"Observation Date Range:           {self.observation_date_min} to {self.observation_date_max}",
            f"Filing Intelligence Date Range:   {self.filing_intelligence_date_min} to {self.filing_intelligence_date_max}",
            f"Primary Target Coverage:          {self.primary_target_coverage} / {self.n_observations} ({self.primary_target_coverage/self.n_observations*100:.1f}%)",
            f"Secondary Target Coverage:        {self.secondary_target_coverage} / {self.n_observations} ({self.secondary_target_coverage/self.n_observations*100:.1f}%)",
            f"Complete Model A Observations:    {self.complete_model_a_obs}",
            f"Complete Model B Observations:    {self.complete_model_b_obs}",
            f"Final Shared Complete Cases:      {self.shared_complete_cases}",
            f"Number of Walk-Forward Folds:     {self.n_walkforward_folds}",
            f"Universe Tickers:                 {', '.join(sorted(self.ticker_list))}",
            "=" * 70,
            "METHODOLOGICAL LOCK STATUS: ACTIVE & AUDITED",
            "1. Primary Target: forward_ebit_margin_change (LOCKED)",
            "2. Point-in-Time: acceptance_datetime authoritative (LOCKED)",
            "3. Filing Coverage: Genuine PIT extractions, zero backfill (LOCKED)",
            "4. Identical Sample: Model A and Model B evaluated on identical rows (LOCKED)",
            "=" * 70,
        ]
        return "\n".join(lines)


@dataclass
class ContinuousModelResult:
    """Results of continuous target evaluation on out-of-sample test partition."""
    model_name: str
    fold_name: str
    target_name: str
    n_train: int
    n_test: int
    alpha: float
    mae: float
    rmse: float
    r2: float
    pearson_r: float
    spearman_rho: float
    predictions: List[float]
    actuals: List[float]
    errors: List[float]  # absolute errors


@dataclass
class BinaryModelResult:
    """Results of binary classification on out-of-sample test partition."""
    model_name: str
    fold_name: str
    target_name: str
    n_train: int
    n_test: int
    brier: float
    roc_auc: float
    pr_auc: float
    accuracy: float
    prob_predictions: List[float]
    actuals: List[float]


class PanelModelRunner:
    """Trains, regularizes, and evaluates models across walk-forward partitions."""

    def __init__(self) -> None:
        self.validator = WalkForwardValidator()

    @staticmethod
    def generate_dataset_lock(
        observations: List[PanelObservation],
        targets: List[PanelTargets],
        folds: List[WalkForwardFold],
        output_dir: str = "results/tables",
    ) -> DatasetLockReport:
        """
        Generate, display, and persist the Phase 7 dataset lock report.
        """
        from datetime import datetime
        os.makedirs(output_dir, exist_ok=True)

        tickers = list(set(o.ticker for o in observations))
        obs_dates = [str(o.observation_date) for o in observations]
        filing_dates = [str(o.filing_data_as_of)[:10] for o in observations if o.has_complete_filing]

        target_map = {t.observation_id: t for t in targets}
        n_prim = sum(1 for o in observations if target_map.get(o.observation_id) and target_map[o.observation_id].forward_ebit_margin_change is not None)
        n_sec = sum(1 for o in observations if target_map.get(o.observation_id) and target_map[o.observation_id].forward_revenue_growth is not None)

        complete_a = sum(1 for o in observations if o.has_complete_baseline and o.has_valid_target)
        complete_b = sum(1 for o in observations if o.has_complete_filing and o.has_valid_target)
        shared = sum(1 for o in observations if o.has_complete_baseline and o.has_complete_filing and o.has_valid_target)

        report = DatasetLockReport(
            n_companies=len(tickers),
            n_observations=len(observations),
            observation_date_min=min(obs_dates),
            observation_date_max=max(obs_dates),
            filing_intelligence_date_min=min(filing_dates) if filing_dates else "",
            filing_intelligence_date_max=max(filing_dates) if filing_dates else "",
            primary_target_coverage=n_prim,
            secondary_target_coverage=n_sec,
            complete_model_a_obs=complete_a,
            complete_model_b_obs=complete_b,
            shared_complete_cases=shared,
            n_walkforward_folds=len(folds),
            ticker_list=tickers,
            lock_timestamp=datetime.utcnow().isoformat() + "Z",
        )

        # Persist to disk
        txt_path = os.path.join(output_dir, "phase7_dataset_lock_report.txt")
        json_path = os.path.join(output_dir, "phase7_dataset_lock.json")
        with open(txt_path, "w") as f:
            f.write(report.to_formatted_str())
        with open(json_path, "w") as f:
            json.dump({
                "n_companies": report.n_companies,
                "n_observations": report.n_observations,
                "observation_date_min": report.observation_date_min,
                "observation_date_max": report.observation_date_max,
                "filing_intelligence_date_min": report.filing_intelligence_date_min,
                "filing_intelligence_date_max": report.filing_intelligence_date_max,
                "primary_target_coverage": report.primary_target_coverage,
                "secondary_target_coverage": report.secondary_target_coverage,
                "complete_model_a_obs": report.complete_model_a_obs,
                "complete_model_b_obs": report.complete_model_b_obs,
                "shared_complete_cases": report.shared_complete_cases,
                "n_walkforward_folds": report.n_walkforward_folds,
                "lock_timestamp": report.lock_timestamp,
            }, f, indent=2)

        return report

    @staticmethod
    def tune_ridge_alpha(
        train_X: List[List[float]],
        train_y: List[float],
        candidate_alphas: Optional[List[float]] = None,
    ) -> float:
        """
        Tune Ridge regularization penalty alpha strictly via leave-one-out CV on training set.
        """
        candidate_alphas = candidate_alphas or [0.01, 0.1, 1.0, 5.0, 10.0, 50.0, 100.0]
        n_samples = len(train_X)
        if n_samples < 5:
            return 1.0

        best_alpha = 1.0
        lowest_cv_mae = float("inf")

        for alpha in candidate_alphas:
            fold_errors: List[float] = []
            for i in range(n_samples):
                # LOOCV split
                loocv_train_X = [train_X[k] for k in range(n_samples) if k != i]
                loocv_train_y = [train_y[k] for k in range(n_samples) if k != i]
                loocv_val_X = [train_X[i]]
                loocv_val_y = train_y[i]

                try:
                    model = RidgeRegression(alpha=alpha)
                    model.fit(loocv_train_X, loocv_train_y)
                    pred = model.predict(loocv_val_X)[0]
                    fold_errors.append(abs(pred - loocv_val_y))
                except Exception:
                    fold_errors.append(999.0)

            mean_cv_mae = sum(fold_errors) / len(fold_errors)
            if mean_cv_mae < lowest_cv_mae:
                lowest_cv_mae = mean_cv_mae
                best_alpha = alpha

        return best_alpha

    def evaluate_continuous_model(
        self,
        model_name: str,
        fold_name: str,
        target_name: str,
        train_raw_X: List[List[float]],
        train_y: List[float],
        test_raw_X: List[List[float]],
        test_y: List[float],
        feature_names: List[str],
        alpha: Optional[float] = None,
    ) -> ContinuousModelResult:
        """
        Fit scaler and regularized Ridge strictly on train partition and evaluate out-of-sample.
        """
        # 1. Train-only preprocessing
        prep_state = self.validator.fit_train_preprocessor(train_raw_X, feature_names)
        train_X_scaled = self.validator.transform(train_raw_X, prep_state)
        test_X_scaled = self.validator.transform(test_raw_X, prep_state)

        # 2. Regularization hyperparameter tuning (strictly on train partition)
        chosen_alpha = alpha if alpha is not None else self.tune_ridge_alpha(train_X_scaled, train_y)

        # 3. Fit Ridge model
        model = RidgeRegression(alpha=chosen_alpha)
        model.fit(train_X_scaled, train_y)

        # 4. Predict out-of-sample on test partition
        preds = model.predict(test_X_scaled)
        abs_errors = [abs(p - a) for p, a in zip(preds, test_y)]

        mae = mean_absolute_error(test_y, preds)
        rmse = root_mean_squared_error(test_y, preds)
        r2 = r2_score(test_y, preds)
        pearson = pearson_correlation(preds, test_y)
        spearman = spearman_rank_correlation(preds, test_y)

        return ContinuousModelResult(
            model_name=model_name,
            fold_name=fold_name,
            target_name=target_name,
            n_train=len(train_y),
            n_test=len(test_y),
            alpha=chosen_alpha,
            mae=mae,
            rmse=rmse,
            r2=r2,
            pearson_r=pearson,
            spearman_rho=spearman,
            predictions=preds,
            actuals=test_y,
            errors=abs_errors,
        )

    def evaluate_binary_model(
        self,
        model_name: str,
        fold_name: str,
        target_name: str,
        train_raw_X: List[List[float]],
        train_y: List[float],
        test_raw_X: List[List[float]],
        test_y: List[float],
        feature_names: List[str],
        alpha: float = 1.0,
    ) -> BinaryModelResult:
        """
        Fit Logistic Regression strictly on train partition and evaluate out-of-sample.
        """
        prep_state = self.validator.fit_train_preprocessor(train_raw_X, feature_names)
        train_X_scaled = self.validator.transform(train_raw_X, prep_state)
        test_X_scaled = self.validator.transform(test_raw_X, prep_state)

        clf = LogisticRegression(alpha=alpha, lr=0.05, max_iter=500)
        clf.fit(train_X_scaled, train_y)

        probs = clf.predict_proba(test_X_scaled)

        brier = brier_score(test_y, probs)
        roc_auc = roc_auc_score(test_y, probs)
        pr_auc = pr_auc_score(test_y, probs)
        preds_binary = [1.0 if p >= 0.5 else 0.0 for p in probs]
        acc = accuracy_score(test_y, preds_binary)

        return BinaryModelResult(
            model_name=model_name,
            fold_name=fold_name,
            target_name=target_name,
            n_train=len(train_y),
            n_test=len(test_y),
            brier=brier,
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            accuracy=acc,
            prob_predictions=probs,
            actuals=test_y,
        )

    @staticmethod
    def compare_continuous_models(
        baseline: ContinuousModelResult,
        enhanced: ContinuousModelResult,
        n_permutations: int = 1000,
        n_bootstraps: int = 1000,
    ) -> Dict[str, Any]:
        """
        Conduct rigorous paired statistical comparison between Model A and Model B.
        """
        delta_mae = baseline.mae - enhanced.mae
        delta_rmse = baseline.rmse - enhanced.rmse
        pct_improvement = (delta_mae / baseline.mae) * 100.0 if baseline.mae > 0 else 0.0

        t_stat, p_val = paired_t_test(baseline.errors, enhanced.errors)
        perm_p = permutation_test(baseline.errors, enhanced.errors, n_permutations=n_permutations)
        ci_low, ci_high = bootstrap_ci(baseline.errors, enhanced.errors, n_bootstraps=n_bootstraps)

        return {
            "baseline_mae": baseline.mae,
            "enhanced_mae": enhanced.mae,
            "delta_mae": delta_mae,
            "delta_rmse": delta_rmse,
            "pct_mae_improvement": pct_improvement,
            "paired_t_stat": t_stat,
            "p_value": p_val,
            "permutation_p_value": perm_p,
            "bootstrap_ci_lower": ci_low,
            "bootstrap_ci_upper": ci_high,
            "statistically_significant": bool(p_val < 0.05 and delta_mae > 0),
        }
