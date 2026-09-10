"""
Research Experiment Orchestrator for Phase 6.

Coordinates end-to-end execution of:
- Task A: Controlled Valuation Bridge across all 30 companies.
- Task B: Predictive Information Content (Baseline vs Enhanced on continuous & binary targets).
- Task C: Category Ablation Studies and Cross-Sector Robustness Checks.
- DuckDB persistence and CSV audit export.
"""
import csv
import logging
import os
from typing import Any, Dict, List, Optional
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.ablation import run_ablation_study
from src.research.dataset_builder import ResearchDatasetBuilder
from src.research.evaluation import compare_models
from src.research.models import (
    ExperimentConfig,
    ModelComparisonResult,
    ValuationComparisonRecord,
)
from src.research.robustness import run_regularization_sensitivity, run_sector_robustness
from src.research.valuation_bridge import run_universe_valuation_bridge

logger = logging.getLogger(__name__)


class ResearchExperimentOrchestrator:
    """Coordinates and logs empirical research experiments."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)
        self.dataset_builder = ResearchDatasetBuilder(db_manager=self.db)

    def run_all_experiments(
        self,
        export_csv_dir: str = "results/tables",
        persist_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute full Phase 6 empirical research workflow.
        """
        os.makedirs(export_csv_dir, exist_ok=True)
        logger.info("Starting Phase 6 Research Integration & Empirical Evaluation...")

        # 1. Build Point-in-Time Research Dataset
        dataset = self.dataset_builder.build_dataset(base_fiscal_year=2023, forward_fiscal_year=2024)
        if persist_db:
            self.dataset_builder.persist_dataset_to_db(dataset)
        logger.info(f"Dataset assembled with {len(dataset['observations'])} observations.")

        observations = dataset["observations"]
        base_features = dataset["baseline_features"]
        filing_features = dataset["filing_features"]
        targets = dataset["targets"]
        metadata = dataset["metadata"]

        # Filter complete-case valid observations
        valid_indices = [i for i, t in enumerate(targets) if t.is_valid]
        logger.info(f"Complete-case valid observations: {len(valid_indices)}/{len(observations)}")

        obs_valid = [observations[i] for i in valid_indices]
        base_valid = [base_features[i] for i in valid_indices]
        filing_valid = [filing_features[i] for i in valid_indices]
        targs_valid = [targets[i] for i in valid_indices]
        tickers = [o.ticker for o in obs_valid]
        obs_ids = [o.observation_id for o in obs_valid]
        sectors = [o.sector for o in obs_valid]

        # Feature matrices
        base_feature_names = [
            "revenue_growth_yoy", "ebit_margin", "gross_margin", "roic",
            "fcf_margin", "net_debt_to_revenue", "owc_to_revenue", "beta", "wacc"
        ]
        filing_feature_names = [
            "margin_pressure_score", "supply_chain_risk_score", "regulatory_risk_score",
            "litigation_risk_score", "demand_uncertainty_score", "guidance_sentiment_score",
            "capital_allocation_score", "total_risk_claims", "high_materiality_risk_count",
            "escalated_risk_count", "net_qualitative_sentiment"
        ]

        X_base = [b.to_vector(base_feature_names) for b in base_valid]
        X_enh = [b.to_vector(base_feature_names) + f.to_vector(filing_feature_names) for b, f in zip(base_valid, filing_valid)]
        filing_dicts = [f.to_dict() for f in filing_valid]

        # ----------------------------------------------------------------------
        # TASK B: PREDICTIVE INFORMATION CONTENT EXPERIMENTS
        # ----------------------------------------------------------------------
        comparisons: List[ModelComparisonResult] = []
        all_model_results: List[Dict[str, Any]] = []
        experiment_records: List[Dict[str, Any]] = []

        # Target 1: Forward 1-Year Operating Margin Change (Continuous Primary)
        y_margin = [float(t.forward_ebit_margin_change) for t in targs_valid]
        exp1_id = "exp_forward_ebit_margin_change"
        config1 = ExperimentConfig(
            experiment_id=exp1_id,
            experiment_name="Predictive_Forward_EBIT_Margin_Change",
            target_name="forward_ebit_margin_change",
            horizon_months=12,
            baseline_model_type="RidgeRegression",
            enhanced_model_type="RidgeRegression",
            validation_method="leave_one_out",
            alpha_ridge=1.0,
            baseline_features=base_feature_names,
            enhanced_features=base_feature_names + filing_feature_names,
        )
        comp1, rows1 = compare_models(
            experiment_id=exp1_id,
            target_name=config1.target_name,
            X_baseline=X_base,
            X_enhanced=X_enh,
            y=y_margin,
            tickers=tickers,
            observation_ids=obs_ids,
            config=config1,
        )
        comparisons.append(comp1)
        all_model_results.extend(rows1)
        experiment_records.append({
            "experiment_id": exp1_id,
            "experiment_name": config1.experiment_name,
            "target_name": config1.target_name,
            "horizon_months": 12,
            "baseline_model_type": config1.baseline_model_type,
            "enhanced_model_type": config1.enhanced_model_type,
            "validation_method": config1.validation_method,
            "sample_size": len(y_margin),
            "features_baseline": ",".join(base_feature_names),
            "features_enhanced": ",".join(base_feature_names + filing_feature_names),
            "hyperparameters": f"alpha={config1.alpha_ridge}",
        })

        # Target 2: Forward 1-Year Revenue Growth (Continuous Secondary)
        y_rev = [float(t.forward_revenue_growth) for t in targs_valid]
        exp2_id = "exp_forward_revenue_growth"
        config2 = ExperimentConfig(
            experiment_id=exp2_id,
            experiment_name="Predictive_Forward_Revenue_Growth",
            target_name="forward_revenue_growth",
            horizon_months=12,
            baseline_model_type="RidgeRegression",
            enhanced_model_type="RidgeRegression",
            validation_method="leave_one_out",
            alpha_ridge=1.0,
            baseline_features=base_feature_names,
            enhanced_features=base_feature_names + filing_feature_names,
        )
        comp2, rows2 = compare_models(
            experiment_id=exp2_id,
            target_name=config2.target_name,
            X_baseline=X_base,
            X_enhanced=X_enh,
            y=y_rev,
            tickers=tickers,
            observation_ids=obs_ids,
            config=config2,
        )
        comparisons.append(comp2)
        all_model_results.extend(rows2)
        experiment_records.append({
            "experiment_id": exp2_id,
            "experiment_name": config2.experiment_name,
            "target_name": config2.target_name,
            "horizon_months": 12,
            "baseline_model_type": config2.baseline_model_type,
            "enhanced_model_type": config2.enhanced_model_type,
            "validation_method": config2.validation_method,
            "sample_size": len(y_rev),
            "features_baseline": ",".join(base_feature_names),
            "features_enhanced": ",".join(base_feature_names + filing_feature_names),
            "hyperparameters": f"alpha={config2.alpha_ridge}",
        })

        # Target 3: Binary Earnings Deterioration
        y_det = [float(t.earnings_deterioration) for t in targs_valid]
        exp3_id = "exp_earnings_deterioration"
        config3 = ExperimentConfig(
            experiment_id=exp3_id,
            experiment_name="Predictive_Earnings_Deterioration",
            target_name="earnings_deterioration",
            horizon_months=12,
            baseline_model_type="LogisticRegression",
            enhanced_model_type="LogisticRegression",
            validation_method="leave_one_out",
            alpha_ridge=1.0,
            baseline_features=base_feature_names,
            enhanced_features=base_feature_names + filing_feature_names,
        )
        comp3, rows3 = compare_models(
            experiment_id=exp3_id,
            target_name=config3.target_name,
            X_baseline=X_base,
            X_enhanced=X_enh,
            y=y_det,
            tickers=tickers,
            observation_ids=obs_ids,
            config=config3,
        )
        comparisons.append(comp3)
        all_model_results.extend(rows3)
        experiment_records.append({
            "experiment_id": exp3_id,
            "experiment_name": config3.experiment_name,
            "target_name": config3.target_name,
            "horizon_months": 12,
            "baseline_model_type": config3.baseline_model_type,
            "enhanced_model_type": config3.enhanced_model_type,
            "validation_method": config3.validation_method,
            "sample_size": len(y_det),
            "features_baseline": ",".join(base_feature_names),
            "features_enhanced": ",".join(base_feature_names + filing_feature_names),
            "hyperparameters": f"alpha={config3.alpha_ridge}",
        })

        if persist_db:
            self.db.insert_research_experiments(experiment_records)
            self.db.insert_research_model_results(all_model_results)

        # ----------------------------------------------------------------------
        # TASK C: ABLATION AND ROBUSTNESS EXPERIMENTS
        # ----------------------------------------------------------------------
        # Ablation on Primary Target (Margin Change)
        ablations = run_ablation_study(
            experiment_id=exp1_id,
            base_features_matrix=X_base,
            filing_feature_dict_list=filing_dicts,
            y=y_margin,
            config=config1,
            baseline_mae=comp1.baseline_metrics.mae,
            baseline_rmse=comp1.baseline_metrics.rmse,
        )
        if persist_db:
            ablation_records = [
                {
                    "ablation_id": f"abl_{exp1_id}_{a.ablation_group}",
                    "experiment_id": exp1_id,
                    "ablation_group": a.ablation_group,
                    "feature_count": a.feature_count,
                    "mae": a.mae,
                    "rmse": a.rmse,
                    "r2": a.r2,
                    "delta_mae_vs_baseline": a.delta_mae_vs_baseline,
                    "delta_rmse_vs_baseline": a.delta_rmse_vs_baseline,
                    "sample_size": a.sample_size,
                }
                for a in ablations
            ]
            self.db.insert_research_ablation_results(ablation_records)

        # Robustness: Cross-Sector Stratification
        sector_robustness = run_sector_robustness(
            experiment_id=exp1_id,
            X_baseline=X_base,
            X_enhanced=X_enh,
            y=y_margin,
            sectors=sectors,
            config=config1,
        )

        # Robustness: Regularization Sensitivity
        lambda_robustness = run_regularization_sensitivity(
            experiment_id=exp1_id,
            X_baseline=X_base,
            X_enhanced=X_enh,
            y=y_margin,
            config=config1,
            lambdas=[0.1, 1.0, 10.0, 50.0],
        )
        all_robustness = sector_robustness + lambda_robustness
        if persist_db:
            robust_records = [
                {
                    "robustness_id": f"rob_{exp1_id}_{r.test_type}_{r.stratum}",
                    "experiment_id": exp1_id,
                    "test_type": r.test_type,
                    "stratum": r.stratum,
                    "sample_size": r.sample_size,
                    "baseline_mae": r.baseline_mae,
                    "enhanced_mae": r.enhanced_mae,
                    "delta_mae": r.delta_mae,
                    "baseline_rmse": r.baseline_rmse,
                    "enhanced_rmse": r.enhanced_rmse,
                    "delta_rmse": r.delta_rmse,
                }
                for r in all_robustness
            ]
            self.db.insert_research_robustness_results(robust_records)

        # ----------------------------------------------------------------------
        # TASK A: VALUATION BRIDGE EXPERIMENT
        # ----------------------------------------------------------------------
        val_comparisons = run_universe_valuation_bridge(valuation_date="2024-12-31", db_manager=self.db)
        logger.info(f"Valuation bridge completed for {len(val_comparisons)} companies.")

        # ----------------------------------------------------------------------
        # EXPORT 5 AUDIT CSV TABLES
        # ----------------------------------------------------------------------
        # 1. phase6_dataset_summary.csv
        dataset_summary_path = os.path.join(export_csv_dir, "phase6_dataset_summary.csv")
        with open(dataset_summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "observation_id", "ticker", "company_name", "sector", "observation_date",
                "data_as_of_date", "fiscal_year", "claims_count", "ebit_margin_t0",
                "rev_growth_t0", "forward_margin_change", "forward_rev_growth",
                "earnings_deterioration", "realization_date", "is_valid"
            ])
            for o, b, t, m in zip(observations, base_features, targets, metadata):
                writer.writerow([
                    o.observation_id, o.ticker, m.get("company_name", ""), o.sector,
                    o.observation_date, o.data_as_of_date, o.fiscal_year,
                    m.get("claims_count", 0), round(b.ebit_margin, 4), round(b.revenue_growth_yoy, 4),
                    round(t.forward_ebit_margin_change, 4) if t.forward_ebit_margin_change is not None else "",
                    round(t.forward_revenue_growth, 4) if t.forward_revenue_growth is not None else "",
                    int(t.earnings_deterioration) if t.earnings_deterioration is not None else "",
                    t.realization_date, t.is_valid,
                ])
        logger.info(f"Saved {dataset_summary_path}")

        # 2. phase6_model_comparison.csv
        model_comp_path = os.path.join(export_csv_dir, "phase6_model_comparison.csv")
        with open(model_comp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "experiment_id", "target_name", "sample_size",
                "baseline_mae", "enhanced_mae", "delta_mae", "pct_mae_improvement",
                "baseline_rmse", "enhanced_rmse", "delta_rmse",
                "baseline_r2", "enhanced_r2", "delta_r2",
                "p_value_paired_t", "p_value_permutation",
                "ci_delta_mae_low", "ci_delta_mae_high", "is_statistically_significant"
            ])
            for c in comparisons:
                pct_imp = (c.delta_mae / c.baseline_metrics.mae) * 100.0 if c.baseline_metrics.mae > 0 else 0.0
                writer.writerow([
                    c.experiment_id, c.target_name, c.baseline_metrics.sample_size,
                    round(c.baseline_metrics.mae, 5), round(c.enhanced_metrics.mae, 5),
                    round(c.delta_mae, 5), round(pct_imp, 2),
                    round(c.baseline_metrics.rmse, 5), round(c.enhanced_metrics.rmse, 5),
                    round(c.delta_rmse, 5),
                    round(c.baseline_metrics.r2, 4), round(c.enhanced_metrics.r2, 4),
                    round(c.delta_r2, 4),
                    round(c.p_value_paired_t, 4), round(c.p_value_permutation, 4),
                    round(c.bootstrap_ci_delta_mae[0], 5), round(c.bootstrap_ci_delta_mae[1], 5),
                    c.is_statistically_significant,
                ])
        logger.info(f"Saved {model_comp_path}")

        # 3. phase6_ablation.csv
        ablation_path = os.path.join(export_csv_dir, "phase6_ablation.csv")
        with open(ablation_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ablation_group", "feature_count", "mae", "rmse", "r2",
                "delta_mae_vs_baseline", "delta_rmse_vs_baseline", "sample_size"
            ])
            for a in ablations:
                writer.writerow([
                    a.ablation_group, a.feature_count,
                    round(a.mae, 5), round(a.rmse, 5), round(a.r2, 4),
                    round(a.delta_mae_vs_baseline, 5), round(a.delta_rmse_vs_baseline, 5),
                    a.sample_size,
                ])
        logger.info(f"Saved {ablation_path}")

        # 4. phase6_robustness.csv
        robust_path = os.path.join(export_csv_dir, "phase6_robustness.csv")
        with open(robust_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "test_type", "stratum", "sample_size", "baseline_mae", "enhanced_mae",
                "delta_mae", "baseline_rmse", "enhanced_rmse", "delta_rmse"
            ])
            for r in all_robustness:
                writer.writerow([
                    r.test_type, r.stratum, r.sample_size,
                    round(r.baseline_mae, 5), round(r.enhanced_mae, 5), round(r.delta_mae, 5),
                    round(r.baseline_rmse, 5), round(r.enhanced_rmse, 5), round(r.delta_rmse, 5),
                ])
        logger.info(f"Saved {robust_path}")

        # 5. phase6_valuation_comparison.csv
        val_comp_path = os.path.join(export_csv_dir, "phase6_valuation_comparison.csv")
        with open(val_comp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ticker", "company_name", "sector", "valuation_date",
                "baseline_fair_value", "enhanced_fair_value", "fair_value_diff",
                "pct_change", "market_price", "baseline_upside", "enhanced_upside",
                "primary_category", "intensity", "key_assumption", "adjustment", "evidence_citation"
            ])
            for v in val_comparisons:
                writer.writerow([
                    v.ticker, v.company_name, v.sector, v.valuation_date,
                    round(v.baseline_fair_value, 2), round(v.enhanced_fair_value, 2),
                    round(v.fair_value_difference, 2), round(v.fair_value_pct_change, 2),
                    round(v.market_price, 2), round(v.baseline_upside, 4), round(v.enhanced_upside, 4),
                    v.primary_signal_category, round(v.signal_intensity, 4),
                    v.key_assumption_adjusted, round(v.adjustment_magnitude, 4),
                    v.evidence_citation,
                ])
        logger.info(f"Saved {val_comp_path}")

        return {
            "comparisons": comparisons,
            "ablations": ablations,
            "robustness": all_robustness,
            "valuation_comparisons": val_comparisons,
        }
