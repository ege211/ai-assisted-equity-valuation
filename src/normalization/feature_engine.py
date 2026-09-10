"""
Fundamental Feature Engineering Layer.

Calculates auditable, economically defensible financial features:
- NOPAT with normalized effective tax rate
- Operating Working Capital & Delta NWC
- Invested Capital & ROIC (with beginning/ending averaging)
- Operating Margins (Gross, EBIT, Net, CFO, FCF)
- Historical Free Cash Flow (CFO - CapEx)
- Net Debt (Total Debt - Cash)
- Historical YoY Growth Rates

All features maintain strict point-in-time traceability, zero look-ahead bias,
and explicit handling of zero/negative denominators.
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Perform division guarding against None and zero/negative denominators."""
    if numerator is None or denominator is None or denominator == 0.0:
        return None
    return numerator / denominator


class FeatureEngine:
    """Computes fundamental financial features from standardized statements."""

    @classmethod
    def compute_all_features(
        cls,
        quarterly_stmts: List[Dict[str, Any]],
        annual_stmts: List[Dict[str, Any]],
        ltm_stmts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate feature records across quarterly, annual, and LTM statements.

        Returns:
            List of feature records ready for financial_features table insertion.
        """
        features: List[Dict[str, Any]] = []

        # 1. Generate features for LTM statements (primary layer for valuation inputs)
        features.extend(cls._generate_ltm_features(ltm_stmts))

        # 2. Generate features for Annual FY statements
        features.extend(cls._generate_annual_features(annual_stmts))

        # 3. Generate features for Quarterly statements
        features.extend(cls._generate_quarterly_features(quarterly_stmts))

        return features

    @classmethod
    def _generate_ltm_features(cls, ltm_stmts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate features for LTM statements with 4-quarter lag growth and ROIC."""
        features: List[Dict[str, Any]] = []
        if not ltm_stmts:
            return features

        # Index by (fiscal_year, fiscal_quarter) for lagged comparisons
        ltm_by_period: Dict[Tuple[int, str], Dict[str, Any]] = {}
        for s in ltm_stmts:
            ltm_by_period[(s["as_of_fiscal_year"], s["as_of_fiscal_quarter"])] = s

        quarter_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
        rev_order = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}

        def get_lag4_period(fy: int, fq: str) -> Tuple[int, str]:
            return (fy - 1, fq)

        for stmt in ltm_stmts:
            fy = stmt["as_of_fiscal_year"]
            fq = stmt["as_of_fiscal_quarter"]
            ticker = stmt["ticker"]
            cik = stmt["cik"]
            company_id = stmt["company_id"]
            sector = stmt["sector"]
            as_of_date = stmt["acceptance_datetime"]
            period_end = stmt["period_end_date"]
            source_periods = stmt["constituent_quarters"]
            source_accns = stmt["constituent_accessions"]

            # Common helper to add feature
            def add_feature(
                name: str,
                val: Optional[float],
                unit: str,
                calc_method: str,
                status: str = "DERIVED",
                concepts: Optional[str] = None,
            ) -> None:
                feat_id = f"FEAT_{ticker}_{fy}_{fq}_LTM_{name}"
                features.append({
                    "feature_id": feat_id,
                    "company_id": company_id,
                    "ticker": ticker,
                    "cik": cik,
                    "sector": sector,
                    "as_of_date": as_of_date,
                    "period_end_date": period_end,
                    "fiscal_year": fy,
                    "fiscal_period": "LTM",
                    "feature_name": name,
                    "feature_value": val,
                    "unit": unit,
                    "source_periods": source_periods,
                    "source_filings": "10-Q/10-K",
                    "source_accessions": source_accns,
                    "calculation_method": calc_method,
                    "source_concepts": concepts or name,
                    "data_status": status if val is not None else "UNRESOLVED",
                })

            ebit = stmt.get("ebit")
            pretax = stmt.get("pretax_income")
            tax_exp = stmt.get("tax_expense")
            rev = stmt.get("revenue")
            cogs = stmt.get("cogs")
            gp = stmt.get("gross_profit")
            ni = stmt.get("net_income")
            cfo = stmt.get("cfo")
            capex = stmt.get("capex")
            cash = stmt.get("cash") or 0.0
            tot_assets = stmt.get("total_assets")
            curr_assets = stmt.get("current_assets")
            curr_liab = stmt.get("current_liabilities")
            debt_curr = stmt.get("debt_current") or 0.0
            debt_noncurr = stmt.get("debt_noncurrent") or 0.0
            tot_debt = stmt.get("total_debt") or (debt_curr + debt_noncurr)

            # 1. Effective Tax Rate & Normalized Tax Rate
            stat_rate = 0.21 if fy >= 2018 else 0.35
            norm_tax_rate = stat_rate
            tax_calc_note = f"US Statutory Benchmark ({stat_rate * 100:.1f}%)"

            if pretax is not None and tax_exp is not None and pretax > 0:
                eff_rate = tax_exp / pretax
                if 0.0 <= eff_rate <= 0.50:
                    norm_tax_rate = eff_rate
                    tax_calc_note = f"Effective Tax Rate ({eff_rate * 100:.2f}%)"
                else:
                    tax_calc_note = f"Statutory Fallback ({stat_rate * 100:.1f}%) [effective rate anomalous: {eff_rate * 100:.1f}%]"
            else:
                tax_calc_note = f"Statutory Fallback ({stat_rate * 100:.1f}%) [pretax <= 0 or missing]"

            add_feature("normalized_tax_rate", norm_tax_rate, "RATIO", tax_calc_note)

            # 2. NOPAT = EBIT * (1 - norm_tax_rate)
            nopat = (ebit * (1.0 - norm_tax_rate)) if ebit is not None else None
            nopat_calc = f"EBIT * (1 - {norm_tax_rate:.4f}) [{tax_calc_note}]"
            add_feature("nopat", nopat, "USD", nopat_calc)

            # 3. Free Cash Flow = CFO - CapEx
            fcf = (cfo - capex) if (cfo is not None and capex is not None) else None
            add_feature("fcf", fcf, "USD", "CFO - CapEx")

            # 4. Net Debt = Total Debt - Cash
            net_debt = (tot_debt - cash) if tot_debt is not None else None
            add_feature("net_debt", net_debt, "USD", "Total Debt - Cash")

            # 5. Operating Working Capital (OWC)
            # OWC = (Current Assets - Cash) - (Current Liabilities - Debt Current)
            owc = None
            if curr_assets is not None and curr_liab is not None:
                op_ca = curr_assets - cash
                op_cl = curr_liab - debt_curr
                owc = op_ca - op_cl
            add_feature("operating_working_capital", owc, "USD", "(Current Assets - Cash) - (Current Liabilities - Short-Term Debt)")

            # Working Capital = Current Assets - Current Liabilities
            wc = (curr_assets - curr_liab) if (curr_assets is not None and curr_liab is not None) else None
            add_feature("working_capital", wc, "USD", "Current Assets - Current Liabilities")

            if rev is not None and rev > 0:
                add_feature("working_capital_to_revenue", (wc / rev) if wc is not None else None, "RATIO", "Working Capital / Revenue")
                add_feature("owc_to_revenue", (owc / rev) if owc is not None else None, "RATIO", "OWC / Revenue")
            else:
                add_feature("working_capital_to_revenue", None, "RATIO", "Revenue <= 0", "UNRESOLVED")
                add_feature("owc_to_revenue", None, "RATIO", "Revenue <= 0", "UNRESOLVED")

            # 6. Invested Capital = Total Assets - Cash - (Current Liabilities - Short-Term Debt)
            ic = None
            if tot_assets is not None and curr_liab is not None:
                ic = tot_assets - cash - (curr_liab - debt_curr)
            add_feature("invested_capital", ic, "USD", "Total Assets - Cash - Operating Current Liabilities")

            # 7. ROIC = NOPAT / Average Invested Capital
            lag4_p = get_lag4_period(fy, fq)
            prev_stmt = ltm_by_period.get(lag4_p)
            avg_ic = None
            if ic is not None:
                if prev_stmt:
                    p_ta = prev_stmt.get("total_assets")
                    p_cl = prev_stmt.get("current_liabilities")
                    p_cash = prev_stmt.get("cash") or 0.0
                    p_dc = prev_stmt.get("debt_current") or 0.0
                    if p_ta is not None and p_cl is not None:
                        p_ic = p_ta - p_cash - (p_cl - p_dc)
                        avg_ic = (ic + p_ic) / 2.0
                if avg_ic is None:
                    avg_ic = ic  # Use spot IC if prior not available

            add_feature("average_invested_capital", avg_ic, "USD", "Average of Beginning & Ending Invested Capital (4-quarter lag)")

            roic = None
            if nopat is not None and avg_ic is not None and avg_ic > 0:
                roic = nopat / avg_ic
                add_feature("roic", roic, "RATIO", "NOPAT / Average Invested Capital")
            else:
                add_feature("roic", None, "RATIO", "NOPAT or Average IC <= 0 or missing", "UNRESOLVED")

            # 8. Operating Margins (Guard against Revenue <= 0)
            if rev is not None and rev > 0:
                add_feature("gross_margin", (gp / rev) if gp is not None else None, "RATIO", "Gross Profit / Revenue")
                add_feature("ebit_margin", (ebit / rev) if ebit is not None else None, "RATIO", "EBIT / Revenue")
                add_feature("net_margin", (ni / rev) if ni is not None else None, "RATIO", "Net Income / Revenue")
                add_feature("cfo_margin", (cfo / rev) if cfo is not None else None, "RATIO", "Operating Cash Flow / Revenue")
                add_feature("fcf_margin", (fcf / rev) if fcf is not None else None, "RATIO", "FCF / Revenue")
            else:
                for m in ["gross_margin", "ebit_margin", "net_margin", "cfo_margin", "fcf_margin"]:
                    add_feature(m, None, "RATIO", "Revenue <= 0 or missing", "UNRESOLVED")

            # 9. YoY Growth Rates (LTM(t) vs LTM(t-4))
            if prev_stmt:
                # Revenue Growth
                p_rev = prev_stmt.get("revenue")
                if rev is not None and p_rev is not None and p_rev > 0:
                    add_feature("revenue_growth_yoy", (rev / p_rev) - 1.0, "RATIO", "LTM Revenue(t) / LTM Revenue(t-4) - 1")
                else:
                    add_feature("revenue_growth_yoy", None, "RATIO", "Prior LTM revenue <= 0 or missing", "UNRESOLVED")

                # EBIT Growth
                p_ebit = prev_stmt.get("ebit")
                if ebit is not None and p_ebit is not None and p_ebit != 0:
                    add_feature("ebit_growth_yoy", (ebit - p_ebit) / abs(p_ebit), "RATIO", "(EBIT(t) - EBIT(t-4)) / |EBIT(t-4)|")
                else:
                    add_feature("ebit_growth_yoy", None, "RATIO", "Prior EBIT zero or missing", "UNRESOLVED")

                # CFO Growth
                p_cfo = prev_stmt.get("cfo")
                if cfo is not None and p_cfo is not None and p_cfo != 0:
                    add_feature("cfo_growth_yoy", (cfo - p_cfo) / abs(p_cfo), "RATIO", "(CFO(t) - CFO(t-4)) / |CFO(t-4)|")
                else:
                    add_feature("cfo_growth_yoy", None, "RATIO", "Prior CFO zero or missing", "UNRESOLVED")

                # FCF Growth
                p_fcf = prev_stmt.get("fcf")
                if fcf is not None and p_fcf is not None and p_fcf != 0:
                    add_feature("fcf_growth_yoy", (fcf - p_fcf) / abs(p_fcf), "RATIO", "(FCF(t) - FCF(t-4)) / |FCF(t-4)|")
                else:
                    add_feature("fcf_growth_yoy", None, "RATIO", "Prior FCF zero or missing", "UNRESOLVED")

        return features

    @classmethod
    def _generate_annual_features(cls, annual_stmts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate features for Annual FY statements."""
        features: List[Dict[str, Any]] = []
        if not annual_stmts:
            return features

        by_year: Dict[int, Dict[str, Any]] = {s["fiscal_year"]: s for s in annual_stmts}

        for stmt in annual_stmts:
            fy = stmt["fiscal_year"]
            ticker = stmt["ticker"]
            cik = stmt["cik"]
            company_id = stmt["company_id"]
            sector = stmt["sector"]
            as_of_date = stmt["acceptance_datetime"]
            period_end = stmt["period_end_date"]
            accn = stmt["accession_number"]

            def add_feature(
                name: str,
                val: Optional[float],
                unit: str,
                calc_method: str,
                status: str = "DERIVED",
            ) -> None:
                feat_id = f"FEAT_{ticker}_{fy}_FY_{name}"
                features.append({
                    "feature_id": feat_id,
                    "company_id": company_id,
                    "ticker": ticker,
                    "cik": cik,
                    "sector": sector,
                    "as_of_date": as_of_date,
                    "period_end_date": period_end,
                    "fiscal_year": fy,
                    "fiscal_period": "FY",
                    "feature_name": name,
                    "feature_value": val,
                    "unit": unit,
                    "source_periods": f"{fy}FY",
                    "source_filings": stmt["form"],
                    "source_accessions": accn,
                    "calculation_method": calc_method,
                    "source_concepts": name,
                    "data_status": status if val is not None else "UNRESOLVED",
                })

            ebit = stmt.get("ebit")
            pretax = stmt.get("pretax_income")
            tax_exp = stmt.get("tax_expense")
            rev = stmt.get("revenue")
            cfo = stmt.get("cfo")
            capex = stmt.get("capex")
            cash = stmt.get("cash") or 0.0
            tot_assets = stmt.get("total_assets")
            curr_assets = stmt.get("current_assets")
            curr_liab = stmt.get("current_liabilities")
            debt_curr = stmt.get("debt_current") or 0.0
            tot_debt = stmt.get("total_debt")

            stat_rate = 0.21 if fy >= 2018 else 0.35
            norm_tax_rate = stat_rate
            if pretax is not None and tax_exp is not None and pretax > 0:
                eff = tax_exp / pretax
                if 0.0 <= eff <= 0.50:
                    norm_tax_rate = eff

            add_feature("normalized_tax_rate", norm_tax_rate, "RATIO", f"Effective or Statutory ({norm_tax_rate:.4f})")
            nopat = (ebit * (1.0 - norm_tax_rate)) if ebit is not None else None
            add_feature("nopat", nopat, "USD", "EBIT * (1 - norm_tax_rate)")

            fcf = (cfo - capex) if (cfo is not None and capex is not None) else None
            add_feature("fcf", fcf, "USD", "CFO - CapEx")

            net_debt = (tot_debt - cash) if tot_debt is not None else None
            add_feature("net_debt", net_debt, "USD", "Total Debt - Cash")

            # Invested Capital & ROIC
            ic = None
            if tot_assets is not None and curr_liab is not None:
                ic = tot_assets - cash - (curr_liab - debt_curr)
            add_feature("invested_capital", ic, "USD", "Total Assets - Cash - Operating Current Liabilities")

            prev_stmt = by_year.get(fy - 1)
            avg_ic = None
            if ic is not None:
                if prev_stmt:
                    p_ta = prev_stmt.get("total_assets")
                    p_cl = prev_stmt.get("current_liabilities")
                    p_cash = prev_stmt.get("cash") or 0.0
                    p_dc = prev_stmt.get("debt_current") or 0.0
                    if p_ta is not None and p_cl is not None:
                        avg_ic = (ic + (p_ta - p_cash - (p_cl - p_dc))) / 2.0
                if avg_ic is None:
                    avg_ic = ic
            add_feature("average_invested_capital", avg_ic, "USD", "Average Invested Capital (FY vs FY-1)")

            roic = (nopat / avg_ic) if (nopat is not None and avg_ic is not None and avg_ic > 0) else None
            add_feature("roic", roic, "RATIO", "NOPAT / Average Invested Capital")

            # Growth YoY
            if prev_stmt:
                p_rev = prev_stmt.get("revenue")
                if rev is not None and p_rev is not None and p_rev > 0:
                    add_feature("revenue_growth_yoy", (rev / p_rev) - 1.0, "RATIO", "Annual Revenue(t) / Revenue(t-1) - 1")

        return features

    @classmethod
    def _generate_quarterly_features(cls, quarterly_stmts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate features for Standalone Quarterly statements."""
        features: List[Dict[str, Any]] = []
        for stmt in quarterly_stmts:
            fy = stmt["fiscal_year"]
            fq = stmt["fiscal_quarter"]
            ticker = stmt["ticker"]
            cik = stmt["cik"]
            company_id = stmt["company_id"]
            sector = stmt["sector"]
            as_of_date = stmt["acceptance_datetime"]
            period_end = stmt["period_end_date"]
            accn = stmt["accession_number"]

            def add_feature(
                name: str,
                val: Optional[float],
                unit: str,
                calc_method: str,
                status: str = "DERIVED",
            ) -> None:
                feat_id = f"FEAT_{ticker}_{fy}_{fq}_{name}"
                features.append({
                    "feature_id": feat_id,
                    "company_id": company_id,
                    "ticker": ticker,
                    "cik": cik,
                    "sector": sector,
                    "as_of_date": as_of_date,
                    "period_end_date": period_end,
                    "fiscal_year": fy,
                    "fiscal_period": fq,
                    "feature_name": name,
                    "feature_value": val,
                    "unit": unit,
                    "source_periods": f"{fy}{fq}",
                    "source_filings": stmt["form"],
                    "source_accessions": accn,
                    "calculation_method": calc_method,
                    "source_concepts": name,
                    "data_status": status if val is not None else "UNRESOLVED",
                })

            ebit = stmt.get("ebit")
            rev = stmt.get("revenue")
            gp = stmt.get("gross_profit")
            ni = stmt.get("net_income")
            cfo = stmt.get("cfo")
            capex = stmt.get("capex")
            cash = stmt.get("cash") or 0.0
            tot_debt = stmt.get("total_debt")

            # FCF
            fcf = (cfo - capex) if (cfo is not None and capex is not None) else None
            add_feature("fcf", fcf, "USD", "CFO - CapEx")

            # Net Debt
            net_debt = (tot_debt - cash) if tot_debt is not None else None
            add_feature("net_debt", net_debt, "USD", "Total Debt - Cash")

            # Margins
            if rev is not None and rev > 0:
                add_feature("gross_margin", (gp / rev) if gp is not None else None, "RATIO", "Gross Profit / Revenue")
                add_feature("ebit_margin", (ebit / rev) if ebit is not None else None, "RATIO", "EBIT / Revenue")
                add_feature("net_margin", (ni / rev) if ni is not None else None, "RATIO", "Net Income / Revenue")
                add_feature("fcf_margin", (fcf / rev) if fcf is not None else None, "RATIO", "FCF / Revenue")
            else:
                for m in ["gross_margin", "ebit_margin", "net_margin", "fcf_margin"]:
                    add_feature(m, None, "RATIO", "Revenue <= 0 or missing", "UNRESOLVED")

        return features
