"""
Weighted Average Cost of Capital (WACC) & CAPM Module.

Calculates:
- Cost of Equity via Capital Asset Pricing Model (CAPM): Re = Rf + Beta * ERP
- After-Tax Cost of Debt: Rd * (1 - t)
- Capital Structure Weightings (We, Wd)
- Blended WACC = We * Re + Wd * Rd * (1 - t)
"""
from typing import Optional
from src.valuation.models import WACCInputs, WACCOutput


def calculate_cost_of_equity(
    risk_free_rate: float,
    beta: float,
    equity_risk_premium: float,
) -> float:
    """
    Calculate Cost of Equity using standard CAPM formula:
    Re = Rf + Beta * ERP
    """
    return risk_free_rate + (beta * equity_risk_premium)


def calculate_wacc(inputs: WACCInputs) -> WACCOutput:
    """
    Compute blended WACC and capital structure components.

    Parameters
    ----------
    inputs : WACCInputs
        Cost of equity/debt parameters, tax rate, and capital amounts.

    Returns
    -------
    WACCOutput
        Detailed cost of capital results and weights.
    """
    re = calculate_cost_of_equity(
        risk_free_rate=inputs.risk_free_rate,
        beta=inputs.beta,
        equity_risk_premium=inputs.equity_risk_premium,
    )

    rd = inputs.cost_of_debt
    tax_rate = max(0.0, min(0.40, inputs.tax_rate))
    after_tax_rd = rd * (1.0 - tax_rate)

    # Determine Capital Weights
    if inputs.target_debt_to_capital is not None and 0.0 <= inputs.target_debt_to_capital <= 1.0:
        wd = inputs.target_debt_to_capital
        we = 1.0 - wd
    elif inputs.market_equity_value is not None and inputs.market_equity_value > 0:
        total_debt = max(0.0, inputs.total_debt)
        total_cap = inputs.market_equity_value + total_debt
        if total_cap > 0:
            we = inputs.market_equity_value / total_cap
            wd = total_debt / total_cap
        else:
            we = 1.0
            wd = 0.0
    else:
        # Default capital structure benchmark
        if inputs.total_debt <= 0:
            we = 1.0
            wd = 0.0
        else:
            # Typical investment-grade capital structure benchmark: 80% Equity / 20% Debt
            we = 0.80
            wd = 0.20

    wacc = (we * re) + (wd * after_tax_rd)

    return WACCOutput(
        cost_of_equity=round(re, 6),
        cost_of_debt=round(rd, 6),
        after_tax_cost_of_debt=round(after_tax_rd, 6),
        weight_equity=round(we, 4),
        weight_debt=round(wd, 4),
        wacc=round(wacc, 6),
    )
