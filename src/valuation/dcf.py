"""
Discounted Cash Flow (DCF) Valuation Engine.

Assembles:
1. Forecast periods and PV of discrete FCFF.
2. Gordon Growth Terminal Value and PV of Terminal Value.
3. Enterprise Value: EV = PV(FCFF) + PV(TV).
4. Equity Value Bridge: Equity Value = EV - Total Debt + Cash.
5. Per-Share Fair Value: Equity Value / Diluted Shares.
6. Upside/Downside vs Market Price.
"""
import uuid
from typing import Optional

from src.valuation.forecast import generate_forecast
from src.valuation.models import (
    DCFResult,
    ForecastAssumptions,
    IncompleteValuationInputsError,
    ValuationInputs,
    WACCInputs,
)
from src.valuation.terminal_value import calculate_terminal_value
from src.valuation.wacc import calculate_wacc


def calculate_dcf(
    inputs: ValuationInputs,
    assumptions: ForecastAssumptions,
    wacc_inputs: WACCInputs,
    valuation_mode: str = "HISTORICAL",
    model_version: str = "v1.0-deterministic",
) -> DCFResult:
    """
    Execute end-to-end DCF valuation.

    Parameters
    ----------
    inputs : ValuationInputs
        Financial statement inputs and share count.
    assumptions : ForecastAssumptions
        Scenario forecast drivers.
    wacc_inputs : WACCInputs
        CAPM and cost of debt inputs.
    valuation_mode : str
        'HISTORICAL' or 'LIVE'.
    model_version : str
        Version identifier.

    Returns
    -------
    DCFResult
        Comprehensive valuation output.
    """
    # Validate required inputs
    if inputs.diluted_shares is None or inputs.diluted_shares <= 0:
        raise IncompleteValuationInputsError(
            f"Missing or invalid diluted shares for {inputs.ticker}: {inputs.diluted_shares}"
        )
    if inputs.ltm_revenue is None or inputs.ltm_revenue <= 0:
        raise IncompleteValuationInputsError(
            f"Missing or non-positive LTM revenue for {inputs.ticker}: {inputs.ltm_revenue}"
        )

    # 1. Compute Cost of Capital (WACC)
    wacc_output = calculate_wacc(wacc_inputs)
    wacc = wacc_output.wacc

    # 2. Discrete Projections (5 Years)
    forecast_periods = generate_forecast(
        inputs=inputs,
        assumptions=assumptions,
        wacc=wacc,
    )
    pv_explicit_fcff = sum(p.pv_fcff for p in forecast_periods)

    # 3. Terminal Value
    final_year_fcff = forecast_periods[-1].fcff
    terminal_value, pv_tv = calculate_terminal_value(
        final_year_fcff=final_year_fcff,
        wacc=wacc,
        terminal_growth=assumptions.terminal_growth_rate,
        forecast_years=assumptions.forecast_years,
        discount_convention=assumptions.discount_convention,
    )

    # 4. Enterprise Value Bridge
    enterprise_value = pv_explicit_fcff + pv_tv
    cash = inputs.cash if inputs.cash is not None else 0.0
    total_debt = inputs.total_debt if inputs.total_debt is not None else 0.0
    net_debt = total_debt - cash
    equity_value = enterprise_value - total_debt + cash

    # 5. Fair Value Per Share
    diluted_shares = inputs.diluted_shares
    fair_value_per_share = equity_value / diluted_shares

    # 6. Market Upside / Downside
    upside_downside = None
    if inputs.current_share_price is not None and inputs.current_share_price > 0:
        upside_downside = (fair_value_per_share - inputs.current_share_price) / inputs.current_share_price

    # Summaries
    growth_str = ", ".join(f"{g * 100:.1f}%" for g in assumptions.revenue_growth_rates)
    margin_str = ", ".join(f"{m * 100:.1f}%" for m in assumptions.ebit_margins)
    val_id = f"val_{inputs.ticker}_{assumptions.scenario_name.lower()}_{inputs.valuation_date.replace('-', '')}_{uuid.uuid4().hex[:6]}"

    data_sources = (
        f"SEC EDGAR XBRL Facts (CIK {inputs.cik}); "
        f"Financial features as of {inputs.data_as_of_date}; "
        f"Diluted shares: {diluted_shares:,.0f}"
    )
    assumption_sources = (
        f"Rf: {wacc_inputs.rf_source} ({wacc_inputs.risk_free_rate * 100:.2f}%); "
        f"Beta: {wacc_inputs.beta_source} ({wacc_inputs.beta:.2f}); "
        f"ERP: {wacc_inputs.erp_source} ({wacc_inputs.equity_risk_premium * 100:.2f}%); "
        f"Rd: {wacc_inputs.cost_of_debt_source} ({wacc_inputs.cost_of_debt * 100:.2f}%)"
    )

    return DCFResult(
        valuation_id=val_id,
        ticker=inputs.ticker,
        company_id=inputs.company_id,
        cik=inputs.cik,
        sector=inputs.sector,
        valuation_date=inputs.valuation_date,
        data_as_of_date=inputs.data_as_of_date,
        valuation_mode=valuation_mode,
        scenario=assumptions.scenario_name,
        model_version=model_version,
        current_share_price=round(inputs.current_share_price, 2) if inputs.current_share_price else None,
        pv_explicit_fcff=round(pv_explicit_fcff, 2),
        terminal_value=round(terminal_value, 2),
        pv_terminal_value=round(pv_tv, 2),
        enterprise_value=round(enterprise_value, 2),
        total_debt=round(total_debt, 2),
        cash=round(cash, 2),
        net_debt=round(net_debt, 2),
        equity_value=round(equity_value, 2),
        diluted_shares=round(diluted_shares, 2),
        fair_value_per_share=round(fair_value_per_share, 2),
        upside_downside=round(upside_downside, 4) if upside_downside is not None else None,
        wacc=round(wacc, 6),
        terminal_growth=round(assumptions.terminal_growth_rate, 4),
        cost_of_equity=round(wacc_output.cost_of_equity, 6),
        cost_of_debt=round(wacc_output.cost_of_debt, 6),
        risk_free_rate=round(wacc_inputs.risk_free_rate, 6),
        beta=round(wacc_inputs.beta, 4),
        erp=round(wacc_inputs.equity_risk_premium, 6),
        revenue_growth_summary=growth_str,
        ebit_margin_summary=margin_str,
        forecast_periods=forecast_periods,
        data_sources=data_sources,
        assumption_sources=assumption_sources,
        calculation_status="SUCCESS",
        status_reason=None,
        lineage=inputs.lineage,
    )
