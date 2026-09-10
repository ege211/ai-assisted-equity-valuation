"""
Comprehensive Unit Test Suite for Phase 4 Deterministic Valuation Engine.

Covers criteria A through Z:
A: FCFF calculation: NOPAT + D&A - CapEx - Delta NWC
B: Multi-year discrete revenue projections compound correctly
C: EBIT margins applied accurately across horizon
D: Effective tax rate applied to compute NOPAT
E: D&A, CapEx, OWC ratios of revenue projected accurately
F: Delta OWC matches period-over-period differences
G: Mid-year discount factors computed accurately
H: CAPM Cost of Equity: Re = Rf + Beta * ERP
I: Pre-tax Cost of Debt empirical proxy and spread fallback
J: Capital structure weights and blended WACC formula
K: Gordon Growth Terminal Value calculation
L: Strict Gordon Growth invariant: WACC <= g raises InvalidTerminalGrowthError
M: Terminal Value discounting to present value
N: Enterprise Value = PV(FCFF) + PV(TV)
O: Equity Value Bridge: EV - Debt + Cash
P: Fair Value Per Share = Equity Value / Diluted Shares
Q: Market upside / downside calculation
R: Scenario analysis: Bull > Base > Bear for profitable firm
S: 2D Sensitivity Grid (WACC x g) dimensions and cell calculation
T: 2D Sensitivity Grid monotonicity validation
U: 2D Sensitivity Grid (Growth shift x Margin shift)
V: Relative valuation multiples and implied equity value
W: Missing or non-positive diluted shares raises IncompleteValuationInputsError
X: Negative EBIT and distressed cash flows handled gracefully
Y: Point-in-time isolation: no look-ahead bias
Z: DuckDB persistence and querying of valuation results
"""
import copy
import os
import unittest

from src.data.db import DatabaseManager
from src.valuation.assumptions import (
    build_forecast_assumptions,
    calculate_cost_of_debt,
    get_beta,
    get_equity_risk_premium,
    get_risk_free_rate,
)
from src.valuation.dcf import calculate_dcf
from src.valuation.engine import ValuationEngine
from src.valuation.forecast import generate_forecast
from src.valuation.models import (
    ForecastAssumptions,
    IncompleteValuationInputsError,
    InvalidTerminalGrowthError,
    ValuationInputs,
    WACCInputs,
)
from src.valuation.relative_valuation import calculate_relative_valuation
from src.valuation.scenarios import run_scenario_analysis
from src.valuation.sensitivity import (
    generate_growth_margin_sensitivity,
    generate_wacc_terminal_growth_sensitivity,
)
from src.valuation.terminal_value import calculate_terminal_value
from src.valuation.wacc import calculate_cost_of_equity, calculate_wacc


class TestPhase4ValuationEngine(unittest.TestCase):
    """Rigorous unit test suite verifying deterministic equity valuation functionality."""

    def setUp(self) -> None:
        """Create baseline mock valuation inputs and standard parameters."""
        self.mock_inputs = ValuationInputs(
            company_id="comp_test_100",
            ticker="TEST",
            cik="0001000000",
            sector="Information Technology",
            valuation_date="2024-12-31",
            data_as_of_date="2024-10-31 16:00:00+00",
            ltm_revenue=100_000.0,
            ltm_ebit=20_000.0,
            ltm_nopat=15_800.0,
            ltm_cfo=22_000.0,
            ltm_capex=5_000.0,
            ltm_da=4_000.0,
            ltm_fcf=17_000.0,
            effective_tax_rate=0.21,
            working_capital=10_000.0,
            operating_working_capital=10_000.0,
            cash=15_000.0,
            total_debt=25_000.0,
            net_debt=10_000.0,
            diluted_shares=1_000.0,
            current_share_price=150.0,
            lineage="Unit Test Mock Lineage",
        )

        self.mock_assumptions = ForecastAssumptions(
            scenario_name="BASE",
            forecast_years=5,
            revenue_growth_rates=[0.08, 0.07, 0.06, 0.05, 0.04],
            ebit_margins=[0.20, 0.20, 0.20, 0.20, 0.20],
            tax_rate=0.21,
            da_ratio_of_rev=0.04,
            capex_ratio_of_rev=0.05,
            nwc_ratio_of_rev=0.10,
            terminal_growth_rate=0.025,
            discount_convention="mid_year",
        )

        self.mock_wacc_inputs = WACCInputs(
            risk_free_rate=0.04,
            beta=1.0,
            equity_risk_premium=0.05,
            cost_of_debt=0.05,
            tax_rate=0.21,
            market_equity_value=150_000.0,
            total_debt=25_000.0,
            target_debt_to_capital=0.20,
        )

    # --- Test A: FCFF Calculation ---
    def test_a_fcff_calculation(self) -> None:
        """FCFF = NOPAT + D&A - CapEx - Delta NWC."""
        periods = generate_forecast(self.mock_inputs, self.mock_assumptions, wacc=0.08)
        p1 = periods[0]
        # Year 1 rev: 100,000 * 1.08 = 108,000
        # EBIT: 108,000 * 0.20 = 21,600
        # NOPAT: 21,600 * (1 - 0.21) = 17,064
        # DA: 108,000 * 0.04 = 4,320
        # CapEx: 108,000 * 0.05 = 5,400
        # NWC: 108,000 * 0.10 = 10,800; delta NWC = 10,800 - 10,000 = 800
        # Expected FCFF = 17,064 + 4,320 - 5,400 - 800 = 15,184
        self.assertAlmostEqual(p1.revenue, 108_000.0, places=1)
        self.assertAlmostEqual(p1.ebit, 21_600.0, places=1)
        self.assertAlmostEqual(p1.nopat, 17_064.0, places=1)
        self.assertAlmostEqual(p1.da, 4_320.0, places=1)
        self.assertAlmostEqual(p1.capex, 5_400.0, places=1)
        self.assertAlmostEqual(p1.delta_nwc, 800.0, places=1)
        self.assertAlmostEqual(p1.fcff, 15_184.0, places=1)

    # --- Test B: Revenue Compound Growth ---
    def test_b_revenue_compound_growth(self) -> None:
        """5-year revenues compound correctly by specified rates."""
        periods = generate_forecast(self.mock_inputs, self.mock_assumptions, wacc=0.08)
        r0 = 100_000.0
        for i, g in enumerate(self.mock_assumptions.revenue_growth_rates):
            expected_rev = r0 * (1.0 + g)
            self.assertAlmostEqual(periods[i].revenue, expected_rev, places=1)
            r0 = expected_rev

    # --- Test C: EBIT Margins ---
    def test_c_ebit_margins(self) -> None:
        """EBIT equals revenue times specified margin for every year."""
        assump = copy.deepcopy(self.mock_assumptions)
        assump.ebit_margins = [0.15, 0.16, 0.17, 0.18, 0.19]
        periods = generate_forecast(self.mock_inputs, assump, wacc=0.08)
        for i, p in enumerate(periods):
            self.assertAlmostEqual(p.ebit, p.revenue * assump.ebit_margins[i], places=1)

    # --- Test D: NOPAT Tax Rate ---
    def test_d_nopat_tax_rate(self) -> None:
        """NOPAT equals EBIT * (1 - tax_rate)."""
        periods = generate_forecast(self.mock_inputs, self.mock_assumptions, wacc=0.08)
        for p in periods:
            self.assertAlmostEqual(p.nopat, p.ebit * (1.0 - p.tax_rate), places=1)

    # --- Test E: Ratios of Revenue ---
    def test_e_ratios_of_revenue(self) -> None:
        """D&A, CapEx, and NWC scale proportionally with revenue."""
        periods = generate_forecast(self.mock_inputs, self.mock_assumptions, wacc=0.08)
        for p in periods:
            self.assertAlmostEqual(p.da, p.revenue * 0.04, places=1)
            self.assertAlmostEqual(p.capex, p.revenue * 0.05, places=1)
            self.assertAlmostEqual(p.nwc, p.revenue * 0.10, places=1)

    # --- Test F: Delta NWC Continuity ---
    def test_f_delta_nwc_continuity(self) -> None:
        """Delta NWC accurately reflects period-to-period change in NWC."""
        periods = generate_forecast(self.mock_inputs, self.mock_assumptions, wacc=0.08)
        for i in range(1, len(periods)):
            self.assertAlmostEqual(periods[i].delta_nwc, periods[i].nwc - periods[i - 1].nwc, places=1)

    # --- Test G: Mid-Year Discounting ---
    def test_g_mid_year_discounting(self) -> None:
        """Mid-year discount factor equals (1 + WACC)^-(t - 0.5)."""
        wacc = 0.08
        periods = generate_forecast(self.mock_inputs, self.mock_assumptions, wacc=wacc)
        for t, p in enumerate(periods, start=1):
            expected_df = 1.0 / ((1.0 + wacc) ** (t - 0.5))
            self.assertAlmostEqual(p.discount_factor, expected_df, places=4)
            self.assertAlmostEqual(p.pv_fcff, p.fcff * p.discount_factor, places=1)

    # --- Test H: CAPM Cost of Equity ---
    def test_h_capm_cost_of_equity(self) -> None:
        """Re = Rf + Beta * ERP."""
        rf = 0.04
        beta = 1.2
        erp = 0.05
        re = calculate_cost_of_equity(rf, beta, erp)
        self.assertAlmostEqual(re, 0.04 + (1.2 * 0.05), places=5)  # 0.10 (10.0%)

    # --- Test I: Cost of Debt Calculation ---
    def test_i_cost_of_debt(self) -> None:
        """Empirical proxy interest/debt used when valid, fallback otherwise."""
        # Valid empirical rate: 500 / 10,000 = 5%
        cod, src = calculate_cost_of_debt(interest_expense=500.0, total_debt=10_000.0, risk_free_rate=0.04)
        self.assertAlmostEqual(cod, 0.05, places=4)
        self.assertIn("Historical Accounting Proxy", src)

        # Missing debt -> spread fallback (Rf + 1.5%)
        cod_fallback, src_fb = calculate_cost_of_debt(interest_expense=0.0, total_debt=0.0, risk_free_rate=0.04)
        self.assertAlmostEqual(cod_fallback, 0.055, places=4)
        self.assertIn("Credit Spread Fallback", src_fb)

    # --- Test J: Capital Weights and Blended WACC ---
    def test_j_capital_weights_and_wacc(self) -> None:
        """WACC = We * Re + Wd * Rd * (1 - t)."""
        w_out = calculate_wacc(self.mock_wacc_inputs)
        # target Wd = 0.20, We = 0.80
        # Re = 0.04 + 1.0 * 0.05 = 0.09
        # After tax Rd = 0.05 * (1 - 0.21) = 0.0395
        # WACC = 0.80 * 0.09 + 0.20 * 0.0395 = 0.072 + 0.0079 = 0.0799
        self.assertAlmostEqual(w_out.weight_equity, 0.80, places=4)
        self.assertAlmostEqual(w_out.weight_debt, 0.20, places=4)
        self.assertAlmostEqual(w_out.wacc, 0.0799, places=4)

    # --- Test K: Gordon Growth Terminal Value ---
    def test_k_gordon_growth_terminal_value(self) -> None:
        """TV = FCFF_N * (1 + g) / (WACC - g)."""
        final_fcff = 20_000.0
        wacc = 0.08
        g = 0.02
        tv, pv_tv = calculate_terminal_value(final_fcff, wacc, g, forecast_years=5)
        expected_tv = (20_000.0 * 1.02) / (0.08 - 0.02)  # 20,400 / 0.06 = 340,000
        self.assertAlmostEqual(tv, expected_tv, places=1)
        expected_pv = expected_tv / (1.08 ** 5)
        self.assertAlmostEqual(pv_tv, expected_pv, places=1)

    # --- Test L: Strict WACC > g Invariant ---
    def test_l_strict_wacc_greater_than_g(self) -> None:
        """Gordon Growth raises InvalidTerminalGrowthError when WACC <= g."""
        with self.assertRaises(InvalidTerminalGrowthError):
            calculate_terminal_value(final_year_fcff=10_000.0, wacc=0.03, terminal_growth=0.03)

        with self.assertRaises(InvalidTerminalGrowthError):
            calculate_terminal_value(final_year_fcff=10_000.0, wacc=0.02, terminal_growth=0.03)

    # --- Test M: Terminal Value Discounting ---
    def test_m_terminal_value_discounting(self) -> None:
        """PV(TV) strictly decreases as WACC increases."""
        tv1, pv1 = calculate_terminal_value(10_000.0, wacc=0.07, terminal_growth=0.02, forecast_years=5)
        tv2, pv2 = calculate_terminal_value(10_000.0, wacc=0.09, terminal_growth=0.02, forecast_years=5)
        self.assertGreater(pv1, pv2)

    # --- Test N: Enterprise Value Formula ---
    def test_n_enterprise_value_formula(self) -> None:
        """Enterprise Value = PV(FCFF) + PV(TV)."""
        dcf = calculate_dcf(self.mock_inputs, self.mock_assumptions, self.mock_wacc_inputs)
        self.assertAlmostEqual(dcf.enterprise_value, dcf.pv_explicit_fcff + dcf.pv_terminal_value, places=1)

    # --- Test O: Equity Value Bridge ---
    def test_o_equity_value_bridge(self) -> None:
        """Equity Value = EV - Total Debt + Cash."""
        dcf = calculate_dcf(self.mock_inputs, self.mock_assumptions, self.mock_wacc_inputs)
        expected_eq = dcf.enterprise_value - self.mock_inputs.total_debt + self.mock_inputs.cash
        self.assertAlmostEqual(dcf.equity_value, expected_eq, places=1)
        self.assertAlmostEqual(dcf.net_debt, self.mock_inputs.total_debt - self.mock_inputs.cash, places=1)

    # --- Test P: Fair Value Per Share ---
    def test_p_fair_value_per_share(self) -> None:
        """Fair Value Per Share = Equity Value / Diluted Shares."""
        dcf = calculate_dcf(self.mock_inputs, self.mock_assumptions, self.mock_wacc_inputs)
        expected_fv = dcf.equity_value / self.mock_inputs.diluted_shares
        self.assertAlmostEqual(dcf.fair_value_per_share, expected_fv, places=2)

    # --- Test Q: Upside / Downside Calculation ---
    def test_q_upside_downside_calculation(self) -> None:
        """Upside/Downside = (FV - Market Price) / Market Price."""
        dcf = calculate_dcf(self.mock_inputs, self.mock_assumptions, self.mock_wacc_inputs)
        price = self.mock_inputs.current_share_price
        expected_up = (dcf.fair_value_per_share - price) / price
        self.assertAlmostEqual(dcf.upside_downside, expected_up, places=3)

    # --- Test R: Scenario Analysis Hierarchy ---
    def test_r_scenario_analysis_hierarchy(self) -> None:
        """Bull scenario FV > Base scenario FV > Bear scenario FV for normal profitable firm."""
        scenarios = run_scenario_analysis(self.mock_inputs, self.mock_wacc_inputs)
        self.assertGreater(scenarios.bull.fair_value_per_share, scenarios.base.fair_value_per_share)
        self.assertGreater(scenarios.base.fair_value_per_share, scenarios.bear.fair_value_per_share)

    # --- Test S: 2D Sensitivity Grid Dimensions ---
    def test_s_sensitivity_grid_dimensions(self) -> None:
        """WACC x g sensitivity matrix contains expected 5x5 grid."""
        grid = generate_wacc_terminal_growth_sensitivity(
            self.mock_inputs,
            self.mock_assumptions,
            self.mock_wacc_inputs,
        )
        self.assertEqual(len(grid.matrix), 5)
        self.assertEqual(len(grid.matrix[0]), 5)

    # --- Test T: 2D Sensitivity Grid Monotonicity ---
    def test_t_sensitivity_grid_monotonicity(self) -> None:
        """WACC monotonicity is True and g monotonicity is True for normal firm."""
        grid = generate_wacc_terminal_growth_sensitivity(
            self.mock_inputs,
            self.mock_assumptions,
            self.mock_wacc_inputs,
        )
        self.assertTrue(grid.is_monotonic_p1)
        self.assertTrue(grid.is_monotonic_p2)

    # --- Test U: Growth and Margin Shift Grid ---
    def test_u_growth_margin_sensitivity_grid(self) -> None:
        """Growth and margin shifts both exhibit positive monotonicity."""
        grid = generate_growth_margin_sensitivity(
            self.mock_inputs,
            self.mock_assumptions,
            self.mock_wacc_inputs,
        )
        self.assertTrue(grid.is_monotonic_p1)
        self.assertTrue(grid.is_monotonic_p2)

    # --- Test V: Relative Valuation Multiples ---
    def test_v_relative_valuation_multiples(self) -> None:
        """Relative valuation outputs EV/EBITDA, EV/EBIT, P/S, P/E, FCF Yield."""
        results = calculate_relative_valuation(self.mock_inputs)
        mult_names = [r.multiple_name for r in results]
        self.assertIn("EV/EBITDA", mult_names)
        self.assertIn("EV/EBIT", mult_names)
        self.assertIn("P/S", mult_names)
        self.assertIn("P/E", mult_names)
        self.assertIn("FCF_YIELD", mult_names)
        for r in results:
            self.assertEqual(r.status, "CALCULATED")
            self.assertIsNotNone(r.implied_fair_value_per_share)

    # --- Test W: Missing Diluted Shares Rejection ---
    def test_w_missing_shares_rejection(self) -> None:
        """Missing or zero diluted shares raises IncompleteValuationInputsError."""
        bad_inputs = copy.deepcopy(self.mock_inputs)
        bad_inputs.diluted_shares = 0.0
        with self.assertRaises(IncompleteValuationInputsError):
            calculate_dcf(bad_inputs, self.mock_assumptions, self.mock_wacc_inputs)

    # --- Test X: Distressed / Negative Cash Flow Handling ---
    def test_x_distressed_negative_cash_flows(self) -> None:
        """Negative EBIT / high debt produces negative equity value without runtime crash."""
        distressed = copy.deepcopy(self.mock_inputs)
        distressed.ltm_ebit = -20_000.0
        distressed.ltm_nopat = -15_800.0
        distressed.total_debt = 200_000.0
        distressed.cash = 1_000.0

        distressed_assump = copy.deepcopy(self.mock_assumptions)
        distressed_assump.ebit_margins = [-0.10] * 5

        dcf = calculate_dcf(distressed, distressed_assump, self.mock_wacc_inputs)
        self.assertLess(dcf.equity_value, 0.0)
        self.assertLess(dcf.fair_value_per_share, 0.0)
        self.assertEqual(dcf.calculation_status, "SUCCESS")

    # --- Test Y: Point-in-Time Date Isolation ---
    def test_y_pit_date_isolation(self) -> None:
        """Engine respects valuation_date boundary and does not include future data."""
        engine = ValuationEngine()
        # Valuing as of 2020-12-31 should pick up 2020 or earlier financials
        inputs_2020 = engine.prepare_valuation_inputs("AAPL", valuation_date="2020-12-31")
        self.assertLessEqual(inputs_2020.valuation_date, "2020-12-31")
        # Ensure risk-free rate for 2020 reflects 2020 yield (0.93%)
        rf_2020, _ = get_risk_free_rate("2020-12-31")
        self.assertAlmostEqual(rf_2020, 0.0093, places=4)

    # --- Test Z: DuckDB Persistence and Query Verification ---
    def test_z_database_persistence_and_query(self) -> None:
        """Valuation results persist into DuckDB and are queryable."""
        engine = ValuationEngine()
        res = engine.value_company("AAPL", valuation_date="2024-12-31", persist=True)
        # Query results
        results = engine.db.query_valuation_results(ticker="AAPL", scenario="BASE")
        self.assertGreater(len(results), 0)
        aapl_res = results[0]
        self.assertEqual(aapl_res["ticker"], "AAPL")
        self.assertEqual(aapl_res["scenario"], "BASE")
        self.assertAlmostEqual(aapl_res["fair_value_per_share"], res["scenarios"].base.fair_value_per_share, places=2)


if __name__ == "__main__":
    unittest.main()
