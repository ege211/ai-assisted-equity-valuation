"""
Valuation Assumptions and Parameter Registry.

Provides explicit, versioned market and macroeconomic inputs:
- Point-in-time Risk-Free Rates (10-Year US Treasury Par Yields)
- 5-Year Blume-Adjusted Market Betas
- Equity Risk Premium (ERP)
- Cost of Debt benchmarks
- Scenario parameter generation (Base, Bull, Bear)
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.valuation.models import ForecastAssumptions, ValuationInputs

logger = logging.getLogger(__name__)

# Historical 10-Year US Treasury Par Yields (home.treasury.gov / Fed H.15)
TREASURY_10Y_HISTORICAL = {
    2014: 0.0217,  # 2014-12-31: 2.17%
    2015: 0.0227,  # 2015-12-31: 2.27%
    2016: 0.0245,  # 2016-12-31: 2.45%
    2017: 0.0241,  # 2017-12-31: 2.41%
    2018: 0.0269,  # 2018-12-31: 2.69%
    2019: 0.0192,  # 2019-12-31: 1.92%
    2020: 0.0093,  # 2020-12-31: 0.93%
    2021: 0.0152,  # 2021-12-31: 1.52%
    2022: 0.0388,  # 2022-12-31: 3.88%
    2023: 0.0388,  # 2023-12-31: 3.88%
    2024: 0.0457,  # 2024-12-31: 4.57%
}
DEFAULT_LIVE_TREASURY_10Y = 0.0425  # 4.25% baseline

# 5-Year Monthly Blume-Adjusted Betas vs S&P 500
COMPANY_BETAS: Dict[str, float] = {
    # Information Technology
    "AAPL": 1.10, "MSFT": 1.05, "NVDA": 1.65, "INTC": 1.15, "CSCO": 0.90,
    # Health Care
    "JNJ": 0.60, "PFE": 0.65, "ABT": 0.75, "MRK": 0.55, "TMO": 0.85,
    # Consumer Staples
    "WMT": 0.55, "PG": 0.45, "KO": 0.60, "PEP": 0.55, "COST": 0.80,
    # Consumer Discretionary
    "AMZN": 1.25, "HD": 1.00, "NKE": 1.05, "MCD": 0.65, "LOW": 1.05,
    # Industrials
    "CAT": 1.15, "MMM": 0.95, "HON": 1.00, "UNP": 0.90, "LMT": 0.65,
    # Energy
    "XOM": 0.95, "CVX": 0.90, "COP": 1.15, "SLB": 1.25, "EOG": 1.20,
}

SECTOR_MEDIAN_BETAS: Dict[str, float] = {
    "Information Technology": 1.10,
    "Health Care": 0.65,
    "Consumer Staples": 0.55,
    "Consumer Discretionary": 1.05,
    "Industrials": 0.95,
    "Energy": 1.15,
}

# Approximate Year-End Closing Share Prices (2024-12-31)
COMPANY_SHARE_PRICES_2024: Dict[str, float] = {
    "AAPL": 250.40, "MSFT": 421.50, "NVDA": 134.30, "INTC": 20.06, "CSCO": 58.75,
    "JNJ": 144.60, "PFE": 25.80, "ABT": 113.80, "MRK": 98.70, "TMO": 512.40,
    "WMT": 89.90, "PG": 168.50, "KO": 62.40, "PEP": 153.20, "COST": 918.00,
    "AMZN": 219.40, "HD": 398.20, "NKE": 74.80, "MCD": 291.50, "LOW": 268.00,
    "CAT": 395.00, "MMM": 129.50, "HON": 214.20, "UNP": 232.00, "LMT": 458.00,
    "XOM": 108.50, "CVX": 149.20, "COP": 104.80, "SLB": 39.80, "EOG": 124.50,
}

DEFAULT_ERP = 0.050  # 5.0% US Equity Risk Premium
DEFAULT_CREDIT_SPREAD = 0.0150  # 150 bps investment grade credit spread


def get_share_price(ticker: str, date_str: Optional[str] = None) -> Optional[float]:
    """Retrieve benchmark closing share price for ticker."""
    return COMPANY_SHARE_PRICES_2024.get(ticker.upper())


def get_risk_free_rate(date_str: str) -> Tuple[float, str]:
    """
    Retrieve point-in-time risk-free rate corresponding to valuation date.
    Returns (rate, source_citation).
    """
    try:
        year = int(str(date_str)[:4])
        if year in TREASURY_10Y_HISTORICAL:
            rate = TREASURY_10Y_HISTORICAL[year]
            return rate, f"US Treasury 10Y Par Yield ({year}-12-31, home.treasury.gov)"
        elif year < 2014:
            rate = TREASURY_10Y_HISTORICAL[2014]
            return rate, f"US Treasury 10Y Benchmark (2014 floor, home.treasury.gov)"
        else:
            rate = TREASURY_10Y_HISTORICAL[2024]
            return rate, f"US Treasury 10Y Benchmark (2024, home.treasury.gov)"
    except Exception:
        return DEFAULT_LIVE_TREASURY_10Y, "US Treasury 10Y Benchmark Default (home.treasury.gov)"


def get_beta(ticker: str, sector: Optional[str] = None) -> Tuple[float, str]:
    """
    Retrieve 5-year Blume-adjusted equity beta.
    Returns (beta, source_citation).
    """
    if ticker in COMPANY_BETAS:
        return COMPANY_BETAS[ticker], f"Company 5Y Blume-Adjusted Beta ({ticker} vs S&P 500)"
    if sector and sector in SECTOR_MEDIAN_BETAS:
        return SECTOR_MEDIAN_BETAS[sector], f"Sector Median Beta ({sector} Peer Group)"
    return 1.0, "Market Average Beta Fallback (1.00)"


def get_equity_risk_premium() -> Tuple[float, str]:
    """Retrieve standard Equity Risk Premium."""
    return DEFAULT_ERP, "US Equity Risk Premium Benchmark (Damodaran 5.0%)"


def calculate_cost_of_debt(
    interest_expense: Optional[float],
    total_debt: Optional[float],
    risk_free_rate: float,
) -> Tuple[float, str]:
    """
    Calculate pre-tax cost of debt using accounting proxy or credit spread fallback.
    """
    if interest_expense is not None and total_debt is not None and total_debt > 0 and interest_expense > 0:
        empirical_rate = interest_expense / total_debt
        # Validate that empirical rate is within reasonable bounds (1.5% to 15%)
        if 0.015 <= empirical_rate <= 0.15:
            return empirical_rate, f"Historical Accounting Proxy (Interest Expense / Total Debt: {empirical_rate * 100:.2f}%)"

    # Spread Fallback: Rf + 150 bps
    fallback_rate = risk_free_rate + DEFAULT_CREDIT_SPREAD
    return fallback_rate, f"Investment Grade Credit Spread Fallback (Rf + {DEFAULT_CREDIT_SPREAD * 100:.1f}%)"


def build_forecast_assumptions(
    scenario: str,
    inputs: ValuationInputs,
) -> ForecastAssumptions:
    """
    Build explicit 5-year forecast assumptions for BASE, BULL, or BEAR scenarios.
    """
    rev = inputs.ltm_revenue
    ebit = inputs.ltm_ebit
    cogs = 0.0  # not strictly required for NOPAT
    da = inputs.ltm_da
    capex = inputs.ltm_capex
    owc = inputs.operating_working_capital

    # Base operating ratios from historical LTM
    base_ebit_margin = (ebit / rev) if (rev > 0 and ebit is not None) else 0.15
    base_da_ratio = (da / rev) if (rev > 0 and da is not None) else 0.04
    base_capex_ratio = (capex / rev) if (rev > 0 and capex is not None) else 0.05
    base_owc_ratio = (owc / rev) if (rev > 0 and owc is not None) else 0.10

    # Clean bounds
    base_ebit_margin = max(0.02, min(0.60, base_ebit_margin))
    base_da_ratio = max(0.01, min(0.20, base_da_ratio))
    base_capex_ratio = max(0.01, min(0.25, base_capex_ratio))
    base_owc_ratio = max(-0.10, min(0.40, base_owc_ratio))

    tax_rate = inputs.effective_tax_rate if (0.10 <= inputs.effective_tax_rate <= 0.35) else 0.21

    scenario_upper = scenario.upper()

    if scenario_upper == "BULL":
        growth_rates = [0.09, 0.08, 0.07, 0.06, 0.05]
        target_margin = base_ebit_margin + 0.020  # +200 bps
        margins = [
            base_ebit_margin + 0.005,
            base_ebit_margin + 0.010,
            base_ebit_margin + 0.015,
            target_margin,
            target_margin,
        ]
        terminal_growth = 0.0275  # 2.75%
    elif scenario_upper == "BEAR":
        growth_rates = [0.03, 0.025, 0.02, 0.02, 0.015]
        target_margin = max(0.02, base_ebit_margin - 0.030)  # -300 bps
        margins = [
            base_ebit_margin - 0.010,
            base_ebit_margin - 0.020,
            target_margin,
            target_margin,
            target_margin,
        ]
        terminal_growth = 0.0200  # 2.00%
    else:  # BASE
        growth_rates = [0.06, 0.055, 0.05, 0.045, 0.04]
        margins = [base_ebit_margin] * 5
        terminal_growth = 0.0250  # 2.50%

    return ForecastAssumptions(
        scenario_name=scenario_upper,
        forecast_years=5,
        revenue_growth_rates=growth_rates,
        ebit_margins=margins,
        tax_rate=tax_rate,
        da_ratio_of_rev=base_da_ratio,
        capex_ratio_of_rev=base_capex_ratio,
        nwc_ratio_of_rev=base_owc_ratio,
        terminal_growth_rate=terminal_growth,
        discount_convention="mid_year",
    )
