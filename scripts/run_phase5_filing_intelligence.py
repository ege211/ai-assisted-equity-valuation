"""
Phase 5 SEC Filing Qualitative Intelligence Universe Runner.

Executes:
1. Systematic sample selection across the 30-company universe (latest 10-K and previous 10-K as of 2024-12-31).
2. Primary HTML document retrieval and local disk caching under data/raw_filings/.
3. Text normalization, structural section detection, and passage retrieval.
4. Structured qualitative claim extraction and rigorous evidence quote verification.
5. Period-over-period change detection (NEW, ESCALATED, RESOLVED, MODIFIED, PERSISTENT).
6. Relational storage in DuckDB.
7. Export of 3 audit CSV tables:
   - results/tables/phase5_filing_coverage.csv
   - results/tables/phase5_extraction_quality.csv
   - results/tables/phase5_signal_summary.csv
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
from src.filing_intelligence.engine import FilingIntelligenceEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Phase5Pipeline")


def run_phase5_pipeline(
    as_of_date: str = "2024-12-31",
    db_path: str = "data/processed/financials.duckdb",
    config_path: str = "config/universe.yaml",
) -> Dict[str, Any]:
    """Execute Phase 5 universe filing intelligence pipeline."""
    full_db_path = os.path.join(WORKSPACE_DIR, db_path)
    full_config_path = os.path.join(WORKSPACE_DIR, config_path)
    tables_dir = os.path.join(WORKSPACE_DIR, "results", "tables")
    os.makedirs(tables_dir, exist_ok=True)

    db = DatabaseManager(full_db_path)
    engine = FilingIntelligenceEngine(db_manager=db)

    with open(full_config_path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)
    universe = conf.get("universe", [])
    name_map = {c["ticker"]: c.get("name", c["ticker"]) for c in universe}

    logger.info("Starting Phase 5 Filing Intelligence across %d companies (as_of_date: %s)...", len(universe), as_of_date)

    coverage_rows: List[Dict[str, Any]] = []
    quality_rows: List[Dict[str, Any]] = []
    signal_rows: List[Dict[str, Any]] = []

    successful_companies = 0
    total_filings_processed = 0
    total_extractions = 0
    total_validated = 0
    total_rejected = 0

    for comp in universe:
        ticker = comp["ticker"]
        name = name_map.get(ticker, ticker)
        sector = comp.get("sector", "Unknown")
        cik = comp["cik"]

        logger.info("Processing %s (%s)...", ticker, name)

        try:
            pair_res = engine.process_company_pair(ticker=ticker, as_of_date=as_of_date, persist=True)

            if pair_res.get("status") != "SUCCESS":
                logger.warning("No eligible filings found for %s as of %s", ticker, as_of_date)
                coverage_rows.append({
                    "ticker": ticker,
                    "name": name,
                    "sector": sector,
                    "cik": cik,
                    "form": "10-K",
                    "accession_number": "NONE",
                    "filing_date": "NONE",
                    "sections_detected": 0,
                    "passages_extracted": 0,
                    "total_claims": 0,
                    "validated_claims": 0,
                    "rejected_claims": 0,
                    "verification_rate": 0.0,
                    "status": "NO_ELIGIBLE_FILINGS",
                })
                continue

            curr = pair_res["current_filing"]
            doc_c = curr["document"]
            v_c = curr["validated_count"]
            r_c = curr["rejected_count"]
            tot_c = curr["total_extractions"]
            rate_c = (v_c / tot_c) if tot_c > 0 else 1.0

            coverage_rows.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "cik": cik,
                "form": doc_c.form,
                "accession_number": doc_c.accession_number,
                "filing_date": doc_c.filing_date,
                "sections_detected": len(curr["sections"]),
                "passages_extracted": curr["total_passages"],
                "total_claims": tot_c,
                "validated_claims": v_c,
                "rejected_claims": r_c,
                "verification_rate": round(rate_c, 4),
                "status": "PROCESSED",
            })

            total_filings_processed += 1
            total_extractions += tot_c
            total_validated += v_c
            total_rejected += r_c

            # Log extractions for quality audit
            for ext in curr["extractions"]:
                quality_rows.append({
                    "ticker": ticker,
                    "accession_number": ext.accession_number,
                    "category": ext.category,
                    "claim": ext.claim,
                    "evidence_quote_length": len(ext.evidence_quote),
                    "confidence": ext.confidence,
                    "direction": ext.direction,
                    "severity": ext.severity,
                    "materiality": ext.materiality,
                    "validation_status": ext.validation_status,
                    "validation_reason": ext.validation_reason,
                })

            # Process previous filing if available
            prev = pair_res.get("previous_filing")
            if prev:
                doc_p = prev["document"]
                v_p = prev["validated_count"]
                r_p = prev["rejected_count"]
                tot_p = prev["total_extractions"]
                rate_p = (v_p / tot_p) if tot_p > 0 else 1.0

                coverage_rows.append({
                    "ticker": ticker,
                    "name": name,
                    "sector": sector,
                    "cik": cik,
                    "form": doc_p.form,
                    "accession_number": doc_p.accession_number,
                    "filing_date": doc_p.filing_date,
                    "sections_detected": len(prev["sections"]),
                    "passages_extracted": prev["total_passages"],
                    "total_claims": tot_p,
                    "validated_claims": v_p,
                    "rejected_claims": r_p,
                    "verification_rate": round(rate_p, 4),
                    "status": "PROCESSED_PREVIOUS",
                })
                total_filings_processed += 1
                total_extractions += tot_p
                total_validated += v_p
                total_rejected += r_p

                for ext in prev["extractions"]:
                    quality_rows.append({
                        "ticker": ticker,
                        "accession_number": ext.accession_number,
                        "category": ext.category,
                        "claim": ext.claim,
                        "evidence_quote_length": len(ext.evidence_quote),
                        "confidence": ext.confidence,
                        "direction": ext.direction,
                        "severity": ext.severity,
                        "materiality": ext.materiality,
                        "validation_status": ext.validation_status,
                        "validation_reason": ext.validation_reason,
                    })

            # Change signals
            signals = pair_res.get("change_signals", [])
            for sig in signals:
                signal_rows.append({
                    "ticker": ticker,
                    "current_accession": sig.current_accession,
                    "previous_accession": sig.previous_accession,
                    "category": sig.category,
                    "change_type": sig.change_type,
                    "direction_shift": sig.direction_shift,
                    "severity_shift": sig.severity_shift,
                    "materiality": sig.materiality,
                    "summary": sig.summary,
                })

            successful_companies += 1
            logger.info(
                "  OK: %s processed (%d current claims, %d change signals)",
                ticker, tot_c, len(signals)
            )

        except Exception as e:
            logger.error("Error processing %s: %s", ticker, e)
            coverage_rows.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "cik": cik,
                "form": "10-K",
                "accession_number": "ERROR",
                "filing_date": "ERROR",
                "sections_detected": 0,
                "passages_extracted": 0,
                "total_claims": 0,
                "validated_claims": 0,
                "rejected_claims": 0,
                "verification_rate": 0.0,
                "status": f"ERROR: {e}",
            })

    # Write Audit Tables
    cov_path = os.path.join(tables_dir, "phase5_filing_coverage.csv")
    with open(cov_path, "w", newline="", encoding="utf-8") as f:
        if coverage_rows:
            writer = csv.DictWriter(f, fieldnames=list(coverage_rows[0].keys()))
            writer.writeheader()
            writer.writerows(coverage_rows)
    logger.info("Saved %s (%d rows)", cov_path, len(coverage_rows))

    qual_path = os.path.join(tables_dir, "phase5_extraction_quality.csv")
    with open(qual_path, "w", newline="", encoding="utf-8") as f:
        if quality_rows:
            writer = csv.DictWriter(f, fieldnames=list(quality_rows[0].keys()))
            writer.writeheader()
            writer.writerows(quality_rows)
    logger.info("Saved %s (%d rows)", qual_path, len(quality_rows))

    sig_path = os.path.join(tables_dir, "phase5_signal_summary.csv")
    with open(sig_path, "w", newline="", encoding="utf-8") as f:
        if signal_rows:
            writer = csv.DictWriter(f, fieldnames=list(signal_rows[0].keys()))
            writer.writeheader()
            writer.writerows(signal_rows)
    logger.info("Saved %s (%d rows)", sig_path, len(signal_rows))

    ver_rate = (total_validated / total_extractions) if total_extractions > 0 else 0.0
    logger.info(
        "Phase 5 Complete: %d/%d companies succeeded, %d filings, %d claims extracted, %d validated (%.1f%%)",
        successful_companies, len(universe), total_filings_processed, total_extractions, total_validated, ver_rate * 100
    )

    return {
        "successful_companies": successful_companies,
        "total_filings_processed": total_filings_processed,
        "total_extractions": total_extractions,
        "total_validated": total_validated,
        "total_rejected": total_rejected,
        "verification_rate": ver_rate,
        "coverage_file": cov_path,
        "quality_file": qual_path,
        "signal_file": sig_path,
    }


if __name__ == "__main__":
    run_phase5_pipeline()
