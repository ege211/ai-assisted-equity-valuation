"""
Phase 4 Valuation Engine Orchestrator and Universe Audit Runner.

Executes deterministic discounted cash flow valuations, multi-scenario projections,
sensitivity analyses, and relative multiples benchmarking across the 30-company universe.

Outputs:
- DuckDB valuation tables:
  - valuation_assumptions
  - forecast_periods
  - valuation_results
  - valuation_sensitivities
  - relative_valuation_results
- Audit summary CSV tables:
  - results/tables/phase4_valuation_coverage.csv
  - results/tables/phase4_sensitivity_summary.csv
  - results/tables/phase4_input_quality.csv
"""
import csv
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import yaml

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from src.data.db import DatabaseManager
from src.valuation.engine import ValuationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Phase4ValuationPipeline")


def run_phase4_valuation(
    valuation_date: str = "2024-12-31",
    valuation_mode: str = "HISTORICAL",
    db_path: str = "data/processed/financials.duckdb",
    config_path: str = "config/universe.yaml",
) -> Dict[str, Any]:
    """Execute complete Phase 4 valuation workflow across the universe."""
    full_db_path = os.path.join(WORKSPACE_DIR, db_path)
    full_config_path = os.path.join(WORKSPACE_DIR, config_path)
    tables_dir = os.path.join(WORKSPACE_DIR, "results", "tables")
    os.makedirs(tables_dir, exist_ok=True)

    db = DatabaseManager(full_db_path)

    # Clean existing valuation tables to ensure fresh reproducible run
    with db.get_connection() as conn:
        conn.execute("DELETE FROM valuation_assumptions;")
        conn.execute("DELETE FROM forecast_periods;")
        conn.execute("DELETE FROM valuation_results;")
        conn.execute("DELETE FROM valuation_sensitivities;")
        conn.execute("DELETE FROM relative_valuation_results;")

    with open(full_config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    universe = config.get("universe", [])
    name_map = {c["ticker"]: c.get("name", c["ticker"]) for c in universe}

    engine = ValuationEngine(db_manager=db)
    logger.info("Executing Universe Valuation as of %s (Mode: %s)...", valuation_date, valuation_mode)
    uni_res = engine.value_universe(
        valuation_date=valuation_date,
        valuation_mode=valuation_mode,
        persist=True,
    )

    results = uni_res["results"]
    logger.info(
        "Universe Valuation Complete. Total: %d, Success: %d, Incomplete: %d, Failed: %d",
        uni_res["total_companies"],
        uni_res["successful_count"],
        uni_res["incomplete_count"],
        uni_res["failed_count"],
    )

    # Prepare Audit Table Rows
    coverage_rows: List[Dict[str, Any]] = []
    sensitivity_rows: List[Dict[str, Any]] = []
    quality_rows: List[Dict[str, Any]] = []

    for ticker, val in sorted(results.items()):
        name = name_map.get(ticker, ticker)

        if val.get("status") in ("INCOMPLETE", "ERROR"):
            coverage_rows.append({
                "ticker": ticker,
                "name": name,
                "sector": "Unknown",
                "cik": "Unknown",
                "ltm_revenue": None,
                "ltm_ebit": None,
                "ltm_nopat": None,
                "diluted_shares": None,
                "wacc": None,
                "base_fair_value": None,
                "bull_fair_value": None,
                "bear_fair_value": None,
                "current_share_price": None,
                "upside_downside_base": None,
                "status": val.get("status"),
                "reason": val.get("reason"),
            })
            continue

        inputs = val["inputs"]
        scenarios = val["scenarios"]
        wacc_in = val["wacc_inputs"]
        sens_wacc_g = val["sensitivities"]["wacc_terminal_growth"]
        sens_gm = val["sensitivities"]["growth_margin"]

        base_res = scenarios.base
        bull_res = scenarios.bull
        bear_res = scenarios.bear

        # Coverage Row
        coverage_rows.append({
            "ticker": ticker,
            "name": name,
            "sector": inputs.sector,
            "cik": inputs.cik,
            "ltm_revenue": inputs.ltm_revenue,
            "ltm_ebit": inputs.ltm_ebit,
            "ltm_nopat": inputs.ltm_nopat,
            "diluted_shares": inputs.diluted_shares,
            "wacc": base_res.wacc,
            "base_fair_value": base_res.fair_value_per_share,
            "bull_fair_value": bull_res.fair_value_per_share,
            "bear_fair_value": bear_res.fair_value_per_share,
            "current_share_price": base_res.current_share_price,
            "upside_downside_base": base_res.upside_downside,
            "status": "SUCCESS",
            "reason": None,
        })

        # Sensitivity Row
        # matrix dimensions: len(wacc_steps) x len(g_steps)
        # wacc_steps typically 5, g_steps typically 5, base is index [2][2]
        m_wg = sens_wacc_g.matrix
        fv_wacc_minus = m_wg[0][2] if len(m_wg) > 0 and len(m_wg[0]) > 2 else None
        fv_wacc_plus = m_wg[-1][2] if len(m_wg) > 0 and len(m_wg[-1]) > 2 else None
        fv_g_minus = m_wg[2][0] if len(m_wg) > 2 and len(m_wg[2]) > 0 else None
        fv_g_plus = m_wg[2][-1] if len(m_wg) > 2 and len(m_wg[2]) > 4 else None

        m_gm = sens_gm.matrix
        fv_rev_down_m_down = m_gm[0][0] if len(m_gm) > 0 and len(m_gm[0]) > 0 else None
        fv_rev_up_m_up = m_gm[-1][-1] if len(m_gm) > 0 and len(m_gm[-1]) > 0 else None

        sensitivity_rows.append({
            "ticker": ticker,
            "sector": inputs.sector,
            "base_wacc": base_res.wacc,
            "base_g": base_res.terminal_growth,
            "base_fair_value": base_res.fair_value_per_share,
            "wacc_minus_100bps_fv": fv_wacc_minus,
            "wacc_plus_100bps_fv": fv_wacc_plus,
            "g_minus_100bps_fv": fv_g_minus,
            "g_plus_100bps_fv": fv_g_plus,
            "growth_plus200_margin_plus200_fv": fv_rev_up_m_up,
            "growth_minus200_margin_minus200_fv": fv_rev_down_m_down,
            "monotonic_wacc": sens_wacc_g.is_monotonic_p1,
            "monotonic_terminal_growth": sens_wacc_g.is_monotonic_p2,
            "monotonic_growth_shift": sens_gm.is_monotonic_p1,
            "monotonic_margin_shift": sens_gm.is_monotonic_p2,
        })

        # Quality Row
        quality_rows.append({
            "ticker": ticker,
            "cik": inputs.cik,
            "valuation_date": inputs.valuation_date,
            "data_as_of_date": inputs.data_as_of_date,
            "diluted_shares": inputs.diluted_shares,
            "beta": wacc_in.beta,
            "beta_source": wacc_in.beta_source,
            "risk_free_rate": wacc_in.risk_free_rate,
            "rf_source": wacc_in.rf_source,
            "equity_risk_premium": wacc_in.equity_risk_premium,
            "cost_of_debt": wacc_in.cost_of_debt,
            "cod_source": wacc_in.cost_of_debt_source,
            "effective_tax_rate": inputs.effective_tax_rate,
            "lineage": inputs.lineage,
            "status": "VALIDATED",
        })

    # Write CSV Tables
    cov_path = os.path.join(tables_dir, "phase4_valuation_coverage.csv")
    with open(cov_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(coverage_rows[0].keys()))
        writer.writeheader()
        writer.writerows(coverage_rows)
    logger.info("Saved %s (%d rows)", cov_path, len(coverage_rows))

    sens_path = os.path.join(tables_dir, "phase4_sensitivity_summary.csv")
    with open(sens_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sensitivity_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sensitivity_rows)
    logger.info("Saved %s (%d rows)", sens_path, len(sensitivity_rows))

    qual_path = os.path.join(tables_dir, "phase4_input_quality.csv")
    with open(qual_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(quality_rows[0].keys()))
        writer.writeheader()
        writer.writerows(quality_rows)
    logger.info("Saved %s (%d rows)", qual_path, len(quality_rows))

    return {
        "coverage_count": len(coverage_rows),
        "sensitivity_count": len(sensitivity_rows),
        "quality_count": len(quality_rows),
        "coverage_file": cov_path,
        "sensitivity_file": sens_path,
        "quality_file": qual_path,
    }


if __name__ == "__main__":
    run_phase4_valuation()
