"""
Terminal Value Calculation Module.

Implements the Gordon Growth (Perpetual Growth) Model:
    TV_n = (FCFF_n * (1 + g)) / (WACC - g)
    PV(TV) = TV_n / (1 + WACC)^n

Enforces strict mathematical invariants:
- WACC must be strictly greater than terminal growth rate g.
- Raises InvalidTerminalGrowthError if WACC <= g.
"""
from typing import Tuple
from src.valuation.models import InvalidTerminalGrowthError


def calculate_terminal_value(
    final_year_fcff: float,
    wacc: float,
    terminal_growth: float,
    forecast_years: int = 5,
    discount_convention: str = "mid_year",
) -> Tuple[float, float]:
    """
    Calculate undiscounted Terminal Value and Present Value of Terminal Value.

    Parameters
    ----------
    final_year_fcff : float
        Free cash flow to firm in the final forecast year (Year N).
    wacc : float
        Weighted Average Cost of Capital (decimal).
    terminal_growth : float
        Long-term perpetual growth rate g (decimal).
    forecast_years : int
        Number of discrete forecast years N (default 5).
    discount_convention : str
        'mid_year' or 'end_of_year'.

    Returns
    -------
    Tuple[float, float]
        (terminal_value, pv_terminal_value)

    Raises
    ------
    InvalidTerminalGrowthError
        If wacc <= terminal_growth or denominator <= 0.
    """
    spread = wacc - terminal_growth
    if spread <= 0.0001:  # Enforce WACC strictly greater than g
        raise InvalidTerminalGrowthError(
            f"Terminal growth rate ({terminal_growth:.4f}) must be strictly less than WACC ({wacc:.4f}). "
            f"Spread ({spread:.4f}) is non-positive, violating the Gordon Growth Model invariant."
        )

    # Next year normalized terminal cash flow
    fcff_terminal = final_year_fcff * (1.0 + terminal_growth)

    # Undiscounted Terminal Value at Year N
    terminal_value = fcff_terminal / spread

    # Discount to present (at Year N)
    # Under standard convention, cash flows after Year N are capitalized at Year N
    if discount_convention == "mid_year":
        # Corporate finance standard: discount factor at Year N = 1 / (1 + wacc)^N
        discount_power = float(forecast_years)
    else:
        discount_power = float(forecast_years)

    if (1.0 + wacc) > 0:
        pv_tv = terminal_value / ((1.0 + wacc) ** discount_power)
    else:
        pv_tv = terminal_value

    return round(terminal_value, 2), round(pv_tv, 2)
