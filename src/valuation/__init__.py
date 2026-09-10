"""
Deterministic Equity Valuation Engine Package.

Provides production-grade, audited intrinsic DCF and relative multiples valuation.
"""
from src.valuation.assumptions import (
    build_forecast_assumptions,
    calculate_cost_of_debt,
    get_beta,
    get_equity_risk_premium,
    get_risk_free_rate,
    get_share_price,
)
from src.valuation.dcf import calculate_dcf
from src.valuation.engine import ValuationEngine
from src.valuation.forecast import generate_forecast
from src.valuation.models import (
    DCFResult,
    ForecastAssumptions,
    ForecastPeriod,
    IncompleteValuationInputsError,
    InvalidTerminalGrowthError,
    RelativeValuationResult,
    ScenarioOutputs,
    SensitivityGrid,
    ValuationError,
    ValuationInputs,
    WACCInputs,
    WACCOutput,
)
from src.valuation.relative_valuation import calculate_relative_valuation
from src.valuation.scenarios import run_scenario_analysis
from src.valuation.sensitivity import (
    generate_growth_margin_sensitivity,
    generate_wacc_terminal_growth_sensitivity,
)
from src.valuation.terminal_value import calculate_terminal_value
from src.valuation.wacc import calculate_cost_of_equity, calculate_wacc

__all__ = [
    "ValuationEngine",
    "calculate_dcf",
    "generate_forecast",
    "calculate_terminal_value",
    "calculate_wacc",
    "calculate_cost_of_equity",
    "run_scenario_analysis",
    "generate_wacc_terminal_growth_sensitivity",
    "generate_growth_margin_sensitivity",
    "calculate_relative_valuation",
    "build_forecast_assumptions",
    "get_risk_free_rate",
    "get_beta",
    "get_equity_risk_premium",
    "get_share_price",
    "calculate_cost_of_debt",
    "ValuationInputs",
    "ForecastAssumptions",
    "ForecastPeriod",
    "WACCInputs",
    "WACCOutput",
    "DCFResult",
    "ScenarioOutputs",
    "SensitivityGrid",
    "RelativeValuationResult",
    "ValuationError",
    "InvalidTerminalGrowthError",
    "IncompleteValuationInputsError",
]
