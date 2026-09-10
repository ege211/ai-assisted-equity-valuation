"""
Point-in-Time Research Panel Builder for Phase 7 Expanded Out-of-Sample Research.

Constructs multi-period company-date observation panels, extracts point-in-time
baseline financial and qualitative filing features, computes forward outcome targets,
and enforces the Phase 7 methodological locks:
1. Primary Target Lock: forward_ebit_margin_change (secondary: forward_revenue_growth, earnings_deterioration)
2. Point-in-Time Lock: SEC acceptance_datetime as authoritative availability timestamp
3. Filing Coverage Lock: Genuine PIT filing coverage without future backfilling
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.valuation.assumptions import get_beta


# Pre-specified qualitative feature groupings
PRESPECIFIED_OPERATIONAL_FEATURES = [
    "margin_pressure_score",
    "supply_chain_risk_score",
]

RISK_GROUP_FEATURES = [
    "regulatory_risk_score",
    "litigation_risk_score",
    "supply_chain_risk_score",
    "competitive_pressure_score",
    "liquidity_risk_score",
]

OPERATING_GROUP_FEATURES = [
    "margin_pressure_score",
    "demand_uncertainty_score",
    "strategic_change_score",
    "material_business_change_score",
]

MANAGEMENT_GROUP_FEATURES = [
    "guidance_direction_score",
    "management_outlook_score",
    "capital_allocation_change_score",
]

OMNIBUS_QUALITATIVE_FEATURES = [
    "margin_pressure_score",
    "supply_chain_risk_score",
    "regulatory_risk_score",
    "litigation_risk_score",
    "demand_uncertainty_score",
    "competitive_pressure_score",
    "liquidity_risk_score",
    "strategic_change_score",
    "material_business_change_score",
    "guidance_direction_score",
    "capital_allocation_change_score",
    "management_outlook_score",
]

BASELINE_FEATURE_NAMES = [
    "revenue_growth_yoy",
    "ebit_margin",
    "gross_margin",
    "roic",
    "fcf_margin",
    "net_debt_to_revenue",
    "owc_to_revenue",
    "asset_turnover",
    "beta",
    "wacc",
]


@dataclass
class PanelObservation:
    """Represents an empirical company-date observation anchored to an SEC filing event."""
    observation_id: str
    company_id: str
    ticker: str
    cik: str
    sector: str
    cohort: str
    observation_date: str                 # YYYY-MM-DD
    acceptance_datetime: str             # ISO timestamp
    latest_filing_form: str
    latest_filing_accession: str
    financial_data_as_of: str
    filing_data_as_of: str
    base_fiscal_year: int
    target_fiscal_year: int
    target_realization_date: str
    target_realization_accession: str
    has_complete_baseline: bool = True
    has_complete_filing: bool = True
    has_valid_target: bool = True


@dataclass
class PanelFeatures:
    """Features associated with an empirical observation."""
    observation_id: str
    ticker: str
    baseline: Dict[str, float] = field(default_factory=dict)
    filing: Dict[str, float] = field(default_factory=dict)


@dataclass
class PanelTargets:
    """Target realizations occurring strictly after observation_date."""
    observation_id: str
    ticker: str
    forward_ebit_margin_change: Optional[float] = None
    forward_revenue_growth: Optional[float] = None
    earnings_deterioration: Optional[float] = None
    realization_date: str = ""
    realization_accession: str = ""
    is_valid: bool = True


class PanelBuilder:
    """Constructs, validates, and persists Phase 7 historical research panel datasets."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)

    def initialize_tables(self) -> None:
        """Create the 8 dedicated Phase 7 DuckDB research tables if they do not exist."""
        with self.db.get_connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS research_panel_observations (
                    observation_id VARCHAR PRIMARY KEY,
                    company_id VARCHAR,
                    ticker VARCHAR,
                    cik VARCHAR,
                    sector VARCHAR,
                    cohort VARCHAR,
                    observation_date DATE,
                    acceptance_datetime VARCHAR,
                    latest_filing_form VARCHAR,
                    latest_filing_accession VARCHAR,
                    financial_data_as_of VARCHAR,
                    filing_data_as_of VARCHAR,
                    base_fiscal_year INTEGER,
                    target_fiscal_year INTEGER,
                    has_complete_baseline BOOLEAN,
                    has_complete_filing BOOLEAN,
                    has_valid_target BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_panel_features (
                    observation_id VARCHAR,
                    ticker VARCHAR,
                    feature_group VARCHAR,
                    feature_name VARCHAR,
                    feature_value DOUBLE,
                    PRIMARY KEY (observation_id, feature_name)
                );

                CREATE TABLE IF NOT EXISTS research_panel_targets (
                    observation_id VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    forward_ebit_margin_change DOUBLE,
                    forward_revenue_growth DOUBLE,
                    earnings_deterioration DOUBLE,
                    realization_date DATE,
                    realization_accession VARCHAR,
                    is_valid BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_walkforward_splits (
                    split_id VARCHAR PRIMARY KEY,
                    fold_number INTEGER,
                    fold_name VARCHAR,
                    train_start_date DATE,
                    train_end_date DATE,
                    test_start_date DATE,
                    test_end_date DATE,
                    n_train INTEGER,
                    n_test INTEGER,
                    train_observation_ids VARCHAR,
                    test_observation_ids VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_panel_model_results (
                    result_id VARCHAR PRIMARY KEY,
                    fold_name VARCHAR,
                    target_name VARCHAR,
                    model_name VARCHAR,
                    model_type VARCHAR,
                    n_train INTEGER,
                    n_test INTEGER,
                    mae DOUBLE,
                    rmse DOUBLE,
                    r2 DOUBLE,
                    pearson_r DOUBLE,
                    spearman_rho DOUBLE,
                    delta_mae DOUBLE,
                    delta_rmse DOUBLE,
                    pct_mae_improvement DOUBLE,
                    paired_t_stat DOUBLE,
                    p_value DOUBLE,
                    permutation_p_value DOUBLE,
                    bootstrap_ci_lower DOUBLE,
                    bootstrap_ci_upper DOUBLE,
                    brier_score DOUBLE,
                    roc_auc DOUBLE,
                    pr_auc DOUBLE,
                    accuracy DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_panel_ablation_results (
                    ablation_id VARCHAR PRIMARY KEY,
                    fold_name VARCHAR,
                    target_name VARCHAR,
                    feature_group_name VARCHAR,
                    feature_names VARCHAR,
                    n_features INTEGER,
                    mae DOUBLE,
                    rmse DOUBLE,
                    delta_mae DOUBLE,
                    pct_mae_improvement DOUBLE,
                    paired_t_stat DOUBLE,
                    p_value DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_panel_robustness_results (
                    robustness_id VARCHAR PRIMARY KEY,
                    test_dimension VARCHAR,
                    subgroup VARCHAR,
                    n_obs INTEGER,
                    baseline_mae DOUBLE,
                    enhanced_mae DOUBLE,
                    delta_mae DOUBLE,
                    pct_improvement DOUBLE,
                    p_value DOUBLE,
                    conclusion VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_panel_leakage_audit (
                    audit_id VARCHAR PRIMARY KEY,
                    observation_id VARCHAR,
                    ticker VARCHAR,
                    check_name VARCHAR,
                    check_status VARCHAR,
                    details VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def build_panel(self) -> Dict[str, Any]:
        """
        Assemble the complete company-date empirical panel.
        Extracts observations across 2023 and 2024 cohorts, applies strict PIT filters,
        constructs features and targets, and returns the assembled dataset.
        """
        self.initialize_tables()

        with self.db.get_connection() as con:
            # 1. Load companies
            comp_rows = con.execute("SELECT company_id, ticker, cik, name, sector FROM companies ORDER BY ticker").fetchall()
            companies = {
                r[1]: {"company_id": r[0], "ticker": r[1], "cik": r[2], "name": r[3], "sector": r[4]}
                for r in comp_rows
            }

            # 2. Load 10-K filing documents
            doc_rows = con.execute("""
                SELECT 
                    ticker, form, filing_date::VARCHAR as filing_date,
                    acceptance_datetime::VARCHAR as acceptance_datetime,
                    accession_number
                FROM filing_documents
                WHERE form = '10-K'
                ORDER BY filing_date
            """).fetchall()

            doc_cols = ["ticker", "form", "filing_date", "acceptance_datetime", "accession_number"]
            filing_docs = [dict(zip(doc_cols, r)) for r in doc_rows]

            # 3. Load annual financial statements
            af_rows = con.execute("""
                SELECT 
                    statement_id, ticker, fiscal_year,
                    filing_date::VARCHAR as filing_date,
                    acceptance_datetime::VARCHAR as acceptance_datetime,
                    accession_number,
                    revenue, cogs, gross_profit, ebit, fcf, cfo,
                    total_assets, accounts_receivable, inventory, accounts_payable,
                    total_debt, cash
                FROM annual_financials
                ORDER BY ticker, fiscal_year
            """).fetchall()

            af_cols = [
                "statement_id", "ticker", "fiscal_year", "filing_date", "acceptance_datetime",
                "accession_number", "revenue", "cogs", "gross_profit", "ebit", "fcf", "cfo",
                "total_assets", "accounts_receivable", "inventory", "accounts_payable",
                "total_debt", "cash"
            ]
            statements_by_ticker_fy: Dict[Tuple[str, int], Dict[str, Any]] = {}
            statements_by_accession: Dict[str, Dict[str, Any]] = {}
            for r in af_rows:
                rd = dict(zip(af_cols, r))
                statements_by_ticker_fy[(rd["ticker"], rd["fiscal_year"])] = rd
                if rd.get("accession_number"):
                    statements_by_accession[rd["accession_number"]] = rd

            # 4. Load financial features (for ROIC, growth rates, etc.)
            feat_rows = con.execute("""
                SELECT ticker, fiscal_year, feature_name, feature_value
                FROM financial_features
                WHERE fiscal_period = 'FY'
            """).fetchall()
            feat_cols = ["ticker", "fiscal_year", "feature_name", "feature_value"]
            features_by_ticker_fy: Dict[Tuple[str, int], Dict[str, float]] = {}
            for r in feat_rows:
                rd = dict(zip(feat_cols, r))
                fval = float(rd["feature_value"]) if rd.get("feature_value") is not None else 0.0
                features_by_ticker_fy.setdefault((rd["ticker"], rd["fiscal_year"]), {})[rd["feature_name"]] = fval

            # 5. Load qualitative extractions
            ext_rows = con.execute("""
                SELECT 
                    extraction_id, ticker, accession_number, category, claim,
                    direction, severity, materiality, confidence,
                    filing_date::VARCHAR as filing_date,
                    acceptance_datetime::VARCHAR as acceptance_datetime
                FROM filing_extractions
                WHERE validation_status = 'VALIDATED'
                ORDER BY ticker, filing_date
            """).fetchall()
            ext_cols = [
                "extraction_id", "ticker", "accession_number", "category", "claim",
                "direction", "severity", "materiality", "confidence",
                "filing_date", "acceptance_datetime"
            ]
            extractions_by_accession: Dict[str, List[Dict[str, Any]]] = {}
            extractions_by_ticker_year: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
            for r in ext_rows:
                rd = dict(zip(ext_cols, r))
                extractions_by_accession.setdefault(rd["accession_number"], []).append(rd)
                fyr = rd["filing_date"][:4]
                extractions_by_ticker_year.setdefault((rd["ticker"], fyr), []).append(rd)

            # 6. Load filing change signals
            sig_rows = con.execute("""
                SELECT ticker, category, change_type, direction_shift, severity_shift, materiality
                FROM filing_change_signals
            """).fetchall()
            sig_cols = ["ticker", "category", "change_type", "direction_shift", "severity_shift", "materiality"]
            signals_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
            for r in sig_rows:
                rd = dict(zip(sig_cols, r))
                signals_by_ticker.setdefault(rd["ticker"], []).append(rd)

        # Assemble observations
        observations: List[PanelObservation] = []
        features_list: List[PanelFeatures] = []
        targets_list: List[PanelTargets] = []

        sev_weights = {"LOW": 0.33, "MEDIUM": 0.67, "HIGH": 1.0}
        mat_weights = {"LOW": 0.33, "MEDIUM": 0.67, "HIGH": 1.0}
        dir_signs = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "MIXED": -0.3, "NEGATIVE": -1.0}

        for doc in filing_docs:
            ticker = doc["ticker"]
            comp_info = companies.get(ticker)
            if not comp_info:
                continue

            obs_acc_dt = doc["acceptance_datetime"] or f"{doc['filing_date']} 23:59:59"
            # Point-in-Time Lock: acceptance_datetime is the authoritative availability timestamp
            obs_date = str(obs_acc_dt)[:10]
            obs_year = obs_date[:4]
            cohort = f"COHORT_{obs_year}"
            accession = doc["accession_number"]

            # Match base annual statement (by accession or ticker + fiscal year)
            base_stmt = statements_by_accession.get(accession)
            if not base_stmt:
                # Fallback: calendar year mapping (2023 10-K -> FY2022, 2024 10-K -> FY2023)
                estimated_base_fy = int(obs_year) - 1
                base_stmt = statements_by_ticker_fy.get((ticker, estimated_base_fy))

            if not base_stmt:
                continue

            base_fy = base_stmt["fiscal_year"]
            target_fy = base_fy + 1
            fwd_stmt = statements_by_ticker_fy.get((ticker, target_fy))

            # Strictly enforce POINT-IN-TIME LOCK:
            # Target statement must have been filed strictly after observation date
            has_valid_target = False
            fwd_filing_date = ""
            fwd_accession = ""
            if fwd_stmt:
                fwd_filing_date = str(fwd_stmt.get("filing_date", ""))
                fwd_accession = str(fwd_stmt.get("accession_number", ""))
                if fwd_filing_date > obs_date:
                    has_valid_target = True

            # Strictly enforce FILING COVERAGE LOCK:
            # Only use extractions from this exact filing document or strictly <= obs_acc_dt
            eligible_exts = extractions_by_accession.get(accession, [])
            if not eligible_exts:
                # Check if extractions exist for this ticker and filing year with filing_date <= obs_date
                candidate_exts = extractions_by_ticker_year.get((ticker, obs_year), [])
                eligible_exts = [
                    e for e in candidate_exts
                    if e["filing_date"] <= obs_date and (not e.get("acceptance_datetime") or e["acceptance_datetime"] <= obs_acc_dt)
                ]

            has_complete_filing = (len(eligible_exts) > 0)

            # Compute Baseline Features
            rev_t0 = float(base_stmt.get("revenue") or 0.0)
            ebit_t0 = float(base_stmt.get("ebit") or 0.0)
            cogs_t0 = float(base_stmt.get("cogs") or 0.0)
            gp_t0 = float(base_stmt.get("gross_profit") or (rev_t0 - cogs_t0 if rev_t0 and cogs_t0 else 0.0))
            fcf_t0 = float(base_stmt.get("fcf") or 0.0)
            cfo_t0 = float(base_stmt.get("cfo") or 0.0)
            assets_t0 = float(base_stmt.get("total_assets") or 0.0)
            debt_t0 = float(base_stmt.get("total_debt") or 0.0)
            cash_t0 = float(base_stmt.get("cash") or 0.0)
            ar_t0 = float(base_stmt.get("accounts_receivable") or 0.0)
            inv_t0 = float(base_stmt.get("inventory") or 0.0)
            ap_t0 = float(base_stmt.get("accounts_payable") or 0.0)

            # Prior year for YoY revenue growth
            prior_stmt = statements_by_ticker_fy.get((ticker, base_fy - 1))
            rev_prior = float(prior_stmt.get("revenue") or 0.0) if prior_stmt else 0.0

            ff_dict = features_by_ticker_fy.get((ticker, base_fy), {})

            rev_growth_yoy = (rev_t0 - rev_prior) / rev_prior if rev_prior > 0.0 else ff_dict.get("revenue_growth_yoy", 0.0)
            ebit_margin = ebit_t0 / rev_t0 if rev_t0 > 0.0 else 0.0
            gross_margin = gp_t0 / rev_t0 if rev_t0 > 0.0 else 0.0
            fcf_margin = fcf_t0 / rev_t0 if rev_t0 > 0.0 else 0.0
            net_debt = (debt_t0 - cash_t0)
            net_debt_to_revenue = net_debt / rev_t0 if rev_t0 > 0.0 else 0.0
            owc = (ar_t0 + inv_t0 - ap_t0)
            owc_to_revenue = owc / rev_t0 if rev_t0 > 0.0 else ff_dict.get("owc_to_revenue", 0.0)
            asset_turnover = rev_t0 / assets_t0 if assets_t0 > 0.0 else 0.0
            roic = ff_dict.get("roic", ebit_margin * asset_turnover * 0.79)  # approximate after-tax roic if missing
            beta_val, _ = get_beta(ticker, comp_info["sector"])
            wacc_val = 0.085

            baseline_dict = {
                "revenue_growth_yoy": float(rev_growth_yoy),
                "ebit_margin": float(ebit_margin),
                "gross_margin": float(gross_margin),
                "roic": float(roic),
                "fcf_margin": float(fcf_margin),
                "net_debt_to_revenue": float(net_debt_to_revenue),
                "owc_to_revenue": float(owc_to_revenue),
                "asset_turnover": float(asset_turnover),
                "beta": float(beta_val),
                "wacc": float(wacc_val),
            }
            has_complete_baseline = (rev_t0 > 0.0 and ebit_t0 != 0.0)

            # Compute Qualitative Filing Features across all 12 categories
            cat_scores: Dict[str, List[float]] = {cat: [] for cat in [
                "MARGIN_PRESSURE", "SUPPLY_CHAIN_RISK", "REGULATORY_RISK", "LITIGATION_RISK",
                "DEMAND_UNCERTAINTY", "COMPETITIVE_PRESSURE", "LIQUIDITY_RISK", "STRATEGIC_CHANGE",
                "MATERIAL_BUSINESS_CHANGE", "GUIDANCE_DIRECTION", "CAPITAL_ALLOCATION_CHANGE",
                "MANAGEMENT_OUTLOOK"
            ]}

            pos_count = 0
            neg_count = 0
            total_risk_claims = 0
            high_mat_count = 0

            for ext in eligible_exts:
                cat = ext.get("category", "")
                direction = ext.get("direction", "NEUTRAL")
                severity = ext.get("severity", "LOW")
                materiality = ext.get("materiality", "LOW")
                conf = float(ext.get("confidence", 0.90))

                s_weight = sev_weights.get(severity, 0.33)
                m_weight = mat_weights.get(materiality, 0.33)
                d_sign = dir_signs.get(direction, 0.0)
                risk_intensity = s_weight * m_weight * conf

                if cat in cat_scores:
                    if cat in ("GUIDANCE_DIRECTION", "CAPITAL_ALLOCATION_CHANGE", "MANAGEMENT_OUTLOOK"):
                        cat_scores[cat].append(d_sign * s_weight * conf)
                    else:
                        cat_scores[cat].append(risk_intensity)

                if direction == "POSITIVE":
                    pos_count += 1
                elif direction in ("NEGATIVE", "MIXED"):
                    neg_count += 1
                    total_risk_claims += 1

                if materiality == "HIGH":
                    high_mat_count += 1

            t_signals = signals_by_ticker.get(ticker, []) if has_complete_filing else []
            escalated_count = sum(1 for sig in t_signals if sig.get("change_type") == "ESCALATED")
            n_claims = len(eligible_exts)
            net_sentiment = (pos_count - neg_count) / max(1, n_claims) if n_claims > 0 else 0.0

            def avg_or_zero(vals: List[float]) -> float:
                return float(sum(vals) / len(vals)) if vals else 0.0

            filing_dict = {
                "margin_pressure_score": avg_or_zero(cat_scores["MARGIN_PRESSURE"]),
                "supply_chain_risk_score": avg_or_zero(cat_scores["SUPPLY_CHAIN_RISK"]),
                "regulatory_risk_score": avg_or_zero(cat_scores["REGULATORY_RISK"]),
                "litigation_risk_score": avg_or_zero(cat_scores["LITIGATION_RISK"]),
                "demand_uncertainty_score": avg_or_zero(cat_scores["DEMAND_UNCERTAINTY"]),
                "competitive_pressure_score": avg_or_zero(cat_scores["COMPETITIVE_PRESSURE"]),
                "liquidity_risk_score": avg_or_zero(cat_scores["LIQUIDITY_RISK"]),
                "strategic_change_score": avg_or_zero(cat_scores["STRATEGIC_CHANGE"]),
                "material_business_change_score": avg_or_zero(cat_scores["MATERIAL_BUSINESS_CHANGE"]),
                "guidance_direction_score": avg_or_zero(cat_scores["GUIDANCE_DIRECTION"]),
                "capital_allocation_change_score": avg_or_zero(cat_scores["CAPITAL_ALLOCATION_CHANGE"]),
                "management_outlook_score": avg_or_zero(cat_scores["MANAGEMENT_OUTLOOK"]),
                "total_risk_claims": float(total_risk_claims),
                "high_materiality_risk_count": float(high_mat_count),
                "escalated_risk_count": float(escalated_count),
                "net_qualitative_sentiment": float(net_sentiment),
            }

            # Compute Target Realizations (PRIMARY: forward_ebit_margin_change)
            targ_margin_change = None
            targ_rev_growth = None
            targ_deterioration = None

            if has_valid_target and fwd_stmt:
                rev_t1 = float(fwd_stmt.get("revenue") or 0.0)
                ebit_t1 = float(fwd_stmt.get("ebit") or 0.0)
                if rev_t0 > 0.0 and rev_t1 > 0.0:
                    ebit_margin_t1 = ebit_t1 / rev_t1
                    # Primary Target
                    targ_margin_change = float(ebit_margin_t1 - ebit_margin)
                    # Secondary Continuous Target
                    targ_rev_growth = float((rev_t1 - rev_t0) / rev_t0)
                    # Secondary Binary Target: 1.0 if operating margin deteriorated, 0.0 otherwise
                    targ_deterioration = 1.0 if (ebit_margin_t1 < ebit_margin) else 0.0

            obs_id = f"panel_{ticker}_{base_fy}"
            obs = PanelObservation(
                observation_id=obs_id,
                company_id=comp_info["company_id"],
                ticker=ticker,
                cik=comp_info["cik"],
                sector=comp_info["sector"],
                cohort=cohort,
                observation_date=obs_date,
                acceptance_datetime=obs_acc_dt,
                latest_filing_form="10-K",
                latest_filing_accession=accession,
                financial_data_as_of=obs_acc_dt,
                filing_data_as_of=obs_acc_dt,
                base_fiscal_year=base_fy,
                target_fiscal_year=target_fy,
                target_realization_date=fwd_filing_date,
                target_realization_accession=fwd_accession,
                has_complete_baseline=has_complete_baseline,
                has_complete_filing=has_complete_filing,
                has_valid_target=(targ_margin_change is not None),
            )

            feats = PanelFeatures(
                observation_id=obs_id,
                ticker=ticker,
                baseline=baseline_dict,
                filing=filing_dict,
            )

            targs = PanelTargets(
                observation_id=obs_id,
                ticker=ticker,
                forward_ebit_margin_change=targ_margin_change,
                forward_revenue_growth=targ_rev_growth,
                earnings_deterioration=targ_deterioration,
                realization_date=fwd_filing_date,
                realization_accession=fwd_accession,
                is_valid=(targ_margin_change is not None),
            )

            observations.append(obs)
            features_list.append(feats)
            targets_list.append(targs)

        # Persist to DuckDB
        self._persist_to_db(observations, features_list, targets_list)

        return {
            "observations": observations,
            "features": features_list,
            "targets": targets_list,
        }

    def _persist_to_db(
        self,
        observations: List[PanelObservation],
        features_list: List[PanelFeatures],
        targets_list: List[PanelTargets],
    ) -> None:
        """Atomically persist panel observations, features, and targets into DuckDB."""
        with self.db.get_connection() as con:
            con.execute("DELETE FROM research_panel_observations")
            con.execute("DELETE FROM research_panel_features")
            con.execute("DELETE FROM research_panel_targets")

            for obs in observations:
                con.execute(
                    """
                    INSERT INTO research_panel_observations (
                        observation_id, company_id, ticker, cik, sector, cohort,
                        observation_date, acceptance_datetime, latest_filing_form,
                        latest_filing_accession, financial_data_as_of, filing_data_as_of,
                        base_fiscal_year, target_fiscal_year,
                        has_complete_baseline, has_complete_filing, has_valid_target
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        obs.observation_id, obs.company_id, obs.ticker, obs.cik, obs.sector, obs.cohort,
                        obs.observation_date, obs.acceptance_datetime, obs.latest_filing_form,
                        obs.latest_filing_accession, obs.financial_data_as_of, obs.filing_data_as_of,
                        obs.base_fiscal_year, obs.target_fiscal_year,
                        obs.has_complete_baseline, obs.has_complete_filing, obs.has_valid_target
                    ],
                )

            for feats in features_list:
                for fname, fval in feats.baseline.items():
                    con.execute(
                        """
                        INSERT INTO research_panel_features (
                            observation_id, ticker, feature_group, feature_name, feature_value
                        ) VALUES (?, ?, 'BASELINE', ?, ?)
                        """,
                        [feats.observation_id, feats.ticker, fname, fval],
                    )
                for fname, fval in feats.filing.items():
                    con.execute(
                        """
                        INSERT INTO research_panel_features (
                            observation_id, ticker, feature_group, feature_name, feature_value
                        ) VALUES (?, ?, 'FILING', ?, ?)
                        """,
                        [feats.observation_id, feats.ticker, fname, fval],
                    )

            for targ in targets_list:
                con.execute(
                    """
                    INSERT INTO research_panel_targets (
                        observation_id, ticker, forward_ebit_margin_change,
                        forward_revenue_growth, earnings_deterioration,
                        realization_date, realization_accession, is_valid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        targ.observation_id, targ.ticker,
                        targ.forward_ebit_margin_change, targ.forward_revenue_growth,
                        targ.earnings_deterioration, targ.realization_date or None,
                        targ.realization_accession or None, targ.is_valid
                    ],
                )
