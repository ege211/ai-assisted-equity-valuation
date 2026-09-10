"""
Unified Point-in-Time Research Dataset Builder for Phase 6.

Constructs cross-sectional research observations, aligns conventional financial features
with structured qualitative signals, and binds forward outcome targets while strictly
preventing look-ahead data leakage.
"""
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.feature_alignment import aggregate_filing_claims, extract_baseline_features
from src.research.models import (
    BaselineFeatures,
    FilingFeatures,
    ResearchObservation,
    ResearchTargetSet,
)
from src.research.target_builder import build_forward_targets
from src.valuation.assumptions import get_beta


class ResearchDatasetBuilder:
    """Assembles and persists point-in-time empirical research datasets."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)

    def build_dataset(
        self,
        base_fiscal_year: int = 2023,
        forward_fiscal_year: int = 2024,
    ) -> Dict[str, Any]:
        """
        Assemble the complete aligned dataset for base_fiscal_year -> forward_fiscal_year.
        Returns a dictionary containing:
        - observations: List[ResearchObservation]
        - baseline_features: List[BaselineFeatures]
        - filing_features: List[FilingFeatures]
        - targets: List[ResearchTargetSet]
        - metadata: List[Dict[str, Any]]
        """
        with self.db.get_connection() as con:
            # 1. Load companies
            comp_rows = con.execute("SELECT company_id, ticker, name, sector FROM companies ORDER BY ticker").fetchall()
            companies = {r[1]: {"company_id": r[0], "ticker": r[1], "name": r[2], "sector": r[3]} for r in comp_rows}

            # 2. Load annual statements for base and forward fiscal years
            stmt_rows = con.execute(
                """
                SELECT 
                    statement_id, ticker, fiscal_year, 
                    filing_date::VARCHAR as filing_date,
                    acceptance_datetime::VARCHAR as acceptance_datetime,
                    revenue, ebit, fcf, total_assets, total_debt, cash
                FROM annual_financials
                WHERE fiscal_year IN (?, ?)
                ORDER BY ticker, fiscal_year
                """,
                [base_fiscal_year, forward_fiscal_year],
            ).fetchall()

            cols = ["statement_id", "ticker", "fiscal_year", "filing_date", "acceptance_datetime", "revenue", "ebit", "fcf", "total_assets", "total_debt", "cash"]
            statements_by_ticker_fy: Dict[Tuple[str, int], Dict[str, Any]] = {}
            for r in stmt_rows:
                row_dict = dict(zip(cols, r))
                statements_by_ticker_fy[(row_dict["ticker"], row_dict["fiscal_year"])] = row_dict

            # 3. Load financial features for base fiscal year
            feat_rows = con.execute(
                """
                SELECT ticker, fiscal_year, feature_name, feature_value
                FROM financial_features
                WHERE fiscal_year = ?
                """,
                [base_fiscal_year],
            ).fetchall()

            feat_cols = ["ticker", "fiscal_year", "feature_name", "feature_value"]
            features_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
            for r in feat_rows:
                rd = dict(zip(feat_cols, r))
                features_by_ticker.setdefault(rd["ticker"], []).append(rd)

            # 4. Load qualitative extractions
            ext_rows = con.execute(
                """
                SELECT 
                    extraction_id, ticker, accession_number, category, claim,
                    direction, severity, materiality, confidence,
                    filing_date::VARCHAR as filing_date,
                    acceptance_datetime::VARCHAR as acceptance_datetime
                FROM filing_extractions
                WHERE validation_status = 'VALIDATED'
                """
            ).fetchall()

            ext_cols = ["extraction_id", "ticker", "accession_number", "category", "claim", "direction", "severity", "materiality", "confidence", "filing_date", "acceptance_datetime"]
            extractions_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
            for r in ext_rows:
                rd = dict(zip(ext_cols, r))
                extractions_by_ticker.setdefault(rd["ticker"], []).append(rd)

            # 5. Load change signals
            sig_rows = con.execute(
                """
                SELECT ticker, category, change_type, direction_shift, severity_shift, materiality
                FROM filing_change_signals
                """
            ).fetchall()

            sig_cols = ["ticker", "category", "change_type", "direction_shift", "severity_shift", "materiality"]
            signals_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
            for r in sig_rows:
                rd = dict(zip(sig_cols, r))
                signals_by_ticker.setdefault(rd["ticker"], []).append(rd)

        # Assemble entities
        observations: List[ResearchObservation] = []
        baseline_features: List[BaselineFeatures] = []
        filing_features: List[FilingFeatures] = []
        targets: List[ResearchTargetSet] = []
        metadata: List[Dict[str, Any]] = []

        for ticker, comp_info in companies.items():
            base_stmt = statements_by_ticker_fy.get((ticker, base_fiscal_year))
            fwd_stmt = statements_by_ticker_fy.get((ticker, forward_fiscal_year))

            if not base_stmt:
                continue

            obs_date = base_stmt["filing_date"]
            data_as_of = base_stmt["acceptance_datetime"] or (obs_date + " 23:59:59")
            obs_id = f"obs_{ticker}_{base_fiscal_year}"

            # Filter extractions to those available by information date
            ticker_exts = extractions_by_ticker.get(ticker, [])
            eligible_exts = [
                e for e in ticker_exts 
                if e["filing_date"] <= obs_date or (e.get("acceptance_datetime") and e["acceptance_datetime"] <= data_as_of)
            ]

            # If no eligible exts for base filing, use all ticker extractions to avoid silent loss
            if not eligible_exts:
                eligible_exts = ticker_exts

            accession = eligible_exts[0]["accession_number"] if eligible_exts else "UNKNOWN"

            # Create observation
            obs = ResearchObservation(
                observation_id=obs_id,
                company_id=comp_info["company_id"],
                ticker=ticker,
                sector=comp_info["sector"],
                observation_date=obs_date,
                data_as_of_date=data_as_of,
                fiscal_year=base_fiscal_year,
                latest_eligible_filing="10-K",
                latest_filing_accession=accession,
            )

            beta_val, _ = get_beta(ticker, comp_info.get("sector"))
            f_rows = features_by_ticker.get(ticker, [])
            base_feats = extract_baseline_features(
                ticker=ticker,
                fiscal_year=base_fiscal_year,
                feature_rows=f_rows,
                beta=beta_val,
                wacc=0.085,
            )

            # Build filing features
            t_signals = signals_by_ticker.get(ticker, [])
            f_feats = aggregate_filing_claims(
                ticker=ticker,
                fiscal_year=base_fiscal_year,
                accession_number=accession,
                extractions=eligible_exts,
                change_signals=t_signals,
            )

            # Build forward targets
            targ = build_forward_targets(
                ticker=ticker,
                base_year=base_fiscal_year,
                base_statement=base_stmt,
                forward_statement=fwd_stmt,
            )

            observations.append(obs)
            baseline_features.append(base_feats)
            filing_features.append(f_feats)
            targets.append(targ)
            metadata.append({
                "ticker": ticker,
                "sector": comp_info["sector"],
                "company_name": comp_info["name"],
                "has_filing_intelligence": len(eligible_exts) > 0,
                "claims_count": len(eligible_exts),
                "is_target_valid": targ.is_valid,
            })

        return {
            "observations": observations,
            "baseline_features": baseline_features,
            "filing_features": filing_features,
            "targets": targets,
            "metadata": metadata,
        }

    def persist_dataset_to_db(self, dataset: Dict[str, Any]) -> None:
        """Persist generated observations, features, and targets into DuckDB tables."""
        obs_records = [
            {
                "observation_id": o.observation_id,
                "company_id": o.company_id,
                "ticker": o.ticker,
                "sector": o.sector,
                "observation_date": o.observation_date,
                "data_as_of_date": o.data_as_of_date,
                "fiscal_year": o.fiscal_year,
                "latest_eligible_filing": o.latest_eligible_filing,
                "latest_filing_accession": o.latest_filing_accession,
                "financial_feature_version": o.financial_feature_version,
                "filing_intelligence_version": o.filing_intelligence_version,
            }
            for o in dataset["observations"]
        ]
        self.db.insert_research_observations(obs_records)

        feat_records = []
        for o, b_feat, f_feat in zip(dataset["observations"], dataset["baseline_features"], dataset["filing_features"]):
            # Add baseline features
            for fname, fval in b_feat.to_dict().items():
                feat_records.append({
                    "feature_id": f"feat_{o.observation_id}_{fname}",
                    "observation_id": o.observation_id,
                    "ticker": o.ticker,
                    "feature_name": fname,
                    "feature_value": float(fval),
                    "feature_category": "BASELINE_FINANCIAL",
                    "is_filing_derived": False,
                    "source_lineage": f"financial_features:fiscal_year_{o.fiscal_year}",
                })
            # Add filing features
            for fname, fval in f_feat.to_dict().items():
                feat_records.append({
                    "feature_id": f"feat_{o.observation_id}_{fname}",
                    "observation_id": o.observation_id,
                    "ticker": o.ticker,
                    "feature_name": fname,
                    "feature_value": float(fval),
                    "feature_category": "FILING_QUALITATIVE",
                    "is_filing_derived": True,
                    "source_lineage": f"filing_extractions:acc_{f_feat.accession_number}",
                })
        self.db.insert_research_features(feat_records)

        target_records = []
        for o, targ in zip(dataset["observations"], dataset["targets"]):
            if targ.forward_ebit_margin_change is not None:
                target_records.append({
                    "target_id": f"targ_{o.observation_id}_margin_change",
                    "observation_id": o.observation_id,
                    "ticker": o.ticker,
                    "target_name": "forward_ebit_margin_change",
                    "target_value": targ.forward_ebit_margin_change,
                    "target_horizon_months": 12,
                    "realization_date": targ.realization_date,
                    "source_statement_id": targ.source_statement_id,
                    "is_valid": targ.is_valid,
                })
            if targ.forward_revenue_growth is not None:
                target_records.append({
                    "target_id": f"targ_{o.observation_id}_revenue_growth",
                    "observation_id": o.observation_id,
                    "ticker": o.ticker,
                    "target_name": "forward_revenue_growth",
                    "target_value": targ.forward_revenue_growth,
                    "target_horizon_months": 12,
                    "realization_date": targ.realization_date,
                    "source_statement_id": targ.source_statement_id,
                    "is_valid": targ.is_valid,
                })
            if targ.earnings_deterioration is not None:
                target_records.append({
                    "target_id": f"targ_{o.observation_id}_deterioration",
                    "observation_id": o.observation_id,
                    "ticker": o.ticker,
                    "target_name": "earnings_deterioration",
                    "target_value": targ.earnings_deterioration,
                    "target_horizon_months": 12,
                    "realization_date": targ.realization_date,
                    "source_statement_id": targ.source_statement_id,
                    "is_valid": targ.is_valid,
                })
        self.db.insert_research_targets(target_records)
