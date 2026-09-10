"""
Relative Valuation and Multiples Benchmarking Module.

Computes peer multiples:
- Price-to-Earnings (P/E)
- Enterprise Value to EBITDA (EV/EBITDA)
- Enterprise Value to EBIT (EV/EBIT)
- Price-to-Sales (P/S)
- Free Cash Flow Yield (FCF Yield)

Compares company multiples against sector median benchmarks and computes
implied equity values and per-share fair values.
"""
from typing import Dict, List, Optional
import uuid

from src.valuation.models import RelativeValuationResult, ValuationInputs

# Sector Median Benchmark Multiples (Reference: Damodaran Sector Multiples / S&P 500 Sector Benchmarks)
SECTOR_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "Information Technology": {
        "P/E": 28.5,
        "EV/EBITDA": 18.0,
        "EV/EBIT": 22.0,
        "P/S": 6.5,
        "FCF_YIELD": 0.035,
    },
    "Health Care": {
        "P/E": 20.0,
        "EV/EBITDA": 13.5,
        "EV/EBIT": 16.0,
        "P/S": 4.0,
        "FCF_YIELD": 0.045,
    },
    "Consumer Staples": {
        "P/E": 22.0,
        "EV/EBITDA": 14.0,
        "EV/EBIT": 17.5,
        "P/S": 2.2,
        "FCF_YIELD": 0.040,
    },
    "Consumer Discretionary": {
        "P/E": 24.0,
        "EV/EBITDA": 15.0,
        "EV/EBIT": 18.0,
        "P/S": 2.5,
        "FCF_YIELD": 0.040,
    },
    "Industrials": {
        "P/E": 19.5,
        "EV/EBITDA": 12.0,
        "EV/EBIT": 15.0,
        "P/S": 1.8,
        "FCF_YIELD": 0.050,
    },
    "Energy": {
        "P/E": 11.5,
        "EV/EBITDA": 6.5,
        "EV/EBIT": 8.5,
        "P/S": 1.2,
        "FCF_YIELD": 0.075,
    },
}

DEFAULT_BENCHMARK: Dict[str, float] = {
    "P/E": 20.0,
    "EV/EBITDA": 12.5,
    "EV/EBIT": 15.0,
    "P/S": 2.5,
    "FCF_YIELD": 0.045,
}


def calculate_relative_valuation(
    inputs: ValuationInputs,
    sector_benchmarks: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[RelativeValuationResult]:
    """
    Compute relative valuation multiples and implied fair values.

    Parameters
    ----------
    inputs : ValuationInputs
        Financial features, capital structure, and diluted shares.
    sector_benchmarks : Optional[Dict[str, Dict[str, float]]]
        Override sector benchmark multiples.

    Returns
    -------
    List[RelativeValuationResult]
        Calculated results for standard multiple categories.
    """
    benchmarks_dict = sector_benchmarks or SECTOR_BENCHMARKS
    benchmarks = benchmarks_dict.get(inputs.sector, DEFAULT_BENCHMARK)

    results: List[RelativeValuationResult] = []

    # Financial bases
    shares = inputs.diluted_shares
    price = inputs.current_share_price
    mkt_cap = (price * shares) if (price is not None and shares > 0) else None
    cash = inputs.cash or 0.0
    debt = inputs.total_debt or 0.0
    net_debt = debt - cash
    ev_market = (mkt_cap + net_debt) if mkt_cap is not None else None

    rev = inputs.ltm_revenue
    ebit = inputs.ltm_ebit
    da = inputs.ltm_da or 0.0
    ebitda = (ebit + da) if ebit is not None else None
    nopat = inputs.ltm_nopat
    fcf = inputs.ltm_fcf

    peer_group_name = f"{inputs.sector} Sector Benchmark"
    source_name = "Damodaran / S&P Sector Multiples Benchmark"

    # 1. EV / EBITDA
    target_ebitda_mult = benchmarks.get("EV/EBITDA")
    if ebitda is not None and ebitda > 0:
        company_ev_ebitda = (ev_market / ebitda) if ev_market is not None else None
        implied_ev = target_ebitda_mult * ebitda if target_ebitda_mult else None
        implied_eq = (implied_ev - debt + cash) if implied_ev is not None else None
        implied_fv = (implied_eq / shares) if (implied_eq is not None and shares > 0) else None
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_evebitda_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="EV/EBITDA",
                company_multiple=round(company_ev_ebitda, 2) if company_ev_ebitda else None,
                peer_median_multiple=target_ebitda_mult,
                implied_equity_value=round(implied_eq, 2) if implied_eq else None,
                implied_fair_value_per_share=round(implied_fv, 2) if implied_fv else None,
                benchmark_source=source_name,
                status="CALCULATED",
            )
        )
    else:
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_evebitda_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="EV/EBITDA",
                company_multiple=None,
                peer_median_multiple=target_ebitda_mult,
                implied_equity_value=None,
                implied_fair_value_per_share=None,
                benchmark_source=source_name,
                status="NOT_MEANINGFUL",
            )
        )

    # 2. EV / EBIT
    target_ebit_mult = benchmarks.get("EV/EBIT")
    if ebit is not None and ebit > 0:
        company_ev_ebit = (ev_market / ebit) if ev_market is not None else None
        implied_ev = target_ebit_mult * ebit if target_ebit_mult else None
        implied_eq = (implied_ev - debt + cash) if implied_ev is not None else None
        implied_fv = (implied_eq / shares) if (implied_eq is not None and shares > 0) else None
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_evebit_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="EV/EBIT",
                company_multiple=round(company_ev_ebit, 2) if company_ev_ebit else None,
                peer_median_multiple=target_ebit_mult,
                implied_equity_value=round(implied_eq, 2) if implied_eq else None,
                implied_fair_value_per_share=round(implied_fv, 2) if implied_fv else None,
                benchmark_source=source_name,
                status="CALCULATED",
            )
        )
    else:
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_evebit_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="EV/EBIT",
                company_multiple=None,
                peer_median_multiple=target_ebit_mult,
                implied_equity_value=None,
                implied_fair_value_per_share=None,
                benchmark_source=source_name,
                status="NOT_MEANINGFUL",
            )
        )

    # 3. P / S (Price-to-Sales)
    target_ps_mult = benchmarks.get("P/S")
    if rev is not None and rev > 0:
        company_ps = (mkt_cap / rev) if mkt_cap is not None else None
        implied_eq = target_ps_mult * rev if target_ps_mult else None
        implied_fv = (implied_eq / shares) if (implied_eq is not None and shares > 0) else None
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_ps_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="P/S",
                company_multiple=round(company_ps, 2) if company_ps else None,
                peer_median_multiple=target_ps_mult,
                implied_equity_value=round(implied_eq, 2) if implied_eq else None,
                implied_fair_value_per_share=round(implied_fv, 2) if implied_fv else None,
                benchmark_source=source_name,
                status="CALCULATED",
            )
        )

    # 4. P / E (Price-to-Earnings proxy using NOPAT or Net Income)
    target_pe_mult = benchmarks.get("P/E")
    if nopat is not None and nopat > 0:
        company_pe = (mkt_cap / nopat) if mkt_cap is not None else None
        implied_eq = target_pe_mult * nopat if target_pe_mult else None
        implied_fv = (implied_eq / shares) if (implied_eq is not None and shares > 0) else None
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_pe_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="P/E",
                company_multiple=round(company_pe, 2) if company_pe else None,
                peer_median_multiple=target_pe_mult,
                implied_equity_value=round(implied_eq, 2) if implied_eq else None,
                implied_fair_value_per_share=round(implied_fv, 2) if implied_fv else None,
                benchmark_source=source_name,
                status="CALCULATED",
            )
        )

    # 5. FCF Yield
    target_fcf_yield = benchmarks.get("FCF_YIELD")
    if fcf is not None and fcf > 0 and target_fcf_yield and target_fcf_yield > 0:
        company_fcf_yield = (fcf / mkt_cap) if mkt_cap is not None else None
        implied_eq = fcf / target_fcf_yield
        implied_fv = (implied_eq / shares) if (implied_eq is not None and shares > 0) else None
        results.append(
            RelativeValuationResult(
                relative_id=f"rel_{inputs.ticker}_fcfyield_{uuid.uuid4().hex[:6]}",
                company_id=inputs.company_id,
                ticker=inputs.ticker,
                cik=inputs.cik,
                sector=inputs.sector,
                valuation_date=inputs.valuation_date,
                as_of_date=inputs.data_as_of_date,
                peer_group=peer_group_name,
                multiple_name="FCF_YIELD",
                company_multiple=round(company_fcf_yield, 4) if company_fcf_yield else None,
                peer_median_multiple=target_fcf_yield,
                implied_equity_value=round(implied_eq, 2) if implied_eq else None,
                implied_fair_value_per_share=round(implied_fv, 2) if implied_fv else None,
                benchmark_source=source_name,
                status="CALCULATED",
            )
        )

    return results
