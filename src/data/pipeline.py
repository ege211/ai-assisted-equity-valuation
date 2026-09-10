"""
Production Financial Statement Pipeline.
Executes end-to-end ingestion from SEC EDGAR / local cache into DuckDB:
1. Ingests 30-company universe from config/universe.yaml.
2. Ingests filing metadata and exact acceptanceDateTime into 'filings' table.
3. Ingests raw XBRL facts into 'raw_xbrl_facts' table.
4. Executes 5-tier concept normalization into 'normalized_financial_facts'.
5. Generates summary and data quality audit tables.
"""
import csv
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Ensure workspace root is in sys.path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from src.data.db import DatabaseManager, compute_fact_id
from src.data.sec_client import SECClient
from src.normalization.concept_normalizer import ConceptNormalizer, INSTANT_VARIABLES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Pipeline")


class FinancialStatementPipeline:
    """End-to-end orchestrator for financial statement ingestion and normalization."""

    def __init__(
        self,
        config_path: str = "config/universe.yaml",
        db_path: str = "data/processed/financials.duckdb",
        cache_dir: str = "data/raw_sec",
    ) -> None:
        self.config_path = os.path.join(WORKSPACE_DIR, config_path)
        self.db_path = os.path.join(WORKSPACE_DIR, db_path)
        self.cache_dir = os.path.join(WORKSPACE_DIR, cache_dir)
        self.db = DatabaseManager(self.db_path)
        self.client = SECClient(cache_dir=self.cache_dir)
        self.normalizer = ConceptNormalizer()

    def run(self, target_years: Optional[List[int]] = None) -> Dict[str, Any]:
        """Execute full pipeline for all companies in universe."""
        years = target_years or list(range(2014, 2025))
        logger.info(f"Starting Financial Statement Pipeline across {len(years)} years: {years}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            universe_conf = yaml.safe_load(f)
        universe = universe_conf.get("universe", [])
        logger.info(f"Loaded {len(universe)} companies from {self.config_path}")

        # 1. Insert Companies
        comp_records = []
        for c in universe:
            comp_records.append({
                "company_id": f"US_{c['ticker']}",
                "ticker": c["ticker"],
                "cik": str(c["cik"]).zfill(10),
                "name": c["name"],
                "sector": c["sector"],
                "fiscal_year_end_month": None,
            })
        self.db.insert_companies(comp_records)

        total_filings_inserted = 0
        total_raw_facts_inserted = 0
        total_norm_facts_inserted = 0
        company_metrics = []

        # 2. Process each company
        for comp in universe:
            ticker = comp["ticker"]
            cik = str(comp["cik"]).zfill(10)
            sector = comp["sector"]
            logger.info(f"Processing {ticker} (CIK {cik})...")

            # A. Submissions & Filings
            submissions = self.client.get_company_submissions(cik)
            filings_catalog = self.client.extract_recent_filings_catalog(submissions)

            filings_map: Dict[str, Dict[str, Any]] = {}
            filing_rows = []
            for f in filings_catalog:
                accn = f.get("accessionNumber")
                if not accn:
                    continue
                f_date = f.get("filingDate") or None
                r_date = f.get("reportDate") or None
                if r_date == "":
                    r_date = None
                acceptance_dt = f.get("acceptanceDateTime") or (f"{f_date}T23:59:59Z" if f_date else "1900-01-01T00:00:00Z")
                filings_map[accn] = {
                    "accession_number": accn,
                    "cik": cik,
                    "ticker": ticker,
                    "form": f.get("form", ""),
                    "filing_date": f_date or "1900-01-01",
                    "report_date": r_date,
                    "acceptance_datetime": acceptance_dt,
                    "primary_document": f.get("primaryDocument"),
                }
                filing_rows.append(filings_map[accn])

            n_filings = self.db.insert_filings(filing_rows)
            total_filings_inserted += n_filings

            # B. Company Facts & Raw XBRL Facts
            facts_data = self.client.get_company_facts(cik)
            us_gaap = facts_data.get("facts", {}).get("us-gaap", {})

            raw_facts_rows = []
            facts_by_concept: Dict[str, List[Dict[str, Any]]] = {}

            for concept_name, concept_data in us_gaap.items():
                units_dict = concept_data.get("units", {})
                for unit_name, entries in units_dict.items():
                    for e in entries:
                        accn = e.get("accn")
                        end_date = e.get("end") or None
                        if not accn or not end_date:
                            continue

                        # Lookup filing metadata if available
                        f_meta = filings_map.get(accn, {})
                        filing_date = e.get("filed") or f_meta.get("filing_date", "1900-01-01")
                        acceptance_dt = f_meta.get("acceptance_datetime") or f"{filing_date}T23:59:59Z"
                        form = e.get("form") or f_meta.get("form", "10-K")
                        start_date = e.get("start") or None
                        if start_date == "":
                            start_date = None
                        is_instant = start_date is None or start_date == end_date
                        val = float(e.get("val", 0.0))

                        fact_id = compute_fact_id(cik, accn, concept_name, unit_name, start_date, end_date, e.get("fy"), e.get("fp"))

                        raw_row = {
                            "fact_id": fact_id,
                            "cik": cik,
                            "accession_number": accn,
                            "form": form,
                            "filing_date": filing_date,
                            "acceptance_datetime": acceptance_dt,
                            "taxonomy": "us-gaap",
                            "concept": concept_name,
                            "start_date": start_date,
                            "end_date": end_date,
                            "is_instant": is_instant,
                            "fiscal_year": e.get("fy"),
                            "fiscal_period": e.get("fp"),
                            "frame": e.get("frame"),
                            "unit": unit_name,
                            "val": val,
                            "description": concept_data.get("description"),
                        }
                        raw_facts_rows.append(raw_row)

                        # Group for normalization
                        e_copy = dict(e)
                        e_copy["concept"] = concept_name
                        e_copy["fact_id"] = fact_id
                        facts_by_concept.setdefault(concept_name, []).append(e_copy)

            # Insert raw facts in chunks
            n_raw = self.db.insert_raw_facts(raw_facts_rows)
            total_raw_facts_inserted += n_raw

            # C. Normalize Facts via 5-Tier Fallback Cascade
            company_meta = {
                "company_id": f"US_{ticker}",
                "ticker": ticker,
                "cik": cik,
                "sector": sector,
            }
            norm_records = self.normalizer.normalize_company_facts(
                company_meta=company_meta,
                raw_facts_by_concept=facts_by_concept,
                filings_map=filings_map,
                target_years=years,
                target_periods=["FY"],
            )

            n_norm = self.db.insert_normalized_facts(norm_records)
            total_norm_facts_inserted += n_norm

            # Per-company audit stats
            complete_count = sum(1 for nr in norm_records if nr["data_status"] in ["DIRECT_STANDARD", "DIRECT_ALTERNATIVE", "DERIVED"])
            total_slots = len(norm_records)
            pct = (complete_count / total_slots * 100) if total_slots > 0 else 0.0

            company_metrics.append({
                "ticker": ticker,
                "cik": cik,
                "sector": sector,
                "raw_concepts_count": len(us_gaap),
                "filings_count": len(filings_map),
                "raw_facts_count": len(raw_facts_rows),
                "normalized_facts_count": len(norm_records),
                "recovered_facts_count": complete_count,
                "completeness_pct": round(pct, 1),
            })

        logger.info("Generating Phase 2 audit tables...")
        self._write_summary_tables(company_metrics)

        db_summary = self.db.get_ingestion_summary()
        logger.info(f"Pipeline finished successfully. DB State: {db_summary}")
        return db_summary

    def _write_summary_tables(self, metrics: List[Dict[str, Any]]) -> None:
        """Write phase2_ingestion_summary.csv and phase2_data_quality.csv."""
        summary_csv = os.path.join(WORKSPACE_DIR, "results/tables/phase2_ingestion_summary.csv")
        os.makedirs(os.path.dirname(summary_csv), exist_ok=True)

        with open(summary_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ticker", "cik", "sector", "raw_concepts_count", "filings_count",
                "raw_facts_count", "normalized_facts_count", "recovered_facts_count", "completeness_pct"
            ])
            for m in metrics:
                writer.writerow([
                    m["ticker"], m["cik"], m["sector"], m["raw_concepts_count"],
                    m["filings_count"], m["raw_facts_count"], m["normalized_facts_count"],
                    m["recovered_facts_count"], m["completeness_pct"]
                ])
        logger.info(f"Wrote {summary_csv}")

        # Data quality breakdown by canonical variable and status
        quality_csv = os.path.join(WORKSPACE_DIR, "results/tables/phase2_data_quality.csv")
        with self.db.get_connection() as con:
            cursor = con.execute("""
                SELECT 
                    canonical_variable,
                    fallback_tier,
                    data_status,
                    COUNT(*) as observation_count,
                    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY canonical_variable), 2) as pct_of_variable
                FROM normalized_financial_facts
                GROUP BY canonical_variable, fallback_tier, data_status
                ORDER BY canonical_variable ASC, fallback_tier ASC;
            """)
            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            with open(quality_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
        logger.info(f"Wrote {quality_csv}")


def main() -> None:
    pipeline = FinancialStatementPipeline()
    summary = pipeline.run(target_years=list(range(2014, 2025)))
    print("\n=== Phase 2 Pipeline Ingestion Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v:,}")


if __name__ == "__main__":
    main()
