"""
Point-in-Time Forward Target Construction Module for Phase 6.

Constructs forward financial outcome targets occurring strictly AFTER the
information date T, ensuring zero look-ahead bias and verifiable temporal separation.
"""
from typing import Any, Dict, Optional

from src.research.models import ResearchTargetSet


def build_forward_targets(
    ticker: str,
    base_year: int,
    base_statement: Dict[str, Any],
    forward_statement: Optional[Dict[str, Any]],
) -> ResearchTargetSet:
    """
    Construct forward financial targets for base_year using the realized statement
    from forward_year (base_year + 1).

    Ensures that forward_statement was filed strictly AFTER base_statement.
    """
    if not forward_statement:
        return ResearchTargetSet(
            ticker=ticker,
            fiscal_year=base_year,
            is_valid=False,
        )

    # Verify temporal ordering of filing dates
    base_filing_date = str(base_statement.get("filing_date", ""))
    forward_filing_date = str(forward_statement.get("filing_date", ""))

    if forward_filing_date <= base_filing_date:
        # Invalid temporal sequence
        return ResearchTargetSet(
            ticker=ticker,
            fiscal_year=base_year,
            is_valid=False,
        )

    rev_t0 = float(base_statement.get("revenue", 0.0) or 0.0)
    ebit_t0 = float(base_statement.get("ebit", 0.0) or 0.0)

    rev_t1 = float(forward_statement.get("revenue", 0.0) or 0.0)
    ebit_t1 = float(forward_statement.get("ebit", 0.0) or 0.0)

    if rev_t0 <= 0.0 or rev_t1 <= 0.0:
        return ResearchTargetSet(
            ticker=ticker,
            fiscal_year=base_year,
            is_valid=False,
        )

    # 1. Forward 1-year revenue growth
    fwd_rev_growth = (rev_t1 - rev_t0) / rev_t0

    # 2. Forward 1-year EBIT margin change
    ebit_margin_t0 = ebit_t0 / rev_t0
    ebit_margin_t1 = ebit_t1 / rev_t1
    fwd_margin_change = ebit_margin_t1 - ebit_margin_t0

    # 3. Binary earnings deterioration indicator (1 if EBIT fell, 0 otherwise)
    earnings_deterioration = 1.0 if ebit_t1 < ebit_t0 else 0.0

    return ResearchTargetSet(
        ticker=ticker,
        fiscal_year=base_year,
        forward_ebit_margin_change=fwd_margin_change,
        forward_revenue_growth=fwd_rev_growth,
        earnings_deterioration=earnings_deterioration,
        realization_date=forward_filing_date,
        source_statement_id=forward_statement.get("statement_id"),
        is_valid=True,
    )
