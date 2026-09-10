# Phase 1 Data & Company Universe Audit Report
## AI-Assisted Equity Valuation & Investment Intelligence Platform

**Date:** September 2026  
**Status:** Complete Empirical Audit  
**Phase Verdict:** **GO WITH CONDITIONS**  
**Author:** Antigravity Research Engineering Team  

---

## 1. Executive Summary

This report presents the complete empirical results of **Phase 1: Data & Company Universe Audit** for the independent research project *AI-Assisted Equity Valuation & Investment Intelligence Platform*. Building upon the Phase 0 feasibility design, Phase 1 establishes and locks a defensible 30-company universe of US-listed non-financial corporations, performs an empirical SEC EDGAR/XBRL audit across 10 core financial concepts spanning 2014 to 2024, evaluates revenue behavior around the ASC 606 transition, tests operating income (EBIT) recovery mechanisms for non-standard reporting firms, designs an auditable 5-tier concept fallback cascade, and defines the canonical relational data schema for subsequent research phases.

### Core Empirical Findings
1. **Universe Integrity & Lock:** A 30-company non-financial universe was selected via objective inclusion rules across 6 major GICS sectors (Information Technology, Health Care, Consumer Staples, Consumer Discretionary, Industrials, Energy; 5 firms per sector). All 30 firms are S&P 500 constituents with complete SEC filing histories dating back to the mandatory XBRL inception.
2. **Concept Normalization Success:** The preliminary Phase 0 risk regarding concept divergence (where ~40% of firms lacked a standard `OperatingIncomeLoss` tag) was systematically analyzed. A 5-tier fallback cascade was implemented and verified against all 30 companies:
   - **Revenue:** 23/30 firms report standard post-2018 ASC 606 `RevenueFromContractWithCustomerExcludingAssessedTax`. The remaining 7 firms report standard US-GAAP alternatives (`SalesRevenueNet` or `Revenues`). A 2-tier cascade recovers 100% of revenue series without gaps.
   - **Operating Income (EBIT):** 24/30 firms report standard `OperatingIncomeLoss`. The 6 non-standard firms (PFE, MRK, NKE, XOM, CVX, COP) report multi-step income statements. EBIT is recovered deterministically via Tier 2 pre-tax income plus interest expense ($EBT + InterestExpense$) or Tier 4 derived gross profit minus SG&A ($GP - SGA$), achieving 100% coverage without inventing arbitrary proxies.
   - **Universal Bedrock Concepts:** `NetIncomeLoss`/`ProfitLoss`, `Assets`, `CashAndCashEquivalentsAtCarryingValue`, and `NetCashProvidedByUsedInOperatingActivities` achieve 100% reporting across all 30 firms.
   - **Sector-Specific CapEx:** Exploration and Production (E&P) energy companies (e.g., EOG Resources) report specialized oil & gas property acquisition tags rather than standard PP&E. Similarly, NVIDIA historically used an extension tag (`nvda:PurchasesOfPropertyAndEquipmentAndIntangibleAssets`) before adopting standard productive assets in 2024. Incorporating explicit Tier 2/3 sector mappings achieves complete CapEx recovery.
3. **Historical Coverage:** Across the 11-year target window (2014–2024; 330 firm-years), the average company has 10.0 full usable years across all 10 concepts simultaneously. 20 of 30 firms (66.7%) have 11/11 complete years; 23 of 30 firms (76.7%) have $\ge 10$ complete years. For a common backtesting window of 2018–2024 (7 full fiscal years), data completeness is **100.0%**.
4. **CIK Lineage Audit:** Live SEC ingestion revealed that corporate restructurings (such as ExxonMobil's creation of holding company CIK `0002115436` in 2024) can trap naive API pipelines into empty historical records. Historical continuity requires binding to operating predecessor CIK `0000034088`.

---

## 2. Primary Objective

The objective of Phase 1 is to **establish and lock** a defensible company universe and data schema for the research platform. Specifically, Phase 1 answers:
1. Which 30 US non-financial public companies constitute the primary research universe?
2. Does SEC EDGAR provide machine-readable, reliable historical XBRL facts for them?
3. Can the 10 core financial statement concepts be mapped consistently across sectors without subjective manipulation?
4. Can a multi-tier fallback cascade recover non-standard concepts with economic fidelity?
5. What are the exact criteria and prerequisites for proceeding to Phase 2 (Financial Statement Pipeline)?

---

## 3. Universe Selection Rules

To prevent data snooping, performance bias, and arbitrary selection, the candidate universe was filtered strictly through objective inclusion and exclusion rules prior to testing:

### 3.1 Inclusion Criteria
1. **US Headquartered & Publicly Listed:** Equity traded on NYSE or NASDAQ with SEC reporting obligations under the Securities Exchange Act of 1934.
2. **S&P 500 Historical Constituent:** Member of the S&P 500 index during the historical baseline cohort (2014/2015), guaranteeing institutional reporting rigor, market liquidity, and public analyst coverage.
3. **Non-Financial Business Model:** Operating revenues derived from industrial, commercial, technological, or energy activities.
4. **SEC XBRL Continuity:** Continuous, unbroken series of Form 10-K filings with machine-readable XBRL facts on SEC EDGAR spanning at least fiscal years 2014 to 2024.
5. **Sector Stratification:** Exact allocation of 5 companies per sector across 6 major non-financial sectors to ensure cross-sectional diversity and sector-relative comparability.

### 3.2 Exclusion Criteria
1. **Financial Institutions (GICS 40):** Commercial banks, investment banks, diversified financials, and insurance carriers (e.g., J.P. Morgan, Goldman Sachs, Berkshire Hathaway) are excluded. Financial firms treat interest expense as an operating cost rather than a financing cash flow; Free Cash Flow to Firm (FCFF), Working Capital, and Operating Income cannot be normalized into a standard industrial DCF framework.
2. **Equity Real Estate Investment Trusts (REITs, GICS 60):** Excluded because REIT valuation relies on Funds From Operations (FFO/AFFO) and property-level cap rates rather than industrial FCFF and CapEx.
3. **Recent IPOs & Spin-offs (< 10 Years Continuous Public Reporting):** Firms lacking continuous 10-K history across the 2014–2024 window (e.g., Uber, Airbnb, Carrier, Otis) are excluded to ensure a uniform longitudinal panel.
4. **Hybrid Industrial-Financial Conglomerates with Discontinued Operations:** Firms with massive legacy captive financing arms undergoing three-way breakups (e.g., General Electric) were audited and excluded in favor of pure-play industrial peers (e.g., Lockheed Martin) to avoid structural accounting discontinuities.

---

## 4. Final Locked 30-Company Universe

The final 30-company universe is locked as follows (saved in [`config/universe.yaml`](file:///Users/macbookair/Desktop/project%202/config/universe.yaml) and [`results/tables/phase1_universe_audit.csv`](file:///Users/macbookair/Desktop/project%202/results/tables/phase1_universe_audit.csv)):

| Ticker | CIK | Company Name | GICS Sector | US-GAAP Facts Count | Fiscal Year-End | Locked Status |
| :--- | :--- | :--- | :--- | :---: | :--- | :---: |
| **AAPL** | `0000320193` | Apple Inc. | Information Technology | 503 | Late September (52/53w) | **LOCKED** |
| **MSFT** | `0000789019` | Microsoft Corporation | Information Technology | 446 | June 30 | **LOCKED** |
| **NVDA** | `0001045810` | NVIDIA Corporation | Information Technology | 572 | Late January (52/53w) | **LOCKED** |
| **INTC** | `0000050863` | Intel Corporation | Information Technology | 525 | Late December (52/53w) | **LOCKED** |
| **CSCO** | `0000858877` | Cisco Systems, Inc. | Information Technology | 454 | Late July (52/53w) | **LOCKED** |
| **JNJ** | `0000200406` | Johnson & Johnson | Health Care | 508 | Late December (52/53w) | **LOCKED** |
| **PFE** | `0000078003` | Pfizer Inc. | Health Care | 664 | December 31 | **LOCKED** |
| **ABT** | `0000001800` | Abbott Laboratories | Health Care | 537 | December 31 | **LOCKED** |
| **MRK** | `0000310158` | Merck & Co., Inc. | Health Care | 545 | December 31 | **LOCKED** |
| **TMO** | `0000097745` | Thermo Fisher Scientific Inc. | Health Care | 679 | December 31 | **LOCKED** |
| **WMT** | `0000104169` | Walmart Inc. | Consumer Staples | 433 | January 31 | **LOCKED** |
| **PG** | `0000080424` | Procter & Gamble Co. | Consumer Staples | 480 | June 30 | **LOCKED** |
| **KO** | `0000021344` | The Coca-Cola Company | Consumer Staples | 512 | December 31 | **LOCKED** |
| **PEP** | `0000077476` | PepsiCo, Inc. | Consumer Staples | 526 | Late December (52/53w) | **LOCKED** |
| **COST** | `0000909832` | Costco Wholesale Corporation | Consumer Staples | 382 | Late August (52/53w) | **LOCKED** |
| **AMZN** | `0001018724` | Amazon.com, Inc. | Consumer Discretionary | 464 | December 31 | **LOCKED** |
| **HD** | `0000354950` | Home Depot, Inc. | Consumer Discretionary | 402 | Late January (52/53w) | **LOCKED** |
| **NKE** | `0000320187` | NIKE, Inc. | Consumer Discretionary | 435 | May 31 | **LOCKED** |
| **MCD** | `0000063908` | McDonald's Corporation | Consumer Discretionary | 443 | December 31 | **LOCKED** |
| **LOW** | `0000060667` | Lowe's Companies, Inc. | Consumer Discretionary | 423 | Late January (52/53w) | **LOCKED** |
| **CAT** | `0000018230` | Caterpillar Inc. | Industrials | 569 | December 31 | **LOCKED** |
| **MMM** | `0000066740` | 3M Company | Industrials | 681 | December 31 | **LOCKED** |
| **HON** | `0000773840` | Honeywell International Inc. | Industrials | 572 | December 31 | **LOCKED** |
| **UNP** | `0000100885` | Union Pacific Corporation | Industrials | 386 | December 31 | **LOCKED** |
| **LMT** | `0000936468` | Lockheed Martin Corporation | Industrials | 481 | December 31 | **LOCKED** |
| **XOM** | `0000034088` | Exxon Mobil Corporation | Energy | 438 | December 31 | **LOCKED** |
| **CVX** | `0000093410` | Chevron Corporation | Energy | 451 | December 31 | **LOCKED** |
| **COP** | `0001163165` | ConocoPhillips | Energy | 469 | December 31 | **LOCKED** |
| **SLB** | `0000087347` | SLB Limited | Energy | 473 | December 31 | **LOCKED** |
| **EOG** | `0000821189` | EOG Resources, Inc. | Energy | 478 | December 31 | **LOCKED** |

---

## 5. Data Source Audit

All financial statement data is audited from primary public sources.

| Source Domain | Endpoint | Authentication | Rate Limit | Verified Historical Depth | Known Limitations |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **SEC Submissions API** | `https://data.sec.gov/submissions/CIK{cik}.json` | User-Agent header | 10 req / sec | 2000–present | Recent 1,000 filings in primary payload; older filings paginated. |
| **SEC Company Facts API** | `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | User-Agent header | 10 req / sec | 2009–present | Exposes standard US-GAAP/DEI taxonomies. Custom company extensions omitted. |
| **SEC Primary Archives** | `https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}` | User-Agent header | 10 req / sec | 1994–present | Full iXBRL/HTML documents (2–15 MB). Requires DOM/HTML parsing for custom tags. |
| **US Treasury Yields** | `https://home.treasury.gov/...daily_treasury_yield_curve...csv` | None (Public Domain) | Unmetered | 1990–present | Annual CSV format; requires standardized date parsing. |
| **Tiingo Market Data** | `https://api.tiingo.com/tiingo/daily/{ticker}/prices` | Free API Key | 1,000 req / day | 1990–present | Raw redistribution forbidden; local caching mandatory. |

---

## 6. SEC API & Concept Audit

For all 30 companies, 10 core financial statement concepts were audited:
1. **Revenue**
2. **Operating Income / EBIT Proxy**
3. **Net Income**
4. **Cash and Cash Equivalents**
5. **Total Long-Term Debt**
6. **Total Assets**
7. **Total Equity**
8. **Cash Flow from Operations (CFO)**
9. **Capital Expenditures (CapEx)**
10. **Depreciation & Amortization (D&A)**

The audit evaluated concept frequency, tag stability across fiscal years, unit conventions, and statement locations.

---

## 7. Revenue / ASC 606 Audit Findings

Accounting Standards Codification (ASC) Topic 606 took effect for annual reporting periods beginning after December 15, 2017. The audit reveals the following empirical structure across the 30 firms:

```
Tag Pattern                                         | Firms Count | Representative Companies
----------------------------------------------------+-------------+----------------------------------------------
Shifted from SalesRevenueNet to ASC 606             | 18 / 30     | AAPL, MSFT, INTC, CSCO, ABT, WMT, AMZN, HD...
Reported Revenues continuously (both pre & post)    | 4 / 30      | MRK, MCD, CAT, EOG
Shifted from SalesRevenueNet to Revenues            | 3 / 30      | PG, KO, PEP
Dual reporting (Revenues overarching + ASC 606)     | 5 / 30      | XOM, CVX, COP, SLB, UNP
```

### Deterministic Revenue Normalization Policy
- **Primary Preference:** Query `RevenueFromContractWithCustomerExcludingAssessedTax` (ASC 606).
- **Secondary Fallback:** If missing (as in pre-2018 periods or Caterpillar/Merck), query `SalesRevenueNet`, then `Revenues`.
- **Economic Consistency:** All three tags represent top-line operating revenues from core business transactions before operating expenses. No firm in the 30-company universe has missing revenue in any year between 2014 and 2024 under this 2-tier cascade.

---

## 8. Operating Income / EBIT Audit Findings

In Phase 0, approximately 40% of non-financial firms appeared to lack an `OperatingIncomeLoss` tag. Phase 1 systematically analyzed the root accounting causes:

### 8.1 The 6 Non-Standard Reporting Firms
1. **Pfizer (PFE) & Merck (MRK):** Present multi-step pharmaceutical income statements grouping R&D, restructuring, and collaboration income, moving directly from gross margin components to Pre-tax Income (`IncomeLossFromContinuingOperationsBeforeIncomeTaxes...`).
2. **ExxonMobil (XOM), Chevron (CVX), ConocoPhillips (COP):** Integrated oil & gas statements categorize expenses into production taxes, exploration expenses, and crude purchases, reporting pre-tax segment earnings rather than a single line labeled "Operating Income."
3. **Nike (NKE):** Uses a multi-step consumer apparel format reporting `GrossProfit` and `SellingGeneralAndAdministrativeExpense`, omitting consolidated operating income as a separate tag in certain historical years.

### 8.2 Recovery Verification
- **Tier 2 Recovery (EBT + Interest Expense):**
  $$EBIT_{\text{proxy}} = \text{PreTaxIncome} + \text{InterestExpense}$$
  Verified for PFE, MRK, XOM, CVX, and COP. This recovers 100% of missing EBIT observations with full economic validity (operating profit before capital structure financing costs).
- **Tier 4 Recovery (Gross Profit - Operating Expenses):**
  $$EBIT_{\text{derived}} = \text{GrossProfit} - \text{SellingGeneralAndAdministrativeExpense}$$
  Verified for Nike. For example, in FY2024: $\text{GP } (\$22.887\text{B}) - \text{SGA } (\$16.576\text{B}) = \text{Derived EBIT } \$6.311\text{B}$.

---

## 9. Multi-Tier Fallback Cascade Design

Every financial concept is governed by an auditable, 5-tier fallback hierarchy (saved in [`results/tables/phase1_concept_mapping.csv`](file:///Users/macbookair/Desktop/project%202/results/tables/phase1_concept_mapping.csv)):

```
Tier 1: Standard US-GAAP XBRL concept (universal standard)
        |
Tier 2: Known alternative standard concept (e.g., SalesRevenueNet, ProfitLoss, ProductiveAssets)
        |
Tier 3: Company-specific extension tag with verified 1-to-1 economic mapping (e.g., NVDA capex)
        |
Tier 4: Derived value calculated strictly from standard accounting identities (e.g., EBT + Interest, GP - SGA)
        |
Tier 5: UNRESOLVED — Do not silently substitute. Log error and flag observation.
```

### Complete Concept Mapping Hierarchy

| Variable | Tier 1 (Preferred) | Tier 2 (Alternative) | Tier 3 (Extension) | Tier 4 (Derived) | Tier 5 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Revenue** | `RevenueFromContract...` | `SalesRevenueNet`, `Revenues` | None | None | `UNRESOLVED` |
| **EBIT** | `OperatingIncomeLoss` | `IncomeLossFromContinuing...` | None | `EBT + Interest` or `GP - SGA` | `UNRESOLVED` |
| **Net Income** | `NetIncomeLoss` | `ProfitLoss`, `NetIncomeAvailable...` | None | None | `UNRESOLVED` |
| **Cash** | `CashAndCashEquivalents...` | `CashCashEquivalentsRestricted...` | None | None | `UNRESOLVED` |
| **Debt (Long)** | `LongTermDebtNoncurrent` | `LongTermDebt`, `...CapitalLeases` | None | None | `UNRESOLVED` |
| **Assets** | `Assets` | None | None | None | `UNRESOLVED` |
| **Equity** | `StockholdersEquity` | `...IncludingPortionNoncontrolling` | None | None | `UNRESOLVED` |
| **CFO** | `NetCashProvidedByUsed...` | `...ContinuingOperations` | None | None | `UNRESOLVED` |
| **CapEx** | `PaymentsToAcquirePPE` | `PaymentsToAcquireProductiveAssets`, `...OilAndGasProperty` | `nvda:PurchasesOfProperty...` | $\Delta PP\&E + D\&A$ | `UNRESOLVED` |
| **D&A** | `DepreciationDepletion...` | `DepreciationAndAmortization`, `Depreciation` | None | None | `UNRESOLVED` |

---

## 10. Period & Fiscal-Year Audit Findings

### 10.1 Fiscal Calendar Heterogeneity
Out of the 30 companies:
- **20 companies (66.7%)** operate on standard **Calendar Fiscal Years** ending December 31.
- **10 companies (33.3%)** operate on **Non-Calendar Fiscal Years** or floating **52/53-week retail calendars**:
  - January 31 / Floating Sunday: Walmart (`WMT`), Home Depot (`HD`), Lowe's (`LOW`), NVIDIA (`NVDA`).
  - June 30: Microsoft (`MSFT`), Procter & Gamble (`PG`).
  - May 31: Nike (`NKE`).
  - July / August / September: Cisco (`CSCO`, July), Costco (`COST`, August), Apple (`AAPL`, September).

### 10.2 Canonical Point-in-Time Temporal Representation
To prevent look-ahead bias across asynchronous fiscal calendars, every record must store both temporal anchors:
1. `fiscal_period_end`: The accounting date when the fiscal period ended (e.g., `2024-01-28`).
2. `acceptance_datetime`: The exact UTC timestamp when the filing became public on SEC EDGAR (e.g., `2024-02-21T16:30:15Z`).
3. **Rule:** For any historical valuation date $T_{val}$, a filing is admissible if and only if $\text{acceptance\_datetime} \le T_{val}$.

---

## 11. Restatements, Amendments & Duplicates Audit

### 11.1 Empirical Audit of Duplicate Facts
Across the 30 companies and 10 core concepts, instances where multiple entries share the exact same `(cik, concept, period_end, unit)` were analyzed:
- In core balance sheet and net income concepts, fewer than 3.3% of annual observations underwent retrospective restatement.
- When amendments occur (e.g., Form 10-K/A), SEC EDGAR archives both filings with distinct `acceptanceDateTime` timestamps and accession numbers.

### 11.2 Ingestion Resolution Rules
1. **As-of-Date Priority Rule:** When querying as of $T_{val}$, select the entry with the highest `acceptanceDateTime` subject to $\text{acceptanceDateTime} \le T_{val}$.
2. **Amendment Policy:** A 10-K/A filed after $T_{val}$ is **strictly ignored** during an as-of $T_{val}$ backtest.
3. **Same-Day Duplicates:** If two entries have the identical filing date, select the entry with form `10-K/A` over `10-K`, or order by accession number descending.

---

## 12. Unit, Sign & Scale Audit Findings

1. **Units:** In SEC company facts, all financial statement line items are reported in `USD`, share counts in `shares`, per-share ratios in `USD/shares`, and ratios in `pure`. The schema explicitly validates that monetary variables match `unit == "USD"`.
2. **Scale:** All values in the SEC JSON API are stored as **exact, unscaled integer/floating values**. For example, Walmart's FY2024 revenue is stored as `567762000000`, not `567.76` or in thousands.
3. **Sign Conventions:**
   - **CapEx:** US-GAAP cash outflows on the cash flow statement are reported as positive amounts in XBRL (`PaymentsToAcquire...`). The normalization engine enforces an absolute value transformation: $\text{CapEx} = |\text{val}|$.
   - **Operating Cash Flow:** Operating cash generation is positive; cash burn is negative.
   - **Net Income & EBIT:** Positive for net profits, negative for operating/net losses.

---

## 13. Historical Coverage Matrix

The coverage matrix evaluates all 30 companies across the 11-year window (2014–2024; saved in [`results/tables/phase1_coverage_matrix.csv`](file:///Users/macbookair/Desktop/project%202/results/tables/phase1_coverage_matrix.csv)):

```
Usable Years Distribution (2014-2024) Across 30 Companies:
============================================================
11 / 11 Years Complete (100%):  20 / 30 Companies (66.7%)
>= 10 Years Complete:           23 / 30 Companies (76.7%)
>= 8 Years Complete:            24 / 30 Companies (80.0%)
>= 7 Years Complete (Minimum):  30 / 30 Companies (100.0%)
------------------------------------------------------------
Mean Usable Years:              10.00 out of 11.00 Years
```

### Common Feasible Historical Backtesting Windows
- **Full Window (2014–2024 — 11 Years):** 20 companies have 100% complete data; remaining 10 companies have 7–10 usable years (primarily due to early XBRL tagging transitions in 2014–2016).
- **Core Recommended Window (2018–2024 — 7 Years):** **100.0% completeness** across all 30 companies and all 10 concepts. Every company has unbroken financial statements post-ASC 606.

---

## 14. Market Data Feasibility Audit

| Parameter | Feasibility Status | Source & Method | Licensing & Redistribution |
| :--- | :---: | :--- | :--- |
| **Historical Daily Close** | **VERIFIED** | Tiingo API / yfinance fallback | Free developer tier (500 symbols). Local cache only; gitignore raw files. |
| **Adjusted Close (Splits/Divs)** | **VERIFIED** | Tiingo adjusted price series | Permitted for personal/academic analysis. |
| **Shares Outstanding** | **VERIFIED** | SEC EDGAR `dei:EntityCommonStockSharesOutstanding` | **Public Domain (US Gov).** 100% reproducible directly from filings. |
| **Market Capitalization** | **VERIFIED** | Deterministic: $\text{Price}_t \times \text{Shares}_t$ | Fully auditable and reproducible. |

*GitHub Policy:* Raw vendor market price feeds must be gitignored in `data/market/`. The repository will provide an automated fetch script (`scripts/fetch_market_data.py`) allowing any researcher to populate the local cache using a free developer API key.

---

## 15. US Treasury / Risk-Free Rate Feasibility

- **Source:** US Department of the Treasury (`home.treasury.gov`).
- **Endpoint:** Direct CSV download of Daily Treasury Par Yield Curve.
- **Licensing:** **Public Domain (US Government Work, 17 U.S.C. § 105).** Zero licensing or redistribution restrictions.
- **Coverage:** Daily par yields from 1990 to present across 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y maturities.
- **Maturity Benchmark:** The **10-Year Treasury Yield** is confirmed as the standard benchmark for WACC and DCF valuation.

---

## 16. Canonical Relational Data Schema

The canonical normalized dataset is structured into a minimal relational schema:

```sql
-- Canonical Financial Facts Schema (DuckDB / SQLite)
CREATE TABLE canonical_financial_facts (
    fact_id               VARCHAR PRIMARY KEY,
    ticker                VARCHAR(10) NOT NULL,
    cik                   VARCHAR(10) NOT NULL,
    sector                VARCHAR(50) NOT NULL,
    fiscal_year           INTEGER NOT NULL,
    fiscal_period         VARCHAR(10) NOT NULL,     -- 'FY', 'Q1', 'Q2', 'Q3'
    period_end_date       DATE NOT NULL,
    filing_date           DATE NOT NULL,
    acceptance_datetime   TIMESTAMP WITH TIME ZONE NOT NULL,
    form_type             VARCHAR(10) NOT NULL,     -- '10-K', '10-Q', '10-K/A'
    accession_number      VARCHAR(25) NOT NULL,
    canonical_variable    VARCHAR(50) NOT NULL,     -- 'revenue', 'ebit', 'net_income'...
    value                 DOUBLE NOT NULL,
    unit                  VARCHAR(10) NOT NULL,     -- 'USD', 'shares'
    source_concept        VARCHAR(120) NOT NULL,
    fallback_tier         VARCHAR(20) NOT NULL,     -- 'Tier 1', 'Tier 2A', 'Tier 4'...
    data_quality_status   VARCHAR(30) NOT NULL      -- 'DIRECT_STANDARD', 'DERIVED'...
);
```

---

## 17. Data Quality Statuses & Permitted Usage

To ensure academic defensibility, every extracted variable is stamped with an explicit quality status:

| Data Quality Status | Definition | Permitted in Valuation Engine? | Permitted in Econometric Tests? |
| :--- | :--- | :---: | :---: |
| `DIRECT_STANDARD` | Concept matched Tier 1 standard US-GAAP tag | **YES** | **YES** |
| `DIRECT_ALTERNATIVE`| Concept matched Tier 2 known standard alternative | **YES** | **YES** |
| `EXTENSION_MAPPED` | Concept matched Tier 3 extension tag with verified mapping | **YES** (with audit flag) | **YES** |
| `DERIVED` | Value mathematically derived from standard accounting identity | **YES** (with formula log) | **YES** |
| `UNRESOLVED` | Concept missing; no valid fallback exists | **NO** (Blocks valuation) | **NO** |
| `AMBIGUOUS` | Multiple conflicting values with equal priority | **NO** (Requires human audit) | **NO** |

---

## 18. Universe Stress Test Results

To deliberately challenge universe stability, extreme edge cases were evaluated:
1. **Worst Concept Divergence:** Integrated Energy firms (XOM, CVX, COP) and Pharma firms (PFE, MRK) lack direct `OperatingIncomeLoss`.  
   *Result:* Successfully resolved via Tier 2 ($EBT + InterestExpense$) without data loss.
2. **Most Fallback-Heavy Company:** NVIDIA (`NVDA`). Required Tier 3 company extension mapping for pre-2024 CapEx.  
   *Result:* Reconciled with primary 10-K instance documents and cross-verified against derived balance sheet changes.
3. **Most Complex Fiscal Calendar:** Walmart (`WMT`), Home Depot (`HD`), and NVIDIA (`NVDA`) follow 52/53-week retail calendars with fiscal years ending in late January or floating Sundays.  
   *Result:* Canonical schema handles non-calendar dates via explicit `period_end_date` and `acceptance_datetime` pairing.
4. **CIK Lineage Anomaly:** ExxonMobil created holding company CIK `0002115436` in 2024 while historical filings reside in CIK `0000034088`.  
   *Result:* CIK `0000034088` locked in universe registry to ensure unbroken 10-year continuity.

---

## 19. Risks & Mitigations

| Risk | Probability | Impact | Mitigation Strategy | Phase 2 Gate Criterion |
| :--- | :---: | :---: | :--- | :--- |
| **1. SEC Concept Inconsistencies** | Low | High | 5-tier fallback cascade with strict logging. | $\ge 98\%$ data completeness on normalized statements. |
| **2. Look-Ahead Bias / Leakage** | Med | Critical | As-of-date filtering on `acceptance_datetime <= T_val`. | Automated leakage unit test passes. |
| **3. Non-Standard CapEx in E&P** | Med | Med | Mapped E&P property acquisition tags. | 100% CapEx recovery across all 5 energy firms. |
| **4. Market Data Scraping Brittleness** | Med | Med | Tiingo official API with local SQLite/Parquet caching. | Automated script populates price history. |

---

## 20. Automated Test Results

Lightweight Phase 1 audit unit tests were implemented in [`tests/test_phase1_audit.py`](file:///Users/macbookair/Desktop/project%202/tests/test_phase1_audit.py):
```bash
python3 -m unittest discover tests
```
- `test_universe_completeness_and_uniqueness`: **PASS** (30 unique tickers, 10-digit CIKs, 6 valid non-financial sectors).
- `test_concept_mapping_integrity`: **PASS** (All 10 concepts mapped, valid tiers, units in USD, detailed economic rationales).
- `test_coverage_matrix_thresholds`: **PASS** (All 30 firms evaluated, usable years $\ge 7$, status PASS).

---

## 21. Phase 1 Go / No-Go Decision

### Verdict: **GO WITH CONDITIONS**

### Strongest Evidence
1. **100% Concept Recovery:** Through the 5-tier fallback cascade, all 10 core financial concepts are recoverable across all 30 companies without introducing economically invalid substitutions.
2. **Unbroken Post-2018 Data Panel:** For the 2018–2024 window, data completeness is **100.0%** across all 300 firm-year-concept observations.
3. **Public-Domain Grounding:** All financial facts and Treasury yields are obtained directly from official US government sources (SEC EDGAR and Treasury.gov) with zero licensing or redistribution friction.

### Biggest Remaining Risk
**Restatement Handling in Automated Ingestion:** Ensuring the Phase 2 database ingestion pipeline correctly enforces point-in-time filtering on SEC `acceptanceDateTime` to guarantee that amended filings (10-K/A) do not leak future information into historical valuation dates.

### Exact Next Step
Proceed to **Phase 2 (Financial Statement Pipeline)**:
1. Implement the rate-limited SEC EDGAR ingestion client (`src/data/sec_client.py`).
2. Build the DuckDB database tables according to the canonical schema.
3. Populate raw financial facts for all 30 companies and verify automated ingestion without manual intervention.

---

## 22. Exact Phase 2 Prerequisites

Before executing Phase 2:
1. Lock [`config/universe.yaml`](file:///Users/macbookair/Desktop/project%202/config/universe.yaml) as the immutable 30-company registry.
2. Embed the 5-tier concept priority cascade into the normalization configuration.
3. Verify that the DuckDB relational schema enforces point-in-time timestamp constraints.
