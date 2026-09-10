"""
Sensitivity Analysis Module.

Computes multi-dimensional sensitivity grids:
1. WACC vs. Terminal Growth Rate (g)
2. Revenue Growth Shift vs. Operating Margin Shift

Validates mathematical monotonicity invariants:
- Fair Value must strictly decrease as WACC increases (holding g constant).
- Fair Value must strictly increase as g increases (holding WACC constant).
"""
import copy
from typing import List, Optional

from src.valuation.assumptions import build_forecast_assumptions
from src.valuation.dcf import calculate_dcf
from src.valuation.models import (
    ForecastAssumptions,
    InvalidTerminalGrowthError,
    SensitivityGrid,
    ValuationInputs,
    WACCInputs,
)
from src.valuation.wacc import calculate_wacc


def generate_wacc_terminal_growth_sensitivity(
    inputs: ValuationInputs,
    assumptions: ForecastAssumptions,
    wacc_inputs: WACCInputs,
    wacc_steps: Optional[List[float]] = None,
    g_steps: Optional[List[float]] = None,
) -> SensitivityGrid:
    """
    Generate 2D grid of Fair Value Per Share across WACC and terminal growth (g).

    Parameters
    ----------
    inputs : ValuationInputs
        Baseline financials and capital structure.
    assumptions : ForecastAssumptions
        Scenario parameters.
    wacc_inputs : WACCInputs
        Cost of capital inputs.
    wacc_steps : Optional[List[float]]
        WACC values to evaluate. If None, derives +/- 100 bps around baseline.
    g_steps : Optional[List[float]]
        Terminal growth rates to evaluate. If None, [0.015, 0.020, 0.025, 0.030, 0.035].

    Returns
    -------
    SensitivityGrid
        Matrix and monotonicity validation results.
    """
    base_wacc_out = calculate_wacc(wacc_inputs)
    center_wacc = base_wacc_out.wacc

    if wacc_steps is None:
        wacc_steps = [
            round(center_wacc - 0.010, 4),
            round(center_wacc - 0.005, 4),
            round(center_wacc, 4),
            round(center_wacc + 0.005, 4),
            round(center_wacc + 0.010, 4),
        ]
        # Filter to strictly positive WACCs
        wacc_steps = [w for w in wacc_steps if w > 0.01]

    if g_steps is None:
        g_steps = [0.015, 0.020, 0.025, 0.030, 0.035]

    matrix: List[List[Optional[float]]] = []

    for w in wacc_steps:
        row: List[Optional[float]] = []
        for g in g_steps:
            if g >= w:
                row.append(None)
                continue
            
            # Create isolated assumptions with specific g
            iter_assumptions = copy.deepcopy(assumptions)
            iter_assumptions.terminal_growth_rate = g

            # Calculate DCF with override WACC by modifying wacc_inputs
            # We construct a custom wacc input where rf is adjusted to match exactly `w`
            # Or pass wacc directly. To keep calculate_dcf clean, we set target parameters:
            iter_wacc_inputs = copy.deepcopy(wacc_inputs)
            # Adjust risk_free_rate so that wacc output equals w exactly
            # Re = Rf + Beta * ERP, WACC = We*Re + Wd*Rd*(1-t)
            # Let's adjust target Rf:
            we = 1.0 - (iter_wacc_inputs.target_debt_to_capital or 0.20)
            wd = 1.0 - we
            after_tax_rd = iter_wacc_inputs.cost_of_debt * (1.0 - iter_wacc_inputs.tax_rate)
            # w = We * (Rf + Beta*ERP) + Wd * after_tax_rd
            # w - Wd*after_tax_rd = We * (Rf + Beta*ERP)
            # (w - Wd*after_tax_rd) / We - Beta*ERP = Rf
            required_rf = (w - (wd * after_tax_rd)) / we - (iter_wacc_inputs.beta * iter_wacc_inputs.equity_risk_premium)
            iter_wacc_inputs.risk_free_rate = required_rf

            try:
                dcf_out = calculate_dcf(
                    inputs=inputs,
                    assumptions=iter_assumptions,
                    wacc_inputs=iter_wacc_inputs,
                )
                row.append(dcf_out.fair_value_per_share)
            except (InvalidTerminalGrowthError, Exception):
                row.append(None)
        matrix.append(row)

    # Monotonicity checks
    # P1 (WACC) should be monotonically decreasing down each column (as WACC increases, FV decreases)
    monotonic_p1 = True
    num_rows = len(matrix)
    num_cols = len(g_steps)

    for col in range(num_cols):
        prev_val = None
        for row in range(num_rows):
            val = matrix[row][col]
            if val is not None:
                if prev_val is not None and val > prev_val + 0.01:  # allow 1 cent precision tolerance
                    monotonic_p1 = False
                    break
                prev_val = val

    # P2 (g) should be monotonically increasing across each row (as g increases, FV increases)
    monotonic_p2 = True
    for row in range(num_rows):
        prev_val = None
        for col in range(num_cols):
            val = matrix[row][col]
            if val is not None:
                if prev_val is not None and val < prev_val - 0.01:
                    monotonic_p2 = False
                    break
                prev_val = val

    return SensitivityGrid(
        parameter_1_name="WACC",
        parameter_1_values=wacc_steps,
        parameter_2_name="Terminal Growth Rate (g)",
        parameter_2_values=g_steps,
        matrix=matrix,
        is_monotonic_p1=monotonic_p1,
        is_monotonic_p2=monotonic_p2,
    )


def generate_growth_margin_sensitivity(
    inputs: ValuationInputs,
    assumptions: ForecastAssumptions,
    wacc_inputs: WACCInputs,
    growth_shifts: Optional[List[float]] = None,
    margin_shifts: Optional[List[float]] = None,
) -> SensitivityGrid:
    """
    Generate 2D grid of Fair Value Per Share across Revenue Growth shift and Margin shift.
    """
    if growth_shifts is None:
        growth_shifts = [-0.02, -0.01, 0.0, 0.01, 0.02]  # -200 bps to +200 bps
    if margin_shifts is None:
        margin_shifts = [-0.02, -0.01, 0.0, 0.01, 0.02]  # -200 bps to +200 bps

    matrix: List[List[Optional[float]]] = []

    for g_shift in growth_shifts:
        row: List[Optional[float]] = []
        for m_shift in margin_shifts:
            iter_assumptions = copy.deepcopy(assumptions)
            iter_assumptions.revenue_growth_rates = [
                max(-0.20, r + g_shift) for r in assumptions.revenue_growth_rates
            ]
            iter_assumptions.ebit_margins = [
                max(0.01, m + m_shift) for m in assumptions.ebit_margins
            ]

            try:
                dcf_out = calculate_dcf(
                    inputs=inputs,
                    assumptions=iter_assumptions,
                    wacc_inputs=wacc_inputs,
                )
                row.append(dcf_out.fair_value_per_share)
            except Exception:
                row.append(None)
        matrix.append(row)

    # Monotonicity: FV increases as growth increases (P1) and as margin increases (P2)
    monotonic_p1 = True
    num_rows = len(matrix)
    num_cols = len(margin_shifts)
    for col in range(num_cols):
        prev_val = None
        for row in range(num_rows):
            val = matrix[row][col]
            if val is not None:
                if prev_val is not None and val < prev_val - 0.01:
                    monotonic_p1 = False
                    break
                prev_val = val

    monotonic_p2 = True
    for row in range(num_rows):
        prev_val = None
        for col in range(num_cols):
            val = matrix[row][col]
            if val is not None:
                if prev_val is not None and val < prev_val - 0.01:
                    monotonic_p2 = False
                    break
                prev_val = val

    return SensitivityGrid(
        parameter_1_name="Revenue Growth Shift",
        parameter_1_values=growth_shifts,
        parameter_2_name="EBIT Margin Shift",
        parameter_2_values=margin_shifts,
        matrix=matrix,
        is_monotonic_p1=monotonic_p1,
        is_monotonic_p2=monotonic_p2,
    )
