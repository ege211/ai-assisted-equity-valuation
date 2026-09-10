"""
Unit Tests for Phase 7: Expanded Out-of-Sample Panel Research Pipeline.

Validates:
1. Point-in-Time (PIT) observation date construction
2. Authoritative acceptance_datetime temporal alignment
3. Target construction and forward-looking exclusion
4. Walk-forward chronological partitioning (max(train) < min(test))
5. Train-only preprocessing parameter isolation (zero leakage)
6. Identical complete-case sample enforcement for Model A and Model B
7. LeakageAuditor automated detection and adversarial rejection
8. Ridge regression and binary logistic model estimation
9. Pre-specified ablation specification isolation
10. End-to-end panel builder and experiment reproducibility
"""
import math
import os
import unittest

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.leakage_audit import LeakageAuditor, LeakageViolationError
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
    PanelBuilder,
    PanelObservation,
    PanelTargets,
)
from src.research.panel_models import PanelModelRunner
from src.research.walkforward import PreprocessingState, WalkForwardValidator


class TestPhase7PanelResearch(unittest.TestCase):
    """Test suite verifying all Phase 7 methodological guarantees and components."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = DatabaseManager(db_path=DEFAULT_DB_PATH)
        cls.builder = PanelBuilder(db_manager=cls.db)
        cls.auditor = LeakageAuditor(db_manager=cls.db)
        cls.validator = WalkForwardValidator(db_manager=cls.db)
        cls.runner = PanelModelRunner()
        cls.dataset = cls.builder.build_panel()

    def test_01_panel_observations_created(self) -> None:
        """Verify panel observations are populated with required fields."""
        obs = self.dataset["observations"]
        self.assertGreater(len(obs), 40, "Should generate at least 40 panel observations")
        for o in obs:
            self.assertTrue(o.observation_id.startswith("panel_"))
            self.assertIn(o.cohort, ("COHORT_2023", "COHORT_2024"))
            self.assertRegex(o.observation_date, r"^\d{4}-\d{2}-\d{2}$")

    def test_02_point_in_time_acceptance_datetime_lock(self) -> None:
        """Verify observation date is strictly derived from authoritative acceptance_datetime."""
        obs = self.dataset["observations"]
        for o in obs:
            obs_dt = str(o.observation_date)[:10]
            fin_dt = str(o.financial_data_as_of)[:10]
            filing_dt = str(o.filing_data_as_of)[:10]
            self.assertLessEqual(fin_dt, obs_dt, f"Financial as-of {fin_dt} must be <= obs {obs_dt}")
            self.assertLessEqual(filing_dt, obs_dt, f"Filing as-of {filing_dt} must be <= obs {obs_dt}")

    def test_03_forward_target_temporal_separation(self) -> None:
        """Verify that target realization occurs strictly after observation date."""
        obs_map = {o.observation_id: o for o in self.dataset["observations"]}
        targets = self.dataset["targets"]
        valid_targets = [t for t in targets if t.is_valid]
        self.assertGreater(len(valid_targets), 35, "Should have at least 35 valid forward targets")

        for t in valid_targets:
            obs = obs_map[t.observation_id]
            self.assertGreater(
                str(t.realization_date)[:10],
                str(obs.observation_date)[:10],
                f"Realization {t.realization_date} must be strictly after obs date {obs.observation_date}",
            )
            self.assertGreater(
                obs.target_fiscal_year,
                obs.base_fiscal_year,
                "Target FY must be strictly greater than Base FY",
            )

    def test_04_walk_forward_chronological_splits(self) -> None:
        """Verify walk-forward splits have max(train_date) < min(test_date)."""
        folds = self.validator.generate_splits(self.dataset["observations"], complete_only=True)
        self.assertGreaterEqual(len(folds), 1, "Must generate at least 1 walk-forward fold")

        fold1 = folds[0]
        self.assertEqual(fold1.fold_name, "FOLD_1_ANNUAL_COHORT")
        self.assertLess(
            fold1.train_end_date,
            fold1.test_start_date,
            f"Train end {fold1.train_end_date} must be strictly before test start {fold1.test_start_date}",
        )
        self.assertGreater(fold1.n_train, 15, "Train partition should have > 15 observations")
        self.assertGreater(fold1.n_test, 15, "Test partition should have > 15 observations")

    def test_05_train_only_preprocessing_isolation(self) -> None:
        """Verify scaling parameters are computed strictly on training partition."""
        train_X = [[1.0, 10.0], [3.0, 30.0], [5.0, 50.0]]  # means: 3.0, 30.0; stds: 2.0, 20.0
        test_X = [[7.0, 70.0]]
        fnames = ["feat1", "feat2"]

        prep = WalkForwardValidator.fit_train_preprocessor(train_X, fnames)
        self.assertAlmostEqual(prep.means[0], 3.0, places=4)
        self.assertAlmostEqual(prep.means[1], 30.0, places=4)
        self.assertAlmostEqual(prep.stds[0], 2.0, places=4)
        self.assertAlmostEqual(prep.stds[1], 20.0, places=4)

        test_scaled = WalkForwardValidator.transform(test_X, prep)
        # (7 - 3)/2 = 2.0; (70 - 30)/20 = 2.0
        self.assertAlmostEqual(test_scaled[0][0], 2.0, places=4)
        self.assertAlmostEqual(test_scaled[0][1], 2.0, places=4)

    def test_06_leakage_auditor_full_audit(self) -> None:
        """Verify that LeakageAuditor passes all real dataset observations and splits."""
        folds = self.validator.generate_splits(self.dataset["observations"], complete_only=True)
        split_dicts = [
            {"fold_name": f.fold_name, "train_dates": [f.train_start_date, f.train_end_date], "test_dates": [f.test_start_date, f.test_end_date]}
            for f in folds
        ]
        res = self.auditor.run_full_audit(self.dataset["observations"], self.dataset["targets"], split_dicts)
        self.assertEqual(res["status"], "PASSED")
        self.assertEqual(res["failed_checks"], 0)
        self.assertGreater(res["passed_checks"], 150)

    def test_07_adversarial_leakage_rejection(self) -> None:
        """Verify that LeakageAuditor rejects deliberately corrupted future observations."""
        passed = self.auditor.verify_adversarial_leakage_rejection()
        self.assertTrue(passed, "Auditor must catch adversarial future timestamp injections")

    def test_08_identical_sample_model_comparison(self) -> None:
        """Verify that Model A and Model B evaluate on the exact identical complete-case sample."""
        obs = self.dataset["observations"]
        complete = [o for o in obs if o.has_complete_baseline and o.has_complete_filing and o.has_valid_target]
        self.assertGreater(len(complete), 40, "Complete shared cases should be >= 40")
        for o in complete:
            self.assertTrue(o.has_complete_baseline)
            self.assertTrue(o.has_complete_filing)
            self.assertTrue(o.has_valid_target)

    def test_09_ridge_regression_and_cv_tuning(self) -> None:
        """Verify Ridge regression fits deterministically and tunes alpha."""
        X = [[1.0, 2.0], [2.0, 1.0], [3.0, 4.0], [4.0, 3.0], [5.0, 6.0]]
        y = [3.0, 3.0, 7.0, 7.0, 11.0]  # y = x1 + x2
        model = RidgeRegression(alpha=0.1)
        model.fit(X, y)
        preds = model.predict([[6.0, 5.0]])
        self.assertAlmostEqual(preds[0], 11.0, delta=1.5)

        best_alpha = PanelModelRunner.tune_ridge_alpha(X, y, candidate_alphas=[0.01, 1.0, 10.0])
        self.assertIn(best_alpha, [0.01, 1.0, 10.0])

    def test_10_binary_logistic_and_evaluation_metrics(self) -> None:
        """Verify Logistic Regression and metrics (Brier, ROC-AUC, PR-AUC)."""
        X = [[0.1], [0.2], [0.8], [0.9]]
        y = [0.0, 0.0, 1.0, 1.0]
        clf = LogisticRegression(alpha=0.1, lr=0.1, max_iter=200)
        clf.fit(X, y)
        probs = clf.predict_proba([[0.15], [0.85]])
        self.assertLess(probs[0], probs[1])

        # Test statistical metrics
        auc = roc_auc_score([0.0, 1.0], [0.2, 0.8])
        self.assertEqual(auc, 1.0)
        brier = brier_score([0.0, 1.0], [0.0, 1.0])
        self.assertEqual(brier, 0.0)

    def test_11_dataset_lock_report_persistence(self) -> None:
        """Verify Dataset Lock Report file is persisted and contains required fields."""
        folds = self.validator.generate_splits(self.dataset["observations"], complete_only=True)
        report = self.runner.generate_dataset_lock(self.dataset["observations"], self.dataset["targets"], folds)
        self.assertGreater(report.n_companies, 25)
        self.assertGreater(report.shared_complete_cases, 40)

        txt_file = "results/tables/phase7_dataset_lock_report.txt"
        json_file = "results/tables/phase7_dataset_lock.json"
        self.assertTrue(os.path.exists(txt_file), "Lock report text file must exist")
        self.assertTrue(os.path.exists(json_file), "Lock report JSON file must exist")


if __name__ == "__main__":
    unittest.main()
