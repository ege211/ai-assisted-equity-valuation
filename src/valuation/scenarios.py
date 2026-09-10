"""
Scenario Analysis Module.

Evaluates Base, Bull, and Bear valuation projections under structured,
versioned macro/operating assumptions.
"""
from src.valuation.assumptions import build_forecast_assumptions
from src.valuation.dcf import calculate_dcf
from src.valuation.models import (
    DCFResult,
    ScenarioOutputs,
    ValuationInputs,
    WACCInputs,
)


def run_scenario_analysis(
    inputs: ValuationInputs,
    wacc_inputs: WACCInputs,
    valuation_mode: str = "HISTORICAL",
    model_version: str = "v1.0-deterministic",
) -> ScenarioOutputs:
    """
    Execute Base, Bull, and Bear scenario valuations.

    Parameters
    ----------
    inputs : ValuationInputs
        Historical inputs and capital structure.
    wacc_inputs : WACCInputs
        Cost of capital inputs.
    valuation_mode : str
        'HISTORICAL' or 'LIVE'.
    model_version : str
        Version identifier.

    Returns
    -------
    ScenarioOutputs
        Dataclass containing base, bull, and bear DCFResult objects.
    """
    # 1. Base Scenario
    base_assumptions = build_forecast_assumptions("BASE", inputs)
    base_res = calculate_dcf(
        inputs=inputs,
        assumptions=base_assumptions,
        wacc_inputs=wacc_inputs,
        valuation_mode=valuation_mode,
        model_version=model_version,
    )

    # 2. Bull Scenario
    bull_assumptions = build_forecast_assumptions("BULL", inputs)
    bull_res = calculate_dcf(
        inputs=inputs,
        assumptions=bull_assumptions,
        wacc_inputs=wacc_inputs,
        valuation_mode=valuation_mode,
        model_version=model_version,
    )

    # 3. Bear Scenario
    bear_assumptions = build_forecast_assumptions("BEAR", inputs)
    bear_res = calculate_dcf(
        inputs=inputs,
        assumptions=bear_assumptions,
        wacc_inputs=wacc_inputs,
        valuation_mode=valuation_mode,
        model_version=model_version,
    )

    return ScenarioOutputs(
        base=base_res,
        bull=bull_res,
        bear=bear_res,
    )
