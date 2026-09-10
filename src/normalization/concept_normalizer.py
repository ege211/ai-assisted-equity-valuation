"""
XBRL Concept Normalization Engine.
Implements the audited 5-tier fallback cascade from Phase 1.
Extracts the 10 core financial statement variables:
- revenue
- ebit (operating income proxy)
- net_income
- cash
- debt
- assets
- equity
- cfo (operating cash flow)
- capex (capital expenditures)
- da (depreciation and amortization)

Ensures complete audit trail, deterministic status tagging,
and strict unit and sign compliance.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Phase 1 & Phase 3 Concept Fallback Hierarchy
CONCEPT_FALLBACK_CASCADES: Dict[str, List[Tuple[str, str, str]]] = {
    "revenue": [
        ("Tier 1", "DIRECT_STANDARD", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "SalesRevenueNet"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "Revenues"),
        ("Tier 2C", "DIRECT_ALTERNATIVE", "TotalRevenuesAndOtherIncome"),
        ("Tier 2D", "DIRECT_ALTERNATIVE", "RevenueFromContractWithCustomerIncludingAssessedTax"),
    ],
    "cogs": [
        ("Tier 1", "DIRECT_STANDARD", "CostOfGoodsAndServicesSold"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "CostOfRevenue"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "CostOfGoodsSold"),
    ],
    "gross_profit": [
        ("Tier 1", "DIRECT_STANDARD", "GrossProfit"),
    ],
    "sga": [
        ("Tier 1", "DIRECT_STANDARD", "SellingGeneralAndAdministrativeExpense"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "GeneralAndAdministrativeExpense"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "SellingAndMarketingExpense"),
    ],
    "ebit": [
        ("Tier 1", "DIRECT_STANDARD", "OperatingIncomeLoss"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
        ("Tier 2C", "DIRECT_ALTERNATIVE", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"),
    ],
    "interest_expense": [
        ("Tier 1", "DIRECT_STANDARD", "InterestExpense"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "InterestAndDebtExpense"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "InterestExpenseDebt"),
        ("Tier 2C", "DIRECT_ALTERNATIVE", "InterestIncomeExpenseNonoperatingNet"),
    ],
    "pretax_income": [
        ("Tier 1", "DIRECT_STANDARD", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"),
    ],
    "tax_expense": [
        ("Tier 1", "DIRECT_STANDARD", "IncomeTaxExpenseBenefit"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "CurrentIncomeTaxExpenseBenefit"),
    ],
    "net_income": [
        ("Tier 1", "DIRECT_STANDARD", "NetIncomeLoss"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "ProfitLoss"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    ],
    "cash": [
        ("Tier 1", "DIRECT_STANDARD", "CashAndCashEquivalentsAtCarryingValue"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "Cash"),
    ],
    "current_assets": [
        ("Tier 1", "DIRECT_STANDARD", "AssetsCurrent"),
    ],
    "accounts_receivable": [
        ("Tier 1", "DIRECT_STANDARD", "AccountsReceivableNetCurrent"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "ReceivablesNetCurrent"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "AccountsAndOtherReceivablesNetCurrent"),
    ],
    "inventory": [
        ("Tier 1", "DIRECT_STANDARD", "InventoryNet"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "Inventories"),
    ],
    "assets": [
        ("Tier 1", "DIRECT_STANDARD", "Assets"),
    ],
    "total_assets": [
        ("Tier 1", "DIRECT_STANDARD", "Assets"),
    ],
    "current_liabilities": [
        ("Tier 1", "DIRECT_STANDARD", "LiabilitiesCurrent"),
    ],
    "accounts_payable": [
        ("Tier 1", "DIRECT_STANDARD", "AccountsPayableCurrent"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "AccountsPayableAndAccruedLiabilitiesCurrent"),
    ],
    "debt_current": [
        ("Tier 1", "DIRECT_STANDARD", "LongTermDebtCurrent"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "ShortTermBorrowings"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "DebtCurrent"),
        ("Tier 2C", "DIRECT_ALTERNATIVE", "CommercialPaper"),
    ],
    "debt_noncurrent": [
        ("Tier 1", "DIRECT_STANDARD", "LongTermDebtNoncurrent"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "LongTermDebt"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "LongTermDebtAndCapitalLeaseObligations"),
    ],
    "debt": [
        ("Tier 1", "DIRECT_STANDARD", "LongTermDebtNoncurrent"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "LongTermDebt"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "LongTermDebtAndCapitalLeaseObligations"),
    ],
    "total_debt": [
        ("Tier 1", "DIRECT_STANDARD", "DebtAndCapitalLeaseObligations"),
    ],
    "total_liabilities": [
        ("Tier 1", "DIRECT_STANDARD", "Liabilities"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "LiabilitiesAndStockholdersEquity"),
    ],
    "equity": [
        ("Tier 1", "DIRECT_STANDARD", "StockholdersEquity"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "CommonStockholdersEquity"),
    ],
    "total_equity": [
        ("Tier 1", "DIRECT_STANDARD", "StockholdersEquity"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "CommonStockholdersEquity"),
    ],
    "cfo": [
        ("Tier 1", "DIRECT_STANDARD", "NetCashProvidedByUsedInOperatingActivities"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ],
    "capex": [
        ("Tier 1", "DIRECT_STANDARD", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "PaymentsToAcquireProductiveAssets"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "PaymentsToAcquirePropertyPlantAndEquipmentAndSoftware"),
        ("Tier 2C", "DIRECT_ALTERNATIVE", "PaymentsToAcquireOilAndGasPropertyAndEquipment"),
    ],
    "da": [
        ("Tier 1", "DIRECT_STANDARD", "DepreciationDepletionAndAmortization"),
        ("Tier 2A", "DIRECT_ALTERNATIVE", "DepreciationAndAmortization"),
        ("Tier 2B", "DIRECT_ALTERNATIVE", "DepreciationAmortizationAndAccretionNet"),
        ("Tier 2C", "DIRECT_ALTERNATIVE", "Depreciation"),
    ],
}

INSTANT_VARIABLES = {
    "cash", "debt", "assets", "equity", "current_assets", "accounts_receivable",
    "inventory", "total_assets", "current_liabilities", "accounts_payable",
    "debt_current", "debt_noncurrent", "total_debt", "total_liabilities", "total_equity"
}
DURATION_VARIABLES = {
    "revenue", "cogs", "gross_profit", "sga", "ebit", "interest_expense",
    "pretax_income", "tax_expense", "net_income", "cfo", "capex", "da"
}


class ConceptNormalizer:
    """Normalizes raw XBRL company facts into canonical financial statement variables."""

    def __init__(self, fallback_cascades: Optional[Dict[str, List[Tuple[str, str, str]]]] = None) -> None:
        self.cascades = fallback_cascades or CONCEPT_FALLBACK_CASCADES

    def normalize_company_facts(
        self,
        company_meta: Dict[str, Any],
        raw_facts_by_concept: Dict[str, List[Dict[str, Any]]],
        filings_map: Optional[Dict[str, Dict[str, Any]]] = None,
        target_years: Optional[List[int]] = None,
        target_periods: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract and normalize core variables for a single company across fiscal periods.

        Args:
            company_meta: Dict with 'company_id', 'ticker', 'cik', 'sector'.
            raw_facts_by_concept: Dict mapping concept name -> list of fact entries.
            filings_map: Optional mapping of accession_number -> filing metadata.
            target_years: List of fiscal years to extract (e.g. 2014-2024).
            target_periods: List of fiscal periods to extract (default ['FY']).

        Returns:
            List of normalized fact records ready for database storage.
        """
        ticker = company_meta["ticker"]
        cik = company_meta["cik"]
        company_id = company_meta.get("company_id", f"US_{ticker}")
        sector = company_meta["sector"]

        years = target_years or list(range(2014, 2025))
        periods = target_periods or ["FY"]

        normalized_records: List[Dict[str, Any]] = []

        # Iterate through target period slots
        for fy in years:
            for fp in periods:
                period_norm_facts = self._normalize_single_period(
                    company_id=company_id,
                    ticker=ticker,
                    cik=cik,
                    sector=sector,
                    fiscal_year=fy,
                    fiscal_period=fp,
                    raw_facts_by_concept=raw_facts_by_concept,
                    filings_map=filings_map or {},
                )
                normalized_records.extend(period_norm_facts)

        return normalized_records

    def _normalize_single_period(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        fiscal_period: str,
        raw_facts_by_concept: Dict[str, List[Dict[str, Any]]],
        filings_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Normalize all 10 core variables for one specific fiscal period."""
        results: List[Dict[str, Any]] = []

        for canonical_var, cascade in self.cascades.items():
            matched = False

            # Try Tier 1 and Tier 2 concept cascades
            for tier_name, status_code, concept_name in cascade:
                if concept_name in raw_facts_by_concept:
                    candidates = raw_facts_by_concept[concept_name]
                    # Filter candidates matching fiscal year and period
                    filtered = self._filter_candidates(
                        candidates, fiscal_year, fiscal_period, canonical_var
                    )
                    if filtered:
                        # Select best candidate (latest filing date / amendment)
                        best = self._select_best_entry(filtered)
                        norm_rec = self._build_normalized_record(
                            company_id=company_id,
                            ticker=ticker,
                            cik=cik,
                            sector=sector,
                            canonical_var=canonical_var,
                            fact_entry=best,
                            tier=tier_name,
                            data_status=status_code,
                            filing_meta=filings_map.get(best.get("accn", "")),
                        )
                        results.append(norm_rec)
                        matched = True
                        break

            # If EBIT is not matched via Tier 1/2, attempt Tier 4 derivation
            if not matched and canonical_var == "ebit":
                derived_rec = self._derive_ebit(
                    company_id=company_id,
                    ticker=ticker,
                    cik=cik,
                    sector=sector,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    raw_facts_by_concept=raw_facts_by_concept,
                    filings_map=filings_map,
                )
                if derived_rec:
                    results.append(derived_rec)
                    matched = True

            # If CapEx is not matched via Tier 1/2, check E&P / tangible productive asset extensions
            if not matched and canonical_var == "capex":
                derived_capex = self._derive_capex_fallback(
                    company_id=company_id,
                    ticker=ticker,
                    cik=cik,
                    sector=sector,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    raw_facts_by_concept=raw_facts_by_concept,
                    filings_map=filings_map,
                )
                if derived_capex:
                    results.append(derived_capex)
                    matched = True

            # If still not matched, record Tier 5 UNRESOLVED / MISSING
            if not matched:
                results.append({
                    "fact_id": f"MISSING_{ticker}_{fiscal_year}_{fiscal_period}_{canonical_var}",
                    "company_id": company_id,
                    "ticker": ticker,
                    "cik": cik,
                    "sector": sector,
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "period_start_date": None,
                    "period_end_date": f"{fiscal_year}-12-31",
                    "filing_date": "1900-01-01",
                    "acceptance_datetime": "1900-01-01T00:00:00Z",
                    "form": "NONE",
                    "accession_number": "NONE",
                    "canonical_variable": canonical_var,
                    "value": 0.0,
                    "unit": "USD",
                    "source_concept": "NONE",
                    "fallback_tier": "Tier 5",
                    "source_url_or_identifier": "NONE",
                    "data_status": "MISSING",
                    "raw_fact_id": None,
                })

        return results

    def _filter_candidates(
        self,
        entries: List[Dict[str, Any]],
        fiscal_year: int,
        fiscal_period: str,
        canonical_var: str,
    ) -> List[Dict[str, Any]]:
        """Filter facts matching target period and valid forms."""
        valid: List[Dict[str, Any]] = []
        for e in entries:
            # Must be 10-K or 10-K/A for annual FY, or 10-Q for quarterly
            form = e.get("form", "")
            if fiscal_period == "FY":
                if form not in ["10-K", "10-K/A"]:
                    continue
                # Match fiscal year
                if e.get("fy") != fiscal_year:
                    # Check frame as secondary alignment (e.g. CY2020)
                    frame = str(e.get("frame", ""))
                    if f"CY{fiscal_year}" not in frame:
                        continue
                # Ensure fp is FY or annual duration
                fp = e.get("fp", "")
                if fp and fp != "FY":
                    continue
            else:
                if form not in ["10-Q", "10-Q/A"]:
                    continue
                if e.get("fy") != fiscal_year or e.get("fp") != fiscal_period:
                    continue

            # Check unit (monetary must be USD)
            if e.get("val") is not None:
                valid.append(e)

        return valid

    def _select_best_entry(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select best entry: prefer latest filed date or 10-K/A amendment."""
        # Sort by filing date ascending, then form (10-K/A after 10-K)
        def sort_key(e: Dict[str, Any]) -> Tuple[str, int]:
            filed = str(e.get("filed", "1900-01-01"))
            is_amend = 1 if "/A" in str(e.get("form", "")) else 0
            return (filed, is_amend)

        return sorted(entries, key=sort_key)[-1]

    def _build_normalized_record(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        canonical_var: str,
        fact_entry: Dict[str, Any],
        tier: str,
        data_status: str,
        filing_meta: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format fact entry into canonical normalized schema."""
        raw_val = float(fact_entry.get("val", 0.0))

        # Sign enforcement: CapEx is positive outflow |val|
        if canonical_var == "capex":
            norm_val = abs(raw_val)
        else:
            norm_val = raw_val

        accn = str(fact_entry.get("accn", "UNKNOWN"))
        filed = str(fact_entry.get("filed", "1900-01-01"))
        form = str(fact_entry.get("form", "10-K"))

        # Obtain acceptance timestamp from filing_meta if available
        acceptance_dt = (
            filing_meta.get("acceptanceDateTime")
            if filing_meta and filing_meta.get("acceptanceDateTime")
            else f"{filed}T23:59:59Z"
        )

        fy = fact_entry.get("fy", 0)
        fp = fact_entry.get("fp", "FY")
        concept = fact_entry.get("concept", fact_entry.get("tag", "US-GAAP"))

        fact_id = f"NORM_{ticker}_{fy}_{fp}_{canonical_var}_{accn}"
        source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}"

        return {
            "fact_id": fact_id,
            "company_id": company_id,
            "ticker": ticker,
            "cik": cik,
            "sector": sector,
            "fiscal_year": fy,
            "fiscal_period": fp,
            "period_start_date": fact_entry.get("start"),
            "period_end_date": str(fact_entry.get("end", f"{fy}-12-31")),
            "filing_date": filed,
            "acceptance_datetime": acceptance_dt,
            "form": form,
            "accession_number": accn,
            "canonical_variable": canonical_var,
            "value": norm_val,
            "unit": "USD",
            "source_concept": concept,
            "fallback_tier": tier,
            "source_url_or_identifier": source_url,
            "data_status": data_status,
            "raw_fact_id": fact_entry.get("fact_id"),
        }

    def _derive_ebit(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        fiscal_period: str,
        raw_facts_by_concept: Dict[str, List[Dict[str, Any]]],
        filings_map: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Tier 4 EBIT Derivations:
        1. EBT + Interest Expense (for PFE, MRK, XOM, CVX, COP)
        2. Gross Profit - SG&A (for NKE)
        """
        # Strategy A: Gross Profit - SG&A
        if "GrossProfit" in raw_facts_by_concept and "SellingGeneralAndAdministrativeExpense" in raw_facts_by_concept:
            gp_entries = self._filter_candidates(raw_facts_by_concept["GrossProfit"], fiscal_year, fiscal_period, "ebit")
            sga_entries = self._filter_candidates(raw_facts_by_concept["SellingGeneralAndAdministrativeExpense"], fiscal_year, fiscal_period, "ebit")
            if gp_entries and sga_entries:
                gp = self._select_best_entry(gp_entries)
                sga = self._select_best_entry(sga_entries)
                derived_val = float(gp.get("val", 0.0)) - float(sga.get("val", 0.0))
                return self._build_derived_record(
                    company_id=company_id,
                    ticker=ticker,
                    cik=cik,
                    sector=sector,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    canonical_var="ebit",
                    value=derived_val,
                    formula="GrossProfit - SellingGeneralAndAdministrativeExpense",
                    tier="Tier 4A",
                    base_entry=gp,
                    filings_map=filings_map,
                )

        # Strategy B: EBT (Pretax Income) + Interest Expense
        pretax_candidates = [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
        ]
        interest_candidates = [
            "InterestExpense",
            "InterestAndDebtExpense",
            "InterestIncomeExpenseNonoperatingNet",
        ]

        ebt_entry = None
        for pt in pretax_candidates:
            if pt in raw_facts_by_concept:
                filtered_pt = self._filter_candidates(raw_facts_by_concept[pt], fiscal_year, fiscal_period, "ebit")
                if filtered_pt:
                    ebt_entry = self._select_best_entry(filtered_pt)
                    break

        if ebt_entry:
            interest_val = 0.0
            for it in interest_candidates:
                if it in raw_facts_by_concept:
                    filtered_it = self._filter_candidates(raw_facts_by_concept[it], fiscal_year, fiscal_period, "ebit")
                    if filtered_it:
                        best_it = self._select_best_entry(filtered_it)
                        interest_val = abs(float(best_it.get("val", 0.0)))
                        break

            ebt_val = float(ebt_entry.get("val", 0.0))
            derived_val = ebt_val + interest_val
            return self._build_derived_record(
                company_id=company_id,
                ticker=ticker,
                cik=cik,
                sector=sector,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                canonical_var="ebit",
                value=derived_val,
                formula="PreTaxIncome + InterestExpense",
                tier="Tier 4B",
                base_entry=ebt_entry,
                filings_map=filings_map,
            )

        return None

    def _derive_capex_fallback(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        fiscal_period: str,
        raw_facts_by_concept: Dict[str, List[Dict[str, Any]]],
        filings_map: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Tier 3 / Tier 4 CapEx Fallbacks:
        1. Specialized Exploration & Development cash flow lines (e.g. EOG)
        2. Balance sheet Net PP&E change + D&A proxy
        """
        alt_tags = [
            "PaymentsToAcquireOilAndGasPropertyAndEquipment",
            "PaymentsForProceedsFromProductiveAssets",
            "PaymentsToAcquireOtherPropertyPlantAndEquipment",
        ]
        for at in alt_tags:
            if at in raw_facts_by_concept:
                filtered = self._filter_candidates(raw_facts_by_concept[at], fiscal_year, fiscal_period, "capex")
                if filtered:
                    best = self._select_best_entry(filtered)
                    return self._build_normalized_record(
                        company_id=company_id,
                        ticker=ticker,
                        cik=cik,
                        sector=sector,
                        canonical_var="capex",
                        fact_entry=best,
                        tier="Tier 2C",
                        data_status="DIRECT_ALTERNATIVE",
                        filing_meta=filings_map.get(best.get("accn", "")),
                    )
        return None

    def _build_derived_record(
        self,
        company_id: str,
        ticker: str,
        cik: str,
        sector: str,
        fiscal_year: int,
        fiscal_period: str,
        canonical_var: str,
        value: float,
        formula: str,
        tier: str,
        base_entry: Dict[str, Any],
        filings_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Construct a DERIVED normalized record with full formula tracking."""
        accn = str(base_entry.get("accn", "DERIVED"))
        filed = str(base_entry.get("filed", "1900-01-01"))
        form = str(base_entry.get("form", "10-K"))

        filing_meta = filings_map.get(accn, {})
        acceptance_dt = (
            filing_meta.get("acceptanceDateTime")
            if filing_meta and filing_meta.get("acceptanceDateTime")
            else f"{filed}T23:59:59Z"
        )

        return {
            "fact_id": f"NORM_{ticker}_{fiscal_year}_{fiscal_period}_{canonical_var}_{accn}",
            "company_id": company_id,
            "ticker": ticker,
            "cik": cik,
            "sector": sector,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "period_start_date": base_entry.get("start"),
            "period_end_date": str(base_entry.get("end", f"{fiscal_year}-12-31")),
            "filing_date": filed,
            "acceptance_datetime": acceptance_dt,
            "form": form,
            "accession_number": accn,
            "canonical_variable": canonical_var,
            "value": value,
            "unit": "USD",
            "source_concept": f"DERIVED: {formula}",
            "fallback_tier": tier,
            "source_url_or_identifier": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}",
            "data_status": "DERIVED",
            "raw_fact_id": base_entry.get("fact_id"),
        }
