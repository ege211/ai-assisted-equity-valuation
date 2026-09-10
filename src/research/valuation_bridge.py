"""
Task A: Controlled Valuation Bridge between Filing Intelligence and Valuation Engine.

Applies predefined, versioned, deterministic scenario mappings from verified
qualitative signals to valuation forecast drivers, preserving core mathematical determinism.
"""
from typing import Any, Dict, List, Optional, Tuple

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.models import ValuationComparisonRecord
from src.valuation.assumptions import build_forecast_assumptions
from src.valuation.dcf import calculate_dcf
from src.valuation.engine import ValuationEngine
from src.valuation.models import ForecastAssumptions, WACCInputs

BRIDGE_VERSION = "valuation_bridge_v1.0"


def bridge_filing_to_valuation(
    ticker: str,
    valuation_date: str = "2024-12-31",
    engine: Optional[ValuationEngine] = None,
    db: Optional[DatabaseManager] = None,
) -> ValuationComparisonRecord:
    """
    Execute controlled bridge comparison for a single company:
    Baseline DCF vs. Filing-Informed Scenario DCF.
    """
    db_mgr = db or DatabaseManager()
    val_engine = engine or ValuationEngine(db_manager=db_mgr)

    # 1. Run baseline valuation
    val_pack = val_engine.value_company(ticker=ticker, valuation_date=valuation_date, persist=False)
    base_dcf = val_pack["scenarios"].base
    inputs = val_pack["inputs"]
    wacc_inputs = val_pack["wacc_inputs"]
    base_assumptions = build_forecast_assumptions("BASE", inputs)

    # 2. Query verified filing claims for this company
    with db_mgr.get_connection() as con:
        comp_row = con.execute("SELECT name, sector FROM companies WHERE ticker = ?", [ticker]).fetchone()
        comp_name = comp_row[0] if comp_row else ticker
        sector = comp_row[1] if comp_row else "Unknown"

        claims = con.execute(
            """
            SELECT category, claim, evidence_quote, severity, materiality, direction, confidence
            FROM filing_extractions
            WHERE ticker = ? AND validation_status = 'VALIDATED'
            ORDER BY confidence DESC
            """,
            [ticker],
        ).fetchall()

    # 3. Aggregate qualitative signals
    cat_scores: Dict[str, float] = {}
    top_claim_by_cat: Dict[str, Tuple[str, str]] = {}  # cat -> (claim, quote)

    for c in claims:
        cat, claim_text, quote, sev, mat, direction, conf = c
        intensity = (1.0 if sev == "HIGH" else 0.67 if sev == "MEDIUM" else 0.33) * float(conf)
        if cat not in cat_scores or intensity > cat_scores[cat]:
            cat_scores[cat] = intensity
            top_claim_by_cat[cat] = (claim_text, quote)

    # 4. Determine primary signal and deterministic scenario adjustment
    # Rule hierarchy: MARGIN_PRESSURE > SUPPLY_CHAIN_RISK > REGULATORY_RISK > DEMAND_UNCERTAINTY > CAPITAL_ALLOCATION_CHANGE
    primary_cat = "NONE"
    signal_intensity = 0.0
    key_assumption = "none"
    adjustment_magnitude = 0.0
    evidence_citation = "No material qualitative adjustment triggered."

    adj_growth = base_assumptions.revenue_growth_rates[:]
    adj_margins = base_assumptions.ebit_margins[:]
    adj_wacc_in = WACCInputs(
        risk_free_rate=wacc_inputs.risk_free_rate,
        beta=wacc_inputs.beta,
        equity_risk_premium=wacc_inputs.equity_risk_premium,
        cost_of_debt=wacc_inputs.cost_of_debt,
        tax_rate=wacc_inputs.tax_rate,
        market_equity_value=wacc_inputs.market_equity_value,
        total_debt=wacc_inputs.total_debt,
        target_debt_to_capital=wacc_inputs.target_debt_to_capital,
        rf_source=wacc_inputs.rf_source,
        beta_source=wacc_inputs.beta_source,
        erp_source=wacc_inputs.erp_source,
        cost_of_debt_source=wacc_inputs.cost_of_debt_source,
    )
    adj_terminal_growth = base_assumptions.terminal_growth_rate

    if cat_scores.get("MARGIN_PRESSURE", 0.0) >= 0.25:
        primary_cat = "MARGIN_PRESSURE"
        signal_intensity = cat_scores["MARGIN_PRESSURE"]
        # Reduce EBIT margins by 50 to 120 bps based on intensity
        margin_cut = min(0.012, max(0.005, signal_intensity * 0.015))
        adj_margins = [max(0.02, m - margin_cut) for m in adj_margins]
        key_assumption = "ebit_margins"
        adjustment_magnitude = -margin_cut
        claim_t, quote_t = top_claim_by_cat["MARGIN_PRESSURE"]
        evidence_citation = f"Item 7 MD&A: \"{quote_t[:120]}...\""

    elif cat_scores.get("SUPPLY_CHAIN_RISK", 0.0) >= 0.25:
        primary_cat = "SUPPLY_CHAIN_RISK"
        signal_intensity = cat_scores["SUPPLY_CHAIN_RISK"]
        # Reduce revenue growth rates by 40 to 100 bps
        growth_cut = min(0.010, max(0.004, signal_intensity * 0.012))
        adj_growth = [max(0.01, g - growth_cut) for g in adj_growth]
        key_assumption = "revenue_growth_rates"
        adjustment_magnitude = -growth_cut
        claim_t, quote_t = top_claim_by_cat["SUPPLY_CHAIN_RISK"]
        evidence_citation = f"Item 1A Risk Factors: \"{quote_t[:120]}...\""

    elif cat_scores.get("REGULATORY_RISK", 0.0) >= 0.25 or cat_scores.get("LITIGATION_RISK", 0.0) >= 0.25:
        primary_cat = "REGULATORY_RISK" if cat_scores.get("REGULATORY_RISK", 0.0) >= cat_scores.get("LITIGATION_RISK", 0.0) else "LITIGATION_RISK"
        signal_intensity = cat_scores[primary_cat]
        # Increase ERP discount premium by 25 to 50 bps
        erp_premium = min(0.005, max(0.0025, signal_intensity * 0.006))
        adj_wacc_in.equity_risk_premium += erp_premium
        key_assumption = "wacc_discount_rate"
        adjustment_magnitude = erp_premium
        claim_t, quote_t = top_claim_by_cat[primary_cat]
        evidence_citation = f"Item 1A / Item 3: \"{quote_t[:120]}...\""

    elif cat_scores.get("CAPITAL_ALLOCATION_CHANGE", 0.0) >= 0.25:
        primary_cat = "CAPITAL_ALLOCATION_CHANGE"
        signal_intensity = cat_scores["CAPITAL_ALLOCATION_CHANGE"]
        # Favorable capital allocation (+25 bps terminal growth efficiency)
        adj_terminal_growth = min(0.035, base_assumptions.terminal_growth_rate + 0.0025)
        key_assumption = "terminal_growth_rate"
        adjustment_magnitude = 0.0025
        claim_t, quote_t = top_claim_by_cat["CAPITAL_ALLOCATION_CHANGE"]
        evidence_citation = f"Item 7 MD&A: \"{quote_t[:120]}...\""

    # 5. Compute Enhanced DCF
    adj_assumptions = ForecastAssumptions(
        scenario_name="FILING_INFORMED",
        forecast_years=base_assumptions.forecast_years,
        revenue_growth_rates=adj_growth,
        ebit_margins=adj_margins,
        tax_rate=base_assumptions.tax_rate,
        da_ratio_of_rev=base_assumptions.da_ratio_of_rev,
        capex_ratio_of_rev=base_assumptions.capex_ratio_of_rev,
        nwc_ratio_of_rev=base_assumptions.nwc_ratio_of_rev,
        terminal_growth_rate=adj_terminal_growth,
        discount_convention=base_assumptions.discount_convention,
    )

    enh_dcf = calculate_dcf(inputs=inputs, assumptions=adj_assumptions, wacc_inputs=adj_wacc_in)

    fv_base = float(base_dcf.fair_value_per_share)
    fv_enh = float(enh_dcf.fair_value_per_share)
    fv_diff = fv_enh - fv_base
    fv_pct = (fv_diff / fv_base) * 100.0 if fv_base != 0.0 else 0.0
    price = float(inputs.current_share_price)
    upside_base = float(base_dcf.upside_downside)
    upside_enh = ((fv_enh - price) / price) if price > 0.0 else 0.0

    return ValuationComparisonRecord(
        ticker=ticker,
        company_name=comp_name,
        sector=sector,
        valuation_date=valuation_date,
        baseline_fair_value=fv_base,
        enhanced_fair_value=fv_enh,
        fair_value_difference=fv_diff,
        fair_value_pct_change=fv_pct,
        market_price=price,
        baseline_upside=upside_base,
        enhanced_upside=upside_enh,
        primary_signal_category=primary_cat,
        signal_intensity=signal_intensity,
        key_assumption_adjusted=key_assumption,
        adjustment_magnitude=adjustment_magnitude,
        evidence_citation=evidence_citation,
    )


def run_universe_valuation_bridge(
    valuation_date: str = "2024-12-31",
    db_manager: Optional[DatabaseManager] = None,
) -> List[ValuationComparisonRecord]:
    """
    Execute valuation bridge across all 30 universe companies and persist to DuckDB.
    """
    db = db_manager or DatabaseManager()
    engine = ValuationEngine(db_manager=db)

    with db.get_connection() as con:
        tickers = [r[0] for r in con.execute("SELECT ticker FROM companies ORDER BY ticker").fetchall()]

    records: List[ValuationComparisonRecord] = []
    db_records: List[Dict[str, Any]] = []

    for t in tickers:
        try:
            rec = bridge_filing_to_valuation(ticker=t, valuation_date=valuation_date, engine=engine, db=db)
            records.append(rec)
            db_records.append({
                "comparison_id": f"vcomp_{t}_{valuation_date}",
                "ticker": rec.ticker,
                "company_name": rec.company_name,
                "sector": rec.sector,
                "valuation_date": rec.valuation_date,
                "baseline_fair_value": rec.baseline_fair_value,
                "enhanced_fair_value": rec.enhanced_fair_value,
                "fair_value_difference": rec.fair_value_difference,
                "fair_value_pct_change": rec.fair_value_pct_change,
                "market_price": rec.market_price,
                "baseline_upside": rec.baseline_upside,
                "enhanced_upside": rec.enhanced_upside,
                "primary_signal_category": rec.primary_signal_category,
                "signal_intensity": rec.signal_intensity,
                "key_assumption_adjusted": rec.key_assumption_adjusted,
                "adjustment_magnitude": rec.adjustment_magnitude,
                "evidence_citation": rec.evidence_citation,
            })
        except Exception as e:
            continue

    if db_records:
        db.insert_valuation_comparison_results(db_records)

    return records
