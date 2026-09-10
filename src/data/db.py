"""
DuckDB database storage and relational management.
Provides thread-safe initialization, schema creation, fact insertion,
and point-in-time querying for financial statements.
"""
import hashlib
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import duckdb

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/processed/financials.duckdb"

SCHEMA_COMPANIES = """
CREATE TABLE IF NOT EXISTS companies (
    company_id VARCHAR PRIMARY KEY,
    ticker VARCHAR NOT NULL UNIQUE,
    cik VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    fiscal_year_end_month INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_FILINGS = """
CREATE TABLE IF NOT EXISTS filings (
    accession_number VARCHAR PRIMARY KEY,
    cik VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    form VARCHAR NOT NULL,
    filing_date DATE NOT NULL,
    report_date DATE,
    acceptance_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    primary_document VARCHAR,
    is_amendment BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_filings_cik_date ON filings(cik, filing_date);
CREATE INDEX IF NOT EXISTS idx_filings_acceptance ON filings(acceptance_datetime);
"""

SCHEMA_RAW_XBRL_FACTS = """
CREATE TABLE IF NOT EXISTS raw_xbrl_facts (
    fact_id VARCHAR PRIMARY KEY,
    cik VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    form VARCHAR NOT NULL,
    filing_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    taxonomy VARCHAR NOT NULL,
    concept VARCHAR NOT NULL,
    start_date DATE,
    end_date DATE NOT NULL,
    is_instant BOOLEAN NOT NULL,
    fiscal_year INTEGER,
    fiscal_period VARCHAR,
    frame VARCHAR,
    unit VARCHAR NOT NULL,
    val DOUBLE PRECISION NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_raw_facts_lookup ON raw_xbrl_facts(cik, concept, end_date);
CREATE INDEX IF NOT EXISTS idx_raw_facts_acceptance ON raw_xbrl_facts(acceptance_datetime);
"""

SCHEMA_NORMALIZED_FINANCIAL_FACTS = """
CREATE TABLE IF NOT EXISTS normalized_financial_facts (
    fact_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR NOT NULL,
    period_start_date DATE,
    period_end_date DATE NOT NULL,
    filing_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    form VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    canonical_variable VARCHAR NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR NOT NULL,
    source_concept VARCHAR NOT NULL,
    fallback_tier VARCHAR NOT NULL,
    source_url_or_identifier VARCHAR NOT NULL,
    data_status VARCHAR NOT NULL,
    raw_fact_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_norm_facts_pit ON normalized_financial_facts(ticker, canonical_variable, acceptance_datetime);
CREATE INDEX IF NOT EXISTS idx_norm_facts_period ON normalized_financial_facts(ticker, fiscal_year, fiscal_period, canonical_variable);
"""

SCHEMA_QUARTERLY_FINANCIALS = """
CREATE TABLE IF NOT EXISTS quarterly_financials (
    statement_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter VARCHAR NOT NULL,
    period_start_date DATE,
    period_end_date DATE NOT NULL,
    filing_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    form VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    revenue DOUBLE PRECISION,
    cogs DOUBLE PRECISION,
    gross_profit DOUBLE PRECISION,
    sga DOUBLE PRECISION,
    ebit DOUBLE PRECISION,
    interest_expense DOUBLE PRECISION,
    pretax_income DOUBLE PRECISION,
    tax_expense DOUBLE PRECISION,
    net_income DOUBLE PRECISION,
    da DOUBLE PRECISION,
    cash DOUBLE PRECISION,
    current_assets DOUBLE PRECISION,
    accounts_receivable DOUBLE PRECISION,
    inventory DOUBLE PRECISION,
    total_assets DOUBLE PRECISION,
    current_liabilities DOUBLE PRECISION,
    accounts_payable DOUBLE PRECISION,
    debt_current DOUBLE PRECISION,
    debt_noncurrent DOUBLE PRECISION,
    total_debt DOUBLE PRECISION,
    total_liabilities DOUBLE PRECISION,
    total_equity DOUBLE PRECISION,
    cfo DOUBLE PRECISION,
    capex DOUBLE PRECISION,
    fcf DOUBLE PRECISION,
    is_derived_quarter BOOLEAN NOT NULL DEFAULT FALSE,
    deaccumulation_status VARCHAR NOT NULL DEFAULT 'DIRECT_STANDARD',
    lineage VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quarterly_fin_pit ON quarterly_financials(ticker, fiscal_year, fiscal_quarter, acceptance_datetime);
CREATE INDEX IF NOT EXISTS idx_quarterly_fin_period ON quarterly_financials(ticker, period_end_date);
"""

SCHEMA_ANNUAL_FINANCIALS = """
CREATE TABLE IF NOT EXISTS annual_financials (
    statement_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR NOT NULL DEFAULT 'FY',
    period_start_date DATE,
    period_end_date DATE NOT NULL,
    filing_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    form VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    revenue DOUBLE PRECISION,
    cogs DOUBLE PRECISION,
    gross_profit DOUBLE PRECISION,
    sga DOUBLE PRECISION,
    ebit DOUBLE PRECISION,
    interest_expense DOUBLE PRECISION,
    pretax_income DOUBLE PRECISION,
    tax_expense DOUBLE PRECISION,
    net_income DOUBLE PRECISION,
    da DOUBLE PRECISION,
    cash DOUBLE PRECISION,
    current_assets DOUBLE PRECISION,
    accounts_receivable DOUBLE PRECISION,
    inventory DOUBLE PRECISION,
    total_assets DOUBLE PRECISION,
    current_liabilities DOUBLE PRECISION,
    accounts_payable DOUBLE PRECISION,
    debt_current DOUBLE PRECISION,
    debt_noncurrent DOUBLE PRECISION,
    total_debt DOUBLE PRECISION,
    total_liabilities DOUBLE PRECISION,
    total_equity DOUBLE PRECISION,
    cfo DOUBLE PRECISION,
    capex DOUBLE PRECISION,
    fcf DOUBLE PRECISION,
    data_status VARCHAR NOT NULL DEFAULT 'DIRECT_STANDARD',
    lineage VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_annual_fin_pit ON annual_financials(ticker, fiscal_year, acceptance_datetime);
CREATE INDEX IF NOT EXISTS idx_annual_fin_period ON annual_financials(ticker, period_end_date);
"""

SCHEMA_LTM_FINANCIALS = """
CREATE TABLE IF NOT EXISTS ltm_financials (
    statement_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    as_of_fiscal_year INTEGER NOT NULL,
    as_of_fiscal_quarter VARCHAR NOT NULL,
    period_end_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    constituent_quarters VARCHAR NOT NULL,
    constituent_accessions VARCHAR NOT NULL,
    revenue DOUBLE PRECISION,
    cogs DOUBLE PRECISION,
    gross_profit DOUBLE PRECISION,
    sga DOUBLE PRECISION,
    ebit DOUBLE PRECISION,
    interest_expense DOUBLE PRECISION,
    pretax_income DOUBLE PRECISION,
    tax_expense DOUBLE PRECISION,
    net_income DOUBLE PRECISION,
    da DOUBLE PRECISION,
    cfo DOUBLE PRECISION,
    capex DOUBLE PRECISION,
    fcf DOUBLE PRECISION,
    cash DOUBLE PRECISION,
    current_assets DOUBLE PRECISION,
    accounts_receivable DOUBLE PRECISION,
    inventory DOUBLE PRECISION,
    total_assets DOUBLE PRECISION,
    current_liabilities DOUBLE PRECISION,
    accounts_payable DOUBLE PRECISION,
    debt_current DOUBLE PRECISION,
    debt_noncurrent DOUBLE PRECISION,
    total_debt DOUBLE PRECISION,
    total_liabilities DOUBLE PRECISION,
    total_equity DOUBLE PRECISION,
    data_status VARCHAR NOT NULL DEFAULT 'DERIVED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ltm_fin_pit ON ltm_financials(ticker, as_of_fiscal_year, as_of_fiscal_quarter, acceptance_datetime);
CREATE INDEX IF NOT EXISTS idx_ltm_fin_period ON ltm_financials(ticker, period_end_date);
"""

SCHEMA_FINANCIAL_FEATURES = """
CREATE TABLE IF NOT EXISTS financial_features (
    feature_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    as_of_date TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end_date DATE NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR NOT NULL,
    feature_name VARCHAR NOT NULL,
    feature_value DOUBLE PRECISION,
    unit VARCHAR NOT NULL DEFAULT 'USD',
    source_periods VARCHAR,
    source_filings VARCHAR,
    source_accessions VARCHAR,
    calculation_method VARCHAR NOT NULL,
    source_concepts VARCHAR,
    data_status VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fin_features_pit ON financial_features(ticker, feature_name, as_of_date);
CREATE INDEX IF NOT EXISTS idx_fin_features_period ON financial_features(ticker, fiscal_year, fiscal_period, feature_name);
"""

SCHEMA_VALUATION_ASSUMPTIONS = """
CREATE TABLE IF NOT EXISTS valuation_assumptions (
    assumption_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    valuation_date DATE NOT NULL,
    scenario VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    forecast_years INTEGER NOT NULL,
    risk_free_rate DOUBLE PRECISION NOT NULL,
    beta DOUBLE PRECISION NOT NULL,
    equity_risk_premium DOUBLE PRECISION NOT NULL,
    cost_of_equity DOUBLE PRECISION NOT NULL,
    cost_of_debt DOUBLE PRECISION NOT NULL,
    effective_tax_rate DOUBLE PRECISION NOT NULL,
    weight_equity DOUBLE PRECISION NOT NULL,
    weight_debt DOUBLE PRECISION NOT NULL,
    wacc DOUBLE PRECISION NOT NULL,
    terminal_growth_rate DOUBLE PRECISION NOT NULL,
    revenue_growth_rates VARCHAR NOT NULL,
    ebit_margins VARCHAR NOT NULL,
    tax_rate_assumptions VARCHAR NOT NULL,
    da_ratio_assumptions VARCHAR,
    capex_ratio_assumptions VARCHAR,
    nwc_ratio_assumptions VARCHAR,
    data_sources VARCHAR,
    assumption_sources VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_val_assump_ticker ON valuation_assumptions(ticker, valuation_date, scenario);
"""

SCHEMA_FORECAST_PERIODS = """
CREATE TABLE IF NOT EXISTS forecast_periods (
    forecast_id VARCHAR PRIMARY KEY,
    valuation_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    fiscal_year INTEGER NOT NULL,
    forecast_year_index INTEGER NOT NULL,
    revenue DOUBLE PRECISION NOT NULL,
    revenue_growth DOUBLE PRECISION NOT NULL,
    ebit_margin DOUBLE PRECISION NOT NULL,
    ebit DOUBLE PRECISION NOT NULL,
    tax_rate DOUBLE PRECISION NOT NULL,
    tax_expense DOUBLE PRECISION NOT NULL,
    nopat DOUBLE PRECISION NOT NULL,
    da DOUBLE PRECISION NOT NULL,
    capex DOUBLE PRECISION NOT NULL,
    nwc DOUBLE PRECISION NOT NULL,
    delta_nwc DOUBLE PRECISION NOT NULL,
    fcff DOUBLE PRECISION NOT NULL,
    discount_factor DOUBLE PRECISION NOT NULL,
    pv_fcff DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fc_val_id ON forecast_periods(valuation_id, forecast_year_index);
"""

SCHEMA_VALUATION_RESULTS = """
CREATE TABLE IF NOT EXISTS valuation_results (
    valuation_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    valuation_date DATE NOT NULL,
    data_as_of_date TIMESTAMP WITH TIME ZONE NOT NULL,
    valuation_mode VARCHAR NOT NULL,
    scenario VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    current_share_price DOUBLE PRECISION,
    pv_explicit_fcff DOUBLE PRECISION NOT NULL,
    terminal_value DOUBLE PRECISION NOT NULL,
    pv_terminal_value DOUBLE PRECISION NOT NULL,
    enterprise_value DOUBLE PRECISION NOT NULL,
    total_debt DOUBLE PRECISION NOT NULL,
    cash DOUBLE PRECISION NOT NULL,
    net_debt DOUBLE PRECISION NOT NULL,
    equity_value DOUBLE PRECISION NOT NULL,
    diluted_shares DOUBLE PRECISION NOT NULL,
    fair_value_per_share DOUBLE PRECISION NOT NULL,
    upside_downside DOUBLE PRECISION,
    wacc DOUBLE PRECISION NOT NULL,
    terminal_growth DOUBLE PRECISION NOT NULL,
    cost_of_equity DOUBLE PRECISION NOT NULL,
    cost_of_debt DOUBLE PRECISION NOT NULL,
    risk_free_rate DOUBLE PRECISION NOT NULL,
    beta DOUBLE PRECISION NOT NULL,
    erp DOUBLE PRECISION NOT NULL,
    revenue_growth_summary VARCHAR,
    ebit_margin_summary VARCHAR,
    data_sources VARCHAR,
    assumption_sources VARCHAR,
    calculation_status VARCHAR NOT NULL,
    status_reason VARCHAR,
    lineage VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_val_results_pit ON valuation_results(ticker, valuation_date, scenario);
"""

SCHEMA_VALUATION_SENSITIVITIES = """
CREATE TABLE IF NOT EXISTS valuation_sensitivities (
    sensitivity_id VARCHAR PRIMARY KEY,
    valuation_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    parameter_1_name VARCHAR NOT NULL,
    parameter_1_value DOUBLE PRECISION NOT NULL,
    parameter_2_name VARCHAR NOT NULL,
    parameter_2_value DOUBLE PRECISION NOT NULL,
    enterprise_value DOUBLE PRECISION,
    equity_value DOUBLE PRECISION,
    fair_value_per_share DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_val_sens_id ON valuation_sensitivities(valuation_id, parameter_1_name, parameter_2_name);
"""

SCHEMA_RELATIVE_VALUATION_RESULTS = """
CREATE TABLE IF NOT EXISTS relative_valuation_results (
    relative_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    valuation_date DATE NOT NULL,
    as_of_date TIMESTAMP WITH TIME ZONE NOT NULL,
    peer_group VARCHAR NOT NULL,
    multiple_name VARCHAR NOT NULL,
    company_multiple DOUBLE PRECISION,
    peer_median_multiple DOUBLE PRECISION,
    implied_equity_value DOUBLE PRECISION,
    implied_fair_value_per_share DOUBLE PRECISION,
    benchmark_source VARCHAR,
    status VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rel_val_ticker ON relative_valuation_results(ticker, valuation_date, multiple_name);
"""

SCHEMA_FILING_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS filing_documents (
    document_id VARCHAR PRIMARY KEY,
    accession_number VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    form VARCHAR NOT NULL,
    filing_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE,
    primary_document VARCHAR NOT NULL,
    file_path VARCHAR,
    content_hash VARCHAR NOT NULL,
    char_count INTEGER NOT NULL,
    word_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fdocs_acc ON filing_documents(accession_number);
CREATE INDEX IF NOT EXISTS idx_fdocs_ticker_form ON filing_documents(ticker, form, filing_date);
"""

SCHEMA_FILING_SECTIONS = """
CREATE TABLE IF NOT EXISTS filing_sections (
    section_id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    section_name VARCHAR NOT NULL,
    section_title VARCHAR NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    detection_confidence VARCHAR NOT NULL,
    section_text VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fsec_doc ON filing_sections(document_id, section_name);
"""

SCHEMA_FILING_PASSAGES = """
CREATE TABLE IF NOT EXISTS filing_passages (
    passage_id VARCHAR PRIMARY KEY,
    section_id VARCHAR NOT NULL,
    document_id VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    section_name VARCHAR NOT NULL,
    category_hint VARCHAR NOT NULL,
    passage_index INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    passage_text VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fpass_sec ON filing_passages(section_id, category_hint);
"""

SCHEMA_FILING_EXTRACTIONS = """
CREATE TABLE IF NOT EXISTS filing_extractions (
    extraction_id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    form VARCHAR NOT NULL,
    filing_date DATE NOT NULL,
    acceptance_datetime TIMESTAMP WITH TIME ZONE,
    filing_period_end DATE,
    section_name VARCHAR NOT NULL,
    passage_id VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    claim VARCHAR NOT NULL,
    evidence_quote VARCHAR NOT NULL,
    evidence_location VARCHAR NOT NULL,
    source_identifier VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    materiality VARCHAR NOT NULL,
    extraction_model VARCHAR NOT NULL,
    prompt_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    extraction_timestamp TIMESTAMP WITH TIME ZONE,
    validation_status VARCHAR NOT NULL,
    validation_reason VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fext_ticker ON filing_extractions(ticker, category, filing_date);
CREATE INDEX IF NOT EXISTS idx_fext_acc ON filing_extractions(accession_number);
"""

SCHEMA_FILING_CHANGE_SIGNALS = """
CREATE TABLE IF NOT EXISTS filing_change_signals (
    signal_id VARCHAR PRIMARY KEY,
    ticker VARCHAR NOT NULL,
    current_accession VARCHAR NOT NULL,
    previous_accession VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    change_type VARCHAR NOT NULL,
    current_claim VARCHAR,
    previous_claim VARCHAR,
    direction_shift VARCHAR,
    severity_shift VARCHAR,
    materiality VARCHAR NOT NULL,
    summary VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fchange_ticker ON filing_change_signals(ticker, category);
"""

SCHEMA_LLM_EXTRACTION_RUNS = """
CREATE TABLE IF NOT EXISTS llm_extraction_runs (
    run_id VARCHAR PRIMARY KEY,
    run_timestamp TIMESTAMP WITH TIME ZONE,
    model_name VARCHAR NOT NULL,
    provider_name VARCHAR NOT NULL,
    prompt_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    temperature DOUBLE PRECISION,
    total_passages_processed INTEGER NOT NULL,
    total_extractions_generated INTEGER NOT NULL,
    total_validated INTEGER NOT NULL,
    total_rejected INTEGER NOT NULL,
    execution_duration_sec DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_RESEARCH_OBSERVATIONS = """
CREATE TABLE IF NOT EXISTS research_observations (
    observation_id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    data_as_of_date TIMESTAMP WITH TIME ZONE NOT NULL,
    fiscal_year INTEGER NOT NULL,
    latest_eligible_filing VARCHAR NOT NULL,
    latest_filing_accession VARCHAR NOT NULL,
    financial_feature_version VARCHAR NOT NULL,
    filing_intelligence_version VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_res_obs_ticker ON research_observations(ticker, observation_date);
"""

SCHEMA_RESEARCH_FEATURES = """
CREATE TABLE IF NOT EXISTS research_features (
    feature_id VARCHAR PRIMARY KEY,
    observation_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    feature_name VARCHAR NOT NULL,
    feature_value DOUBLE PRECISION NOT NULL,
    feature_category VARCHAR NOT NULL,
    is_filing_derived BOOLEAN NOT NULL,
    source_lineage VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_res_feat_obs ON research_features(observation_id, feature_category);
"""

SCHEMA_RESEARCH_TARGETS = """
CREATE TABLE IF NOT EXISTS research_targets (
    target_id VARCHAR PRIMARY KEY,
    observation_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_value DOUBLE PRECISION,
    target_horizon_months INTEGER NOT NULL,
    realization_date DATE NOT NULL,
    source_statement_id VARCHAR,
    is_valid BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_res_targ_obs ON research_targets(observation_id, target_name);
"""

SCHEMA_RESEARCH_EXPERIMENTS = """
CREATE TABLE IF NOT EXISTS research_experiments (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    horizon_months INTEGER NOT NULL,
    baseline_model_type VARCHAR NOT NULL,
    enhanced_model_type VARCHAR NOT NULL,
    validation_method VARCHAR NOT NULL,
    sample_size INTEGER NOT NULL,
    features_baseline VARCHAR NOT NULL,
    features_enhanced VARCHAR NOT NULL,
    hyperparameters VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_RESEARCH_MODEL_RESULTS = """
CREATE TABLE IF NOT EXISTS research_model_results (
    result_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    model_role VARCHAR NOT NULL,
    observation_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    actual_value DOUBLE PRECISION NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    residual DOUBLE PRECISION NOT NULL,
    absolute_error DOUBLE PRECISION NOT NULL,
    squared_error DOUBLE PRECISION NOT NULL,
    validation_fold VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_res_mod_exp ON research_model_results(experiment_id, model_role);
"""

SCHEMA_RESEARCH_ABLATION_RESULTS = """
CREATE TABLE IF NOT EXISTS research_ablation_results (
    ablation_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    ablation_group VARCHAR NOT NULL,
    feature_count INTEGER NOT NULL,
    mae DOUBLE PRECISION NOT NULL,
    rmse DOUBLE PRECISION NOT NULL,
    r2 DOUBLE PRECISION NOT NULL,
    delta_mae_vs_baseline DOUBLE PRECISION NOT NULL,
    delta_rmse_vs_baseline DOUBLE PRECISION NOT NULL,
    sample_size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_RESEARCH_ROBUSTNESS_RESULTS = """
CREATE TABLE IF NOT EXISTS research_robustness_results (
    robustness_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    test_type VARCHAR NOT NULL,
    stratum VARCHAR NOT NULL,
    sample_size INTEGER NOT NULL,
    baseline_mae DOUBLE PRECISION NOT NULL,
    enhanced_mae DOUBLE PRECISION NOT NULL,
    delta_mae DOUBLE PRECISION NOT NULL,
    baseline_rmse DOUBLE PRECISION NOT NULL,
    enhanced_rmse DOUBLE PRECISION NOT NULL,
    delta_rmse DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_VALUATION_COMPARISON_RESULTS = """
CREATE TABLE IF NOT EXISTS valuation_comparison_results (
    comparison_id VARCHAR PRIMARY KEY,
    ticker VARCHAR NOT NULL,
    company_name VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    valuation_date DATE NOT NULL,
    baseline_fair_value DOUBLE PRECISION NOT NULL,
    enhanced_fair_value DOUBLE PRECISION NOT NULL,
    fair_value_difference DOUBLE PRECISION NOT NULL,
    fair_value_pct_change DOUBLE PRECISION NOT NULL,
    market_price DOUBLE PRECISION NOT NULL,
    baseline_upside DOUBLE PRECISION NOT NULL,
    enhanced_upside DOUBLE PRECISION NOT NULL,
    primary_signal_category VARCHAR NOT NULL,
    signal_intensity DOUBLE PRECISION NOT NULL,
    key_assumption_adjusted VARCHAR NOT NULL,
    adjustment_magnitude DOUBLE PRECISION NOT NULL,
    evidence_citation VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_val_comp_ticker ON valuation_comparison_results(ticker, valuation_date);
"""


def compute_fact_id(*components: Any) -> str:
    """Compute a deterministic SHA-256 hash string for unique fact identification."""
    content = "|".join(str(c) if c is not None else "" for c in components)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]


class DatabaseManager:
    """Manages DuckDB embedded relational storage for financial statements."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.init_schema()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Return a fresh DuckDB connection."""
        return duckdb.connect(self.db_path)

    def init_schema(self) -> None:
        """Initialize all relational tables and indexes."""
        with self.get_connection() as con:
            con.execute(SCHEMA_COMPANIES)
            con.execute(SCHEMA_FILINGS)
            con.execute(SCHEMA_RAW_XBRL_FACTS)
            con.execute(SCHEMA_NORMALIZED_FINANCIAL_FACTS)
            con.execute(SCHEMA_QUARTERLY_FINANCIALS)
            con.execute(SCHEMA_ANNUAL_FINANCIALS)
            con.execute(SCHEMA_LTM_FINANCIALS)
            con.execute(SCHEMA_FINANCIAL_FEATURES)
            con.execute(SCHEMA_VALUATION_ASSUMPTIONS)
            con.execute(SCHEMA_FORECAST_PERIODS)
            con.execute(SCHEMA_VALUATION_RESULTS)
            con.execute(SCHEMA_VALUATION_SENSITIVITIES)
            con.execute(SCHEMA_RELATIVE_VALUATION_RESULTS)
            con.execute(SCHEMA_FILING_DOCUMENTS)
            con.execute(SCHEMA_FILING_SECTIONS)
            con.execute(SCHEMA_FILING_PASSAGES)
            con.execute(SCHEMA_FILING_EXTRACTIONS)
            con.execute(SCHEMA_FILING_CHANGE_SIGNALS)
            con.execute(SCHEMA_LLM_EXTRACTION_RUNS)
            con.execute(SCHEMA_RESEARCH_OBSERVATIONS)
            con.execute(SCHEMA_RESEARCH_FEATURES)
            con.execute(SCHEMA_RESEARCH_TARGETS)
            con.execute(SCHEMA_RESEARCH_EXPERIMENTS)
            con.execute(SCHEMA_RESEARCH_MODEL_RESULTS)
            con.execute(SCHEMA_RESEARCH_ABLATION_RESULTS)
            con.execute(SCHEMA_RESEARCH_ROBUSTNESS_RESULTS)
            con.execute(SCHEMA_VALUATION_COMPARISON_RESULTS)

    def insert_companies(self, companies: List[Dict[str, Any]]) -> int:
        """Insert company records, ignoring duplicates."""
        if not companies:
            return 0
        with self.get_connection() as con:
            inserted = 0
            for c in companies:
                con.execute(
                    """
                    INSERT OR IGNORE INTO companies (
                        company_id, ticker, cik, name, sector, fiscal_year_end_month
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        c["company_id"],
                        c["ticker"],
                        c["cik"],
                        c["name"],
                        c["sector"],
                        c.get("fiscal_year_end_month"),
                    ],
                )
                inserted += 1
            return inserted

    def insert_filings(self, filings: List[Dict[str, Any]]) -> int:
        """Insert filings catalog, updating or ignoring existing accession numbers."""
        if not filings:
            return 0
        with self.get_connection() as con:
            inserted = 0
            for f in filings:
                is_amend = "/A" in str(f.get("form", ""))
                con.execute(
                    """
                    INSERT OR IGNORE INTO filings (
                        accession_number, cik, ticker, form, filing_date, report_date,
                        acceptance_datetime, primary_document, is_amendment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f["accession_number"],
                        f["cik"],
                        f["ticker"],
                        f["form"],
                        f["filing_date"],
                        f.get("report_date"),
                        f["acceptance_datetime"],
                        f.get("primary_document"),
                        is_amend,
                    ],
                )
                inserted += 1
            return inserted

    def insert_raw_facts(self, raw_facts: List[Dict[str, Any]]) -> int:
        """Bulk insert raw XBRL facts using executemany for high throughput."""
        if not raw_facts:
            return 0
        tuples_data = [
            (
                r["fact_id"],
                r["cik"],
                r["accession_number"],
                r["form"],
                r["filing_date"],
                r["acceptance_datetime"],
                r["taxonomy"],
                r["concept"],
                r.get("start_date"),
                r["end_date"],
                r["is_instant"],
                r.get("fiscal_year"),
                r.get("fiscal_period"),
                r.get("frame"),
                r["unit"],
                r["val"],
                r.get("description"),
            )
            for r in raw_facts
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR IGNORE INTO raw_xbrl_facts (
                    fact_id, cik, accession_number, form, filing_date, acceptance_datetime,
                    taxonomy, concept, start_date, end_date, is_instant, fiscal_year,
                    fiscal_period, frame, unit, val, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_normalized_facts(self, normalized_facts: List[Dict[str, Any]]) -> int:
        """Bulk insert normalized financial observations."""
        if not normalized_facts:
            return 0
        tuples_data = [
            (
                nf["fact_id"],
                nf["company_id"],
                nf["ticker"],
                nf["cik"],
                nf["sector"],
                nf["fiscal_year"],
                nf["fiscal_period"],
                nf.get("period_start_date"),
                nf["period_end_date"],
                nf["filing_date"],
                nf["acceptance_datetime"],
                nf["form"],
                nf["accession_number"],
                nf["canonical_variable"],
                nf["value"],
                nf["unit"],
                nf["source_concept"],
                nf["fallback_tier"],
                nf["source_url_or_identifier"],
                nf["data_status"],
                nf.get("raw_fact_id"),
            )
            for nf in normalized_facts
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO normalized_financial_facts (
                    fact_id, company_id, ticker, cik, sector, fiscal_year, fiscal_period,
                    period_start_date, period_end_date, filing_date, acceptance_datetime,
                    form, accession_number, canonical_variable, value, unit,
                    source_concept, fallback_tier, source_url_or_identifier,
                    data_status, raw_fact_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def query_point_in_time(
        self,
        ticker: str,
        as_of_date: str,
        canonical_variables: Optional[List[str]] = None,
        fiscal_period: str = "FY",
    ) -> List[Dict[str, Any]]:
        """
        Query normalized financial facts for a company as of a specific point in time.

        Enforces strict Point-in-Time information availability:
        - Only filings accepted on or before as_of_date are considered.
        - If amendments occurred on or before as_of_date, the latest revision is used.
        - Amendments occurring after as_of_date are strictly excluded.

        Args:
            ticker: Company ticker symbol.
            as_of_date: String ISO timestamp/date (e.g., '2021-01-15' or '2021-01-15T00:00:00Z').
            canonical_variables: Optional subset of variables to retrieve.
            fiscal_period: 'FY' for annual statements, or 'Q1', 'Q2', 'Q3'.

        Returns:
            List of normalized fact records meeting PIT criteria.
        """
        query = """
        WITH ranked_facts AS (
            SELECT
                fact_id, company_id, ticker, cik, sector, fiscal_year, fiscal_period,
                period_start_date::VARCHAR as period_start_date,
                period_end_date::VARCHAR as period_end_date,
                filing_date::VARCHAR as filing_date,
                acceptance_datetime::VARCHAR as acceptance_datetime,
                form, accession_number, canonical_variable, value, unit,
                source_concept, fallback_tier, source_url_or_identifier,
                data_status, raw_fact_id,
                ROW_NUMBER() OVER (
                    PARTITION BY ticker, fiscal_year, fiscal_period, canonical_variable
                    ORDER BY acceptance_datetime DESC, filing_date DESC
                ) as rev_rank
            FROM normalized_financial_facts
            WHERE ticker = ?
              AND fiscal_period = ?
              AND acceptance_datetime <= ?::TIMESTAMP WITH TIME ZONE
        )
        SELECT 
            fact_id, company_id, ticker, cik, sector, fiscal_year, fiscal_period,
            period_start_date, period_end_date, filing_date, acceptance_datetime,
            form, accession_number, canonical_variable, value, unit,
            source_concept, fallback_tier, source_url_or_identifier,
            data_status, raw_fact_id
        FROM ranked_facts
        WHERE rev_rank = 1
        """
        params: List[Any] = [ticker, fiscal_period, as_of_date]

        if canonical_variables:
            placeholders = ",".join("?" for _ in canonical_variables)
            query += f" AND canonical_variable IN ({placeholders})"
            params.extend(canonical_variables)

        query += " ORDER BY fiscal_year ASC, canonical_variable ASC;"

        with self.get_connection() as con:
            cursor = con.execute(query, params)
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def insert_quarterly_financials(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert quarterly financial statements."""
        if not records:
            return 0
        tuples_data = [
            (
                r["statement_id"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["sector"],
                r["fiscal_year"],
                r["fiscal_quarter"],
                r.get("period_start_date"),
                r["period_end_date"],
                r["filing_date"],
                r["acceptance_datetime"],
                r["form"],
                r["accession_number"],
                r.get("revenue"),
                r.get("cogs"),
                r.get("gross_profit"),
                r.get("sga"),
                r.get("ebit"),
                r.get("interest_expense"),
                r.get("pretax_income"),
                r.get("tax_expense"),
                r.get("net_income"),
                r.get("da"),
                r.get("cash"),
                r.get("current_assets"),
                r.get("accounts_receivable"),
                r.get("inventory"),
                r.get("total_assets"),
                r.get("current_liabilities"),
                r.get("accounts_payable"),
                r.get("debt_current"),
                r.get("debt_noncurrent"),
                r.get("total_debt"),
                r.get("total_liabilities"),
                r.get("total_equity"),
                r.get("cfo"),
                r.get("capex"),
                r.get("fcf"),
                r.get("is_derived_quarter", False),
                r.get("deaccumulation_status", "DIRECT_STANDARD"),
                r.get("lineage"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO quarterly_financials (
                    statement_id, company_id, ticker, cik, sector, fiscal_year, fiscal_quarter,
                    period_start_date, period_end_date, filing_date, acceptance_datetime,
                    form, accession_number, revenue, cogs, gross_profit, sga, ebit,
                    interest_expense, pretax_income, tax_expense, net_income, da,
                    cash, current_assets, accounts_receivable, inventory, total_assets,
                    current_liabilities, accounts_payable, debt_current, debt_noncurrent,
                    total_debt, total_liabilities, total_equity, cfo, capex, fcf,
                    is_derived_quarter, deaccumulation_status, lineage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_annual_financials(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert annual financial statements."""
        if not records:
            return 0
        tuples_data = [
            (
                r["statement_id"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["sector"],
                r["fiscal_year"],
                r.get("fiscal_period", "FY"),
                r.get("period_start_date"),
                r["period_end_date"],
                r["filing_date"],
                r["acceptance_datetime"],
                r["form"],
                r["accession_number"],
                r.get("revenue"),
                r.get("cogs"),
                r.get("gross_profit"),
                r.get("sga"),
                r.get("ebit"),
                r.get("interest_expense"),
                r.get("pretax_income"),
                r.get("tax_expense"),
                r.get("net_income"),
                r.get("da"),
                r.get("cash"),
                r.get("current_assets"),
                r.get("accounts_receivable"),
                r.get("inventory"),
                r.get("total_assets"),
                r.get("current_liabilities"),
                r.get("accounts_payable"),
                r.get("debt_current"),
                r.get("debt_noncurrent"),
                r.get("total_debt"),
                r.get("total_liabilities"),
                r.get("total_equity"),
                r.get("cfo"),
                r.get("capex"),
                r.get("fcf"),
                r.get("data_status", "DIRECT_STANDARD"),
                r.get("lineage"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO annual_financials (
                    statement_id, company_id, ticker, cik, sector, fiscal_year, fiscal_period,
                    period_start_date, period_end_date, filing_date, acceptance_datetime,
                    form, accession_number, revenue, cogs, gross_profit, sga, ebit,
                    interest_expense, pretax_income, tax_expense, net_income, da,
                    cash, current_assets, accounts_receivable, inventory, total_assets,
                    current_liabilities, accounts_payable, debt_current, debt_noncurrent,
                    total_debt, total_liabilities, total_equity, cfo, capex, fcf,
                    data_status, lineage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_ltm_financials(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert LTM financial statements."""
        if not records:
            return 0
        tuples_data = [
            (
                r["statement_id"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["sector"],
                r["as_of_fiscal_year"],
                r["as_of_fiscal_quarter"],
                r["period_end_date"],
                r["acceptance_datetime"],
                r["constituent_quarters"],
                r["constituent_accessions"],
                r.get("revenue"),
                r.get("cogs"),
                r.get("gross_profit"),
                r.get("sga"),
                r.get("ebit"),
                r.get("interest_expense"),
                r.get("pretax_income"),
                r.get("tax_expense"),
                r.get("net_income"),
                r.get("da"),
                r.get("cfo"),
                r.get("capex"),
                r.get("fcf"),
                r.get("cash"),
                r.get("current_assets"),
                r.get("accounts_receivable"),
                r.get("inventory"),
                r.get("total_assets"),
                r.get("current_liabilities"),
                r.get("accounts_payable"),
                r.get("debt_current"),
                r.get("debt_noncurrent"),
                r.get("total_debt"),
                r.get("total_liabilities"),
                r.get("total_equity"),
                r.get("data_status", "DERIVED"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO ltm_financials (
                    statement_id, company_id, ticker, cik, sector, as_of_fiscal_year,
                    as_of_fiscal_quarter, period_end_date, acceptance_datetime,
                    constituent_quarters, constituent_accessions, revenue, cogs,
                    gross_profit, sga, ebit, interest_expense, pretax_income, tax_expense,
                    net_income, da, cfo, capex, fcf, cash, current_assets, accounts_receivable,
                    inventory, total_assets, current_liabilities, accounts_payable,
                    debt_current, debt_noncurrent, total_debt, total_liabilities, total_equity,
                    data_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_financial_features(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert computed financial features."""
        if not records:
            return 0
        tuples_data = [
            (
                r["feature_id"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["sector"],
                r["as_of_date"],
                r["period_end_date"],
                r["fiscal_year"],
                r["fiscal_period"],
                r["feature_name"],
                r.get("feature_value"),
                r.get("unit", "USD"),
                r.get("source_periods"),
                r.get("source_filings"),
                r.get("source_accessions"),
                r["calculation_method"],
                r.get("source_concepts"),
                r["data_status"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO financial_features (
                    feature_id, company_id, ticker, cik, sector, as_of_date,
                    period_end_date, fiscal_year, fiscal_period, feature_name,
                    feature_value, unit, source_periods, source_filings, source_accessions,
                    calculation_method, source_concepts, data_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def query_features_pit(
        self,
        ticker: str,
        as_of_date: str,
        feature_names: Optional[List[str]] = None,
        fiscal_period: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query fundamental financial features as of a specific point in time.

        Only features with as_of_date <= target date are admitted.
        Returns the latest revision for each feature.
        """
        query = """
        WITH ranked_features AS (
            SELECT
                feature_id, company_id, ticker, cik, sector,
                as_of_date::VARCHAR as as_of_date,
                period_end_date::VARCHAR as period_end_date,
                fiscal_year, fiscal_period, feature_name, feature_value, unit,
                source_periods, source_filings, source_accessions,
                calculation_method, source_concepts, data_status,
                ROW_NUMBER() OVER (
                    PARTITION BY ticker, fiscal_year, fiscal_period, feature_name
                    ORDER BY as_of_date DESC
                ) as rev_rank
            FROM financial_features
            WHERE ticker = ?
              AND as_of_date <= ?::TIMESTAMP WITH TIME ZONE
        """
        params: List[Any] = [ticker, as_of_date]

        if fiscal_period:
            query += " AND fiscal_period = ?"
            params.append(fiscal_period)

        if feature_names:
            placeholders = ",".join("?" for _ in feature_names)
            query += f" AND feature_name IN ({placeholders})"
            params.extend(feature_names)

        query += """
        )
        SELECT
            feature_id, company_id, ticker, cik, sector, as_of_date,
            period_end_date, fiscal_year, fiscal_period, feature_name,
            feature_value, unit, source_periods, source_filings, source_accessions,
            calculation_method, source_concepts, data_status
        FROM ranked_features
        WHERE rev_rank = 1
        ORDER BY fiscal_year ASC, fiscal_period ASC, feature_name ASC;
        """

        with self.get_connection() as con:
            cursor = con.execute(query, params)
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def insert_valuation_assumptions(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert valuation assumptions."""
        if not records:
            return 0
        tuples_data = [
            (
                r["assumption_id"],
                r["company_id"],
                r["ticker"],
                r["valuation_date"],
                r["scenario"],
                r["model_version"],
                r["forecast_years"],
                r["risk_free_rate"],
                r["beta"],
                r["equity_risk_premium"],
                r["cost_of_equity"],
                r["cost_of_debt"],
                r["effective_tax_rate"],
                r["weight_equity"],
                r["weight_debt"],
                r["wacc"],
                r["terminal_growth_rate"],
                r["revenue_growth_rates"],
                r["ebit_margins"],
                r["tax_rate_assumptions"],
                r.get("da_ratio_assumptions"),
                r.get("capex_ratio_assumptions"),
                r.get("nwc_ratio_assumptions"),
                r.get("data_sources"),
                r.get("assumption_sources"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO valuation_assumptions (
                    assumption_id, company_id, ticker, valuation_date, scenario,
                    model_version, forecast_years, risk_free_rate, beta,
                    equity_risk_premium, cost_of_equity, cost_of_debt, effective_tax_rate,
                    weight_equity, weight_debt, wacc, terminal_growth_rate,
                    revenue_growth_rates, ebit_margins, tax_rate_assumptions,
                    da_ratio_assumptions, capex_ratio_assumptions, nwc_ratio_assumptions,
                    data_sources, assumption_sources
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_forecast_periods(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert period-by-period forecasts."""
        if not records:
            return 0
        tuples_data = [
            (
                r["forecast_id"],
                r["valuation_id"],
                r["ticker"],
                r["fiscal_year"],
                r["forecast_year_index"],
                r["revenue"],
                r["revenue_growth"],
                r["ebit_margin"],
                r["ebit"],
                r["tax_rate"],
                r["tax_expense"],
                r["nopat"],
                r["da"],
                r["capex"],
                r["nwc"],
                r["delta_nwc"],
                r["fcff"],
                r["discount_factor"],
                r["pv_fcff"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO forecast_periods (
                    forecast_id, valuation_id, ticker, fiscal_year, forecast_year_index,
                    revenue, revenue_growth, ebit_margin, ebit, tax_rate, tax_expense,
                    nopat, da, capex, nwc, delta_nwc, fcff, discount_factor, pv_fcff
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_valuation_results(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert final valuation results."""
        if not records:
            return 0
        tuples_data = [
            (
                r["valuation_id"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["sector"],
                r["valuation_date"],
                r["data_as_of_date"],
                r["valuation_mode"],
                r["scenario"],
                r["model_version"],
                r.get("current_share_price"),
                r["pv_explicit_fcff"],
                r["terminal_value"],
                r["pv_terminal_value"],
                r["enterprise_value"],
                r["total_debt"],
                r["cash"],
                r["net_debt"],
                r["equity_value"],
                r["diluted_shares"],
                r["fair_value_per_share"],
                r.get("upside_downside"),
                r["wacc"],
                r["terminal_growth"],
                r["cost_of_equity"],
                r["cost_of_debt"],
                r["risk_free_rate"],
                r["beta"],
                r["erp"],
                r.get("revenue_growth_summary"),
                r.get("ebit_margin_summary"),
                r.get("data_sources"),
                r.get("assumption_sources"),
                r["calculation_status"],
                r.get("status_reason"),
                r.get("lineage"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO valuation_results (
                    valuation_id, company_id, ticker, cik, sector, valuation_date,
                    data_as_of_date, valuation_mode, scenario, model_version,
                    current_share_price, pv_explicit_fcff, terminal_value, pv_terminal_value,
                    enterprise_value, total_debt, cash, net_debt, equity_value,
                    diluted_shares, fair_value_per_share, upside_downside, wacc,
                    terminal_growth, cost_of_equity, cost_of_debt, risk_free_rate,
                    beta, erp, revenue_growth_summary, ebit_margin_summary,
                    data_sources, assumption_sources, calculation_status, status_reason, lineage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_valuation_sensitivities(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert sensitivity grid points."""
        if not records:
            return 0
        tuples_data = [
            (
                r["sensitivity_id"],
                r["valuation_id"],
                r["ticker"],
                r["parameter_1_name"],
                r["parameter_1_value"],
                r["parameter_2_name"],
                r["parameter_2_value"],
                r.get("enterprise_value"),
                r.get("equity_value"),
                r.get("fair_value_per_share"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO valuation_sensitivities (
                    sensitivity_id, valuation_id, ticker, parameter_1_name,
                    parameter_1_value, parameter_2_name, parameter_2_value,
                    enterprise_value, equity_value, fair_value_per_share
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_relative_valuation_results(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert relative valuation results."""
        if not records:
            return 0
        tuples_data = [
            (
                r["relative_id"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["sector"],
                r["valuation_date"],
                r["as_of_date"],
                r["peer_group"],
                r["multiple_name"],
                r.get("company_multiple"),
                r.get("peer_median_multiple"),
                r.get("implied_equity_value"),
                r.get("implied_fair_value_per_share"),
                r.get("benchmark_source"),
                r["status"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO relative_valuation_results (
                    relative_id, company_id, ticker, cik, sector, valuation_date,
                    as_of_date, peer_group, multiple_name, company_multiple,
                    peer_median_multiple, implied_equity_value, implied_fair_value_per_share,
                    benchmark_source, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def query_valuation_results(
        self,
        ticker: Optional[str] = None,
        valuation_date: Optional[str] = None,
        scenario: str = "BASE",
    ) -> List[Dict[str, Any]]:
        """Query valuation results with optional ticker and date filters."""
        query = """
        SELECT
            valuation_id, company_id, ticker, cik, sector,
            valuation_date::VARCHAR as valuation_date,
            data_as_of_date::VARCHAR as data_as_of_date,
            valuation_mode, scenario, model_version, current_share_price,
            pv_explicit_fcff, terminal_value, pv_terminal_value, enterprise_value,
            total_debt, cash, net_debt, equity_value, diluted_shares,
            fair_value_per_share, upside_downside, wacc, terminal_growth,
            cost_of_equity, cost_of_debt, risk_free_rate, beta, erp,
            revenue_growth_summary, ebit_margin_summary,
            data_sources, assumption_sources, calculation_status, status_reason, lineage
        FROM valuation_results
        WHERE scenario = ?
        """
        params: List[Any] = [scenario]
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        if valuation_date:
            query += " AND valuation_date <= ?::DATE"
            params.append(valuation_date)

        query += " ORDER BY ticker ASC, valuation_date DESC;"

        with self.get_connection() as con:
            cursor = con.execute(query, params)
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def insert_filing_documents(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert filing document metadata."""
        if not records:
            return 0
        tuples_data = [
            (
                r["document_id"],
                r["accession_number"],
                r["cik"],
                r["ticker"],
                r["form"],
                r["filing_date"],
                r.get("acceptance_datetime"),
                r["primary_document"],
                r.get("file_path"),
                r["content_hash"],
                r["char_count"],
                r["word_count"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO filing_documents (
                    document_id, accession_number, cik, ticker, form, filing_date,
                    acceptance_datetime, primary_document, file_path, content_hash,
                    char_count, word_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_filing_sections(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert parsed filing sections."""
        if not records:
            return 0
        tuples_data = [
            (
                r["section_id"],
                r["document_id"],
                r["accession_number"],
                r["ticker"],
                r["section_name"],
                r["section_title"],
                r["start_char"],
                r["end_char"],
                r["char_count"],
                r["detection_confidence"],
                r.get("section_text"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO filing_sections (
                    section_id, document_id, accession_number, ticker, section_name,
                    section_title, start_char, end_char, char_count, detection_confidence,
                    section_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_filing_passages(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert retrieved candidate passages."""
        if not records:
            return 0
        tuples_data = [
            (
                r["passage_id"],
                r["section_id"],
                r["document_id"],
                r["accession_number"],
                r["ticker"],
                r["section_name"],
                r["category_hint"],
                r["passage_index"],
                r["start_char"],
                r["end_char"],
                r["passage_text"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO filing_passages (
                    passage_id, section_id, document_id, accession_number, ticker,
                    section_name, category_hint, passage_index, start_char, end_char,
                    passage_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_filing_extractions(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert validated/rejected qualitative extractions."""
        if not records:
            return 0
        tuples_data = [
            (
                r["extraction_id"],
                r["document_id"],
                r["accession_number"],
                r["company_id"],
                r["ticker"],
                r["cik"],
                r["form"],
                r["filing_date"],
                r.get("acceptance_datetime"),
                r.get("filing_period_end"),
                r["section_name"],
                r["passage_id"],
                r["category"],
                r["claim"],
                r["evidence_quote"],
                r["evidence_location"],
                r["source_identifier"],
                r["direction"],
                r["severity"],
                r["confidence"],
                r["materiality"],
                r["extraction_model"],
                r["prompt_version"],
                r["schema_version"],
                r.get("extraction_timestamp"),
                r["validation_status"],
                r.get("validation_reason"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO filing_extractions (
                    extraction_id, document_id, accession_number, company_id, ticker,
                    cik, form, filing_date, acceptance_datetime, filing_period_end,
                    section_name, passage_id, category, claim, evidence_quote,
                    evidence_location, source_identifier, direction, severity,
                    confidence, materiality, extraction_model, prompt_version,
                    schema_version, extraction_timestamp, validation_status, validation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_filing_change_signals(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert period-over-period change signals."""
        if not records:
            return 0
        tuples_data = [
            (
                r["signal_id"],
                r["ticker"],
                r["current_accession"],
                r["previous_accession"],
                r["category"],
                r["change_type"],
                r.get("current_claim"),
                r.get("previous_claim"),
                r.get("direction_shift"),
                r.get("severity_shift"),
                r["materiality"],
                r["summary"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO filing_change_signals (
                    signal_id, ticker, current_accession, previous_accession, category,
                    change_type, current_claim, previous_claim, direction_shift,
                    severity_shift, materiality, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_llm_extraction_runs(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert extraction execution runs."""
        if not records:
            return 0
        tuples_data = [
            (
                r["run_id"],
                r["run_timestamp"],
                r["model_name"],
                r["provider_name"],
                r["prompt_version"],
                r["schema_version"],
                r.get("temperature"),
                r["total_passages_processed"],
                r["total_extractions_generated"],
                r["total_validated"],
                r["total_rejected"],
                r["execution_duration_sec"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO llm_extraction_runs (
                    run_id, run_timestamp, model_name, provider_name, prompt_version,
                    schema_version, temperature, total_passages_processed,
                    total_extractions_generated, total_validated, total_rejected,
                    execution_duration_sec
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def query_filing_extractions(
        self,
        ticker: Optional[str] = None,
        category: Optional[str] = None,
        validation_status: str = "VALIDATED",
        as_of_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query qualitative extractions with optional filters."""
        query = """
        SELECT
            extraction_id, document_id, accession_number, company_id, ticker,
            cik, form, filing_date::VARCHAR as filing_date,
            acceptance_datetime::VARCHAR as acceptance_datetime,
            filing_period_end::VARCHAR as filing_period_end,
            section_name, passage_id, category, claim, evidence_quote,
            evidence_location, source_identifier, direction, severity,
            confidence, materiality, extraction_model, prompt_version,
            schema_version, extraction_timestamp::VARCHAR as extraction_timestamp,
            validation_status, validation_reason
        FROM filing_extractions
        WHERE validation_status = ?
        """
        params: List[Any] = [validation_status]
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        if category:
            query += " AND category = ?"
            params.append(category)
        if as_of_date:
            query += " AND (acceptance_datetime::VARCHAR <= (? || ' 23:59:59') OR filing_date <= ?::DATE)"
            params.append(as_of_date)
            params.append(as_of_date)

        query += " ORDER BY filing_date DESC, confidence DESC;"

        with self.get_connection() as con:
            cursor = con.execute(query, params)
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def insert_research_observations(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert research observations."""
        if not records:
            return 0
        tuples_data = [
            (
                r["observation_id"],
                r["company_id"],
                r["ticker"],
                r["sector"],
                r["observation_date"],
                r["data_as_of_date"],
                r["fiscal_year"],
                r["latest_eligible_filing"],
                r["latest_filing_accession"],
                r["financial_feature_version"],
                r["filing_intelligence_version"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_observations (
                    observation_id, company_id, ticker, sector, observation_date,
                    data_as_of_date, fiscal_year, latest_eligible_filing,
                    latest_filing_accession, financial_feature_version,
                    filing_intelligence_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_research_features(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert aligned research features."""
        if not records:
            return 0
        tuples_data = [
            (
                r["feature_id"],
                r["observation_id"],
                r["ticker"],
                r["feature_name"],
                r["feature_value"],
                r["feature_category"],
                r["is_filing_derived"],
                r.get("source_lineage"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_features (
                    feature_id, observation_id, ticker, feature_name,
                    feature_value, feature_category, is_filing_derived,
                    source_lineage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_research_targets(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert research forward targets."""
        if not records:
            return 0
        tuples_data = [
            (
                r["target_id"],
                r["observation_id"],
                r["ticker"],
                r["target_name"],
                r["target_value"],
                r["target_horizon_months"],
                r["realization_date"],
                r.get("source_statement_id"),
                r["is_valid"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_targets (
                    target_id, observation_id, ticker, target_name,
                    target_value, target_horizon_months, realization_date,
                    source_statement_id, is_valid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_research_experiments(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert research experiment definitions."""
        if not records:
            return 0
        tuples_data = [
            (
                r["experiment_id"],
                r["experiment_name"],
                r["target_name"],
                r["horizon_months"],
                r["baseline_model_type"],
                r["enhanced_model_type"],
                r["validation_method"],
                r["sample_size"],
                r["features_baseline"],
                r["features_enhanced"],
                r.get("hyperparameters"),
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_experiments (
                    experiment_id, experiment_name, target_name, horizon_months,
                    baseline_model_type, enhanced_model_type, validation_method,
                    sample_size, features_baseline, features_enhanced, hyperparameters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_research_model_results(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert out-of-sample research model results."""
        if not records:
            return 0
        tuples_data = [
            (
                r["result_id"],
                r["experiment_id"],
                r["model_role"],
                r["observation_id"],
                r["ticker"],
                r["target_name"],
                r["actual_value"],
                r["predicted_value"],
                r["residual"],
                r["absolute_error"],
                r["squared_error"],
                r["validation_fold"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_model_results (
                    result_id, experiment_id, model_role, observation_id,
                    ticker, target_name, actual_value, predicted_value,
                    residual, absolute_error, squared_error, validation_fold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_research_ablation_results(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert ablation experiment results."""
        if not records:
            return 0
        tuples_data = [
            (
                r["ablation_id"],
                r["experiment_id"],
                r["ablation_group"],
                r["feature_count"],
                r["mae"],
                r["rmse"],
                r["r2"],
                r["delta_mae_vs_baseline"],
                r["delta_rmse_vs_baseline"],
                r["sample_size"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_ablation_results (
                    ablation_id, experiment_id, ablation_group, feature_count,
                    mae, rmse, r2, delta_mae_vs_baseline, delta_rmse_vs_baseline,
                    sample_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_research_robustness_results(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert robustness check results."""
        if not records:
            return 0
        tuples_data = [
            (
                r["robustness_id"],
                r["experiment_id"],
                r["test_type"],
                r["stratum"],
                r["sample_size"],
                r["baseline_mae"],
                r["enhanced_mae"],
                r["delta_mae"],
                r["baseline_rmse"],
                r["enhanced_rmse"],
                r["delta_rmse"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO research_robustness_results (
                    robustness_id, experiment_id, test_type, stratum,
                    sample_size, baseline_mae, enhanced_mae, delta_mae,
                    baseline_rmse, enhanced_rmse, delta_rmse
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def insert_valuation_comparison_results(self, records: List[Dict[str, Any]]) -> int:
        """Bulk insert baseline vs filing-informed valuation comparisons."""
        if not records:
            return 0
        tuples_data = [
            (
                r["comparison_id"],
                r["ticker"],
                r["company_name"],
                r["sector"],
                r["valuation_date"],
                r["baseline_fair_value"],
                r["enhanced_fair_value"],
                r["fair_value_difference"],
                r["fair_value_pct_change"],
                r["market_price"],
                r["baseline_upside"],
                r["enhanced_upside"],
                r["primary_signal_category"],
                r["signal_intensity"],
                r["key_assumption_adjusted"],
                r["adjustment_magnitude"],
                r["evidence_citation"],
            )
            for r in records
        ]
        with self.get_connection() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO valuation_comparison_results (
                    comparison_id, ticker, company_name, sector, valuation_date,
                    baseline_fair_value, enhanced_fair_value, fair_value_difference,
                    fair_value_pct_change, market_price, baseline_upside,
                    enhanced_upside, primary_signal_category, signal_intensity,
                    key_assumption_adjusted, adjustment_magnitude, evidence_citation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples_data,
            )
            return len(tuples_data)

    def get_ingestion_summary(self) -> Dict[str, Any]:
        """Return counts of records across all tables."""
        with self.get_connection() as con:
            n_companies = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            n_filings = con.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
            n_raw_facts = con.execute("SELECT COUNT(*) FROM raw_xbrl_facts").fetchone()[0]
            n_norm_facts = con.execute("SELECT COUNT(*) FROM normalized_financial_facts").fetchone()[0]
            n_quarterly = con.execute("SELECT COUNT(*) FROM quarterly_financials").fetchone()[0]
            n_annual = con.execute("SELECT COUNT(*) FROM annual_financials").fetchone()[0]
            n_ltm = con.execute("SELECT COUNT(*) FROM ltm_financials").fetchone()[0]
            n_features = con.execute("SELECT COUNT(*) FROM financial_features").fetchone()[0]
            n_assump = con.execute("SELECT COUNT(*) FROM valuation_assumptions").fetchone()[0]
            n_forecasts = con.execute("SELECT COUNT(*) FROM forecast_periods").fetchone()[0]
            n_val_results = con.execute("SELECT COUNT(*) FROM valuation_results").fetchone()[0]
            n_sens = con.execute("SELECT COUNT(*) FROM valuation_sensitivities").fetchone()[0]
            n_rel = con.execute("SELECT COUNT(*) FROM relative_valuation_results").fetchone()[0]
            n_fdocs = con.execute("SELECT COUNT(*) FROM filing_documents").fetchone()[0]
            n_fsec = con.execute("SELECT COUNT(*) FROM filing_sections").fetchone()[0]
            n_fpass = con.execute("SELECT COUNT(*) FROM filing_passages").fetchone()[0]
            n_fext = con.execute("SELECT COUNT(*) FROM filing_extractions").fetchone()[0]
            n_fchange = con.execute("SELECT COUNT(*) FROM filing_change_signals").fetchone()[0]
            n_fruns = con.execute("SELECT COUNT(*) FROM llm_extraction_runs").fetchone()[0]
            n_robs = con.execute("SELECT COUNT(*) FROM research_observations").fetchone()[0]
            n_rfeat = con.execute("SELECT COUNT(*) FROM research_features").fetchone()[0]
            n_rtarg = con.execute("SELECT COUNT(*) FROM research_targets").fetchone()[0]
            n_rexp = con.execute("SELECT COUNT(*) FROM research_experiments").fetchone()[0]
            n_rmod = con.execute("SELECT COUNT(*) FROM research_model_results").fetchone()[0]
            n_rabl = con.execute("SELECT COUNT(*) FROM research_ablation_results").fetchone()[0]
            n_rrob = con.execute("SELECT COUNT(*) FROM research_robustness_results").fetchone()[0]
            n_vcomp = con.execute("SELECT COUNT(*) FROM valuation_comparison_results").fetchone()[0]
            return {
                "companies_count": n_companies,
                "filings_count": n_filings,
                "raw_facts_count": n_raw_facts,
                "normalized_facts_count": n_norm_facts,
                "quarterly_financials_count": n_quarterly,
                "annual_financials_count": n_annual,
                "ltm_financials_count": n_ltm,
                "financial_features_count": n_features,
                "valuation_assumptions_count": n_assump,
                "forecast_periods_count": n_forecasts,
                "valuation_results_count": n_val_results,
                "valuation_sensitivities_count": n_sens,
                "relative_valuation_results_count": n_rel,
                "filing_documents_count": n_fdocs,
                "filing_sections_count": n_fsec,
                "filing_passages_count": n_fpass,
                "filing_extractions_count": n_fext,
                "filing_change_signals_count": n_fchange,
                "llm_extraction_runs_count": n_fruns,
                "research_observations_count": n_robs,
                "research_features_count": n_rfeat,
                "research_targets_count": n_rtarg,
                "research_experiments_count": n_rexp,
                "research_model_results_count": n_rmod,
                "research_ablation_results_count": n_rabl,
                "research_robustness_results_count": n_rrob,
                "valuation_comparison_results_count": n_vcomp,
            }
