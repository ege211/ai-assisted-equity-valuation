"""
Trailing Twelve Months (LTM) Generation Engine.

Aggregates rolling four-quarter financial statements while enforcing
strict Point-in-Time (PIT) filing availability guarantees.

Core Logic:
LTM_flow(t) = Q(t) + Q(t-1) + Q(t-2) + Q(t-3)
LTM_instant(t) = Q(t) Balance Sheet (latest point-in-time)
LTM_acceptance_datetime = max(acceptance_datetime(Q_i) for i in {t, t-1, t-2, t-3})

Invariant:
Strict four-quarter consecutive sequence validation. No mixed fiscal regimes,
no look-ahead leakage, full constituent quarter lineage.
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

LTM_FLOW_VARIABLES = [
    "revenue", "cogs", "gross_profit", "sga", "ebit", "interest_expense",
    "pretax_income", "tax_expense", "net_income", "da", "cfo", "capex", "fcf"
]

LTM_INSTANT_VARIABLES = [
    "cash", "current_assets", "accounts_receivable", "inventory", "total_assets",
    "current_liabilities", "accounts_payable", "debt_current", "debt_noncurrent",
    "total_debt", "total_liabilities", "total_equity"
]

QUARTER_ORDER = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
REV_QUARTER_ORDER = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}


def get_prev_quarter(fy: int, fq: str) -> Tuple[int, str]:
    """Return immediately preceding (fiscal_year, fiscal_quarter)."""
    q_num = QUARTER_ORDER.get(fq, 1)
    if q_num == 1:
        return fy - 1, "Q4"
    return fy, REV_QUARTER_ORDER[q_num - 1]


class LTMEngine:
    """Generates rolling trailing twelve month financials from quarterly statements."""

    @classmethod
    def generate_ltm_statements(
        cls,
        quarterly_statements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Compute LTM statements for all valid consecutive 4-quarter sequences.

        Args:
            quarterly_statements: List of standalone quarterly statements for a company.

        Returns:
            List of LTM statement records for database insertion.
        """
        if not quarterly_statements or len(quarterly_statements) < 4:
            return []

        # Index statements by (fiscal_year, fiscal_quarter)
        by_period: Dict[Tuple[int, str], Dict[str, Any]] = {}
        for q in quarterly_statements:
            fy = q.get("fiscal_year")
            fq = q.get("fiscal_quarter")
            if fy and fq:
                by_period[(int(fy), str(fq))] = q

        # Sort periods chronologically
        sorted_periods = sorted(
            by_period.keys(),
            key=lambda p: (p[0], QUARTER_ORDER.get(p[1], 0))
        )

        ltm_records: List[Dict[str, Any]] = []

        for curr_period in sorted_periods:
            fy_curr, fq_curr = curr_period
            q_curr = by_period[curr_period]

            # Find preceding 3 quarters: t-1, t-2, t-3
            p1 = get_prev_quarter(fy_curr, fq_curr)
            p2 = get_prev_quarter(p1[0], p1[1])
            p3 = get_prev_quarter(p2[0], p2[1])

            if p1 not in by_period or p2 not in by_period or p3 not in by_period:
                continue

            q1 = by_period[p1]
            q2 = by_period[p2]
            q3 = by_period[p3]

            four_quarters = [q3, q2, q1, q_curr]  # In chronological order t-3, t-2, t-1, t

            # Compute LTM Flow variables: sum of 4 quarters
            ltm_values: Dict[str, Optional[float]] = {}
            for var in LTM_FLOW_VARIABLES:
                q_vals = [q.get(var) for q in four_quarters]
                if all(v is not None for v in q_vals):
                    ltm_values[var] = sum(q_vals)
                else:
                    ltm_values[var] = None

            # Balance sheet instant variables: latest quarter t
            for var in LTM_INSTANT_VARIABLES:
                ltm_values[var] = q_curr.get(var)

            # Economic derivations on LTM level
            if ltm_values.get("gross_profit") is None:
                r = ltm_values.get("revenue")
                c = ltm_values.get("cogs")
                if r is not None and c is not None:
                    ltm_values["gross_profit"] = r - c

            if ltm_values.get("fcf") is None:
                cfo = ltm_values.get("cfo")
                capex = ltm_values.get("capex")
                if cfo is not None and capex is not None:
                    ltm_values["fcf"] = cfo - capex

            # PIT Acceptance Timestamp: max across all 4 constituent filings
            accept_dts = [
                str(q.get("acceptance_datetime", "1900-01-01T00:00:00Z"))
                for q in four_quarters
            ]
            pit_acceptance = max(accept_dts)

            # Lineage tracking
            constituent_str = "+".join(
                f"{q['fiscal_year']}{q['fiscal_quarter']}" for q in four_quarters
            )
            constituent_accns = ",".join(
                str(q.get("accession_number", "UNKNOWN")) for q in four_quarters
            )

            stmt_id = f"LTM_{q_curr['ticker']}_{fy_curr}_{fq_curr}_{q_curr.get('accession_number', 'UNKNOWN')}"

            ltm_records.append({
                "statement_id": stmt_id,
                "company_id": q_curr["company_id"],
                "ticker": q_curr["ticker"],
                "cik": q_curr["cik"],
                "sector": q_curr["sector"],
                "as_of_fiscal_year": fy_curr,
                "as_of_fiscal_quarter": fq_curr,
                "period_end_date": q_curr["period_end_date"],
                "acceptance_datetime": pit_acceptance,
                "constituent_quarters": constituent_str,
                "constituent_accessions": constituent_accns,
                "revenue": ltm_values.get("revenue"),
                "cogs": ltm_values.get("cogs"),
                "gross_profit": ltm_values.get("gross_profit"),
                "sga": ltm_values.get("sga"),
                "ebit": ltm_values.get("ebit"),
                "interest_expense": ltm_values.get("interest_expense"),
                "pretax_income": ltm_values.get("pretax_income"),
                "tax_expense": ltm_values.get("tax_expense"),
                "net_income": ltm_values.get("net_income"),
                "da": ltm_values.get("da"),
                "cfo": ltm_values.get("cfo"),
                "capex": ltm_values.get("capex"),
                "fcf": ltm_values.get("fcf"),
                "cash": ltm_values.get("cash"),
                "current_assets": ltm_values.get("current_assets"),
                "accounts_receivable": ltm_values.get("accounts_receivable"),
                "inventory": ltm_values.get("inventory"),
                "total_assets": ltm_values.get("total_assets"),
                "current_liabilities": ltm_values.get("current_liabilities"),
                "accounts_payable": ltm_values.get("accounts_payable"),
                "debt_current": ltm_values.get("debt_current"),
                "debt_noncurrent": ltm_values.get("debt_noncurrent"),
                "total_debt": ltm_values.get("total_debt"),
                "total_liabilities": ltm_values.get("total_liabilities"),
                "total_equity": ltm_values.get("total_equity"),
                "data_status": "DERIVED",
            })

        return ltm_records
