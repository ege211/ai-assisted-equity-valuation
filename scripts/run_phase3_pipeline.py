"""
Phase 3 Pipeline Orchestrator.
Executes Accounting Normalization, Quarterly De-accumulation, LTM Generation,
and Fundamental Feature Engineering across the 30-company universe.

Generates:
- DuckDB tables:
  - quarterly_financials
  - annual_financials
  - ltm_financials
  - financial_features
- Audit summary tables:
  - results/tables/phase3_feature_coverage.csv
  - results/tables/phase3_data_quality.csv
  - results/tables/phase3_ltm_coverage.csv
"""
import csv
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

import yaml

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from src.data.db import DatabaseManager
from src.normalization.quarterly_engine import QuarterlyEngine
from src.normalization.ltm_engine import LTMEngine
from src.normalization.feature_engine import FeatureEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Phase3Pipeline")


class Phase3Orchestrator:
    """End-to-end runner for Phase 3 accounting normalization and feature engineering."""

    def __init__(
        self,
        config_path: str = "config/universe.yaml",
        db_path: str = "data/processed/financials.duckdb",
    ) -> None:
        self.config_path = os.path.join(WORKSPACE_DIR, config_path)
        self.db_path = os.path.join(WORKSPACE_DIR, db_path)
        self.db = DatabaseManager(self.db_path)
        self.quarterly_engine = QuarterlyEngine()

    def run(self, target_years: Optional[List[int]] = None) -> Dict[str, Any]:
        """Execute Phase 3 pipeline for all 30 companies."""
        years = target_years or list(range(2014, 2025))
        logger.info(f"Starting Phase 3 Pipeline across {len(years)} years: {years}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            universe_conf = yaml.safe_load(f)
        universe = universe_conf.get("universe", [])
        logger.info(f"Loaded {len(universe)} companies from {self.config_path}")

        total_q_inserted = 0
        total_ann_inserted = 0
        total_ltm_inserted = 0
        total_feat_inserted = 0

        comp_coverage_rows: List[Dict[str, Any]] = []
        ltm_coverage_rows: List[Dict[str, Any]] = []

        start_time = time.time()

        for comp in universe:
            ticker = comp["ticker"]
            cik = str(comp["cik"]).zfill(10)
            sector = comp["sector"]
            name = comp["name"]
            logger.info(f"Processing {ticker} ({name}, CIK {cik})...")

            # 1. Fetch raw facts and filings from DuckDB
            with self.db.get_connection() as con:
                cursor = con.execute(
                    """
                    SELECT fact_id, cik, accession_number, form, filing_date::VARCHAR as filing_date,
                           acceptance_datetime::VARCHAR as acceptance_datetime, taxonomy, concept,
                           start_date::VARCHAR as start_date, end_date::VARCHAR as end_date,
                           is_instant, fiscal_year, fiscal_period, frame, unit, val, description
                    FROM raw_xbrl_facts
                    WHERE cik = ?
                    """,
                    [cik],
                )
                cols = [d[0] for d in cursor.description]
                raw_facts = [dict(zip(cols, r)) for r in cursor.fetchall()]

                cursor = con.execute(
                    """
                    SELECT accession_number, filing_date::VARCHAR as filing_date,
                           report_date::VARCHAR as report_date,
                           acceptance_datetime::VARCHAR as acceptance_datetime,
                           form, primary_document
                    FROM filings
                    WHERE cik = ?
                    """,
                    [cik],
                )
                f_cols = [d[0] for d in cursor.description]
                filings_map = {r[0]: dict(zip(f_cols, r)) for r in cursor.fetchall()}

            comp_meta = {
                "ticker": ticker,
                "cik": cik,
                "company_id": f"US_{ticker}",
                "sector": sector,
            }

            # 2. Quarterly De-accumulation & Annual Statement Extraction
            q_stmts, ann_stmts = self.quarterly_engine.process_company(
                comp_meta, raw_facts, filings_map, target_years=years
            )
            n_q = self.db.insert_quarterly_financials(q_stmts)
            n_ann = self.db.insert_annual_financials(ann_stmts)
            total_q_inserted += n_q
            total_ann_inserted += n_ann

            # 3. LTM Aggregation
            ltm_stmts = LTMEngine.generate_ltm_statements(q_stmts)
            n_ltm = self.db.insert_ltm_financials(ltm_stmts)
            total_ltm_inserted += n_ltm

            # 4. Fundamental Feature Engineering
            feats = FeatureEngine.compute_all_features(q_stmts, ann_stmts, ltm_stmts)
            n_feats = self.db.insert_financial_features(feats)
            total_feat_inserted += n_feats

            # 5. Compile Per-Company Metrics
            avail_feats = [f for f in feats if f["data_status"] in ["DIRECT_STANDARD", "DERIVED"]]
            nopat_cnt = sum(1 for f in avail_feats if f["feature_name"] == "nopat")
            roic_cnt = sum(1 for f in avail_feats if f["feature_name"] == "roic")
            fcf_cnt = sum(1 for f in avail_feats if f["feature_name"] == "fcf")
            net_debt_cnt = sum(1 for f in avail_feats if f["feature_name"] == "net_debt")

            comp_coverage_rows.append({
                "ticker": ticker,
                "sector": sector,
                "quarterly_observations": len(q_stmts),
                "annual_observations": len(ann_stmts),
                "ltm_observations": len(ltm_stmts),
                "total_features": len(feats),
                "available_features": len(avail_feats),
                "unresolved_features": len(feats) - len(avail_feats),
                "feature_completeness_pct": round(len(avail_feats) / len(feats) * 100, 1) if feats else 0.0,
                "nopat_count": nopat_cnt,
                "roic_count": roic_cnt,
                "fcf_count": fcf_cnt,
                "net_debt_count": net_debt_cnt,
            })

            oldest_ltm = f"{ltm_stmts[0]['as_of_fiscal_year']}{ltm_stmts[0]['as_of_fiscal_quarter']}" if ltm_stmts else "NONE"
            newest_ltm = f"{ltm_stmts[-1]['as_of_fiscal_year']}{ltm_stmts[-1]['as_of_fiscal_quarter']}" if ltm_stmts else "NONE"

            ltm_coverage_rows.append({
                "ticker": ticker,
                "sector": sector,
                "quarterly_count": len(q_stmts),
                "ltm_count": len(ltm_stmts),
                "oldest_ltm": oldest_ltm,
                "newest_ltm": newest_ltm,
                "ltm_ratio_pct": round(len(ltm_stmts) / (len(q_stmts) - 3) * 100, 1) if len(q_stmts) >= 4 else 0.0,
            })

        elapsed = time.time() - start_time
        logger.info(f"All 30 companies processed in {elapsed:.2f}s.")

        # 6. Write CSV Audit Tables
        logger.info("Generating Phase 3 audit tables...")
        self._write_audit_tables(comp_coverage_rows, ltm_coverage_rows)

        summary = self.db.get_ingestion_summary()
        logger.info(f"Pipeline finished successfully. DB State: {summary}")
        return summary

    def _write_audit_tables(
        self,
        comp_coverage: List[Dict[str, Any]],
        ltm_coverage: List[Dict[str, Any]],
    ) -> None:
        """Write feature coverage, data quality, and LTM coverage audit CSVs."""
        out_dir = os.path.join(WORKSPACE_DIR, "results/tables")
        os.makedirs(out_dir, exist_ok=True)

        # 1. Feature Coverage
        fc_csv = os.path.join(out_dir, "phase3_feature_coverage.csv")
        with open(fc_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ticker", "sector", "quarterly_observations", "annual_observations",
                "ltm_observations", "total_features", "available_features",
                "unresolved_features", "feature_completeness_pct",
                "nopat_count", "roic_count", "fcf_count", "net_debt_count"
            ])
            writer.writeheader()
            writer.writerows(comp_coverage)
        logger.info(f"Wrote {fc_csv}")

        # 2. LTM Coverage
        ltm_csv = os.path.join(out_dir, "phase3_ltm_coverage.csv")
        with open(ltm_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ticker", "sector", "quarterly_count", "ltm_count",
                "oldest_ltm", "newest_ltm", "ltm_ratio_pct"
            ])
            writer.writeheader()
            writer.writerows(ltm_coverage)
        logger.info(f"Wrote {ltm_csv}")

        # 3. Data Quality (Breakdown by feature_name and status from DuckDB)
        dq_csv = os.path.join(out_dir, "phase3_data_quality.csv")
        with self.db.get_connection() as con:
            cursor = con.execute("""
                SELECT 
                    feature_name,
                    fiscal_period,
                    data_status,
                    COUNT(*) as observation_count,
                    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY feature_name, fiscal_period), 2) as pct_of_group
                FROM financial_features
                GROUP BY feature_name, fiscal_period, data_status
                ORDER BY feature_name ASC, fiscal_period ASC, data_status ASC;
            """)
            cols = [d[0] for d in cursor.description]
            rows = cursor.fetchall()

            with open(dq_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
        logger.info(f"Wrote {dq_csv}")


def main() -> None:
    orchestrator = Phase3Orchestrator()
    summary = orchestrator.run()
    print("\n=== Phase 3 Accounting & Feature Pipeline Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v:,}")


if __name__ == "__main__":
    main()
