"""
Data Models and Strongly-Typed Contracts for the Deterministic Valuation Engine.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ValuationError(Exception):
    """Base exception for valuation failures."""
    pass


class InvalidTerminalGrowthError(ValuationError):
    """Raised when terminal growth rate >= WACC, violating Gordon Growth model."""
    pass


class IncompleteValuationInputsError(ValuationError):
    """Raised when required valuation inputs (e.g. shares, cash, EBIT) are missing."""
    pass


@dataclass
class ValuationInputs:
    """Historical baseline features and capital structure inputs."""
    company_id: str
    ticker: str
    cik: str
    sector: str
    valuation_date: str
    data_as_of_date: str
    ltm_revenue: float
    ltm_ebit: float
    ltm_nopat: float
    ltm_cfo: float
    ltm_capex: float
    ltm_da: float
    ltm_fcf: float
    effective_tax_rate: float
    working_capital: float
    operating_working_capital: float
    cash: float
    total_debt: float
    net_debt: float
    diluted_shares: float
    current_share_price: Optional[float] = None
    lineage: str = ""


@dataclass
class ForecastAssumptions:
    """Explicit parameters governing the 5-year discrete forecast."""
    scenario_name: str
    forecast_years: int
    revenue_growth_rates: List[float]
    ebit_margins: List[float]
    tax_rate: float
    da_ratio_of_rev: float
    capex_ratio_of_rev: float
    nwc_ratio_of_rev: float
    terminal_growth_rate: float
    discount_convention: str = "mid_year"  # 'mid_year' or 'end_of_year'


@dataclass
class ForecastPeriod:
    """Projections for a single forecast year."""
    forecast_year_index: int
    fiscal_year: int
    revenue: float
    revenue_growth: float
    ebit_margin: float
    ebit: float
    tax_rate: float
    tax_expense: float
    nopat: float
    da: float
    capex: float
    nwc: float
    delta_nwc: float
    fcff: float
    discount_factor: float
    pv_fcff: float


@dataclass
class WACCInputs:
    """Inputs required for CAPM Cost of Equity and Blended WACC."""
    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    cost_of_debt: float
    tax_rate: float
    market_equity_value: Optional[float] = None
    total_debt: float = 0.0
    target_debt_to_capital: Optional[float] = None
    rf_source: str = "US Treasury 10Y Par Yield (home.treasury.gov)"
    beta_source: str = "5Y Monthly Blume-Adjusted Beta vs S&P 500"
    erp_source: str = "US Equity Risk Premium Benchmark"
    cost_of_debt_source: str = "Interest Expense / Average Debt"


@dataclass
class WACCOutput:
    """Computed cost of capital and weighting parameters."""
    cost_of_equity: float
    cost_of_debt: float
    after_tax_cost_of_debt: float
    weight_equity: float
    weight_debt: float
    wacc: float


@dataclass
class DCFResult:
    """Comprehensive intrinsic discounted cash flow valuation output."""
    valuation_id: str
    ticker: str
    company_id: str
    cik: str
    sector: str
    valuation_date: str
    data_as_of_date: str
    valuation_mode: str
    scenario: str
    model_version: str
    current_share_price: Optional[float]
    pv_explicit_fcff: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    total_debt: float
    cash: float
    net_debt: float
    equity_value: float
    diluted_shares: float
    fair_value_per_share: float
    upside_downside: Optional[float]
    wacc: float
    terminal_growth: float
    cost_of_equity: float
    cost_of_debt: float
    risk_free_rate: float
    beta: float
    erp: float
    revenue_growth_summary: str
    ebit_margin_summary: str
    forecast_periods: List[ForecastPeriod]
    data_sources: str
    assumption_sources: str
    calculation_status: str
    status_reason: Optional[str] = None
    lineage: str = ""


@dataclass
class ScenarioOutputs:
    """Encapsulates Base, Bull, and Bear valuation results."""
    base: DCFResult
    bull: DCFResult
    bear: DCFResult


@dataclass
class SensitivityGrid:
    """Two-dimensional sensitivity matrix across parameter axes."""
    parameter_1_name: str
    parameter_1_values: List[float]
    parameter_2_name: str
    parameter_2_values: List[float]
    matrix: List[List[Optional[float]]]  # row: p1, col: p2 -> fair_value_per_share
    is_monotonic_p1: bool
    is_monotonic_p2: bool


@dataclass
class RelativeValuationResult:
    """Relative multiples and peer benchmarking result."""
    relative_id: str
    company_id: str
    ticker: str
    cik: str
    sector: str
    valuation_date: str
    as_of_date: str
    peer_group: str
    multiple_name: str
    company_multiple: Optional[float]
    peer_median_multiple: Optional[float]
    implied_equity_value: Optional[float]
    implied_fair_value_per_share: Optional[float]
    benchmark_source: str
    status: str
