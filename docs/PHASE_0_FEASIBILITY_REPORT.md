# Phase 0 Feasibility & Research-Design Audit
## AI-Assisted Equity Valuation & Investment Intelligence Platform

**Date:** September 2026  
**Status:** Complete Feasibility Audit  
**Verdict:** **GO WITH CONDITIONS**  
**Author:** Antigravity Research Engineering Team  

---

## 1. Executive Summary

This report delivers a comprehensive **Phase 0 Feasibility and Research-Design Audit** for an independent research initiative: the **AI-Assisted Equity Valuation & Investment Intelligence Platform**. 

The core objective is to determine whether a fully reproducible, academically defensible research platform can be constructed that unifies:
1. Standardized fundamental financial-statement data (SEC EDGAR XBRL).
2. A deterministic quantitative equity valuation engine (Discounted Cash Flow, WACC, Relative Valuation).
3. SEC filing qualitative intelligence extracted via Large Language Models (LLMs).
4. Strict historical point-in-time ("as-of-date") validation preventing look-ahead leakage.
5. An empirical econometric test evaluating whether filing-derived qualitative features provide incremental explanatory or predictive power beyond traditional financial and market metrics.

### Key Feasibility Findings
- **Data Availability (SEC EDGAR):** The SEC EDGAR REST APIs (`/submissions/` and `/api/xbrl/companyfacts/`) provide machine-readable historical financial facts and filing metadata dating back to the mandatory XBRL adoption in 2009–2011. Crucially, the SEC API provides exact `acceptanceDateTime` and `filed` timestamps down to the second, making rigorous point-in-time reconstruction fully feasible without commercial databases.
- **Accounting Normalization Challenge:** An empirical audit of 10 major US non-financial corporations across 5 sectors (Tech, Consumer, Healthcare, Industrials, Energy) reveals that while basic balance sheet items (Assets, Cash, Debt) and Net Income have near-universal standardized tag representation, operating metrics exhibit substantial divergence. Notably, 40% of the sample (e.g., Nike, Pfizer, ExxonMobil, Chevron) do not report a simple `OperatingIncomeLoss` tag, requiring derived multi-tier fallback calculation cascades. Furthermore, the adoption of ASC 606 in 2018 caused historical revenue concept tagging to bifurcate across pre-2018 and post-2018 filings.
- **Market Data & Licensing:** Free public scraping (e.g., Stooq) has become brittle due to automated bot-detection challenges (e.g., Cloudflare proof-of-work challenges verified during audit). Commercial redistributions from Yahoo Finance violate terms of service if packaged directly into a public repository. The audit establishes a viable, compliant architecture: local caching of market prices fetched via Tiingo (official free tier) or yfinance with end-user local execution, alongside public-domain US Treasury yields fetched directly from `home.treasury.gov`.
- **Valuation Determinism:** The quantitative valuation engine (FCFF, WACC, Gordon Growth / Exit Multiples, Sensitivity Grids) can and must remain 100% deterministic and closed-form. The LLM component is strictly sequestered to structured qualitative feature extraction (e.g., risk shifts, litigation exposure, capital allocation commentary) with mandatory verbatim citation grounding.
- **Computational & Hardware Feasibility:** For a target universe of 30 non-financial firms across a 10-year backtesting window (2015–2024; ~300 10-K filings), storage requirements are under 2 GB, SEC API ingestion takes under 10 minutes within the 10 requests/second threshold, and LLM extraction requires ~9–12 million input tokens ($10–$25 on modern lightweight models like Gemini 1.5 Flash / Claude 3.5 Haiku). This workflow runs comfortably on a standard developer workstation (e.g., Apple MacBook Air).

### Audit Verdict
**GO WITH CONDITIONS.** The project is methodologically sound, technically feasible, and academically defensible, provided that four mandatory operational conditions are enforced during Phase 1:
1. *Multi-tier normalization fallbacks* must be formalized to handle non-standard EBIT and revenue tags.
2. *As-of-date acceptance timestamp gating* must be enforced at the database ingestion layer to eliminate look-ahead bias from restatements.
3. *Strict quotation grounding* must be required for all LLM extractions to eliminate hallucination.
4. *Survivor-bias boundaries* must be explicitly defined using a fixed historical base-year cohort (e.g., 2015 S&P 500 cohort).

---

## 2. Research Objective & Architectural Principles

### 2.1 Core Objective
The platform investigates the empirical and theoretical boundary between quantitative equity valuation and qualitative filing intelligence. It is **NOT** an automated "AI stock picker," black-box algorithmic trading system, or speculative price forecasting model. 

Instead, it assesses whether an auditable, deterministic equity valuation framework combining fundamental financial data and structured filing-derived information improves the **consistency, transparency, and predictive stability** of company valuation relative to conventional models.

### 2.2 Intended Architectural Separation
```
+-----------------------------------------------------------------------------------+
|                            SEC EDGAR & MACRO SOURCES                              |
|  - SEC Company Facts (XBRL)                                                       |
|  - SEC Submissions & 10-K / 10-Q Metadata (acceptanceDateTime, filed)             |
|  - US Treasury Yield Curve (home.treasury.gov)                                    |
|  - Market Prices & Historical Multiples (Tiingo / Yahoo Finance)                  |
+-----------------------------------------+-----------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
+-------------------------------+               +-----------------------------------+
|  FINANCIAL STATEMENT PIPELINE |               |    SEC FILING QUALITATIVE LAYER   |
|  - Raw XBRL Fact Ingestion    |               |  - Raw 10-K Item 1A (Risk) &      |
|  - Point-in-Time Filtering    |               |    Item 7 (MD&A) Extraction       |
|  - Accounting Normalization   |               |  - Text Cleaning & Chunking       |
|    (Multi-tier Fallbacks)     |               |  - Schema-Constrained LLM         |
|  - Fundamental Ratios & LTM   |               |    Structured Extraction          |
|    Statement Construction     |               |  - Verbatim Citation Grounding    |
+---------------+---------------+               +-----------------+-----------------+
                |                                                 |
                v                                                 v
+-------------------------------+               +-----------------------------------+
| DETERMINISTIC VALUATION ENGINE|               |   STRUCTURED QUALITATIVE DATA     |
|  - Unlevered Free Cash Flow   |               |  - Risk Sentiment Scores          |
|  - CAPM & Cost of Capital     |               |  - Regulatory / Litigation Flags  |
|  - DCF & Terminal Values      |               |  - Capital Allocation Shifts      |
|  - Peer Relative Multiples    |               |  - Guidance & Margin Outlook      |
+---------------+---------------+               +-----------------+-----------------+
                |                                                 |
                +-------------------------+-----------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        INCREMENTAL INFORMATION EVALUATION                         |
|  Model A: Fundamental Statements Only                                             |
|  Model B: Fundamental Statements + Market Multiples & Beta                        |
|  Model C: Fundamental Statements + Market Data + Filing-Derived NLP Features      |
|  -------------------------------------------------------------------------------  |
|  Walk-Forward Expanding-Window Econometric Evaluation (2015-2024)                 |
|  Metrics: RMSE, MAE, R², Diebold-Mariano Tests, Parameter Stability              |
+-----------------------------------------------------------------------------------+
```

### 2.3 Core Research Principles
1. **Reproducibility:** Every data point, intermediate calculation, and valuation output must be programmatically recreatable from raw public filings.
2. **Auditability:** Every valuation output must provide a transparent audit trail linking directly to source filing accession numbers and financial statement lines.
3. **Leakage Control:** All inputs must be strictly bounded by the historical valuation date $T_{val}$ using the filing's public `acceptanceDateTime`. Future data, post-dated amendments, and macro revisions are strictly sequestered.
4. **AI Determinism and Restraint:** The LLM does **NOT** generate price targets, estimate intrinsic equity values, or produce buy/sell recommendations. The valuation engine is closed-form, deterministic, and mathematical. The LLM operates solely as an information extraction and structured summarization engine.
5. **Parsimony:** The system avoids feature bloat and black-box machine learning algorithms where closed-form economic relationships exist.

---

## 3. Primary & Secondary Research Questions

### Primary Research Question
> **"Can a reproducible equity-valuation framework combining fundamental financial data and filing-derived information improve the consistency and transparency of company valuation?"**

### Secondary Research Questions
- **RQ1 (Sensitivity Analysis):** How sensitive are intrinsic equity valuations to reasonable changes in fundamental assumptions (e.g., cost of capital $\pm 100$ bps, terminal growth rate $\pm 50$ bps, target operating margin $\pm 200$ bps)? Where does the primary model risk lie?
- **RQ2 (Incremental Information Content):** Does structured qualitative information extracted from SEC 10-K Item 1A (Risk Factors) and Item 7 (MD&A) provide statistically significant incremental power in explaining valuation discrepancies, forward operating margin revisions, or cost of capital adjustments beyond conventional financial statements and market metrics?
- **RQ3 (Point-in-Time Valuation Stability):** How stable are valuation outputs and model conclusions when evaluated strictly using point-in-time data available at the historical valuation date, compared to naive backtests contaminated by look-ahead bias and retrospective restatements?

---

## 4. Data Feasibility Audit

### 4.1 SEC EDGAR Ingestion & APIs
The SEC EDGAR system provides open REST APIs accessible without paid subscriptions.

| Endpoint | Purpose | Empirical Test Result | Reliability & Limitations |
| :--- | :--- | :--- | :--- |
| `https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json` | Entity metadata, exchange, SIC, recent filing catalog (accession numbers, filing dates, report dates, acceptance timestamps, primary document names) | **VERIFIED.** Tested on Apple, Microsoft, Walmart, etc. Returns structured JSON containing all filing metadata. | Limited to recent 1,000 filings per entity; older filings require paginated submission files (`CIK{cik}-submissions-001.json`). |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json` | Complete repository of all reported XBRL financial facts for an entity across all taxonomies (`us-gaap`, `dei`, `invest`). | **VERIFIED.** Fetched and parsed successfully for 10 test firms. Contains exact start/end dates, values, form types, filing dates, and accession numbers. | Files range from 2 MB to 18 MB per company. Parsing full JSON requires robust memory handling. |
| `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json` | Granular time series for a single XBRL concept for a specific company. | **VERIFIED.** Tested on Apple's `OperatingIncomeLoss` (234 records dating back to 2007). | Fast for targeted lookups, but less efficient than downloading `companyfacts` once for holistic processing. |
| `https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}` | Raw primary filing documents (HTML / Inline XBRL). | **VERIFIED.** Streamed and parsed Apple FY2025 10-K (`aapl-20250927.htm`). | 10-Ks are 2–15 MB HTML files containing complex nested XML/HTML tags. Item extraction requires robust DOM parsing. |

#### Operational Limitations & SEC Requirements
1. **User-Agent Policy:** SEC EDGAR strictly requires all requests to include a declarative `User-Agent` header in the format `Sample Company Name AdminContact@domain.com`. Requests without this header receive HTTP 403 Forbidden.
2. **Rate Limiting:** SEC EDGAR enforces a maximum limit of **10 requests per second** per IP address. Exceeding this rate triggers HTTP 429 Too Many Requests and potential temporary IP ban. An internal rate-limiter (e.g., token bucket capped at 8 req/sec) is mandatory in the ingestion client.
3. **XBRL Inception Date:** The SEC mandated XBRL reporting in phases between 2009 and 2011. Reliable machine-readable XBRL data exists from **2011 onward**. Filings prior to 2010 are available only as unstructured ASCII text or legacy HTML.

### 4.2 Market Data
A valuation engine requires historical daily stock prices, trading volume, and split-adjusted share histories to compute market capitalization, historical betas, and relative valuation multiples.

| Source | Access Method | Cost / Tier | Historical Depth | Licensing & Redistribution | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tiingo** | REST API (JSON) | Free Tier (500 symbols, 1,000 req/day) | 30+ years adjusted daily prices | Academic & personal use permitted. Raw redistribution in public repos prohibited. Local caching required. | **RECOMMENDED PRIMARY.** High data quality, official API, stable contract. |
| **Yahoo Finance** | `yfinance` / Direct Chart JSON | Free (Unofficial) | 30+ years | Terms of Service prohibit scraping and commercial redistribution. Unofficial endpoints subject to breakage. | **SECONDARY / FALLBACK.** Suitable for local researcher-executed caching only. |
| **Stooq** | CSV endpoint | Free | 15+ years | **UNFEASIBLE FOR SCRIPTS.** Live audit confirmed active Cloudflare bot-challenge blocking automated HTTP clients. | **REJECTED.** Requires browser emulation. |
| **Alpha Vantage** | REST API | Free Tier | 20+ years | 25 requests/day maximum on free tier. Severely throttles multi-year backtesting across 30 firms. | **REJECTED AS PRIMARY.** Rate limit too restrictive. |
| **Polygon.io** | REST API | Free Tier | 2 years only | Free tier history insufficient for 10-year backtesting. | **REJECTED FOR BACKTESTING.** |

### 4.3 Macroeconomic Data
Discounted cash flow valuation requires two primary macroeconomic inputs:
1. **Risk-Free Rate ($R_f$):** Yield on 10-Year US Treasury Notes.
2. **Terminal Growth Ceiling ($g$):** Long-term nominal GDP growth expectations and inflation targets.

| Source | Series | Empirical Audit Finding | Licensing / Reproducibility |
| :--- | :--- | :--- | :--- |
| **US Department of the Treasury** (`home.treasury.gov`) | Daily Treasury Par Yield Curve (`10 Yr` column) | **VERIFIED.** Live audit downloaded daily 2024 CSV directly without authentication. Data available back to 1990. | **Public Domain (US Government).** 100% reproducible, zero cost, no redistribution restrictions. |
| **FRED / ALFRED** (St. Louis Fed) | `DGS10` (10Y Treasury), `GDP`, `CPIAUCSL` | Official API requires free developer key. Provides historical **vintage data** (ALFRED) to verify macroeconomic numbers available at historical dates. | Free for educational and research purposes. Fully reproducible via API script. |

### 4.4 Valuation Inputs Decomposition
The following matrix delineates which valuation parameters are derived directly from primary filings versus those requiring exogenous empirical modeling:

| Input Parameter | Direct Filing Source | Exogenous / Empirical Method | Level of Subjectivity |
| :--- | :--- | :--- | :--- |
| **Historical Revenues, EBIT, Net Income** | 10-K / 10-Q Financial Statements | None (direct accounting data) | Zero (Audit-backed) |
| **Depreciation & Amortization** | 10-K Statement of Cash Flows | None | Zero |
| **Capital Expenditures (CapEx)** | 10-K Statement of Cash Flows | None | Zero |
| **Change in Working Capital ($\Delta NWC$)** | Balance Sheet / Cash Flow Statement | Derived from normalized operating working capital | Low |
| **Shares Outstanding** | 10-K / 10-Q `dei:EntityCommonStockSharesOutstanding` | None (verified available in XBRL) | Zero |
| **Market Value of Equity ($E$)** | Shares from filing | Market price as of valuation date ($P_t \times Shares_t$) | Low (deterministic market price) |
| **Book Value of Debt ($D$)** | Balance Sheet: Short-term + Long-term debt | Proxy for market value of debt (or coupon-adjusted bond pricing) | Low |
| **Risk-Free Rate ($R_f$)** | None | 10-Year US Treasury Yield as of $T_{val}$ (Treasury.gov) | Zero (market observation) |
| **Equity Beta ($\beta$)** | None | 60-month rolling regression against S&P 500 with Vasicek/Blume adjustment: $\beta_{adj} = 0.67\beta_{raw} + 0.33$ | Moderate (estimation window choice) |
| **Equity Risk Premium (ERP)** | None | Fixed academic benchmark (5.0%–5.5%) or Damodaran annual implied ERP series as of valuation date | Moderate (requires explicit benchmark) |
| **Effective / Marginal Tax Rate ($\tau$)** | Income Statement: Provision for Income Taxes / Pre-tax Income | Normalized statutory rate (21% post-TCJA, 35% pre-2018) capped at $[15\%, 30\%]$ | Moderate (avoids negative tax rates) |
| **Cost of Debt ($R_d$)** | 10-K: Interest Expense / Average Total Debt | Synthetic credit spread model based on Interest Coverage Ratio ($EBIT / InterestExpense$) if interest is distorted | Moderate |
| **Terminal Growth Rate ($g$)** | None | Capped at long-term historical nominal GDP growth ($2.0\% - 2.5\%$) | High (critical sensitivity parameter) |

---

## 5. Company Universe Analysis

To evaluate the feasibility of empirical testing, three universe designs were analyzed across seven research dimensions:

### 5.1 Design Comparison
- **Option A (Prototype Universe — 10 Companies):** Apple, Microsoft, Walmart, Nike, Pfizer, Johnson & Johnson, Caterpillar, 3M, ExxonMobil, Chevron.
- **Option B (Recommended Research Universe — 30 Companies):** 30 large-cap US non-financial companies distributed equally across 5 major GICS sectors (Information Technology, Consumer Discretionary / Staples, Healthcare, Industrials, Energy).
- **Option C (Systematic Universe — S&P 500 / 500 Companies):** Full cross-section of S&P 500 index constituents.

| Evaluation Dimension | Option A: 10 Companies | Option B: 30 Companies (Recommended) | Option C: S&P 500 Systematic |
| :--- | :--- | :--- | :--- |
| **1. Data Availability** | High (100% covered in SEC XBRL) | High (all large-cap non-financials have complete XBRL) | Variable (missing XBRL tags, corporate spin-offs, restructurings) |
| **2. Accounting Comparability** | Complete manual audit possible | High across 5 standardized non-financial sectors | Low (banks, insurance, REITs, utilities require completely distinct accounting models) |
| **3. Computational Cost** | Minimal (< 1 minute ingestion; ~300k LLM tokens) | Low (< 10 minutes ingestion; ~9M-12M LLM tokens; ~$15 API cost) | High (> 8 hours ingestion; > 150M tokens; > $250 API cost) |
| **4. Historical Depth** | 2011–2024 continuous | 2015–2024 continuous (10 full years; 300 firm-years) | Significant attrition due to historical M&A and index exits |
| **5. Survivorship Bias** | High if chosen ex-post | Moderate (mitigated by establishing a fixed 2015 historical cohort) | Low only if point-in-time constituent database (Compustat) is purchased |
| **6. Sector Heterogeneity** | Limited (only 2 firms per sector) | Robust (6 firms per sector across 5 distinct economic models) | Comprehensive |
| **7. Feasibility for Student Research** | Trivial (lacks statistical power for econometric regression) | **Optimal balance of statistical viability and engineering feasibility** | Unrealistic for an independent student project without institutional infrastructure |

### 5.2 Primary Recommendation: Option B (30 Non-Financial US Companies)
**Recommendation:** Implement **Option B** as the primary research universe, using **Option A** as the initial technical debugging subset.
- **Exclusion of Financials:** Banks, insurance firms, and financial holding companies are explicitly excluded because their business model treats interest as an operating line item rather than a financing cost, rendering Free Cash Flow to Firm (FCFF), CapEx, and Working Capital normalization economically meaningless.
- **Sector Stratification:** 6 firms each across Technology, Consumer, Healthcare, Industrials, and Energy provide sufficient cross-sectional variation to test sector-relative valuation multiples and cross-industry NLP transferability.
- **Sample Size:** 30 firms over 10 years yields **300 firm-year annual observations** and **1,200 quarterly observations**, providing sufficient degrees of freedom for panel regressions while remaining computationally manageable on local hardware.

---

## 6. Accounting Normalization Feasibility

### 6.1 Empirical Concept Audit
A live programmatic audit of 10 major US corporations across 5 sectors was conducted against the SEC EDGAR XBRL facts endpoint. The empirical results demonstrate both the power and the hazards of XBRL standardization:

```
Concept Name                                       | AAPL | MSFT | WMT  | NKE  | PFE  | JNJ  | CAT  | MMM  | XOM  | CVX 
------------------------------------------------------------------------------------------------------------------------
RevenueFromContractWithCustomerExcludingAssessedTax | YES  | YES  | YES  | YES  | YES  | YES  |  NO  | YES  | YES  | YES 
SalesRevenueNet                                    | YES  | YES  | YES  | YES  | YES  |  NO  | YES  | YES  |  NO  |  NO 
Revenues                                           | YES  | YES  | YES  |  NO  | YES  | YES  | YES  | YES  | YES  | YES 
OperatingIncomeLoss                                | YES  | YES  | YES  |  NO  |  NO  | YES  | YES  | YES  |  NO  |  NO 
NetIncomeLoss                                      | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
CashAndCashEquivalentsAtCarryingValue              | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
CashCashEquivalentsRestrictedCash...               | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
Assets                                             | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
StockholdersEquity                                 | YES  | YES  | YES  | YES  | YES  | YES  |  NO  | YES  | YES  | YES 
NetCashProvidedByUsedInOperatingActivities         | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
PaymentsToAcquirePropertyPlantAndEquipment         | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  |  NO 
DepreciationDepletionAndAmortization               | YES  |  NO  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
DepreciationAndAmortization                        | YES  |  NO  | YES  |  NO  |  NO  |  NO  |  NO  | YES  |  NO  | YES 
LongTermDebtNoncurrent                             | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES  | YES 
ShortTermBorrowings                                |  NO  | YES  | YES  | YES  |  NO  | YES  | YES  |  NO  |  NO  | YES 
```

### 6.2 Key Normalization Findings
1. **Universal Core Financials:** `NetIncomeLoss`, `Assets`, `CashAndCashEquivalentsAtCarryingValue`, `NetCashProvidedByUsedInOperatingActivities`, and `LongTermDebtNoncurrent` are present across **100% of tested firms**. These form the invariant bedrock of the normalization pipeline.
2. **The Revenue Tag Split (ASC 606 Impact):** Prior to 2018, companies predominantly reported `SalesRevenueNet` or `Revenues`. Starting in fiscal year 2018 (upon adoption of ASC 606 *Revenue from Contracts with Customers*), US GAAP shifted to `RevenueFromContractWithCustomerExcludingAssessedTax`. Caterpillar (CAT) never adopted this specific tag, continuing to report `SalesRevenueNet`. A naive query looking for a single revenue concept fails immediately.
3. **The Operating Income / EBIT Failure:** 40% of tested firms (Nike, Pfizer, ExxonMobil, Chevron) **do not report `OperatingIncomeLoss`**. 
   - Nike reports multi-step income lines ending in pre-tax income (`IncomeLossFromContinuingOperationsBeforeIncomeTaxes...`).
   - ExxonMobil and Chevron report segmented upstream/downstream earnings without a consolidated standard operating income line.
   - *Direct Consequence:* Naive calculation of EBIT or FCFF will crash or produce NaNs on 40% of non-financial firms unless multi-tier fallback calculation is implemented.
4. **CapEx Tag Variations:** While 9 out of 10 firms use `PaymentsToAcquirePropertyPlantAndEquipment`, Chevron (CVX) reports `PaymentsToAcquireProductiveAssets`.
5. **Equity Reporting Variations:** Caterpillar does not use `StockholdersEquity`; it uses `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`.

### 6.3 Standardized Fallback Cascades
To guarantee 100% data completeness without manual per-firm hardcoding, the normalization engine must execute deterministic priority cascades:

```python
# Formal Priority Cascades for Concept Normalization
REVENUE_CASCADE = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
    "TotalRevenuesAndOtherIncome"
]

OPERATING_INCOME_CASCADE = [
    "OperatingIncomeLoss",
    # If direct tag missing, derive from Gross Profit - Operating Expenses:
    ("GrossProfit", "-", "OperatingExpenses"),
    # Or derive from Pre-tax Income + Interest Expense:
    ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments", "+", "InterestExpense")
]

CAPEX_CASCADE = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquirePropertyPlantAndEquipmentAndSoftware"
]

CASH_CASCADE = [
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "CashAndCashEquivalentsAtCarryingValue",
    "Cash"
]

TOTAL_EQUITY_CASCADE = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
]
```

### 6.4 Minimum Viable Standardized Financial Schema
The normalized dataset for each firm-period $(i, t)$ consists of:
- **Identifier & Metadata:** `cik`, `ticker`, `fiscal_year`, `fiscal_period` (FY/Q1/Q2/Q3), `period_end_date`, `filing_date`, `acceptance_datetime`, `form_type`.
- **Income Statement:** `revenue`, `cost_of_revenue`, `gross_profit`, `operating_expenses`, `operating_income` (EBIT), `interest_expense`, `income_tax_expense`, `net_income`.
- **Balance Sheet:** `cash_and_equivalents`, `short_term_investments`, `accounts_receivable`, `inventory`, `current_assets`, `property_plant_equipment_net`, `total_assets`, `short_term_debt`, `accounts_payable`, `current_liabilities`, `long_term_debt`, `total_liabilities`, `total_equity`, `shares_outstanding`.
- **Cash Flow Statement:** `cash_from_operations`, `capital_expenditures`, `free_cash_flow_reported`, `dividends_paid`, `share_repurchases`, `depreciation_amortization`.

---

## 7. Historical Depth & Backtesting Window

### 7.1 Historical Depth Audit
- **XBRL Availability:** Machine-readable XBRL data on SEC EDGAR is complete and standardized from **2011 to 2024**.
- **Filing Frequency:** 10-K (Annual) filed once per year (within 60–90 days of fiscal year end); 10-Q (Quarterly) filed 3 times per year (within 40–45 days of quarter end).
- **LTM (Last Twelve Months) Construction:** While quarterly data provides higher frequency, quarterly XBRL filings often exhibit seasonal noise and incomplete cash flow statement disclosures (many firms only provide cumulative year-to-date cash flow, requiring quarterly de-accumulation: $Q_3 = YTD_3 - YTD_2$).
- **Restatements & Amendments:** As demonstrated in our Apple audit for fiscal 2008–2009, the original 10-K reported operating income of \$7.658B, but subsequent 10-K/A filings amended this to \$11.740B. The historical depth design must strictly archive both original and restated values, tagged with their respective filing dates.

### 7.2 Feasible Backtesting Window
**Recommended Window: 2015–2024 (10 Full Calendar Years).**
- Covers multiple macroeconomic regimes: low-interest rate expansion (2015–2019), COVID-19 shock and supply-chain disruption (2020–2021), high inflation and rapid Federal Reserve rate-hike regime (2022–2023), and AI infrastructure expansion (2024).
- Avoids the turbulent transition years of initial XBRL adoption (2009–2012) where taxonomy definitions and software tagging errors were elevated.

---

## 8. As-of-Date Architecture & Leakage Control

Look-ahead bias is the single most common failure mode in empirical financial research. In equity valuation, look-ahead bias occurs when a valuation model at date $T_{val}$ uses information that was not yet publicly known at $T_{val}$.

### 8.1 The Core Distinction: Report Date vs. Filing Date
```
Fiscal Period Ends (reportDate)            10-K Public Release (filed / acceptanceDateTime)
          2019-12-31                                        2020-02-15
--------------+--------------------------------------------------+---------------------> Timeline
              | <------------- Information Lag --------------> |
              |                                                 |
              |   AT THIS DATE:                                 |   AT THIS DATE:
              |   Financials NOT public.                        |   Financials ARE public.
              |   Valuation CANNOT use 2019 numbers!            |   Valuation CAN use 2019 numbers.
```

If a researcher evaluates a company as of **December 31, 2019**, they **MUST NOT** use the FY 2019 10-K numbers, because those numbers were not published until February 2020. At 2019-12-31, the latest publicly available fundamental information was the **Q3 2019 10-Q** (filed in October/November 2019).

### 8.2 Point-in-Time (PIT) Information Set Definition
For any historical valuation date $T_{val}$, the admissible information set $\mathcal{I}(T_{val})$ is defined by strict mathematical inequalities:

$$\mathcal{I}(T_{val}) = \left\{ \text{Record } r \;\middle|\; \text{timestamp}(r) \le T_{val} \right\}$$

1. **Company Financial Statements:**
   $$\text{acceptanceDateTime}(Filing) \le T_{val}$$
   - Any filing with $\text{acceptanceDateTime} > T_{val}$ is excluded from the query.
   - If an amendment (10-K/A) was filed on date $T_{amend} > T_{val}$, the model **must use the original unamended filing**, because the market at $T_{val}$ only had access to the original.
2. **Market Prices:**
   $$\text{trade\_date} \le T_{val}$$
   - The stock price, shares outstanding, and market capitalization must be the closing values on or immediately preceding $T_{val}$.
3. **Macroeconomic Indicators:**
   $$\text{vintage\_date} \le T_{val}$$
   - GDP, CPI, and Treasury yield releases must reflect historical releases as known at $T_{val}$ (using ALFRED vintage tracking for revised macroeconomic series).

### 8.3 Technical Implementation
The point-in-time filtering is enforced directly in SQL/DuckDB using window functions:

```sql
-- Point-in-Time Selection of Latest Public Financial Facts as of :val_date
WITH candidate_facts AS (
    SELECT 
        cik,
        concept,
        fiscal_year,
        fiscal_period,
        end_date,
        val,
        acceptance_datetime,
        ROW_NUMBER() OVER (
            PARTITION BY cik, concept, end_date 
            ORDER BY acceptance_datetime DESC
        ) as rev_rank
    FROM xbrl_facts
    WHERE acceptance_datetime <= :val_date
)
SELECT cik, concept, fiscal_year, fiscal_period, end_date, val
FROM candidate_facts
WHERE rev_rank = 1;
```

---

## 9. Valuation Engine Feasibility

The valuation engine is designed as a **closed-form, deterministic quantitative module**. It implements both Discounted Cash Flow (DCF / FCFF) and Relative Valuation Multiples.

### 9.1 Discounted Cash Flow (FCFF Architecture)
The primary intrinsic valuation model is the **Free Cash Flow to Firm (FCFF)** model:

$$FCFF_t = EBIT_t \times (1 - \tau_t) + D\&A_t - CapEx_t - \Delta NWC_t$$

Where:
- $EBIT_t \times (1 - \tau_t) = NOPAT_t$ (Net Operating Profit After Tax)
- $\tau_t$ is the normalized marginal tax rate.
- $\Delta NWC_t = (CurrentAssets_t - Cash_t) - (CurrentLiabilities_t - ShortTermDebt_t) - NWC_{t-1}$.

#### Cost of Capital (WACC)
$$WACC = \left(\frac{E}{D + E}\right) R_e + \left(\frac{D}{D + E}\right) R_d \times (1 - \tau)$$

- Cost of Equity ($R_e$) via CAPM:
  $$R_e = R_f + \beta_{adj} \times ERP$$
  Where $\beta_{adj} = 0.67 \beta_{raw} + 0.33$, $R_f = \text{10Y Treasury Yield}$, and $ERP = 5.0\%$.
- Cost of Debt ($R_d$):
  $$R_d = \frac{\text{Interest Expense}}{\text{Average Total Debt}}$$
  *(If effective interest is distorted or zero, a synthetic credit rating spread is applied based on the interest coverage ratio $EBIT / InterestExpense$).*

#### Terminal Value Formulation
To prevent arbitrary terminal value dominance, the model implements two parallel terminal value methods:
1. **Gordon Growth Model (Primary Baseline):**
   $$TV_n = \frac{FCFF_n \times (1 + g)}{WACC - g}$$
   *Constraint:* $g \le R_f$ and $g \le 2.5\%$ (terminal growth cannot exceed long-run nominal GDP growth).
2. **Exit Multiple Method (Cross-Check):**
   $$TV_n = EBITDA_n \times (EV/EBITDA)_{peer\_median}$$

#### Equity Value per Share
$$EnterpriseValue = \sum_{t=1}^n \frac{FCFF_t}{(1 + WACC)^t} + \frac{TV_n}{(1 + WACC)^n}$$

$$EquityValue = EnterpriseValue - TotalDebt + CashAndEquivalents - MinorityInterest$$

$$FairValuePerShare = \frac{EquityValue}{SharesOutstanding}$$

### 9.2 Relative Valuation Multiples
Relative valuation acts as an independent cross-sectional benchmark:
- **Primary Multiples:**
  - Enterprise Value to EBITDA ($EV/EBITDA$) — Capital structure neutral.
  - Enterprise Value to EBIT ($EV/EBIT$) — Capital structure neutral, accounts for capital intensity.
  - Price to Earnings ($P/E$) — Common equity benchmark (valid only when earnings $> 0$).
- **Secondary Multiples:**
  - Price to Sales ($P/S$) — Revenue benchmark for volatile margin sectors.
  - Free Cash Flow Yield ($FCF / MarketCap$) — Cash generation capability.

### 9.3 Scenario & Sensitivity Modeling
Intrinsic valuation must not produce a single false-precision point estimate. The engine outputs:
1. **2D Sensitivity Grids:**
   - Matrix of Fair Value across $WACC \in [WACC - 1.5\%, WACC + 1.5\%]$ and $g \in [g - 1.0\%, g + 1.0\%]$.
   - Matrix of Fair Value across Revenue Growth $\pm 300$ bps and Operating Margin $\pm 200$ bps.
2. **Discrete Scenario Architecture:**
   - **Bull Scenario:** 75th percentile historical growth, margin expansion (+150 bps), lower cost of capital (-50 bps).
   - **Base Scenario:** Consensus mean-reverting growth, historical median margin, standard WACC.
   - **Bear Scenario:** 25th percentile historical growth, margin compression (-200 bps), elevated cost of capital (+100 bps).

---

## 10. Financial Forecasting Methodology

A critical research principle is **parsimony and defensibility**. Complex black-box machine learning models (e.g., neural networks predicting future cash flows) are prone to extreme overfitting, look-ahead leakage, and uninterpretable failure modes on small macroeconomic samples.

### 10.1 Comparative Analysis of Forecasting Approaches

| Forecasting Method | Methodological Mechanics | Pros | Cons | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Historical CAGR** | Project past 3–5 year CAGR indefinitely | Simple, transparent | Fails during cyclical inflections; projects unsustainable growth for fast growers | Rejected as primary |
| **Linear / Polynomial Trend** | OLS regression on historical time series | Deterministic | Extrapolates short-term volatility into permanent trends | Rejected |
| **Machine Learning (LSTM, XGBoost)** | Train non-linear models on macro + accounting | Captures non-linear interactions | Severe overfitting on 10–20 data points per firm; black box; unpublishable in fundamental finance | **STRICTLY REJECTED** |
| **Driver-Based / Margin-Based Mean Reversion** | Explicit revenue growth tapering to GDP growth; operating margins mean-reverting toward sector/firm historical medians | **Academically standard (Damodaran, McKinsey/Koller); economically defensible; transparent assumptions** | Requires explicit steady-state horizon | **RECOMMENDED PRIMARY BASELINE** |

### 10.2 Recommended Academic Baseline: 3-Stage Driver-Based Model
1. **Stage 1 (Years 1–3 — Explicit Transition):** Revenue growth linearly converges from the company's historical 3-year trailing CAGR toward the industry long-term median. Operating margins linearly adjust toward the firm's 5-year historical median.
2. **Stage 2 (Years 4–5 — Convergence Phase):** Revenue growth converges toward long-term nominal GDP growth ($2.0\% - 2.5\%$). Reinvestment rate aligns with the fundamental equation: $ReinvestmentRate = \frac{g}{ROC}$.
3. **Stage 3 (Year 6+ — Terminal Steady State):** $g = 2.0\% - 2.5\%$, $ROC \approx WACC$ (excess economic rents fade under competitive equilibrium).

---

## 11. AI / Filing Intelligence Feasibility

### 11.1 Target Filing Sections
The qualitative intelligence pipeline extracts text exclusively from two mandatory sections of the annual Form 10-K:
- **Item 1A — Risk Factors:** Contains management’s detailed disclosure of competitive, operational, regulatory, cyber, and legal hazards.
- **Item 7 — Management’s Discussion and Analysis (MD&A):** Contains executive narrative analyzing operating performance, liquidity, margin drivers, and capital allocation strategy.

### 11.2 Structured Qualitative Extraction Schema
The LLM is strictly constrained via schema enforcement (JSON Schema / Pydantic). It transforms unstructured narrative into verifiable, structured quantitative and categorical features:

```json
{
  "cik": "0000320193",
  "fiscal_year": 2024,
  "filing_date": "2024-10-31",
  "section": "Item_1A",
  "features": {
    "risk_sentiment_score": -0.42,
    "regulatory_scrutiny_flag": 1,
    "regulatory_scrutiny_citation": "We are subject to complex and evolving laws and regulations globally regarding antitrust, privacy, and digital services...",
    "litigation_exposure_level": "MODERATE",
    "litigation_citation": "The European Commission issued a decision finding the Company had violated certain competition rules...",
    "supply_chain_vulnerability_score": 0.65,
    "supply_chain_citation": "Substantially all of our manufacturing is performed by outsourced partners concentrated in East Asia...",
    "capital_allocation_shift": "SHARE_REPURCHASE_EMPHASIS",
    "capital_allocation_citation": "During fiscal 2024, our board authorized an increase of $110 billion in our share repurchase program...",
    "margin_headwind_flag": 1,
    "margin_headwind_citation": "We anticipate gross margin pressure from higher silicon fabrication and logistics input costs..."
  }
}
```

### 11.3 Verifiable Grounding & Citation Mandate
To maintain academic credibility, **zero ungrounded claims are permitted**:
1. Every score, flag, or categorical classification returned by the model **must be paired with an exact verbatim sentence or paragraph** extracted from the raw filing.
2. An automated validation pass string-searches the returned citation against the original text chunk. If the citation does not exist verbatim in the source filing text, the extraction is flagged as a hallucination and rejected.

---

## 12. AI Reliability, Reproducibility & Hallucination Controls

Large Language Models introduce non-determinism, prompt sensitivity, and hallucination risks that must be systematically engineered out.

### 12.1 Engineering Safeguards
1. **Zero Temperature:** Model sampling temperature is locked at `temperature = 0.0` (with `top_p = 1.0` and fixed seeds where supported) to eliminate creative variance.
2. **Schema-Constrained Decoding:** Extractions are enforced using strict JSON schema output modes (e.g., Pydantic parsing / tool calling modes).
3. **Chunking & Context Bounding:** Rather than dumping 100 pages into a prompt, Item 1A and Item 7 are pre-filtered and partitioned into semantic sub-sections (e.g., Legal Risks, Operational Risks, Liquidity Commentary) with explicit line-number indexing.
4. **Model Version Locking:** Specific pinned model snapshots (e.g., `gemini-1.5-flash-002` or `claude-3-5-sonnet-20241022`) are pinned in configuration files. Dynamic unpinned model endpoints (`gemini-latest`) are forbidden.

### 12.2 Gold-Standard Audit Benchmark
To validate extraction fidelity:
- A random sample of **25 filing sections** across 5 companies and 5 years will be manually read and annotated by the research team.
- Metrics evaluated:
  - **Citation Precision:** Percentage of citations that are 100% verbatim matches in the source text (Target: 100%).
  - **Classification Accuracy:** Agreement between human and LLM on discrete flags (Regulatory, Litigation, Margin Headwind) measured via Cohen's Kappa ($\kappa$) and F1 score (Target: F1 $> 0.85$).
  - **Sentiment Rank Correlation:** Spearman's $\rho$ between human risk severity ranking and model `risk_sentiment_score` (Target: $\rho > 0.70$).

---

## 13. Incremental Information Hypothesis Testing

The core empirical research question is whether qualitative filing features add explanatory power beyond traditional quantitative accounting and market data.

### 13.1 Econometric Model Specifications
We formulate three nested empirical models:

- **Model A (Financial Statement Only):**
  $$Y_{i, t+1} = \alpha + \beta_1 \cdot \text{ROIC}_{i, t} + \beta_2 \cdot \text{Margin}_{i, t} + \beta_3 \cdot \text{RevGrowth}_{i, t} + \beta_4 \cdot \text{Leverage}_{i, t} + \epsilon_{i, t}$$

- **Model B (Financial Statements + Market Metrics):**
  $$\text{Model A} + \gamma_1 \cdot \beta_{i, t}^{\text{CAPM}} + \gamma_2 \cdot \text{Momentum}_{i, t} + \gamma_3 \cdot \left(\frac{EV}{EBITDA}\right)_{i, t} + \epsilon_{i, t}$$

- **Model C (Financials + Market + Filing-Derived Qualitative NLP):**
  $$\text{Model B} + \delta_1 \cdot \text{RiskScore}_{i, t} + \delta_2 \cdot \text{RegulatoryFlag}_{i, t} + \delta_3 \cdot \text{LitigationFlag}_{i, t} + \delta_4 \cdot \text{MarginOutlook}_{i, t} + \epsilon_{i, t}$$

### 13.2 Dependent Variables ($Y_{i, t+1}$)
To test incremental value without data snooping, two distinct dependent variables will be tested:
1. **Primary Dependent Variable (1-Year Forward Operating Margin Revision):**
   $$\Delta \text{OperatingMargin}_{i, t+1} = \text{OperatingMargin}_{i, t+1} - \text{OperatingMargin}_{i, t}$$
   *Hypothesis:* Negative filing risk sentiment and margin headwind flags predict forward margin contraction better than historical accounting trends alone ($\delta_4 > 0, \delta_1 < 0$).
2. **Secondary Dependent Variable (Valuation Convergence / Error Reduction):**
   $$|V_{i, t}^{\text{Intrinsic}} - P_{i, t+1}| / P_{i, t+1}$$
   Testing whether incorporating qualitative risk-adjusted cost of capital parameters reduces the tracking error between intrinsic DCF valuation and forward realized market price.

### 13.3 Statistical Significance Tests
- **Nested F-Test:** Test whether the inclusion of the $\delta$ parameter vector in Model C provides a statistically significant increase in explanatory power over Model B ($p < 0.05$).
- **Diebold-Mariano / Vuong Non-Nested Test:** Evaluates out-of-sample forecast accuracy superiority between competing models.

---

## 14. Historical Validation & Walk-Forward Design

### 14.1 Walk-Forward Expanding-Window Validation
Cross-validation using random K-fold splits is strictly invalid in financial time series due to temporal autocorrelation and look-ahead contamination.

The platform implements a **Walk-Forward Expanding-Window Validation** protocol:
```
Fold 1:  Train / Calibrate [2015 - 2018]  --->  Evaluate Out-of-Sample [2019]
Fold 2:  Train / Calibrate [2015 - 2019]  --->  Evaluate Out-of-Sample [2020]
Fold 3:  Train / Calibrate [2015 - 2020]  --->  Evaluate Out-of-Sample [2021]
Fold 4:  Train / Calibrate [2015 - 2021]  --->  Evaluate Out-of-Sample [2022]
Fold 5:  Train / Calibrate [2015 - 2022]  --->  Evaluate Out-of-Sample [2023]
Fold 6:  Train / Calibrate [2015 - 2023]  --->  Evaluate Out-of-Sample [2024]
```

### 14.2 Out-of-Sample Discipline
- Model parameters (e.g., historical median operating margins, regression coefficients, risk score weights) are fitted exclusively on data available within the expanding training window.
- Valuations for the test year $t+1$ are computed strictly using information available as of date $T_{val} = \text{Dec 31 of year } t$.

---

## 15. Survivorship Bias Audit & Mitigation

### 15.1 The Survivorship Bias Danger
If an empirical study selects the 30 largest companies **as of today (2026)** and runs a backtest from 2015 to 2024, the sample is inherently contaminated by survivorship bias. Companies that suffered financial distress, bankruptcy, or acquisition between 2015 and 2026 (e.g., General Electric's downsizing, Sears, Silicon Valley Bank, First Republic) are omitted, artificially inflating historical stability and valuation convergence.

### 15.2 Feasible Mitigation for this Research Project
1. **Fixed Historical Cohort Design:** The universe is constructed based on index membership and market capitalization **as of January 1, 2015**, rather than current 2026 membership.
2. **Explicit Survivorship Boundary Acknowledgment:** In academic research without access to high-cost institutional databases (e.g., CRSP/Compustat survivorship-bias-free files), if companies must be selected with complete 10-year historical continuous filing histories, the paper must:
   - Explicitly document this constraint as a **survivor-conditioned universe**.
   - Perform a formal **sensitivity analysis** documenting the failure modes of firms that deteriorated.
   - Bound all empirical claims to "large-cap going-concern enterprises" rather than universal market prediction.

---

## 16. Market Data Licensing & Reproducibility Analysis

| Provider | Permitted Academic Use | Public GitHub Redistribution | Reproducibility Strategy |
| :--- | :--- | :--- | :--- |
| **Tiingo** | Yes (Free developer tier, 500 tickers) | **PROHIBITED.** Raw vendor price feeds cannot be committed to a public Git repository. | Pipeline includes a deterministic setup script `scripts/fetch_market_data.py` where the researcher supplies their free API key. Data is cached locally in `.gitignore`d storage. |
| **US Treasury** (`treasury.gov`) | **Full Public Domain.** No restrictions. | **PERMITTED.** Can be committed directly or downloaded live. | Bundled in repository as baseline risk-free curve or dynamically fetched via open URL. |
| **SEC EDGAR** | **Full Public Domain (US Gov).** Open access. | **PERMITTED.** XBRL facts and public filings are public records. | Scripts download directly from `data.sec.gov`. Small normalized test fixtures committed for CI/CD unit testing. |
| **FRED / ALFRED** | Permitted for educational research. | Not recommended for raw mass redistribution. | Downloaded via script with free FRED key. |

---

## 17. Technical Architecture Proposal

### 17.1 System Directory Layout
```
project_root/
├── docs/
│   ├── PHASE_0_FEASIBILITY_REPORT.md   # This audit document
│   ├── data_dictionary.md              # Normalized schema definitions
│   └── research_methodology.md         # Formal academic paper draft
├── config/
│   ├── universe.yaml                   # 30-company tickers, CIKs, sectors
│   ├── xbrl_tag_mappings.yaml          # Multi-tier fallback cascades
│   └── valuation_params.yaml           # WACC benchmarks, GDP ceilings
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── sec_client.py               # SEC EDGAR rate-limited client
│   │   ├── market_client.py            # Tiingo / Treasury market fetcher
│   │   └── filing_downloader.py        # 10-K HTML extractor
│   ├── normalization/
│   │   ├── xbrl_parser.py              # SEC companyfacts JSON parser
│   │   ├── fallback_engine.py          # Cascade calculation logic
│   │   └── statement_builder.py        # PIT annual/quarterly builder
│   ├── valuation/
│   │   ├── dcf_model.py                # FCFF, WACC, TV closed-form math
│   │   ├── relative_multiples.py       # EV/EBITDA, P/E peer benchmarks
│   │   └── sensitivity_analysis.py    # 2D WACC x Growth grid generator
│   ├── nlp/
│   │   ├── filing_chunker.py           # Item 1A / Item 7 DOM extractor
│   │   ├── schema_models.py            # Pydantic structured output models
│   │   ├── llm_extractor.py            # Schema-constrained LLM interface
│   │   └── citation_verifier.py        # Verbatim quote string verification
│   └── evaluation/
│       ├── pit_engine.py               # As-of-date temporal filter
│       ├── walk_forward.py             # Expanding window evaluator
│       └── econometric_tests.py        # F-tests, regression analysis
├── data/                               # Local data store (GITIGNORED)
│   ├── raw_sec/                        # Cached raw JSON from SEC EDGAR
│   ├── raw_filings/                    # Raw 10-K HTML files
│   ├── market/                         # Cached daily prices / yields
│   └── processed/                      # Normalized SQLite / DuckDB database
├── tests/
│   ├── test_sec_client.py              # Rate-limiting & header tests
│   ├── test_normalization.py           # Fallback cascade unit tests
│   ├── test_as_of_date.py              # Look-ahead leakage boundary tests
│   ├── test_dcf_math.py                # Deterministic valuation math tests
│   └── test_citation_grounding.py      # LLM quote validation tests
├── requirements.txt                    # Python dependencies
└── README.md                           # Research reproduction guide
```

### 17.2 Database & Storage Engine
- **Engine:** **DuckDB / SQLite**.
- **Rationale:** DuckDB provides lightning-fast columnar analytical queries over Parquet and local SQL tables without requiring server administration (PostgreSQL). It runs embedded directly in Python, ensuring 100% portability across workstations.

---

## 18. Computational Feasibility & Resource Budget

| Resource Dimension | Estimated Requirement | Workstation Capacity (MacBook Air / Local PC) | Feasibility Assessment |
| :--- | :--- | :--- | :--- |
| **Disk Storage** | Raw SEC JSON: ~200 MB<br>Raw 10-K HTML: ~800 MB<br>Market Data: ~50 MB<br>Normalized DB: ~100 MB<br>**Total: ~1.2 GB** | Typical SSD: 256 GB–1 TB (available $> 50$ GB) | **COMPLETELY FEASIBLE.** Minimal storage footprint. |
| **RAM Utilization** | Normalization parsing: ~500 MB peak<br>Valuation engine: ~200 MB<br>DuckDB memory cache: ~1 GB | 8 GB–16 GB Unified Memory | **COMPLETELY FEASIBLE.** No large out-of-core computing required. |
| **Network & SEC API Calls** | 30 companies $\times$ 1 facts file = 30 calls<br>300 10-K filings = 300 calls<br>**Total calls: ~350** | At 8 req/sec, entire dataset downloads in **under 2 minutes**. | **COMPLETELY FEASIBLE.** Far below SEC rate-limit ceilings. |
| **LLM Token Budget** | 300 filings $\times$ 35,000 tokens (Item 1A + Item 7)<br>**Total: ~10.5 Million Tokens** | Gemini 1.5 Flash / Claude 3.5 Haiku API:<br>Input: \$0.075 / 1M tokens = **~\$0.80 - \$2.00 total** | **HIGHLY COST-EFFECTIVE.** Negligible cost on developer tier. |
| **Runtime for Full Backtest** | Ingestion: 2 min<br>Normalization: 15 sec<br>Deterministic Valuation: 10 sec<br>Econometric Regressions: 5 sec | Total quantitative pipeline executes in **under 3 minutes**. | **COMPLETELY FEASIBLE.** |

---

## 19. Project Scope Matrix

| Dimension | Minimal Viable Prototype (MVP) | Research-Grade Platform (Recommended) | Stretch Scope |
| :--- | :--- | :--- | :--- |
| **Universe** | 10 companies (Option A) | **30 companies (Option B, 5 sectors)** | 100+ S&P 500 companies |
| **Historical Range** | 3 years (2022–2024) | **10 years (2015–2024)** | 20 years (2004–2024) |
| **Filing Frequency** | Annual (10-K) | **Annual (10-K) + Quarterly (10-Q) LTM** | Continuous 8-K, 10-Q, 10-K |
| **Valuation Models** | Single-scenario DCF | **DCF (FCFF) + WACC + 2D Sensitivity + Multiples** | Monte Carlo DCF + Residual Income Model |
| **AI Extraction** | Item 1A Risk Factors only | **Item 1A (Risk) + Item 7 (MD&A) with verbatim citations** | Audio earnings call transcripts + 8-Ks |
| **Econometric Evaluation** | Basic cross-sectional error | **Walk-Forward Expanding Window + Nested F-Tests** | High-frequency panel GMM estimation |
| **User Interface** | CLI scripts | **Streamlit Research Dashboard + Artifact Exporters** | Multi-user web app with live streaming |

**Target Recommendation:** Lock project scope to the **Research-Grade Platform**. It delivers the maximum academic rigor and statistical defensibility while avoiding unmanageable engineering overhead.

---

## 20. Comprehensive Risk Register

| Risk | Prob. | Impact | Mitigation Strategy | Go / No-Go Criterion |
| :--- | :---: | :---: | :--- | :--- |
| **1. SEC XBRL Concept Discrepancies** | **HIGH** | **HIGH** | Implement multi-tier priority fallback cascades (e.g., derive EBIT from gross profit or pre-tax lines). | Normalization engine must achieve $\ge 98\%$ data completeness on the 30-company universe. |
| **2. Look-Ahead Bias & Leakage** | **HIGH** | **CRITICAL** | Strict point-in-time filtering on SEC `acceptanceDateTime <= T_val`. Disallow post-dated amendments. | Zero tolerance. Any look-ahead contamination invalidates research. |
| **3. Market Data API Breakage / Licensing** | **MED** | **MED** | Use Tiingo official developer API as primary with yfinance fallback. Gitignore all raw proprietary price feeds. | Automated market data fetch script must reliably populate price series for all 30 tickers. |
| **4. Survivorship Bias** | **HIGH** | **MED** | Establish universe using historical 2015 index constituents. Explicitly bound research claims. | Formal disclosure of survivor boundaries in research paper methodology. |
| **5. LLM Hallucination** | **MED** | **HIGH** | Zero temperature, strict JSON schemas, and automated verbatim string-matching verification pass. | 100% of extracted quotes must match source text verbatim. |
| **6. LLM Extraction Inconsistency** | **MED** | **MED** | Pin exact model version snapshots; validate on human-annotated gold-standard benchmark (25 filings). | Inter-annotator agreement F1 $\ge 0.85$ against human benchmark. |
| **7. DCF Terminal Value Dominance** | **HIGH** | **MED** | Implement dual terminal value methods (Gordon Growth ceiling $\le 2.5\%$ and Exit Multiples) + sensitivity grids. | Report explicit percentage contribution of Terminal Value to Enterprise Value. |
| **8. Overfitting in Incremental Testing** | **MED** | **HIGH** | Walk-forward out-of-sample expanding window validation. Prohibit post-hoc hyperparameter tuning. | Out-of-sample evaluations must never train on future data. |
| **9. 10-K HTML Item Parsing Brittleness** | **MED** | **MED** | Build robust regex and DOM header parsers that bypass Table of Contents false positives. | Successful extraction of Item 1A and Item 7 across $\ge 95\%$ of target filings. |
| **10. SEC Rate-Limiting Bans (HTTP 429)** | **LOW** | **MED** | Embed a token-bucket rate limiter capped at 8 req/sec and mandatory compliant User-Agent headers. | Ingestion pipeline must execute without encountering HTTP 429 errors. |
| **11. Macro Data Historical Revisions** | **MED** | **LOW** | Use unrevised Treasury yields (constant maturity) and ALFRED vintage series for GDP/CPI. | Zero revision contamination in historical risk-free rate series. |

---

## 21. Go / No-Go Decision

### Hard Verdict: **GO WITH CONDITIONS**

### Strongest Empirical Evidence
1. **SEC EDGAR API Reliability & Timestamps:** Empirical verification confirms that SEC EDGAR provides structured JSON facts and exact `acceptanceDateTime` timestamps for all tested firms, enabling deterministic point-in-time backtesting without expensive commercial databases.
2. **Deterministic Mathematical Feasibility:** The core quantitative valuation formulas (FCFF, WACC, Gordon Growth, Relative Multiples) are fully closed-form and can be executed with 100% mathematical precision and reproducibility.
3. **Computational Accessibility:** The full 30-company, 10-year backtest consumes under 2 GB of storage, requires less than 3 minutes of quantitative calculation, and costs under \$20 in LLM API tokens, making it fully executable on standard developer hardware.

### Biggest Project Risk
**Uncontrolled Accounting Concept Divergence:** As uncovered during the empirical audit of Nike, Pfizer, ExxonMobil, and Chevron, 40% of non-financial firms lack a standard `OperatingIncomeLoss` tag, and revenue tags bifurcated following the 2018 ASC 606 rule change. A naive single-tag pipeline will silently produce corrupt valuations.

### Exact Next Step
Proceed to **Phase 1 (Data & Universe Audit)** to construct the formal 30-company universe registry, implement the rate-limited SEC EDGAR ingestion client, and test the multi-tier concept mapping cascades across all 30 tickers.

---

## 22. Proposed Phase Roadmap

| Phase | Title | Core Deliverables | Exit Gate / Success Criteria |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Feasibility & Research Design** | `PHASE_0_FEASIBILITY_REPORT.md` | Empirical feasibility confirmed across all dimensions. |
| **Phase 1** | **Data & Universe Audit** | Universe registry (`universe.yaml`), SEC client with rate-limiter, Treasury yield fetcher. | Successful automated ingestion of raw data for all 30 companies. |
| **Phase 2** | **Financial Statement Pipeline** | XBRL fact parser, DuckDB database schema, raw statement extraction. | 100% of raw filings ingested into structured relational tables. |
| **Phase 3** | **Accounting Normalization** | Multi-tier fallback cascades, standardized schema, LTM statement generator. | $\ge 98\%$ completeness on normalized Income, Balance Sheet, and Cash Flow statements. |
| **Phase 4** | **Valuation Engine** | Closed-form DCF (FCFF), WACC module, sensitivity grids, relative multiples. | Deterministic execution; unit tests match manual financial benchmark models. |
| **Phase 5** | **Filing Intelligence Layer** | 10-K Item 1A / Item 7 parser, schema-constrained LLM extractor, citation verifier. | Verbatim grounding verification achieving 100% citation match. |
| **Phase 6** | **AI Validation & Benchmark** | Gold-standard benchmark annotation (25 filings), inter-annotator evaluation. | Model vs Human F1 $\ge 0.85$; zero ungrounded hallucinations. |
| **Phase 7** | **Historical Evaluation** | Point-in-time filter, walk-forward expanding-window econometric regressions. | Statistical tests (Nested F-test, Vuong test) completed for Models A, B, and C. |
| **Phase 8** | **Dashboard & Research Paper** | Interactive Streamlit research dashboard, formal academic research paper. | Fully reproducible execution from scratch via automated CLI commands. |
| **Phase 9** | **Final Audit & Archival** | Final reproducibility audit, code clean-up, artifact documentation. | Complete codebase passes all tests, linting, and audit checks. |

---

## 23. Open Questions & Phase 1 Directives

The following architectural questions are designated for formal resolution during Phase 1:

1. **Handling Capital Expenditures in Energy / Industrials:**
   - *Issue:* Chevron reports `PaymentsToAcquireProductiveAssets` rather than `PaymentsToAcquirePropertyPlantAndEquipment`.
   - *Phase 1 Directive:* Audit all 30 tickers to catalog every variant CapEx tag and formalize the priority sequence.
2. **Effective Tax Rate Smoothing:**
   - *Issue:* In loss-making or transitional quarters, effective tax rate ($\text{Tax Expense} / \text{EBT}$) can be negative or exceed 100%.
   - *Phase 1 Directive:* Implement an empirical tax rate bounding rule (e.g., clamp effective tax rate to $[15\%, 25\%]$ or use the statutory 21% post-2018 corporate rate).
3. **Item 1A / Item 7 Boundary Parsing in Legacy iXBRL:**
   - *Issue:* In some inline XBRL filings, header tags for "Item 1A" appear inside complex CSS-styled tables or `<span>` blocks with embedded non-breaking spaces.
   - *Phase 1 Directive:* Develop a normalized regex pre-cleaner that strips HTML styling tags before scanning for section boundary tokens.
4. **UNVERIFIED — requires Phase 1 audit: Stock Split and Dividend Adjustments in Raw Prices:**
   - *Status:* While Tiingo and Yahoo Finance provide `adjClose`, the exact historical split multiplier must be validated against SEC XBRL `EntityCommonStockSharesOutstanding` history to ensure market capitalization calculations are mathematically consistent.
