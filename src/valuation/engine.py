"""
Valuation Engine Orchestrator.

Integrates:
- Historical point-in-time financial feature layer (Phase 3)
- Point-in-time share counts from SEC XBRL facts
- Macroeconomic and capital structure assumptions registry
- Deterministic 5-year discrete financial forecasting
- Gordon Growth terminal value and mid-year discounting
- Base, Bull, and Bear scenario execution
- Multi-dimensional sensitivity grids
- Relative multiples benchmarking
- DuckDB persistence for valuation audits
"""
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.valuation.assumptions import (
    calculate_cost_of_debt,
    get_beta,
    get_equity_risk_premium,
    get_risk_free_rate,
    get_share_price,
    build_forecast_assumptions,
)
from src.valuation.dcf import calculate_dcf
from src.valuation.models import (
    DCFResult,
    ForecastAssumptions,
    IncompleteValuationInputsError,
    RelativeValuationResult,
    ScenarioOutputs,
    SensitivityGrid,
    ValuationInputs,
    WACCInputs,
)
from src.valuation.relative_valuation import calculate_relative_valuation
from src.valuation.scenarios import run_scenario_analysis
from src.valuation.sensitivity import (
    generate_growth_margin_sensitivity,
    generate_wacc_terminal_growth_sensitivity,
)
from src.valuation.wacc import calculate_wacc

logger = logging.getLogger(__name__)


class ValuationEngine:
    """Production Deterministic Valuation Engine."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)

    def prepare_valuation_inputs(
        self,
        ticker: str,
        valuation_date: str = "2024-12-31",
        valuation_mode: str = "HISTORICAL",
    ) -> ValuationInputs:
        """
        Assemble strictly point-in-time financial statement inputs and share count.
        """
        ticker = ticker.upper()

        with self.db.get_connection() as conn:
            # 1. Company Metadata
            comp = conn.execute(
                "SELECT company_id, ticker, cik, sector FROM companies WHERE ticker = ?",
                [ticker],
            ).fetchone()
            if not comp:
                raise IncompleteValuationInputsError(f"Ticker {ticker} not found in companies table.")
            company_id, _, cik, sector = comp

            # 2. Latest LTM Financials on or before valuation_date
            # Enforce PIT: period_end_date <= valuation_date and filing acceptance_datetime <= valuation_date
            ltm_query = """
            SELECT
                statement_id, period_end_date::VARCHAR, acceptance_datetime::VARCHAR, constituent_quarters,
                constituent_accessions, revenue, ebit, cfo, capex, da, fcf, cash,
                total_debt, tax_expense, pretax_income, interest_expense
            FROM ltm_financials
            WHERE ticker = ? AND period_end_date <= ?::DATE
            """
            params: List[Any] = [ticker, valuation_date]
            if valuation_mode.upper() == "HISTORICAL":
                ltm_query += " AND acceptance_datetime::VARCHAR <= (? || ' 23:59:59')"
                params.append(valuation_date)
            ltm_query += " ORDER BY period_end_date DESC, acceptance_datetime DESC LIMIT 1"

            ltm_row = conn.execute(ltm_query, params).fetchone()
            if not ltm_row or ltm_row[5] is None or ltm_row[5] <= 0:
                raise IncompleteValuationInputsError(
                    f"No valid LTM financials available for {ticker} as of {valuation_date}."
                )

            (
                stmt_id, period_end_date, acceptance_dt, const_qtrs,
                const_accessions, rev, ebit, cfo, capex, da, fcf, cash,
                total_debt, tax_expense, pretax_income, interest_expense
            ) = ltm_row

            # 3. Features for this exact period
            feats = conn.execute(
                """
                SELECT feature_name, feature_value
                FROM financial_features
                WHERE ticker = ? AND period_end_date = ?::DATE
                """,
                [ticker, period_end_date],
            ).fetchall()
            feat_map = {f[0]: f[1] for f in feats}

            # NOPAT & Tax Rate
            nopat = feat_map.get("nopat")
            norm_tax_rate = feat_map.get("normalized_tax_rate")
            if norm_tax_rate is None or norm_tax_rate <= 0 or norm_tax_rate >= 0.50:
                if pretax_income and pretax_income > 0 and tax_expense and tax_expense > 0:
                    norm_tax_rate = tax_expense / pretax_income
                    norm_tax_rate = max(0.10, min(0.35, norm_tax_rate))
                else:
                    norm_tax_rate = 0.21  # US statutory benchmark

            if nopat is None:
                nopat = (ebit or 0.0) * (1.0 - norm_tax_rate)

            # Working Capital
            owc = feat_map.get("operating_working_capital")
            wc = feat_map.get("working_capital")
            if owc is None:
                owc = wc if wc is not None else 0.0

            # Net Debt
            net_debt = feat_map.get("net_debt")
            if net_debt is None:
                net_debt = (total_debt or 0.0) - (cash or 0.0)

            # 4. Point-in-time Diluted Shares
            # Priority: Diluted shares -> Basic shares -> Common stock
            shares_query = """
            SELECT val, concept, filing_date::VARCHAR, end_date::VARCHAR
            FROM raw_xbrl_facts
            WHERE cik = ?
              AND concept IN (
                'WeightedAverageNumberOfDilutedSharesOutstanding',
                'WeightedAverageNumberOfSharesOutstandingBasic',
                'CommonStockSharesOutstanding'
              )
              AND filing_date <= ?::DATE
              AND end_date <= ?::DATE
            ORDER BY
              CASE concept
                WHEN 'WeightedAverageNumberOfDilutedSharesOutstanding' THEN 1
                WHEN 'WeightedAverageNumberOfSharesOutstandingBasic' THEN 2
                ELSE 3
              END,
              end_date DESC,
              filing_date DESC
            LIMIT 1
            """
            shares_row = conn.execute(shares_query, [cik, valuation_date, valuation_date]).fetchone()
            if not shares_row or shares_row[0] is None or shares_row[0] <= 0:
                raise IncompleteValuationInputsError(
                    f"No point-in-time share count found in SEC facts for CIK {cik} ({ticker}) as of {valuation_date}."
                )
            diluted_shares = float(shares_row[0])
            # Account for filings reporting shares in millions (e.g. MCD reporting 722.7 instead of 722,700,000)
            if diluted_shares < 100_000:
                diluted_shares *= 1_000_000.0

            # 5. Share price
            share_price = get_share_price(ticker, valuation_date)

            # Lineage
            lineage = (
                f"LTM Stmt: {stmt_id} | PeriodEnd: {period_end_date} | "
                f"Acceptance: {acceptance_dt} | SharesConcept: {shares_row[1]} ({shares_row[3]})"
            )

            return ValuationInputs(
                company_id=company_id,
                ticker=ticker,
                cik=cik,
                sector=sector,
                valuation_date=str(valuation_date),
                data_as_of_date=str(acceptance_dt),
                ltm_revenue=float(rev),
                ltm_ebit=float(ebit) if ebit is not None else 0.0,
                ltm_nopat=float(nopat),
                ltm_cfo=float(cfo) if cfo is not None else 0.0,
                ltm_capex=float(capex) if capex is not None else 0.0,
                ltm_da=float(da) if da is not None else 0.0,
                ltm_fcf=float(fcf) if fcf is not None else 0.0,
                effective_tax_rate=float(norm_tax_rate),
                working_capital=float(wc) if wc is not None else 0.0,
                operating_working_capital=float(owc),
                cash=float(cash) if cash is not None else 0.0,
                total_debt=float(total_debt) if total_debt is not None else 0.0,
                net_debt=float(net_debt),
                diluted_shares=diluted_shares,
                current_share_price=share_price,
                lineage=lineage,
            )

    def prepare_wacc_inputs(self, inputs: ValuationInputs) -> WACCInputs:
        """
        Assemble WACC and CAPM parameters for given valuation inputs.
        """
        rf, rf_src = get_risk_free_rate(inputs.valuation_date)
        beta, beta_src = get_beta(inputs.ticker, inputs.sector)
        erp, erp_src = get_equity_risk_premium()

        # Cost of Debt
        # Use total debt and historical interest expense if available
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT interest_expense, total_debt FROM ltm_financials WHERE ticker = ? ORDER BY period_end_date DESC LIMIT 1",
                [inputs.ticker],
            ).fetchone()
            interest_expense = row[0] if row else None
            tot_debt = row[1] if row else inputs.total_debt

        cost_of_debt, cod_src = calculate_cost_of_debt(
            interest_expense=interest_expense,
            total_debt=tot_debt,
            risk_free_rate=rf,
        )

        mkt_equity = (inputs.current_share_price * inputs.diluted_shares) if inputs.current_share_price else None

        return WACCInputs(
            risk_free_rate=rf,
            beta=beta,
            equity_risk_premium=erp,
            cost_of_debt=cost_of_debt,
            tax_rate=inputs.effective_tax_rate,
            market_equity_value=mkt_equity,
            total_debt=inputs.total_debt,
            rf_source=rf_src,
            beta_source=beta_src,
            erp_source=erp_src,
            cost_of_debt_source=cod_src,
        )

    def value_company(
        self,
        ticker: str,
        valuation_date: str = "2024-12-31",
        valuation_mode: str = "HISTORICAL",
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute complete deterministic valuation workflow for a single company.
        """
        inputs = self.prepare_valuation_inputs(
            ticker=ticker,
            valuation_date=valuation_date,
            valuation_mode=valuation_mode,
        )
        wacc_inputs = self.prepare_wacc_inputs(inputs)

        # 1. Scenarios (Base, Bull, Bear)
        scenarios = run_scenario_analysis(
            inputs=inputs,
            wacc_inputs=wacc_inputs,
            valuation_mode=valuation_mode,
        )

        # 2. Sensitivities on Base Scenario
        base_assumptions = build_forecast_assumptions("BASE", inputs)
        wacc_g_sens = generate_wacc_terminal_growth_sensitivity(
            inputs=inputs,
            assumptions=base_assumptions,
            wacc_inputs=wacc_inputs,
        )
        growth_margin_sens = generate_growth_margin_sensitivity(
            inputs=inputs,
            assumptions=base_assumptions,
            wacc_inputs=wacc_inputs,
        )

        # 3. Relative Valuation Multiples
        rel_results = calculate_relative_valuation(inputs)

        # 4. Database Persistence
        if persist:
            self._persist_valuation(
                inputs=inputs,
                wacc_inputs=wacc_inputs,
                scenarios=scenarios,
                sensitivities=[wacc_g_sens, growth_margin_sens],
                relative_results=rel_results,
            )

        return {
            "inputs": inputs,
            "wacc_inputs": wacc_inputs,
            "scenarios": scenarios,
            "sensitivities": {
                "wacc_terminal_growth": wacc_g_sens,
                "growth_margin": growth_margin_sens,
            },
            "relative_valuation": rel_results,
        }

    def _persist_valuation(
        self,
        inputs: ValuationInputs,
        wacc_inputs: WACCInputs,
        scenarios: ScenarioOutputs,
        sensitivities: List[SensitivityGrid],
        relative_results: List[RelativeValuationResult],
    ) -> None:
        """Persist valuation records into DuckDB."""
        # 1. Assumptions and Results for each scenario
        assumptions_records: List[Dict[str, Any]] = []
        forecast_records: List[Dict[str, Any]] = []
        results_records: List[Dict[str, Any]] = []

        for scen_name, dcf_res in [
            ("BASE", scenarios.base),
            ("BULL", scenarios.bull),
            ("BEAR", scenarios.bear),
        ]:
            assump = build_forecast_assumptions(scen_name, inputs)
            w_out = calculate_wacc(wacc_inputs)
            assump_id = f"assump_{inputs.ticker}_{scen_name.lower()}_{inputs.valuation_date.replace('-', '')}"

            assumptions_records.append({
                "assumption_id": assump_id,
                "company_id": inputs.company_id,
                "ticker": inputs.ticker,
                "valuation_date": inputs.valuation_date,
                "scenario": scen_name,
                "model_version": dcf_res.model_version,
                "forecast_years": assump.forecast_years,
                "risk_free_rate": wacc_inputs.risk_free_rate,
                "beta": wacc_inputs.beta,
                "equity_risk_premium": wacc_inputs.equity_risk_premium,
                "cost_of_equity": w_out.cost_of_equity,
                "cost_of_debt": w_out.cost_of_debt,
                "effective_tax_rate": inputs.effective_tax_rate,
                "weight_equity": w_out.weight_equity,
                "weight_debt": w_out.weight_debt,
                "wacc": w_out.wacc,
                "terminal_growth_rate": assump.terminal_growth_rate,
                "revenue_growth_rates": json.dumps(assump.revenue_growth_rates),
                "ebit_margins": json.dumps(assump.ebit_margins),
                "tax_rate_assumptions": str(assump.tax_rate),
                "da_ratio_assumptions": assump.da_ratio_of_rev,
                "capex_ratio_assumptions": assump.capex_ratio_of_rev,
                "nwc_ratio_assumptions": assump.nwc_ratio_of_rev,
                "data_sources": dcf_res.data_sources,
                "assumption_sources": dcf_res.assumption_sources,
            })

            # Forecast Periods
            for p in dcf_res.forecast_periods:
                forecast_records.append({
                    "forecast_id": f"fc_{dcf_res.valuation_id}_{p.forecast_year_index}",
                    "valuation_id": dcf_res.valuation_id,
                    "ticker": inputs.ticker,
                    "fiscal_year": p.fiscal_year,
                    "forecast_year_index": p.forecast_year_index,
                    "revenue": p.revenue,
                    "revenue_growth": p.revenue_growth,
                    "ebit_margin": p.ebit_margin,
                    "ebit": p.ebit,
                    "tax_rate": p.tax_rate,
                    "tax_expense": p.tax_expense,
                    "nopat": p.nopat,
                    "da": p.da,
                    "capex": p.capex,
                    "nwc": p.nwc,
                    "delta_nwc": p.delta_nwc,
                    "fcff": p.fcff,
                    "discount_factor": p.discount_factor,
                    "pv_fcff": p.pv_fcff,
                })

            # DCF Result
            results_records.append({
                "valuation_id": dcf_res.valuation_id,
                "company_id": inputs.company_id,
                "ticker": inputs.ticker,
                "cik": inputs.cik,
                "sector": inputs.sector,
                "valuation_date": inputs.valuation_date,
                "data_as_of_date": inputs.data_as_of_date,
                "valuation_mode": dcf_res.valuation_mode,
                "scenario": scen_name,
                "model_version": dcf_res.model_version,
                "current_share_price": dcf_res.current_share_price,
                "pv_explicit_fcff": dcf_res.pv_explicit_fcff,
                "terminal_value": dcf_res.terminal_value,
                "pv_terminal_value": dcf_res.pv_terminal_value,
                "enterprise_value": dcf_res.enterprise_value,
                "total_debt": dcf_res.total_debt,
                "cash": dcf_res.cash,
                "net_debt": dcf_res.net_debt,
                "equity_value": dcf_res.equity_value,
                "diluted_shares": dcf_res.diluted_shares,
                "fair_value_per_share": dcf_res.fair_value_per_share,
                "upside_downside": dcf_res.upside_downside,
                "wacc": dcf_res.wacc,
                "terminal_growth": dcf_res.terminal_growth,
                "cost_of_equity": dcf_res.cost_of_equity,
                "cost_of_debt": dcf_res.cost_of_debt,
                "risk_free_rate": dcf_res.risk_free_rate,
                "beta": dcf_res.beta,
                "erp": dcf_res.erp,
                "revenue_growth_summary": dcf_res.revenue_growth_summary,
                "ebit_margin_summary": dcf_res.ebit_margin_summary,
                "data_sources": dcf_res.data_sources,
                "assumption_sources": dcf_res.assumption_sources,
                "calculation_status": dcf_res.calculation_status,
                "status_reason": dcf_res.status_reason,
                "lineage": dcf_res.lineage,
            })

        self.db.insert_valuation_assumptions(assumptions_records)
        self.db.insert_forecast_periods(forecast_records)
        self.db.insert_valuation_results(results_records)

        # 2. Sensitivities
        base_val_id = scenarios.base.valuation_id
        sens_records: List[Dict[str, Any]] = []
        for s in sensitivities:
            p1_name = s.parameter_1_name
            p2_name = s.parameter_2_name
            for i, p1_val in enumerate(s.parameter_1_values):
                for j, p2_val in enumerate(s.parameter_2_values):
                    fv = s.matrix[i][j]
                    sens_records.append({
                        "sensitivity_id": f"sens_{base_val_id}_{p1_name[:4]}_{i}_{p2_name[:4]}_{j}",
                        "valuation_id": base_val_id,
                        "ticker": inputs.ticker,
                        "parameter_1_name": p1_name,
                        "parameter_1_value": float(p1_val),
                        "parameter_2_name": p2_name,
                        "parameter_2_value": float(p2_val),
                        "enterprise_value": None,
                        "equity_value": None,
                        "fair_value_per_share": float(fv) if fv is not None else None,
                    })
        self.db.insert_valuation_sensitivities(sens_records)

        # 3. Relative Valuation
        rel_records: List[Dict[str, Any]] = []
        for r in relative_results:
            rel_records.append({
                "relative_id": r.relative_id,
                "company_id": r.company_id,
                "ticker": r.ticker,
                "cik": r.cik,
                "sector": r.sector,
                "valuation_date": r.valuation_date,
                "as_of_date": r.as_of_date,
                "peer_group": r.peer_group,
                "multiple_name": r.multiple_name,
                "company_multiple": r.company_multiple,
                "peer_median_multiple": r.peer_median_multiple,
                "implied_equity_value": r.implied_equity_value,
                "implied_fair_value_per_share": r.implied_fair_value_per_share,
                "benchmark_source": r.benchmark_source,
                "status": r.status,
            })
        self.db.insert_relative_valuation_results(rel_records)

    def value_universe(
        self,
        valuation_date: str = "2024-12-31",
        valuation_mode: str = "HISTORICAL",
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute deterministic valuation across the entire locked universe.
        """
        with self.db.get_connection() as conn:
            companies = conn.execute("SELECT ticker, sector FROM companies ORDER BY ticker").fetchall()

        results: Dict[str, Any] = {}
        successful: List[str] = []
        incomplete: List[str] = []
        failed: List[str] = []

        for ticker, sector in companies:
            try:
                val = self.value_company(
                    ticker=ticker,
                    valuation_date=valuation_date,
                    valuation_mode=valuation_mode,
                    persist=persist,
                )
                results[ticker] = val
                successful.append(ticker)
                logger.info("Valued %s successfully: Base FV/share = $%.2f", ticker, val["scenarios"].base.fair_value_per_share)
            except IncompleteValuationInputsError as e:
                logger.warning("Incomplete inputs for %s: %s", ticker, str(e))
                incomplete.append(ticker)
                results[ticker] = {"status": "INCOMPLETE", "reason": str(e)}
            except Exception as e:
                logger.error("Failed valuation for %s: %s", ticker, str(e))
                failed.append(ticker)
                results[ticker] = {"status": "ERROR", "reason": str(e)}

        return {
            "total_companies": len(companies),
            "successful_count": len(successful),
            "incomplete_count": len(incomplete),
            "failed_count": len(failed),
            "successful_tickers": successful,
            "incomplete_tickers": incomplete,
            "failed_tickers": failed,
            "results": results,
        }
