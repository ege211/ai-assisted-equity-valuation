"""
Empirical Experiment Execution, Ablation, and Robustness Orchestrator for Phase 7.

Orchestrates the entire out-of-sample panel research evaluation:
1. Assembles panel observations, features, and targets (PanelBuilder)
2. Executes automated point-in-time leakage audit (LeakageAuditor)
3. Generates chronological walk-forward splits (WalkForwardValidator)
4. Displays and persists Dataset Lock Report (PanelModelRunner)
5. Evaluates Model A vs Model B across primary/secondary targets & folds
6. Conducts binary classification for earnings deterioration
7. Executes pre-specified ablation study across feature groupings
8. Evaluates robustness across sectors, sub-periods, alphas, and outlier trimming
9. Persists all metrics to DuckDB and exports the 8 required CSV tables.
"""
from dataclasses import asdict
from datetime import datetime
import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.leakage_audit import LeakageAuditor
from src.research.math_utils import (
    bootstrap_ci,
    mean_absolute_error,
    paired_t_test,
    permutation_test,
    root_mean_squared_error,
)
from src.research.panel_builder import (
    BASELINE_FEATURE_NAMES,
    MANAGEMENT_GROUP_FEATURES,
    OMNIBUS_QUALITATIVE_FEATURES,
    OPERATING_GROUP_FEATURES,
    PRESPECIFIED_OPERATIONAL_FEATURES,
    RISK_GROUP_FEATURES,
    PanelBuilder,
    PanelFeatures,
    PanelObservation,
    PanelTargets,
)
from src.research.panel_models import (
    ContinuousModelResult,
    DatasetLockReport,
    PanelModelRunner,
)
from src.research.walkforward import WalkForwardFold, WalkForwardValidator


class PanelExperiment:
    """Executes the Phase 7 out-of-sample empirical research experiment."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        db_path: str = DEFAULT_DB_PATH,
        output_dir: str = "results/tables",
    ) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)
        self.output_dir = output_dir
        self.panel_builder = PanelBuilder(db_manager=self.db, db_path=db_path)
        self.auditor = LeakageAuditor(db_manager=self.db, db_path=db_path)
        self.validator = WalkForwardValidator(db_manager=self.db, db_path=db_path)
        self.runner = PanelModelRunner()
        os.makedirs(self.output_dir, exist_ok=True)

    def run_experiment(self) -> Dict[str, Any]:
        """
        Execute full Phase 7 empirical pipeline end-to-end.
        """
        # Step 1: Build Panel
        print("\n[Phase 7] 1. Building Panel Observations, Features, and Targets...")
        dataset = self.panel_builder.build_panel()
        observations: List[PanelObservation] = dataset["observations"]
        features_list: List[PanelFeatures] = dataset["features"]
        targets_list: List[PanelTargets] = dataset["targets"]

        # Step 2: Generate Chronological Walk-Forward Splits
        print("\n[Phase 7] 2. Generating Chronological Walk-Forward Splits...")
        folds = self.validator.generate_splits(observations, complete_only=True)
        for f in folds:
            print(f"  - Fold {f.fold_number} ({f.fold_name}): Train={f.n_train} obs, Test={f.n_test} obs")

        # Step 3: Run Automated Point-in-Time Leakage Audit
        print("\n[Phase 7] 3. Running Automated Data Leakage Audit...")
        split_dicts = [
            {
                "fold_name": f.fold_name,
                "train_dates": [f.train_start_date, f.train_end_date],
                "test_dates": [f.test_start_date, f.test_end_date],
            }
            for f in folds
        ]
        audit_res = self.auditor.run_full_audit(observations, targets_list, split_dicts)
        print(f"  - Audit Status: {audit_res['status']} ({audit_res['passed_checks']}/{audit_res['total_checks']} checks passed)")

        # Step 4: Generate Dataset Lock Report
        print("\n[Phase 7] 4. Generating & Persisting Dataset Lock Report...")
        lock_report = self.runner.generate_dataset_lock(
            observations, targets_list, folds, output_dir=self.output_dir
        )
        print(lock_report.to_formatted_str())

        # Step 5: Prepare Aligned Feature and Target Matrices
        obs_map = {o.observation_id: o for o in observations}
        feat_map = {f.observation_id: f for f in features_list}
        targ_map = {t.observation_id: t for t in targets_list}

        # Filter to complete cases shared by Model A and Model B
        complete_obs = [
            o for o in observations
            if o.has_complete_baseline and o.has_complete_filing and o.has_valid_target
        ]
        complete_ids = set(o.observation_id for o in complete_obs)

        # Step 6: Primary and Secondary Model Comparisons across Folds
        print("\n[Phase 7] 5. Training & Evaluating Models on Walk-Forward Splits...")
        model_results_records: List[Dict[str, Any]] = []
        all_continuous_results: Dict[str, Dict[str, ContinuousModelResult]] = {}

        targets_to_evaluate = [
            ("forward_ebit_margin_change", "PRIMARY"),
            ("forward_revenue_growth", "SECONDARY_CONT"),
        ]

        feature_specs = [
            ("BASELINE", BASELINE_FEATURE_NAMES, "Baseline (Fundamentals)"),
            ("ENHANCED_OPERATIONAL", BASELINE_FEATURE_NAMES + PRESPECIFIED_OPERATIONAL_FEATURES, "Enhanced (Operational Risk Pre-Specified)"),
            ("ENHANCED_RISK", BASELINE_FEATURE_NAMES + RISK_GROUP_FEATURES, "Enhanced (Risk Group)"),
            ("ENHANCED_OPERATING", BASELINE_FEATURE_NAMES + OPERATING_GROUP_FEATURES, "Enhanced (Operating Group)"),
            ("ENHANCED_MANAGEMENT", BASELINE_FEATURE_NAMES + MANAGEMENT_GROUP_FEATURES, "Enhanced (Management Group)"),
            ("ENHANCED_OMNIBUS", BASELINE_FEATURE_NAMES + OMNIBUS_QUALITATIVE_FEATURES, "Enhanced (Omnibus All 12)"),
        ]

        for fold in folds:
            train_obs_fold = [obs_map[oid] for oid in fold.train_obs_ids if oid in complete_ids]
            test_obs_fold = [obs_map[oid] for oid in fold.test_obs_ids if oid in complete_ids]

            for targ_col, targ_role in targets_to_evaluate:
                train_y = [getattr(targ_map[o.observation_id], targ_col) for o in train_obs_fold]
                test_y = [getattr(targ_map[o.observation_id], targ_col) for o in test_obs_fold]

                fold_key = f"{fold.fold_name}_{targ_col}"
                all_continuous_results[fold_key] = {}

                # First, fit Baseline Model A
                base_fnames = BASELINE_FEATURE_NAMES
                train_raw_base = [[feat_map[o.observation_id].baseline.get(fn, 0.0) for fn in base_fnames] for o in train_obs_fold]
                test_raw_base = [[feat_map[o.observation_id].baseline.get(fn, 0.0) for fn in base_fnames] for o in test_obs_fold]

                base_res = self.runner.evaluate_continuous_model(
                    model_name="BASELINE",
                    fold_name=fold.fold_name,
                    target_name=targ_col,
                    train_raw_X=train_raw_base,
                    train_y=train_y,
                    test_raw_X=test_raw_base,
                    test_y=test_y,
                    feature_names=base_fnames,
                )
                all_continuous_results[fold_key]["BASELINE"] = base_res

                # Record baseline row
                model_results_records.append({
                    "result_id": str(uuid.uuid4()),
                    "fold_name": fold.fold_name,
                    "target_name": targ_col,
                    "model_name": "BASELINE",
                    "model_type": "RidgeRegression",
                    "n_train": base_res.n_train,
                    "n_test": base_res.n_test,
                    "mae": base_res.mae,
                    "rmse": base_res.rmse,
                    "r2": base_res.r2,
                    "pearson_r": base_res.pearson_r,
                    "spearman_rho": base_res.spearman_rho,
                    "delta_mae": 0.0,
                    "delta_rmse": 0.0,
                    "pct_mae_improvement": 0.0,
                    "paired_t_stat": 0.0,
                    "p_value": 1.0,
                    "permutation_p_value": 1.0,
                    "bootstrap_ci_lower": 0.0,
                    "bootstrap_ci_upper": 0.0,
                    "brier_score": None,
                    "roc_auc": None,
                    "pr_auc": None,
                    "accuracy": None,
                })

                # Now fit each Enhanced specification
                for spec_id, fnames, label in feature_specs:
                    if spec_id == "BASELINE":
                        continue

                    def build_row(obs_obj: PanelObservation) -> List[float]:
                        fobj = feat_map[obs_obj.observation_id]
                        row: List[float] = []
                        for fn in fnames:
                            if fn in fobj.baseline:
                                row.append(fobj.baseline[fn])
                            else:
                                row.append(fobj.filing.get(fn, 0.0))
                        return row

                    train_raw_enh = [build_row(o) for o in train_obs_fold]
                    test_raw_enh = [build_row(o) for o in test_obs_fold]

                    enh_res = self.runner.evaluate_continuous_model(
                        model_name=spec_id,
                        fold_name=fold.fold_name,
                        target_name=targ_col,
                        train_raw_X=train_raw_enh,
                        train_y=train_y,
                        test_raw_X=test_raw_enh,
                        test_y=test_y,
                        feature_names=fnames,
                    )
                    all_continuous_results[fold_key][spec_id] = enh_res

                    # Compare against Baseline
                    comp = self.runner.compare_continuous_models(base_res, enh_res)

                    model_results_records.append({
                        "result_id": str(uuid.uuid4()),
                        "fold_name": fold.fold_name,
                        "target_name": targ_col,
                        "model_name": spec_id,
                        "model_type": "RidgeRegression",
                        "n_train": enh_res.n_train,
                        "n_test": enh_res.n_test,
                        "mae": enh_res.mae,
                        "rmse": enh_res.rmse,
                        "r2": enh_res.r2,
                        "pearson_r": enh_res.pearson_r,
                        "spearman_rho": enh_res.spearman_rho,
                        "delta_mae": comp["delta_mae"],
                        "delta_rmse": comp["delta_rmse"],
                        "pct_mae_improvement": comp["pct_mae_improvement"],
                        "paired_t_stat": comp["paired_t_stat"],
                        "p_value": comp["p_value"],
                        "permutation_p_value": comp["permutation_p_value"],
                        "bootstrap_ci_lower": comp["bootstrap_ci_lower"],
                        "bootstrap_ci_upper": comp["bootstrap_ci_upper"],
                        "brier_score": None,
                        "roc_auc": None,
                        "pr_auc": None,
                        "accuracy": None,
                    })

            # Evaluate Binary Target: earnings_deterioration
            train_y_bin = [getattr(targ_map[o.observation_id], "earnings_deterioration") for o in train_obs_fold]
            test_y_bin = [getattr(targ_map[o.observation_id], "earnings_deterioration") for o in test_obs_fold]

            # Model A Binary
            train_raw_base = [[feat_map[o.observation_id].baseline.get(fn, 0.0) for fn in BASELINE_FEATURE_NAMES] for o in train_obs_fold]
            test_raw_base = [[feat_map[o.observation_id].baseline.get(fn, 0.0) for fn in BASELINE_FEATURE_NAMES] for o in test_obs_fold]
            bin_base = self.runner.evaluate_binary_model(
                model_name="BASELINE_LOGISTIC",
                fold_name=fold.fold_name,
                target_name="earnings_deterioration",
                train_raw_X=train_raw_base,
                train_y=train_y_bin,
                test_raw_X=test_raw_base,
                test_y=test_y_bin,
                feature_names=BASELINE_FEATURE_NAMES,
            )
            model_results_records.append({
                "result_id": str(uuid.uuid4()),
                "fold_name": fold.fold_name,
                "target_name": "earnings_deterioration",
                "model_name": "BASELINE_LOGISTIC",
                "model_type": "LogisticRegression",
                "n_train": bin_base.n_train,
                "n_test": bin_base.n_test,
                "mae": None,
                "rmse": None,
                "r2": None,
                "pearson_r": None,
                "spearman_rho": None,
                "delta_mae": None,
                "delta_rmse": None,
                "pct_mae_improvement": None,
                "paired_t_stat": None,
                "p_value": None,
                "permutation_p_value": None,
                "bootstrap_ci_lower": None,
                "bootstrap_ci_upper": None,
                "brier_score": bin_base.brier,
                "roc_auc": bin_base.roc_auc,
                "pr_auc": bin_base.pr_auc,
                "accuracy": bin_base.accuracy,
            })

            # Model B Operational Binary
            op_fnames = BASELINE_FEATURE_NAMES + PRESPECIFIED_OPERATIONAL_FEATURES
            def build_bin_row(obs_obj: PanelObservation) -> List[float]:
                fobj = feat_map[obs_obj.observation_id]
                return [
                    fobj.baseline[fn] if fn in fobj.baseline else fobj.filing.get(fn, 0.0)
                    for fn in op_fnames
                ]
            train_raw_enh_bin = [build_bin_row(o) for o in train_obs_fold]
            test_raw_enh_bin = [build_bin_row(o) for o in test_obs_fold]
            bin_enh = self.runner.evaluate_binary_model(
                model_name="ENHANCED_OPERATIONAL_LOGISTIC",
                fold_name=fold.fold_name,
                target_name="earnings_deterioration",
                train_raw_X=train_raw_enh_bin,
                train_y=train_y_bin,
                test_raw_X=test_raw_enh_bin,
                test_y=test_y_bin,
                feature_names=op_fnames,
            )
            model_results_records.append({
                "result_id": str(uuid.uuid4()),
                "fold_name": fold.fold_name,
                "target_name": "earnings_deterioration",
                "model_name": "ENHANCED_OPERATIONAL_LOGISTIC",
                "model_type": "LogisticRegression",
                "n_train": bin_enh.n_train,
                "n_test": bin_enh.n_test,
                "mae": None,
                "rmse": None,
                "r2": None,
                "pearson_r": None,
                "spearman_rho": None,
                "delta_mae": None,
                "delta_rmse": None,
                "pct_mae_improvement": None,
                "paired_t_stat": None,
                "p_value": None,
                "permutation_p_value": None,
                "bootstrap_ci_lower": None,
                "bootstrap_ci_upper": None,
                "brier_score": bin_enh.brier,
                "roc_auc": bin_enh.roc_auc,
                "pr_auc": bin_enh.pr_auc,
                "accuracy": bin_enh.accuracy,
            })

        # Step 7: Structured Ablation Study (Fold 1, Primary Target)
        print("\n[Phase 7] 6. Running Pre-Specified Ablation Study...")
        ablation_records: List[Dict[str, Any]] = []
        fold1 = folds[0]
        f1_key = f"{fold1.fold_name}_forward_ebit_margin_change"
        f1_base_res = all_continuous_results[f1_key]["BASELINE"]

        ablation_specs = [
            ("A. Baseline Fundamentals", BASELINE_FEATURE_NAMES),
            ("B. Baseline + All Filing Features", BASELINE_FEATURE_NAMES + OMNIBUS_QUALITATIVE_FEATURES),
            ("C. Baseline + Operational Risk Group", BASELINE_FEATURE_NAMES + PRESPECIFIED_OPERATIONAL_FEATURES),
            ("D. Baseline + Risk Group", BASELINE_FEATURE_NAMES + RISK_GROUP_FEATURES),
            ("E. Baseline + Operating Group", BASELINE_FEATURE_NAMES + OPERATING_GROUP_FEATURES),
            ("F. Baseline + Management Group", BASELINE_FEATURE_NAMES + MANAGEMENT_GROUP_FEATURES),
        ]

        train_obs_f1 = [obs_map[oid] for oid in fold1.train_obs_ids if oid in complete_ids]
        test_obs_f1 = [obs_map[oid] for oid in fold1.test_obs_ids if oid in complete_ids]
        train_y_f1 = [targ_map[o.observation_id].forward_ebit_margin_change for o in train_obs_f1]
        test_y_f1 = [targ_map[o.observation_id].forward_ebit_margin_change for o in test_obs_f1]

        for grp_name, fnames in ablation_specs:
            def build_abl_row(obs_obj: PanelObservation) -> List[float]:
                fobj = feat_map[obs_obj.observation_id]
                return [fobj.baseline[fn] if fn in fobj.baseline else fobj.filing.get(fn, 0.0) for fn in fnames]

            train_X = [build_abl_row(o) for o in train_obs_f1]
            test_X = [build_abl_row(o) for o in test_obs_f1]

            abl_eval = self.runner.evaluate_continuous_model(
                model_name=grp_name,
                fold_name=fold1.fold_name,
                target_name="forward_ebit_margin_change",
                train_raw_X=train_X,
                train_y=train_y_f1,
                test_raw_X=test_X,
                test_y=test_y_f1,
                feature_names=fnames,
            )
            comp = self.runner.compare_continuous_models(f1_base_res, abl_eval)
            ablation_records.append({
                "ablation_id": str(uuid.uuid4()),
                "fold_name": fold1.fold_name,
                "target_name": "forward_ebit_margin_change",
                "feature_group_name": grp_name,
                "feature_names": ", ".join(fnames),
                "n_features": len(fnames),
                "mae": abl_eval.mae,
                "rmse": abl_eval.rmse,
                "delta_mae": comp["delta_mae"],
                "pct_mae_improvement": comp["pct_mae_improvement"],
                "paired_t_stat": comp["paired_t_stat"],
                "p_value": comp["p_value"],
            })

        # Step 8: Rigorous Robustness Checks
        print("\n[Phase 7] 7. Running Multi-Dimensional Robustness Checks...")
        robustness_records: List[Dict[str, Any]] = []

        # 8.1 Sector-Level Breakdown (Fold 1, Operational Model)
        op_fnames = BASELINE_FEATURE_NAMES + PRESPECIFIED_OPERATIONAL_FEATURES
        f1_op_res = all_continuous_results[f1_key]["ENHANCED_OPERATIONAL"]
        sectors = sorted(list(set(o.sector for o in test_obs_f1)))

        for sec in sectors:
            sec_indices = [i for i, o in enumerate(test_obs_f1) if o.sector == sec]
            if len(sec_indices) >= 2:
                sec_base_errs = [f1_base_res.errors[i] for i in sec_indices]
                sec_enh_errs = [f1_op_res.errors[i] for i in sec_indices]
                sec_base_mae = sum(sec_base_errs) / len(sec_base_errs)
                sec_enh_mae = sum(sec_enh_errs) / len(sec_enh_errs)
                delta = sec_base_mae - sec_enh_mae
                pct = (delta / sec_base_mae) * 100.0 if sec_base_mae > 0 else 0.0
                t_stat, p_val = paired_t_test(sec_base_errs, sec_enh_errs)
                conclusion = "IMPROVED" if delta > 0 and p_val < 0.10 else ("DEGRADED" if delta < 0 else "NEUTRAL")

                robustness_records.append({
                    "robustness_id": str(uuid.uuid4()),
                    "test_dimension": "SECTOR_SUBSAMPLE",
                    "subgroup": sec,
                    "n_obs": len(sec_indices),
                    "baseline_mae": sec_base_mae,
                    "enhanced_mae": sec_enh_mae,
                    "delta_mae": delta,
                    "pct_improvement": pct,
                    "p_value": p_val,
                    "conclusion": conclusion,
                })

        # 8.2 Regularization Sensitivity Check (alpha = 0.01 to 100.0)
        train_base_f1 = [[feat_map[o.observation_id].baseline.get(fn, 0.0) for fn in base_fnames] for o in train_obs_f1]
        test_base_f1 = [[feat_map[o.observation_id].baseline.get(fn, 0.0) for fn in base_fnames] for o in test_obs_f1]
        train_op_f1 = [
            [feat_map[o.observation_id].baseline[fn] if fn in feat_map[o.observation_id].baseline else feat_map[o.observation_id].filing.get(fn, 0.0) for fn in op_fnames]
            for o in train_obs_f1
        ]
        test_op_f1 = [
            [feat_map[o.observation_id].baseline[fn] if fn in feat_map[o.observation_id].baseline else feat_map[o.observation_id].filing.get(fn, 0.0) for fn in op_fnames]
            for o in test_obs_f1
        ]

        alphas_to_test = [0.01, 0.1, 1.0, 10.0, 50.0, 100.0]
        for a in alphas_to_test:
            # Baseline with fixed alpha
            b_eval = self.runner.evaluate_continuous_model(
                model_name=f"BASELINE_ALPHA_{a}",
                fold_name=fold1.fold_name,
                target_name="forward_ebit_margin_change",
                train_raw_X=train_base_f1,
                train_y=train_y_f1,
                test_raw_X=test_base_f1,
                test_y=test_y_f1,
                feature_names=base_fnames,
                alpha=a,
            )
            e_eval = self.runner.evaluate_continuous_model(
                model_name=f"ENHANCED_ALPHA_{a}",
                fold_name=fold1.fold_name,
                target_name="forward_ebit_margin_change",
                train_raw_X=train_op_f1,
                train_y=train_y_f1,
                test_raw_X=test_op_f1,
                test_y=test_y_f1,
                feature_names=op_fnames,
                alpha=a,
            )
            comp_a = self.runner.compare_continuous_models(b_eval, e_eval)
            conc = "ROBUST" if comp_a["delta_mae"] >= 0 else "SENSITIVE_TO_PENALTY"
            robustness_records.append({
                "robustness_id": str(uuid.uuid4()),
                "test_dimension": "REGULARIZATION_SENSITIVITY",
                "subgroup": f"Alpha={a}",
                "n_obs": len(test_y_f1),
                "baseline_mae": b_eval.mae,
                "enhanced_mae": e_eval.mae,
                "delta_mae": comp_a["delta_mae"],
                "pct_improvement": comp_a["pct_mae_improvement"],
                "p_value": comp_a["p_value"],
                "conclusion": conc,
            })

        # 8.3 Outlier Trimming Check (Trim Top 10% extreme errors)
        n_test = len(f1_base_res.errors)
        trim_k = max(1, int(0.10 * n_test))
        # Find indices of largest baseline errors
        sorted_err_idx = sorted(range(n_test), key=lambda i: f1_base_res.errors[i])
        trimmed_idx = sorted_err_idx[:-trim_k]
        trim_base_errs = [f1_base_res.errors[i] for i in trimmed_idx]
        trim_enh_errs = [f1_op_res.errors[i] for i in trimmed_idx]
        t_base_mae = sum(trim_base_errs) / len(trim_base_errs)
        t_enh_mae = sum(trim_enh_errs) / len(trim_enh_errs)
        t_delta = t_base_mae - t_enh_mae
        t_pct = (t_delta / t_base_mae) * 100.0
        t_stat, t_pval = paired_t_test(trim_base_errs, trim_enh_errs)

        robustness_records.append({
            "robustness_id": str(uuid.uuid4()),
            "test_dimension": "OUTLIER_TRIMMING",
            "subgroup": f"Trimmed_Top_{trim_k}_Outliers",
            "n_obs": len(trimmed_idx),
            "baseline_mae": t_base_mae,
            "enhanced_mae": t_enh_mae,
            "delta_mae": t_delta,
            "pct_improvement": t_pct,
            "p_value": t_pval,
            "conclusion": "ROBUST" if t_delta > 0 else "DRIVEN_BY_OUTLIERS",
        })

        # 8.4 Filing Features Only (No Fundamentals)
        pure_filing_fnames = PRESPECIFIED_OPERATIONAL_FEATURES
        train_pure_filing = [[feat_map[o.observation_id].filing.get(fn, 0.0) for fn in pure_filing_fnames] for o in train_obs_f1]
        test_pure_filing = [[feat_map[o.observation_id].filing.get(fn, 0.0) for fn in pure_filing_fnames] for o in test_obs_f1]
        pure_f_eval = self.runner.evaluate_continuous_model(
            model_name="FILING_ONLY_OPERATIONAL",
            fold_name=fold1.fold_name,
            target_name="forward_ebit_margin_change",
            train_raw_X=train_pure_filing,
            train_y=train_y_f1,
            test_raw_X=test_pure_filing,
            test_y=test_y_f1,
            feature_names=pure_filing_fnames,
        )
        comp_pf = self.runner.compare_continuous_models(f1_base_res, pure_f_eval)
        robustness_records.append({
            "robustness_id": str(uuid.uuid4()),
            "test_dimension": "FILING_FEATURES_ONLY",
            "subgroup": "Margin_Pressure_Supply_Chain_Only",
            "n_obs": len(test_y_f1),
            "baseline_mae": f1_base_res.mae,
            "enhanced_mae": pure_f_eval.mae,
            "delta_mae": comp_pf["delta_mae"],
            "pct_improvement": comp_pf["pct_mae_improvement"],
            "p_value": comp_pf["p_value"],
            "conclusion": "PARITY_NO_SIGNIFICANCE" if comp_pf["p_value"] >= 0.05 else ("IMPROVED" if comp_pf["delta_mae"] > 0 else "DEGRADED"),
        })

        # Step 9: Persist All Results to DuckDB
        print("\n[Phase 7] 8. Persisting Results to DuckDB...")
        self._persist_experiment_results(model_results_records, ablation_records, robustness_records)

        # Step 10: Export All 8 CSV Tables
        print("\n[Phase 7] 9. Exporting 8 CSV Audit Tables to results/tables/...")
        csv_paths = self.export_all_csv_tables()

        return {
            "dataset_lock": lock_report,
            "audit_result": audit_res,
            "model_results": model_results_records,
            "ablation_results": ablation_records,
            "robustness_results": robustness_records,
            "csv_paths": csv_paths,
        }

    def _persist_experiment_results(
        self,
        model_records: List[Dict[str, Any]],
        ablation_records: List[Dict[str, Any]],
        robustness_records: List[Dict[str, Any]],
    ) -> None:
        """Persist model, ablation, and robustness results into DuckDB."""
        with self.db.get_connection() as con:
            con.execute("DELETE FROM research_panel_model_results")
            con.execute("DELETE FROM research_panel_ablation_results")
            con.execute("DELETE FROM research_panel_robustness_results")

            for r in model_records:
                con.execute(
                    """
                    INSERT INTO research_panel_model_results (
                        result_id, fold_name, target_name, model_name, model_type,
                        n_train, n_test, mae, rmse, r2, pearson_r, spearman_rho,
                        delta_mae, delta_rmse, pct_mae_improvement, paired_t_stat, p_value,
                        permutation_p_value, bootstrap_ci_lower, bootstrap_ci_upper,
                        brier_score, roc_auc, pr_auc, accuracy
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        r["result_id"], r["fold_name"], r["target_name"], r["model_name"], r["model_type"],
                        r["n_train"], r["n_test"], r["mae"], r["rmse"], r["r2"], r["pearson_r"], r["spearman_rho"],
                        r["delta_mae"], r["delta_rmse"], r["pct_mae_improvement"], r["paired_t_stat"], r["p_value"],
                        r["permutation_p_value"], r["bootstrap_ci_lower"], r["bootstrap_ci_upper"],
                        r["brier_score"], r["roc_auc"], r["pr_auc"], r["accuracy"]
                    ],
                )

            for r in ablation_records:
                con.execute(
                    """
                    INSERT INTO research_panel_ablation_results (
                        ablation_id, fold_name, target_name, feature_group_name, feature_names,
                        n_features, mae, rmse, delta_mae, pct_mae_improvement, paired_t_stat, p_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        r["ablation_id"], r["fold_name"], r["target_name"], r["feature_group_name"],
                        r["feature_names"], r["n_features"], r["mae"], r["rmse"],
                        r["delta_mae"], r["pct_mae_improvement"], r["paired_t_stat"], r["p_value"]
                    ],
                )

            for r in robustness_records:
                con.execute(
                    """
                    INSERT INTO research_panel_robustness_results (
                        robustness_id, test_dimension, subgroup, n_obs, baseline_mae, enhanced_mae,
                        delta_mae, pct_improvement, p_value, conclusion
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        r["robustness_id"], r["test_dimension"], r["subgroup"], r["n_obs"],
                        r["baseline_mae"], r["enhanced_mae"], r["delta_mae"], r["pct_improvement"],
                        r["p_value"], r["conclusion"]
                    ],
                )

    def export_all_csv_tables(self) -> Dict[str, str]:
        """
        Export all 8 research tables from DuckDB into standardized CSV audit files.
        """
        table_mappings = [
            ("research_panel_observations", "phase7_panel_observations.csv"),
            ("research_panel_features", "phase7_panel_features.csv"),
            ("research_panel_targets", "phase7_panel_targets.csv"),
            ("research_walkforward_splits", "phase7_walkforward_splits.csv"),
            ("research_panel_model_results", "phase7_panel_model_results.csv"),
            ("research_panel_ablation_results", "phase7_panel_ablation_results.csv"),
            ("research_panel_robustness_results", "phase7_panel_robustness_results.csv"),
            ("research_panel_leakage_audit", "phase7_panel_leakage_audit.csv"),
        ]

        paths: Dict[str, str] = {}
        with self.db.get_connection() as con:
            for tbl, fname in table_mappings:
                fpath = os.path.join(self.output_dir, fname)
                con.execute(f"COPY {tbl} TO '{fpath}' (HEADER, DELIMITER ',')")
                paths[tbl] = fpath

        return paths
