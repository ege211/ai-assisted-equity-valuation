"""
Discrete Multi-Year Financial Forecast Engine.

Projects 5-year discrete income statement and cash flow items:
- Revenue (compound growth)
- EBIT and EBIT margin
- Effective Tax Expense and NOPAT (EBIT * (1 - t))
- Depreciation & Amortization
- Capital Expenditures
- Operating Working Capital and Delta OWC
- Free Cash Flow to Firm: FCFF = NOPAT + D&A - CapEx - Delta OWC
- Discount factors and Present Value of FCFF
"""
from typing import List, Optional
from src.valuation.models import ForecastAssumptions, ForecastPeriod, ValuationInputs


def generate_forecast(
    inputs: ValuationInputs,
    assumptions: ForecastAssumptions,
    wacc: float,
) -> List[ForecastPeriod]:
    """
    Generate 5-year discrete financial projections and discounted cash flows.

    Parameters
    ----------
    inputs : ValuationInputs
        Baseline historical LTM financials.
    assumptions : ForecastAssumptions
        Growth rates, margins, ratios, and discount convention.
    wacc : float
        Weighted Average Cost of Capital (decimal, e.g. 0.085).

    Returns
    -------
    List[ForecastPeriod]
        5 discrete annual projection periods.
    """
    periods: List[ForecastPeriod] = []
    
    # Parse base year from valuation_date or data_as_of_date
    try:
        base_year = int(str(inputs.valuation_date)[:4])
    except Exception:
        base_year = 2024

    prev_rev = inputs.ltm_revenue
    prev_nwc = inputs.operating_working_capital

    # In case historical operating working capital was 0 or anomalous, align baseline
    if prev_nwc is None or prev_nwc == 0.0:
        prev_nwc = prev_rev * assumptions.nwc_ratio_of_rev

    for t in range(1, assumptions.forecast_years + 1):
        idx = t - 1
        g = assumptions.revenue_growth_rates[idx] if idx < len(assumptions.revenue_growth_rates) else assumptions.revenue_growth_rates[-1]
        m = assumptions.ebit_margins[idx] if idx < len(assumptions.ebit_margins) else assumptions.ebit_margins[-1]

        # Revenue
        rev = prev_rev * (1.0 + g)
        
        # EBIT
        ebit = rev * m

        # Tax & NOPAT
        tax_rate = assumptions.tax_rate
        tax_expense = max(0.0, ebit * tax_rate) if ebit > 0 else 0.0
        nopat = ebit * (1.0 - tax_rate)

        # D&A and CapEx
        da = rev * assumptions.da_ratio_of_rev
        capex = rev * assumptions.capex_ratio_of_rev

        # Operating Working Capital & Delta
        nwc = rev * assumptions.nwc_ratio_of_rev
        delta_nwc = nwc - prev_nwc

        # Free Cash Flow to Firm (FCFF)
        fcff = nopat + da - capex - delta_nwc

        # Discount Factor
        if assumptions.discount_convention == "end_of_year":
            period_power = float(t)
        else:
            # mid-year convention
            period_power = float(t) - 0.5

        if (1.0 + wacc) > 0:
            df = 1.0 / ((1.0 + wacc) ** period_power)
        else:
            df = 1.0

        pv_fcff = fcff * df

        period = ForecastPeriod(
            forecast_year_index=t,
            fiscal_year=base_year + t,
            revenue=round(rev, 2),
            revenue_growth=round(g, 4),
            ebit_margin=round(m, 4),
            ebit=round(ebit, 2),
            tax_rate=round(tax_rate, 4),
            tax_expense=round(tax_expense, 2),
            nopat=round(nopat, 2),
            da=round(da, 2),
            capex=round(capex, 2),
            nwc=round(nwc, 2),
            delta_nwc=round(delta_nwc, 2),
            fcff=round(fcff, 2),
            discount_factor=round(df, 6),
            pv_fcff=round(pv_fcff, 2),
        )
        periods.append(period)

        # Step forward
        prev_rev = rev
        prev_nwc = nwc

    return periods
