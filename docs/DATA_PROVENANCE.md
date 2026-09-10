# Data Provenance & Lineage Architecture

**Document Version:** 1.0.0  
**Phase:** Phase 9 (Academic Documentation & Reproducibility Package)  
**System Component:** Point-in-Time Accounting & Text Data Store  
**Storage Engine:** DuckDB 0.9.2+ / Embedded In-Process Engine  

---

## 1. System Overview & Lineage Principles

Data integrity in empirical finance relies on absolute transparency regarding where raw data originates, how it is ingested, the exact transformations applied, and how temporal barriers are established. 

This platform implements a four-stage auditable data lineage architecture:

```
[Raw Regulatory Source] 
  (SEC EDGAR API / U.S. Treasury)
           ↓ (Stage 1: Ingestion & Local Caching)
[Raw Local Stores] 
  (data/sec_cache/*.json, raw HTML/XML 10-K filings)
           ↓ (Stage 2: Parsing & 5-Tier Normalization)
[Normalized Structured Database] 
  (DuckDB: company_facts, financial_statements, ratios_ltm, filing_intelligence)
           ↓ (Stage 3: Point-in-Time Filtering)
[Analytical View / Valuation Models] 
  (acceptance_datetime <= cutoff 23:59:59)
```

Every analytical output displayed in the terminal or referenced in the research paper traces back to an immutable raw source record.

---

## 2. Primary Data Sources

### 2.1 SEC EDGAR Company Facts API
* **Source Authority:** U.S. Securities and Exchange Commission (SEC).
* **Endpoint:** `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json`
* **Data Ingested:** Full XBRL taxonomy disclosures filed under US-GAAP and IFRS by corporate registrants from 2014 to 2024.
* **Update Frequency:** Real-time upon registrant acceptance by EDGAR.
* **Fields Extracted:** Balance sheet, income statement, and statement of cash flows raw concepts, units, calendar fiscal periods, form types (`10-K`, `10-Q`), filing dates, and official acceptance timestamps (`acceptance_datetime`).

### 2.2 SEC EDGAR Form 10-K Statutory Filings
* **Source Authority:** SEC Electronic Data Gathering, Analysis, and Retrieval (EDGAR) system.
* **Format:** Unstructured raw HTML and XML registrant submissions.
* **Data Ingested:** Statutory annual disclosures across 30 large-cap corporations (330 filing years).
* **Target Sections Extracted:**
  * **Item 1:** Business
  * **Item 1A:** Risk Factors
  * **Item 7:** Management’s Discussion and Analysis of Financial Condition and Results of Operations (MD&A).

### 2.3 U.S. Department of the Treasury Benchmark Yields
* **Source Authority:** U.S. Department of the Treasury (Resource Center).
* **Data Ingested:** Daily Treasury Par Yield Curve Rates, specifically the 10-Year Constant Maturity Treasury (CMT) yield.
* **Usage:** Serves as the risk-free rate ($R_f$) coordinate in CAPM cost of equity and WACC discount rate calculations.

---

## 3. Ingestion Pipelines & Local Cache Architecture

### 3.1 Rate Limiting and Fair Access Compliance
To comply strictly with the SEC's Fair Access Policy:
* All requests pass an institutional User-Agent header declaring the researcher and host institution.
* The crawler enforces a hard rate limit of no more than 10 requests per second via token-bucket pacing.
* Requests exceeding rate limits or encountering HTTP 429 back off exponentially.

### 3.2 Local Caching Architecture
To guarantee offline reproducibility and protect against upstream schema modifications:
* Raw SEC API responses are cached as immutable JSON documents in `data/sec_cache/` using the zero-padded CIK identifier:
  `CIK0000320187.json` (Apple Inc.), `CIK0000789019.json` (Microsoft Corp.), etc.
* Cached JSON payloads are never modified post-ingestion. Subsequent pipeline executions read from local cache by default.

---

## 4. Database Schema (DuckDB)

Structured data is stored in DuckDB (`data/financials.duckdb` or in-memory instance). The database schema comprises five primary relational entities:

### 4.1 `company_facts`
Raw XBRL concept disclosures extracted directly from EDGAR JSON feeds.
* `fact_id` (VARCHAR, Primary Key): Unique hash of CIK, concept, period end, and acceptance timestamp.
* `ticker` (VARCHAR): Trading symbol.
* `cik` (VARCHAR): SEC Central Index Key.
* `taxonomy` (VARCHAR): Accounting taxonomy (e.g., `us-gaap`, `dei`).
* `concept` (VARCHAR): Standardized or extended XBRL concept name (e.g., `OperatingIncomeLoss`).
* `period_start` (DATE): Start date of reporting period (for flow items).
* `period_end` (DATE): End date of reporting period.
* `val` (DOUBLE): Numerical monetary value reported.
* `form` (VARCHAR): Filing form type (`10-K`, `10-Q`).
* `filed_date` (DATE): Official SEC filing date.
* `acceptance_datetime` (TIMESTAMP): Precise microsecond timestamp assigned by EDGAR upon receipt.

### 4.2 `financial_statements`
Standardized, normalized financial statement line items resolved via the 5-tier concept cascade.
* `statement_id` (VARCHAR, Primary Key): Composite key of ticker, fiscal year, and period.
* `ticker` (VARCHAR): Corporate ticker.
* `fiscal_year` (INTEGER): Reporting fiscal year.
* `period` (VARCHAR): `FY` (annual) or `Q1`, `Q2`, `Q3`, `Q4`.
* `period_end_date` (DATE): Period closing date.
* `acceptance_datetime` (TIMESTAMP): SEC acceptance timestamp of source filing.
* `revenues` (DOUBLE): Normalized total revenue.
* `cogs` (DOUBLE): Cost of goods and services sold.
* `gross_profit` (DOUBLE): Gross profit.
* `operating_income` (DOUBLE): Operating income ($EBIT$).
* `net_income` (DOUBLE): Net income available to common equity.
* `total_assets` (DOUBLE): Total balance sheet assets.
* `cash_and_equivalents` (DOUBLE): Cash, cash equivalents, and marketable securities.
* `total_debt` (DOUBLE): Short-term debt + long-term debt.
* `operating_working_capital` (DOUBLE): Accounts receivable + inventory - accounts payable.
* `capex` (DOUBLE): Capital expenditures from statement of cash flows.

### 4.3 `ratios_ltm`
Trailing twelve months (LTM) fundamental accounting ratios used in valuation and forecasting.
* `ticker` (VARCHAR): Corporate ticker.
* `as_of_date` (DATE): Calculation reference date.
* `acceptance_datetime` (TIMESTAMP): Maximum acceptance timestamp among constituent statements.
* `ebit_margin` (DOUBLE): $EBIT / Revenues$.
* `gross_margin` (DOUBLE): $Gross Profit / Revenues$.
* `roic` (DOUBLE): Return on invested capital ($NOPAT / Invested Capital$).
* `fcf_margin` (DOUBLE): Free cash flow margin.
* `net_debt_to_revenue` (DOUBLE): $(Total Debt - Cash) / Revenues$.
* `owc_to_revenue` (DOUBLE): $Operating Working Capital / Revenues$.
* `asset_turnover` (DOUBLE): $Revenues / Total Assets$.
* `effective_tax_rate` (DOUBLE): Computed effective tax rate or statutory fallback.

### 4.4 `filing_intelligence`
Pre-specified quantitative text metrics extracted from annual Form 10-K filings.
* `filing_id` (VARCHAR, Primary Key): Composite key of ticker, filing year, and accession number.
* `ticker` (VARCHAR): Corporate ticker.
* `acceptance_datetime` (TIMESTAMP): Microsecond EDGAR acceptance timestamp.
* `margin_pressure_score` (DOUBLE): Frequency of input inflation, wage, and margin compression terms in Item 7.
* `supply_chain_risk_score` (DOUBLE): Occurrences of logistics and supplier bottlenecks in Item 1A.
* `regulatory_risk_score` (DOUBLE): Mentions of regulatory scrutiny and compliance actions in Item 1A.
* `litigation_risk_score` (DOUBLE): Disclosed lawsuits, subpoenas, and legal claims in Item 1A / 7.
* `competitive_pressure_score` (DOUBLE): Pricing pressure and peer competition terms in Item 1 / 1A.
* `guidance_direction_score` (DOUBLE): Forward projection sentiment ratio in Item 7.
* `management_outlook_score` (DOUBLE): Qualitative optimism/pessimism metric in Item 7.

---

## 5. Timestamp & Point-in-Time (PIT) Logic

### 5.1 The Tri-Temporal Coordinate System
To prevent lookahead leakage, financial and textual disclosures must never be indexed solely by their fiscal period end date:

```
[Fiscal Period Ends]   -----------> [Filing Assembled & Submitted] ---> [SEC Accepts Filing]
  2023-12-31                           2024-02-02 16:14:00               2024-02-02 16:15:32
(period_end_date)                       (filing_date)                    (acceptance_datetime)
```

1. **`period_end_date` (2023-12-31):** Reflects the economic period measured, but the market and analyst have ZERO knowledge of the numbers on this date.
2. **`filing_date` (2024-02-02):** The business day of filing.
3. **`acceptance_datetime` (2024-02-02 16:15:32 EST):** The exact instant when the filing became publicly accessible on EDGAR.

### 5.2 The Historical Temporal Barrier
When the research terminal or econometric model operates under **HISTORICAL Mode** with cutoff date $T_{\text{cutoff}}$:

$$\text{WHERE } acceptance\_datetime \le T_{\text{cutoff}} \text{ 23:59:59}$$

Filings submitted after 23:59:59 on $T_{\text{cutoff}}$ are completely excluded from the dataset. Trailing twelve months metrics revert to the prior filing that was publicly available as of $T_{\text{cutoff}}$.

---

## 6. Normalization Rules & Edge Case Handling

### 6.1 Missing XBRL Concept Resolution
When a primary XBRL concept is absent due to registrant reporting choices, the engine resolves values through a strict five-tier cascade (see Appendix A of `docs/RESEARCH_PAPER.md`). If all five tiers fail, the field is flagged as missing and subjected to complete-case auditing.

### 6.2 Negative and Distorted Effective Tax Rates
Empirical effective tax rates ($\frac{Tax Expense}{Pre-Tax Income}$) frequently distort operating cash flow calculations due to one-time legal settlements, deferred tax asset allowances, or statutory tax reform (such as the 2017 Tax Cuts and Jobs Act). 

The platform applies the following audited convention:
* If $0.05 \le \tau_{\text{empirical}} \le 0.40$, use $\tau_{\text{empirical}}$.
* Otherwise, fall back to the prevailing U.S. federal statutory corporate tax rate:
  * $21.0\%$ for fiscal periods ending on or after 2018-01-01.
  * $35.0\%$ for fiscal periods ending prior to 2018-01-01.

### 6.3 Negative Operating Working Capital
Firms operating with negative working capital (e.g., Apple, Amazon, Walmart) generate structural cash advances from suppliers. The valuation engine treats negative OWC explicitly rather than truncating at zero, adjusting reinvestment rates in free cash flow projections accordingly.

---

## 7. Known Biases & Methodological Boundaries

1. **Large-Cap Representation Bias:** The 30-firm universe comprises major S&P 500 non-financial corporations. These firms face extensive analyst coverage and institutional scrutiny, potentially reducing the informational inefficiency of 10-K disclosures relative to micro-cap equities.
2. **Exclusion of Financial Services:** Banks, insurers, and broker-dealers are excluded due to fundamental non-comparability of revenue, debt, and working capital.
3. **Survivorship Bias Mitigation:** While the 30 firms were selected from active registrants as of 2024, all historical data from 2014–2024 is strictly point-in-time and reflects as-filed financial statements without retrospective adjustment for subsequent restatements.
