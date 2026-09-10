"""
Phase 6 Experiment Execution Runner.

Executes the complete Phase 6 empirical evaluation pipeline across the 30-company universe:
1. Point-in-time dataset construction and DuckDB persistence.
2. Baseline (Model A) vs Filing-Enhanced (Model B) predictive evaluation.
3. Category ablation analysis.
4. Cross-sector robustness and lambda sensitivity checks.
5. Task A Valuation bridge execution across all 30 companies.
6. Exporting audit CSV tables to results/tables/.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.research.experiment import ResearchExperimentOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Phase6Pipeline")


def main() -> None:
    logger.info("Initializing Phase 6 Research Experiment Orchestrator...")
    orchestrator = ResearchExperimentOrchestrator()

    logger.info("Executing Phase 6 empirical research experiments...")
    results = orchestrator.run_all_experiments(
        export_csv_dir="results/tables",
        persist_db=True,
    )

    logger.info("=" * 70)
    logger.info("PHASE 6 EMPIRICAL EVALUATION SUMMARY")
    logger.info("=" * 70)

    for comp in results["comparisons"]:
        pct_imp = (comp.delta_mae / comp.baseline_metrics.mae) * 100.0 if comp.baseline_metrics.mae > 0 else 0.0
        logger.info(
            f"Target: {comp.target_name} (N={comp.baseline_metrics.sample_size}) | "
            f"Base MAE: {comp.baseline_metrics.mae:.5f} -> Enh MAE: {comp.enhanced_metrics.mae:.5f} "
            f"({pct_imp:+.2f}%) | Perm p-val: {comp.p_value_permutation:.4f} | "
            f"Sig: {comp.is_statistically_significant}"
        )

    logger.info("\nCategory Ablation Results (Target: forward_ebit_margin_change):")
    for a in results["ablations"]:
        logger.info(
            f"  {a.ablation_group:<28} (p={a.feature_count:>2}) | "
            f"MAE: {a.mae:.5f} (Delta: {a.delta_mae_vs_baseline:+.5f}) | R2: {a.r2:+.4f}"
        )

    logger.info(f"\nValuation Bridge: Completed for {len(results['valuation_comparisons'])} companies.")
    logger.info("Phase 6 experiments completed successfully.")


if __name__ == "__main__":
    main()
