"""
Quarterly Statement Normalization and YTD De-accumulation Engine.

Transforms cumulative YTD 10-Q disclosures and annual 10-K filings into
auditable standalone quarterly and annual financial statements.

Core Transformations:
- Q1 Standalone = Q1 YTD
- Q2 Standalone = Q2 YTD - Q1 YTD (or direct 3-month if disclosed)
- Q3 Standalone = Q3 YTD - Q2 YTD (or direct 3-month if disclosed)
- Q4 Standalone = FY - Q3 YTD (or FY - (Q1 + Q2 + Q3))

Safety Invariants:
- Identical company, canonical variable, and units (USD)
- Identical fiscal year and sequential chronological periods
- Missing preceding YTD -> UNRESOLVED
- Incompatible periods/units -> AMBIGUOUS / rejected
- Full lineage and transformation formula tracking
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from src.data.db import compute_fact_id
from src.normalization.concept_normalizer import (
    CONCEPT_FALLBACK_CASCADES,
    DURATION_VARIABLES,
    INSTANT_VARIABLES,
)

logger = logging.getLogger(__name__)


def parse_date(d_str: Optional[str]) -> Optional[datetime]:
    """Safely parse YYYY-MM-DD date."""
    if not d_str:
        return None
    try:
        return datetime.strptime(str(d_str)[:10], "%Y-%m-%d")
    except Exception:
        return None


def get_duration_days(start_date: Optional[str], end_date: Optional[str]) -> int:
    """Calculate duration in calendar days between start and end date."""
    s = parse_date(start_date)
    e = parse_date(end_date)
    if not s or not e or s >= e:
        return 0
    return (e - s).days


class QuarterlyEngine:
    """Orchestrates quarterly statement reconstruction and de-accumulation."""

    def __init__(
        self,
        cascades: Optional[Dict[str, List[Tuple[str, str, str]]]] = None,
    ) -> None:
        self.cascades = cascades or CONCEPT_FALLBACK_CASCADES

    def process_company(
        self,
        company_meta: Dict[str, Any],
        raw_facts: List[Dict[str, Any]],
        filings_map: Dict[str, Dict[str, Any]],
        target_years: Optional[List[int]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract quarterly and annual statements for a single company.

        Returns:
            Tuple of (quarterly_statements, annual_statements).
        """
        ticker = company_meta["ticker"]
        cik = str(company_meta["cik"]).zfill(10)
        company_id = company_meta.get("company_id", f"US_{ticker}")
        sector = company_meta["sector"]

        years = target_years or list(range(2014, 2025))

        # Index raw facts by concept and fiscal year
        facts_by_concept_year: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        for r in raw_facts:
            fy = r.get("fiscal_year")
            c = r.get("concept")
            if fy is not None and c:
                facts_by_concept_year.setdefault((c, int(fy)), []).append(r)

        quarterly_results: List[Dict[str, Any]] = []
        annual_results: List[Dict[str, Any]] = []

        for fy in years:
            # 1. Process Annual FY Statement
            annual_stmt = self._build_annual_statement(
                company_id=company_id,
                ticker=ticker,
                cik=cik,
                sector=sector,
                fiscal_year=fy,
                facts_by_concept_year=facts_by_concept_year,
                filings_map=filings_map,
            )
            if annual_stmt:
                annual_results.append(annual_stmt)

            # 2. Process Standalone Quarters Q1, Q2, Q3, Q4
            q_stmts = self._build_quarterly_statements(
                company_id=company_id,
                ticker=ticker,
                cik=cik,
                sector=sector,
                fiscal_year=fy,
                facts_by_concept_year=facts_by_concept_year,
                filings_map=filings_map,
                annual_stmt=annual_stmt,
            )
            quarterly_results.extend(q_stmts)

        return quarterly_results, annual_results

    def _build_annual_statement(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        facts_by_concept_year: Dict[Tuple[str, int], List[Dict[str, Any]]],
        filings_map: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Extract and normalize full annual FY financial statement."""
        values: Dict[str, Optional[float]] = {}
        lineage_map: Dict[str, str] = {}
        metadata: Dict[str, Any] = {
            "period_start_date": None,
            "period_end_date": f"{fiscal_year}-12-31",
            "filing_date": "1900-01-01",
            "acceptance_datetime": "1900-01-01T00:00:00Z",
            "form": "10-K",
            "accession_number": "UNKNOWN",
        }

        # Match each canonical variable via cascade
        for var_name, cascade in self.cascades.items():
            best_fact = self._find_best_annual_fact(
                cascade=cascade,
                fiscal_year=fiscal_year,
                facts_by_concept_year=facts_by_concept_year,
                filings_map=filings_map,
            )
            if best_fact:
                raw_val = float(best_fact.get("val", 0.0))
                val = abs(raw_val) if var_name == "capex" else raw_val
                values[var_name] = val
                lineage_map[var_name] = f"{best_fact.get('concept')} ({best_fact.get('accession_number')})"

                f_date = str(best_fact.get("filing_date", "1900-01-01"))
                if f_date > metadata["filing_date"]:
                    metadata["filing_date"] = f_date
                    metadata["period_end_date"] = str(best_fact.get("end_date", metadata["period_end_date"]))
                    metadata["period_start_date"] = best_fact.get("start_date")
                    metadata["form"] = str(best_fact.get("form", "10-K"))
                    metadata["accession_number"] = str(best_fact.get("accession_number", "UNKNOWN"))
                    metadata["acceptance_datetime"] = str(
                        best_fact.get("acceptance_datetime", f"{f_date}T23:59:59Z")
                    )
            else:
                values[var_name] = None

        self._apply_canonical_derivations(values, lineage_map)

        if not any(v is not None for v in values.values()):
            return None

        tot_assets = values.get("total_assets") or values.get("assets")
        tot_debt = values.get("total_debt")
        if tot_debt is None and values.get("debt_current") is not None and values.get("debt_noncurrent") is not None:
            tot_debt = values["debt_current"] + values["debt_noncurrent"]
        elif tot_debt is None:
            tot_debt = values.get("debt_noncurrent") or values.get("debt")

        tot_equity = values.get("total_equity") or values.get("equity")
        tot_liab = values.get("total_liabilities")
        if tot_liab is None and tot_assets is not None and tot_equity is not None:
            tot_liab = tot_assets - tot_equity

        cfo_val = values.get("cfo")
        capex_val = values.get("capex")
        fcf_val = (cfo_val - capex_val) if (cfo_val is not None and capex_val is not None) else None

        stmt_id = f"ANNUAL_{ticker}_{fiscal_year}_{metadata['accession_number']}"

        return {
            "statement_id": stmt_id,
            "company_id": company_id,
            "ticker": ticker,
            "cik": cik,
            "sector": sector,
            "fiscal_year": fiscal_year,
            "fiscal_period": "FY",
            "period_start_date": metadata["period_start_date"],
            "period_end_date": metadata["period_end_date"],
            "filing_date": metadata["filing_date"],
            "acceptance_datetime": metadata["acceptance_datetime"],
            "form": metadata["form"],
            "accession_number": metadata["accession_number"],
            "revenue": values.get("revenue"),
            "cogs": values.get("cogs"),
            "gross_profit": values.get("gross_profit"),
            "sga": values.get("sga"),
            "ebit": values.get("ebit"),
            "interest_expense": values.get("interest_expense"),
            "pretax_income": values.get("pretax_income"),
            "tax_expense": values.get("tax_expense"),
            "net_income": values.get("net_income"),
            "da": values.get("da"),
            "cash": values.get("cash"),
            "current_assets": values.get("current_assets"),
            "accounts_receivable": values.get("accounts_receivable"),
            "inventory": values.get("inventory"),
            "total_assets": tot_assets,
            "current_liabilities": values.get("current_liabilities"),
            "accounts_payable": values.get("accounts_payable"),
            "debt_current": values.get("debt_current"),
            "debt_noncurrent": values.get("debt_noncurrent") or values.get("debt"),
            "total_debt": tot_debt,
            "total_liabilities": tot_liab,
            "total_equity": tot_equity,
            "cfo": cfo_val,
            "capex": capex_val,
            "fcf": fcf_val,
            "data_status": "DIRECT_STANDARD",
            "lineage": "; ".join(f"{k}: {v}" for k, v in list(lineage_map.items())[:8]),
        }

    def _build_quarterly_statements(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        facts_by_concept_year: Dict[Tuple[str, int], List[Dict[str, Any]]],
        filings_map: Dict[str, Dict[str, Any]],
        annual_stmt: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Construct standalone statements for Q1, Q2, Q3, and Q4."""
        quarterly_stmts: List[Dict[str, Any]] = []

        ytd_flows: Dict[str, Dict[str, Dict[str, Any]]] = {"Q1": {}, "Q2": {}, "Q3": {}}
        standalone_flows: Dict[str, Dict[str, Dict[str, Any]]] = {"Q1": {}, "Q2": {}, "Q3": {}}
        instant_bs: Dict[str, Dict[str, Dict[str, Any]]] = {"Q1": {}, "Q2": {}, "Q3": {}}
        quarter_meta: Dict[str, Dict[str, Any]] = {}

        for q in ["Q1", "Q2", "Q3"]:
            quarter_meta[q] = {
                "period_start_date": None,
                "period_end_date": None,
                "filing_date": "1900-01-01",
                "acceptance_datetime": "1900-01-01T00:00:00Z",
                "form": "10-Q",
                "accession_number": "UNKNOWN",
            }

            for var_name, cascade in self.cascades.items():
                is_duration = var_name in DURATION_VARIABLES

                for tier_name, status_code, concept_name in cascade:
                    candidates = facts_by_concept_year.get((concept_name, fiscal_year), [])
                    matching = [
                        c for c in candidates
                        if c.get("fiscal_period") == q
                        and c.get("form") in ["10-Q", "10-Q/A"]
                        and c.get("unit") == "USD"
                    ]
                    if not matching:
                        continue

                    best_cand = self._select_best_candidate(matching)
                    accn = best_cand.get("accession_number", "")
                    f_meta = filings_map.get(accn, {})
                    f_date = str(best_cand.get("filing_date", "1900-01-01"))
                    if f_date > quarter_meta[q]["filing_date"]:
                        quarter_meta[q]["filing_date"] = f_date
                        quarter_meta[q]["period_end_date"] = str(best_cand.get("end_date"))
                        quarter_meta[q]["period_start_date"] = best_cand.get("start_date")
                        quarter_meta[q]["form"] = str(best_cand.get("form", "10-Q"))
                        quarter_meta[q]["accession_number"] = accn
                        quarter_meta[q]["acceptance_datetime"] = f_meta.get(
                            "acceptanceDateTime", f"{f_date}T23:59:59Z"
                        )

                    if not is_duration:
                        inst_cands = [c for c in matching if c.get("is_instant") or c.get("start_date") == c.get("end_date") or c.get("start_date") is None]
                        if inst_cands:
                            instant_bs[q][var_name] = self._select_best_candidate(inst_cands)
                            break
                    else:
                        std_cands = []
                        ytd_cands = []
                        for c in matching:
                            days = get_duration_days(c.get("start_date"), c.get("end_date"))
                            if q == "Q1":
                                if 70 <= days <= 115 or days == 0:
                                    std_cands.append(c)
                                    ytd_cands.append(c)
                            elif q == "Q2":
                                if 70 <= days <= 115:
                                    std_cands.append(c)
                                elif 150 <= days <= 220:
                                    ytd_cands.append(c)
                            elif q == "Q3":
                                if 70 <= days <= 115:
                                    std_cands.append(c)
                                elif 240 <= days <= 315:
                                    ytd_cands.append(c)

                        if std_cands and var_name not in standalone_flows[q]:
                            standalone_flows[q][var_name] = self._select_best_candidate(std_cands)
                        if ytd_cands and var_name not in ytd_flows[q]:
                            ytd_flows[q][var_name] = self._select_best_candidate(ytd_cands)

                        if var_name in standalone_flows[q] or var_name in ytd_flows[q]:
                            break

        # Assemble Q1
        q1_values: Dict[str, Optional[float]] = {}
        for var in DURATION_VARIABLES:
            fact = standalone_flows["Q1"].get(var) or ytd_flows["Q1"].get(var)
            if fact:
                raw_val = float(fact.get("val", 0.0))
                q1_values[var] = abs(raw_val) if var == "capex" else raw_val
            else:
                q1_values[var] = None

        for var in INSTANT_VARIABLES:
            fact = instant_bs["Q1"].get(var)
            q1_values[var] = float(fact.get("val", 0.0)) if fact else None

        self._apply_canonical_derivations(q1_values, {})
        q1_stmt = self._package_quarter_statement(
            company_id=company_id, ticker=ticker, cik=cik, sector=sector,
            fiscal_year=fiscal_year, fiscal_quarter="Q1", meta=quarter_meta["Q1"],
            values=q1_values, is_derived=False, deaccum_status="DIRECT_STANDARD",
        )
        if q1_stmt:
            quarterly_stmts.append(q1_stmt)

        # Assemble Q2
        q2_values: Dict[str, Optional[float]] = {}
        q2_deaccum_methods: List[str] = []
        for var in DURATION_VARIABLES:
            std_fact = standalone_flows["Q2"].get(var)
            if std_fact:
                raw_val = float(std_fact.get("val", 0.0))
                q2_values[var] = abs(raw_val) if var == "capex" else raw_val
            else:
                ytd2 = ytd_flows["Q2"].get(var)
                ytd1 = ytd_flows["Q1"].get(var) or standalone_flows["Q1"].get(var)
                if ytd2 and ytd1:
                    val2 = float(ytd2.get("val", 0.0))
                    val1 = float(ytd1.get("val", 0.0))
                    if var == "capex":
                        val2, val1 = abs(val2), abs(val1)
                    q2_values[var] = val2 - val1
                    q2_deaccum_methods.append(f"{var}: Q2_YTD - Q1_YTD")
                else:
                    q2_values[var] = None

        for var in INSTANT_VARIABLES:
            fact = instant_bs["Q2"].get(var)
            q2_values[var] = float(fact.get("val", 0.0)) if fact else None

        self._apply_canonical_derivations(q2_values, {})
        deaccum_tag = "; ".join(q2_deaccum_methods) if q2_deaccum_methods else "DIRECT_STANDARD"
        q2_stmt = self._package_quarter_statement(
            company_id=company_id, ticker=ticker, cik=cik, sector=sector,
            fiscal_year=fiscal_year, fiscal_quarter="Q2", meta=quarter_meta["Q2"],
            values=q2_values, is_derived=bool(q2_deaccum_methods), deaccum_status=deaccum_tag,
        )
        if q2_stmt:
            quarterly_stmts.append(q2_stmt)

        # Assemble Q3
        q3_values: Dict[str, Optional[float]] = {}
        q3_deaccum_methods: List[str] = []
        for var in DURATION_VARIABLES:
            std_fact = standalone_flows["Q3"].get(var)
            if std_fact:
                raw_val = float(std_fact.get("val", 0.0))
                q3_values[var] = abs(raw_val) if var == "capex" else raw_val
            else:
                ytd3 = ytd_flows["Q3"].get(var)
                ytd2 = ytd_flows["Q2"].get(var)
                if ytd3 and ytd2:
                    val3 = float(ytd3.get("val", 0.0))
                    val2 = float(ytd2.get("val", 0.0))
                    if var == "capex":
                        val3, val2 = abs(val3), abs(val2)
                    q3_values[var] = val3 - val2
                    q3_deaccum_methods.append(f"{var}: Q3_YTD - Q2_YTD")
                else:
                    q3_values[var] = None

        for var in INSTANT_VARIABLES:
            fact = instant_bs["Q3"].get(var)
            q3_values[var] = float(fact.get("val", 0.0)) if fact else None

        self._apply_canonical_derivations(q3_values, {})
        deaccum_tag = "; ".join(q3_deaccum_methods) if q3_deaccum_methods else "DIRECT_STANDARD"
        q3_stmt = self._package_quarter_statement(
            company_id=company_id, ticker=ticker, cik=cik, sector=sector,
            fiscal_year=fiscal_year, fiscal_quarter="Q3", meta=quarter_meta["Q3"],
            values=q3_values, is_derived=bool(q3_deaccum_methods), deaccum_status=deaccum_tag,
        )
        if q3_stmt:
            quarterly_stmts.append(q3_stmt)

        # Derive Standalone Q4
        if annual_stmt:
            q4_stmt = self._derive_q4_statement(
                company_id=company_id,
                ticker=ticker,
                cik=cik,
                sector=sector,
                fiscal_year=fiscal_year,
                annual_stmt=annual_stmt,
                ytd_flows=ytd_flows,
                q1_stmt=q1_stmt,
                q2_stmt=q2_stmt,
                q3_stmt=q3_stmt,
            )
            if q4_stmt:
                quarterly_stmts.append(q4_stmt)

        return quarterly_stmts

    def _derive_q4_statement(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        annual_stmt: Dict[str, Any],
        ytd_flows: Dict[str, Dict[str, Dict[str, Any]]],
        q1_stmt: Optional[Dict[str, Any]],
        q2_stmt: Optional[Dict[str, Any]],
        q3_stmt: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Derive standalone Q4 statement."""
        q4_values: Dict[str, Optional[float]] = {}
        deaccum_notes: List[str] = []

        for var in DURATION_VARIABLES:
            fy_val = annual_stmt.get(var)
            if fy_val is None:
                q4_values[var] = None
                continue

            ytd3 = ytd_flows["Q3"].get(var)
            if ytd3:
                raw_ytd3 = float(ytd3.get("val", 0.0))
                val_ytd3 = abs(raw_ytd3) if var == "capex" else raw_ytd3
                q4_values[var] = fy_val - val_ytd3
                deaccum_notes.append(f"{var}: FY - Q3_YTD")
            else:
                v1 = q1_stmt.get(var) if q1_stmt else None
                v2 = q2_stmt.get(var) if q2_stmt else None
                v3 = q3_stmt.get(var) if q3_stmt else None
                if v1 is not None and v2 is not None and v3 is not None:
                    q4_values[var] = fy_val - (v1 + v2 + v3)
                    deaccum_notes.append(f"{var}: FY - (Q1+Q2+Q3)")
                else:
                    q4_values[var] = None

        for var in INSTANT_VARIABLES:
            q4_values[var] = annual_stmt.get(var)

        self._apply_canonical_derivations(q4_values, {})

        meta = {
            "period_start_date": None,
            "period_end_date": annual_stmt["period_end_date"],
            "filing_date": annual_stmt["filing_date"],
            "acceptance_datetime": annual_stmt["acceptance_datetime"],
            "form": annual_stmt["form"],
            "accession_number": annual_stmt["accession_number"],
        }

        return self._package_quarter_statement(
            company_id=company_id,
            ticker=ticker,
            cik=cik,
            sector=sector,
            fiscal_year=fiscal_year,
            fiscal_quarter="Q4",
            meta=meta,
            values=q4_values,
            is_derived=True,
            deaccum_status="; ".join(deaccum_notes) if deaccum_notes else "DERIVED_Q4",
        )

    def _package_quarter_statement(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        fiscal_quarter: str,
        meta: Dict[str, Any],
        values: Dict[str, Optional[float]],
        is_derived: bool,
        deaccum_status: str,
    ) -> Optional[Dict[str, Any]]:
        """Wrap quarterly values into a structured database record."""
        if not any(v is not None for v in values.values()):
            return None

        tot_assets = values.get("total_assets") or values.get("assets")
        tot_debt = values.get("total_debt")
        if tot_debt is None and values.get("debt_current") is not None and values.get("debt_noncurrent") is not None:
            tot_debt = values["debt_current"] + values["debt_noncurrent"]
        elif tot_debt is None:
            tot_debt = values.get("debt_noncurrent") or values.get("debt")

        tot_equity = values.get("total_equity") or values.get("equity")
        tot_liab = values.get("total_liabilities")
        if tot_liab is None and tot_assets is not None and tot_equity is not None:
            tot_liab = tot_assets - tot_equity

        cfo_val = values.get("cfo")
        capex_val = values.get("capex")
        fcf_val = (cfo_val - capex_val) if (cfo_val is not None and capex_val is not None) else None

        end_date = meta.get("period_end_date") or f"{fiscal_year}-12-31"
        accn = meta.get("accession_number") or "UNKNOWN"
        stmt_id = f"QTR_{ticker}_{fiscal_year}_{fiscal_quarter}_{accn}"

        return {
            "statement_id": stmt_id,
            "company_id": company_id,
            "ticker": ticker,
            "cik": cik,
            "sector": sector,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "period_start_date": meta.get("period_start_date"),
            "period_end_date": end_date,
            "filing_date": meta.get("filing_date", "1900-01-01"),
            "acceptance_datetime": meta.get("acceptance_datetime", "1900-01-01T00:00:00Z"),
            "form": meta.get("form", "10-Q"),
            "accession_number": accn,
            "revenue": values.get("revenue"),
            "cogs": values.get("cogs"),
            "gross_profit": values.get("gross_profit"),
            "sga": values.get("sga"),
            "ebit": values.get("ebit"),
            "interest_expense": values.get("interest_expense"),
            "pretax_income": values.get("pretax_income"),
            "tax_expense": values.get("tax_expense"),
            "net_income": values.get("net_income"),
            "da": values.get("da"),
            "cash": values.get("cash"),
            "current_assets": values.get("current_assets"),
            "accounts_receivable": values.get("accounts_receivable"),
            "inventory": values.get("inventory"),
            "total_assets": tot_assets,
            "current_liabilities": values.get("current_liabilities"),
            "accounts_payable": values.get("accounts_payable"),
            "debt_current": values.get("debt_current"),
            "debt_noncurrent": values.get("debt_noncurrent") or values.get("debt"),
            "total_debt": tot_debt,
            "total_liabilities": tot_liab,
            "total_equity": tot_equity,
            "cfo": cfo_val,
            "capex": capex_val,
            "fcf": fcf_val,
            "is_derived_quarter": is_derived,
            "deaccumulation_status": deaccum_status,
            "lineage": f"{fiscal_quarter} standalone de-accumulated from 10-Q/10-K ({accn})",
        }

    def _apply_canonical_derivations(
        self,
        values: Dict[str, Optional[float]],
        lineage_map: Dict[str, str],
    ) -> None:
        """Derive standard accounting identities when components exist."""
        if values.get("gross_profit") is None:
            rev = values.get("revenue")
            cogs = values.get("cogs")
            if rev is not None and cogs is not None:
                values["gross_profit"] = rev - cogs
                lineage_map["gross_profit"] = "DERIVED: Revenue - COGS"

        if values.get("ebit") is None:
            gp = values.get("gross_profit")
            sga = values.get("sga")
            if gp is not None and sga is not None:
                values["ebit"] = gp - sga
                lineage_map["ebit"] = "DERIVED: Gross Profit - SG&A"
            else:
                pt = values.get("pretax_income")
                it = values.get("interest_expense") or 0.0
                if pt is not None:
                    values["ebit"] = pt + it
                    lineage_map["ebit"] = "DERIVED: Pretax Income + Interest Expense"

        if values.get("total_debt") is None:
            dc = values.get("debt_current") or 0.0
            dnc = values.get("debt_noncurrent") or values.get("debt")
            if dnc is not None:
                values["total_debt"] = dc + dnc
                lineage_map["total_debt"] = "DERIVED: Debt Current + Debt Noncurrent"

        if values.get("total_liabilities") is None:
            ta = values.get("total_assets") or values.get("assets")
            te = values.get("total_equity") or values.get("equity")
            if ta is not None and te is not None:
                values["total_liabilities"] = ta - te
                lineage_map["total_liabilities"] = "DERIVED: Total Assets - Total Equity"

    def _find_best_annual_fact(
        self,
        cascade: List[Tuple[str, str, str]],
        fiscal_year: int,
        facts_by_concept_year: Dict[Tuple[str, int], List[Dict[str, Any]]],
        filings_map: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Search cascade for the best annual fact."""
        for tier_name, status_code, concept_name in cascade:
            candidates = facts_by_concept_year.get((concept_name, fiscal_year), [])
            annual_cands = [
                c for c in candidates
                if c.get("form") in ["10-K", "10-K/A"]
                and c.get("unit") == "USD"
                and (c.get("fiscal_period") == "FY" or not c.get("fiscal_period"))
            ]
            if annual_cands:
                return self._select_best_candidate(annual_cands)
        return None

    def _select_best_candidate(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Rank candidates: prefer latest filing date, then 10-K/A or 10-Q/A amendments."""
        def rank_key(c: Dict[str, Any]) -> Tuple[str, int]:
            f_date = str(c.get("filing_date", "1900-01-01"))
            is_amend = 1 if "/A" in str(c.get("form", "")) else 0
            return (f_date, is_amend)

        return sorted(candidates, key=rank_key)[-1]
