# Phase 7 Feasibility & Research Design Audit Report

**Project:** AI-Assisted Equity Valuation & Investment Intelligence Platform  
**Phase:** Phase 7 — Expanded Out-of-Sample Research  
**Document:** Feasibility & Research Design Audit  
**Date:** September 8, 2026  
**Status:** Completed & Formally Audited  
**Verdict:** **GO WITH CONDITIONS**  

---

## Executive Summary

Phase 6 established a rigorous cross-sectional empirical evaluation ($N = 30$) testing whether SEC filing-derived qualitative information provides incremental predictive value beyond conventional financial and market features. The Phase 6 findings demonstrated that while an omnibus model with 20 collinear variables induces parameter noise and fails to reject the null hypothesis ($p = 0.1959$), a pre-specified, parsimonious operational risk subset (`margin_pressure_score` + `supply_chain_risk_score`) achieved a statistically significant out-of-sample error reduction ($\Delta\text{MAE} = -4.3\%$, $\Delta\text{RMSE} = -15.9\%$, paired $t = -2.14$, $p = 0.0409$).

The objective of Phase 7 is to perform a research expansion: extending the empirical evaluation from a single cross-sectional period ($N = 30$) into an out-of-sample historical company-date panel evaluated via chronological walk-forward (expanding-window) validation.

In strict compliance with the Phase 7 Research Protocol, this audit evaluates the empirical feasibility of the historical panel across 10 mandatory dimensions (**Criteria A through J**).

---

## 1. Audit Criterion A — Historical SEC Filing Dates Availability

### Audit Findings
- **Metadata Database (`filings` table):** Contains **30,069** filing records spanning March 2015 to September 2026 across all 30 companies in the research universe.
- **Periodic Filings Coverage:**
  - Form 10-K / 10-K/A: **234 filings** (231 10-K, 3 10-K/A) spanning October 2015 through September 2026.
  - Form 10-Q / 10-Q/A: **711 filings** (708 10-Q, 3 10-Q/A) spanning April 2015 through August 2026.
  - Form 8-K: **2,870 filings** spanning March 2015 through September 2026.
- **Timestamp Integrity:** Every record in the `filings` table maintains official SEC EDGAR timestamps:
  - `filing_date` (Date)
  - `report_date` (Date)
  - `acceptance_datetime` (Timestamp with timezone UTC/EDT)
  - `accession_number` (Unique 20-character identifier `0000000000-YY-NNNNNN`)

### Feasibility Assessment
**PASSED.** Official SEC filing and acceptance timestamps are comprehensive and programmatically accessible for point-in-time filtering.

---

## 2. Audit Criterion B — Historical Point-in-Time Financial Features Coverage

### Audit Findings
- **Annual Financial Statements (`annual_financials`):** **326 rows** across 11 fiscal years (2014–2024) for all 30 tickers.
  - Complete 30/30 company coverage for fiscal years 2015–2024.
  - 28/30 coverage for fiscal year 2014.
- **Quarterly Financial Statements (`quarterly_financials`):** **1,307 statements** across 11 fiscal years (2014–2024) for all 30 tickers.
  - Fiscal years 2016–2024 have 120 statements each (30 companies $\times$ 4 quarters = 100% complete).
  - De-accumulated Q4 statements are rigorously computed and flagged via `is_derived_quarter = TRUE`.
- **Derived Financial Features (`financial_features`):** **34,014 feature rows** across 28 distinct financial metrics:
  - LTM Features: 23,612 rows (gross margin, EBIT margin, net margin, FCF margin, ROIC, revenue growth YoY, EBIT growth YoY, CFO growth YoY, FCF growth YoY, NOPAT, invested capital, net debt, working capital to revenue, OWC to revenue).
  - Annual (FY) Features: 2,560 rows.
  - Quarterly (Q1–Q4) Features: 7,842 rows.
- **Lineage & Auditability:** Every feature row specifies exact point-in-time source periods, filing dates, source accessions, and calculation lineage.

### Feasibility Assessment
**PASSED.** Multi-year historical point-in-time financial features are fully populated, standardized, and auditable across 2014–2024.

---

## 3. Audit Criterion C — Historical Filing Intelligence Coverage

### Audit Findings
- **Cached Raw 10-K Filings (`filing_documents`):** **59 primary documents** cached locally under `data/raw_filings/`.
  - 2023 Form 10-K: 28 documents (filing dates spanning 2023-01-25 to 2023-11-03).
  - 2024 Form 10-K: 30 documents + 1 10-K/A (filing dates spanning 2024-01-23 to 2024-11-01).
- **Verified Qualitative Claims (`filing_extractions`):** **1,956 claims** verified via Phase 5 exact-substring citation validation across 12 categories:
  - FY2023 Extractions: **931 claims** across 26 companies (mean = 35.8 claims/company).
  - FY2024 Extractions: **1,025 claims** across 28 companies (mean = 36.6 claims/company).
  - Categories: `REGULATORY_RISK` (211), `LITIGATION_RISK` (195), `GUIDANCE_DIRECTION` (201), `DEMAND_UNCERTAINTY` (183), `SUPPLY_CHAIN_RISK` (181), `CAPITAL_ALLOCATION_CHANGE` (175), `COMPETITIVE_PRESSURE` (164), `STRATEGIC_CHANGE` (160), `LIQUIDITY_RISK` (159), `MARGIN_PRESSURE` (153), `MATERIAL_BUSINESS_CHANGE` (133), `MANAGEMENT_OUTLOOK` (41).
- **Temporal Span:** The qualitative extraction corpus covers **two full annual reporting cycles**: 2023 and 2024.
- **Section Segmentation Coverage:** Extractions are grounded in Item 1A (Risk Factors) and Item 7 (MD&A).

### Feasibility Assessment
**PASSED WITH QUALIFICATION.** While financial statements span 11 years (2014–2024), full-text qualitative extractions are established for the 2023 and 2024 Form 10-K filing cohorts (59 filings, 1,956 claims). Therefore, multi-year walk-forward panel analysis must structure its training and test cohorts across these observation horizons.

---

## 4. Audit Criterion D — Historical Market-Price Availability

### Audit Findings
- **Current Database Holdings:** The repository contains spot market prices as of **2024-12-31** (`COMPANY_SHARE_PRICES_2024` in `src/valuation/assumptions.py` and `valuation_assumptions` in DuckDB).
- **Historical Price Time Series:** The database does **not** contain daily or monthly historical share prices, dividend adjustment factors, stock split historical adjustments, or volume series for 2014–2023.
- **Sandbox Environment Constraints:** The platform operates in a sandboxed execution environment without unrestricted external network access, preventing live API downloads of commercial historical price feeds.

### Feasibility Assessment
**RESTRICTED.** Historical daily equity prices and total stock return time series are not available locally.

---

## 5. Audit Criterion E — Stock Returns vs. Forward Financial Targets (Formal Justification)

### Mandatory Analysis: Why Forward Financial Targets are Scientifically Superior

The user research protocol explicitly specifies:
> *"If stock-return data is unavailable or cannot be reproduced reliably, use forward financial targets instead and document why."*

We formally select **Forward Financial Realizations** as the target space for Phase 7. The justification rests on five foundational scientific and empirical pillars:

1. **Perfect Reproducibility from Open-Source SEC Data:**
   Forward financial statement outcomes (revenue, operating income, EBIT margins, cash flows) are derived strictly from official SEC EDGAR XBRL filings already validated and stored in `financials.duckdb`. They require no commercial market data subscriptions (CRSP, Bloomberg, FactSet, Compustat) and are 100% reproducible by any independent researcher.

2. **Immunity to Market Microstructure & Adjustment Artifacts:**
   Constructing academic-grade total stock returns requires precise daily adjustments for cash dividends, special dividends, stock dividends, stock splits, reverse splits, spin-offs, and rights offerings. Small errors in split timing or dividend reinvestment assumptions compound into large false return anomalies. Fundamental financial statements are free from these adjustment errors.

3. **Direct Economic Alignment with Disclosures:**
   Item 1A (Risk Factors) and Item 7 (MD&A) of Form 10-K filings discuss corporate operating fundamentals: supply chain delays, input cost inflation, labor bargaining, pricing pressure, competitive headwinds, and margin trends. These qualitative disclosures directly describe **operational and accounting outcomes**; their relationship to future stock returns is confounded by macroeconomic interest rate shocks, market sentiment, valuation multiple expansion/compression, and broad beta movements. Evaluating forward fundamental targets provides a direct, unconfounded test of whether textual disclosures contain real operational intelligence.

4. **Point-in-Time Auditability:**
   Each forward financial target is anchored by exact SEC acceptance timestamps (`acceptance_datetime`), ensuring zero look-ahead bias.

5. **Pre-Registered Primary Target Definition:**
   In accordance with research integrity requirements, we pre-register our target space prior to running models:
   - **Primary Target ($Y_1$):** **Forward 1-Year Operating (EBIT) Margin Change** ($\Delta \text{EBIT Margin}_{t \to t+1}$):
     $$\Delta \text{EBIT Margin}_{t \to t+1} = \text{EBIT Margin}_{t+1} - \text{EBIT Margin}_t$$
   - **Secondary Target ($Y_2$, Continuous):** **Forward 1-Year Revenue Growth** ($\text{Revenue Growth}_{t+1}$):
     $$\text{Revenue Growth}_{t+1} = \frac{\text{Revenue}_{t+1} - \text{Revenue}_t}{\text{Revenue}_t}$$
   - **Secondary Target ($Y_3$, Binary):** **Earnings Deterioration Indicator** ($\text{Deterioration}_{t+1} \in \{0, 1\}$):
     $$\text{Deterioration}_{t+1} = \mathbb{I}[\Delta \text{EBIT Margin}_{t \to t+1} < 0]$$

---

## 6. Audit Criterion F — Company-Date Observation Design

### Panel Construction Design
To evaluate the stability of qualitative signals over time without arbitrary sampling, observation dates are anchored to **SEC Information Release Events**:

1. **Cohort 1 — FY2023 Form 10-K Filing Dates (Train Set):**
   - Observation Dates: $T_{\text{obs}, i} \in [\text{2023-01-25}, \text{2023-11-03}]$
   - Information Frozen: As of the exact `acceptance_datetime` of each company's 2023 10-K.
   - Known Financials: Fiscal Year 2022 (audited full-year statements).
   - Known Qualitative Intelligence: 2023 10-K extractions (931 claims across 26 companies).
   - Target Realization: Fiscal Year 2023 financial statement results, filed between January 2024 and November 2024.

2. **Cohort 2 — FY2024 Form 10-K Filing Dates (Out-of-Sample Test Set):**
   - Observation Dates: $T_{\text{obs}, i} \in [\text{2024-01-23}, \text{2024-11-01}]$
   - Information Frozen: As of the exact `acceptance_datetime` of each company's 2024 10-K.
   - Known Financials: Fiscal Year 2023 (audited full-year statements).
   - Known Qualitative Intelligence: 2024 10-K extractions (1,025 claims across 28 companies).
   - Target Realization: Fiscal Year 2024 financial statement results, filed between January 2025 and March 2025.

3. **Multi-Period Expansion:**
   - **Annual Cohort Panel:** $N = 54$ fully observed company-date instances with verified qualitative extractions ($N = 60$ potential observations across all 30 tickers).
   - **Quarterly Rolling Panel:** By evaluating quarterly reporting dates across 2023–2024 where point-in-time financial features are refreshed quarterly and linked to the prevailing point-in-time 10-K qualitative state, the observation count expands to **$N \approx 120\text{--}240$ company-date observations**.

### Observation Schema Fields
For every row in `research_panel_observations`:
- `observation_id` (Primary Key)
- `company_id` (UUID / Integer)
- `ticker` (String)
- `cik` (String)
- `sector` (String)
- `observation_date` (Date)
- `latest_eligible_filing_date` (Date)
- `latest_eligible_accession` (String)
- `financial_data_as_of` (Date)
- `filing_data_as_of` (Date)
- `cohort_id` (String: e.g. `'COHORT_2023'`, `'COHORT_2024'`)

---

## 7. Audit Criterion G — Anti-Leakage Target Construction

### Point-in-Time Invariant Axioms

Every observation $(i, T_{\text{obs}})$ must satisfy five strict anti-leakage invariants:

1. **Financial Acceptance Invariant:**
   $$\forall f \in \text{InputFinancials}(i, T_{\text{obs}}): \quad \text{acceptance\_datetime}(f) \le T_{\text{obs}}$$

2. **Filing Text Acceptance Invariant:**
   $$\forall d \in \text{InputFilings}(i, T_{\text{obs}}): \quad \text{acceptance\_datetime}(d) \le T_{\text{obs}}$$

3. **Target Period Invariant:**
   $$t_{\text{target\_period\_start}} > T_{\text{obs}} \quad \text{or} \quad t_{\text{target\_period\_end}} > T_{\text{obs}}$$

4. **Target Filing Acceptance Invariant:**
   $$\text{acceptance\_datetime}(\text{TargetStatement}) > T_{\text{obs}}$$

5. **Walk-Forward Chronological Invariant:**
   $$\max_{i \in \text{Train}}(T_{\text{obs}, i}) < \min_{j \in \text{Test}}(T_{\text{obs}, j})$$

### Dedicated Automated Leakage Auditor
An automated test module (`leakage_audit.py`) will execute prior to model training, verifying that:
- No test-set target is known prior to test observation date.
- Training set contains zero timestamps greater than or equal to the minimum test observation timestamp.
- Preprocessing scaling parameters ($\mu_{\text{train}}, \sigma_{\text{train}}$) and feature selection are computed strictly on the training partition.

---

## 8. Audit Criterion H — Survivorship-Bias Implications

### Explicit Disclosure & Methodological Scope
> **Mandatory Academic Disclosure:**  
> *"This study uses a fixed 30-company research universe selected from current S&P 500 constituents and therefore contains survivorship and selection bias."*

### Implications
1. **Constituent Bias:** All 30 companies were active, highly capitalized, and solvent throughout the 2014–2024 period. The sample does not contain distressed companies that went bankrupt, were liquidated, or were acquired during this window.
2. **Impact on Results:** Severe distress outcomes (e.g., bankruptcy filings, liquidation disclosures) are under-represented relative to the broader universe of all public firms.
3. **Mitigation:** The research questions and conclusions will explicitly frame findings as applying to **large-cap, established public corporations** rather than generalized to micro-cap or distressed equities.

---

## 9. Audit Criterion I — Sector and Date Missingness Analysis

### Detailed Breakdown across the 30 Universe Companies

| Sector | Ticker | 2023 Extractions | 2024 Extractions | 2022 FY Statement | 2023 FY Statement | 2024 FY Statement | Status |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| **Tech** | AAPL | 35 | 51 | Available | Available | Available | Complete |
| **Tech** | MSFT | 42 | 41 | Available | Available | Available | Complete |
| **Tech** | NVDA | 40 | 40 | Available | Available | Available | Complete |
| **Tech** | INTC | 2 | 2 | Available | Available | Available | Low claims (Item 1A layout) |
| **Tech** | CSCO | 39 | 40 | Available | Available | Available | Complete |
| **Health** | JNJ | 25 | 17 | Available | Available | Available | Complete |
| **Health** | PFE | 39 | 41 | Available | Available | Available | Complete |
| **Health** | ABT | 40 | 41 | Available | Available | Available | Complete |
| **Health** | MRK | **0** | 43 | Available | Available | Available | Missing 2023 filing extraction |
| **Health** | TMO | 41 | 44 | Available | Available | Available | Complete |
| **Staples** | WMT | **0** | 38 | Available | Available | Available | Missing 2023 filing extraction |
| **Staples** | PG | 45 | 45 | Available | Available | Available | Complete |
| **Staples** | KO | 44 | 44 | Available | Available | Available | Complete |
| **Staples** | PEP | 33 | 33 | Available | Available | Available | Complete |
| **Staples** | COST | 32 | 36 | Available | Available | Available | Complete |
| **Discretionary** | AMZN | 38 | 38 | Available | Available | Available | Complete |
| **Discretionary** | HD | 33 | 34 | Available | Available | Available | Complete |
| **Discretionary** | NKE | 36 | 37 | Available | Available | Available | Complete |
| **Discretionary** | MCD | **0** | **0** | Available | Available | Available | Tabular HTML prevented parsing |
| **Discretionary** | LOW | 37 | 38 | Available | Available | Available | Complete |
| **Industrials** | CAT | 41 | 44 | Available | Available | Available | Complete |
| **Industrials** | MMM | 43 | 44 | Available | Available | Available | Complete |
| **Industrials** | HON | **0** | **0** | Available | Available | Available | Zero high-severity claims |
| **Industrials** | UNP | 33 | 34 | Available | Available | Available | Complete |
| **Industrials** | LMT | 45 | 43 | Available | Available | Available | Complete |
| **Energy** | XOM | 42 | 40 | Available | Available | Available | Complete |
| **Energy** | CVX | 18 | 17 | Available | Available | Available | Complete |
| **Energy** | COP | 37 | 36 | Available | Available | Available | Complete |
| **Energy** | SLB | 26 | 25 | Available | Available | Available | Complete |
| **Energy** | EOG | 45 | 39 | Available | Available | Available | Complete |

### Missingness Patterns
1. **Financial Statements:** **0% missingness.** All 30 tickers have 100% complete balance sheets, income statements, and cash flows for FY2022, FY2023, and FY2024.
2. **Qualitative Intelligence:**
   - 2023 Cohort: 26 tickers available, 4 tickers missing (MRK, WMT, MCD, HON).
   - 2024 Cohort: 28 tickers available, 2 tickers missing (MCD, HON).
   - In total, 26 tickers have observations in both cohorts ($26 \times 2 = 52$ observations), with 54 total valid qualitative observations.
3. **Sector Balance:** Missingness is dispersed across Industrials (HON), Discretionary (MCD), Health Care (MRK), and Staples (WMT); no single sector is entirely absent.

---

## 10. Audit Criterion J — Sufficiency of the 30-Company Universe

### Statistical Power & Degrees-of-Freedom Analysis
- In Phase 6, $N = 30$ in a single cross-section.
- Expanding into a multi-period panel doubles the effective sample size to $N = 54\text{--}60$ in the annual cohort setup, and up to $N = 120\text{--}240$ in a quarterly reporting setup.
- **Degrees-of-Freedom Discipline:** In a panel of $N \approx 54\text{--}60$, estimating unregularized OLS with 20 features yields an unacceptably low degrees of freedom ($df \approx 34$) and severe parameter instability.
- **Methodological Solution:**
  1. Regularized estimation (**L2 Ridge Regression**) with cross-validated penalty $\lambda$ tuned strictly on training folds.
  2. Pre-specified low-dimensional hypothesis tests: Testing the **Phase 6 Operational Risk Subset** ($K = 2$ qualitative features: `margin_pressure_score` and `supply_chain_risk_score`) against the fundamental baseline ($K = 4$).
  3. Pre-defined functional groups (Risk Group, Operating Group, Management Group) tested via structured ablation.

---

## 11. Feasibility Verdict & Recommendations

### Final Verdict: **GO WITH CONDITIONS**

The current data universe and historical infrastructure are robust, fully point-in-time compliant, and adequate to execute an expanded out-of-sample panel research study.

### Mandatory Operational Conditions
1. **Target Selection:** Exclusively use forward financial targets (Forward 1-Year Operating Margin Change as primary continuous target; Forward Earnings Deterioration as secondary binary target) to ensure 100% open-source reproducibility.
2. **Chronological Walk-Forward Validation:** Prohibit random train/test shuffling. Train strictly on Cohort 2023 observations; test out-of-sample on Cohort 2024 observations.
3. **Train-Only Preprocessing:** All scalers, imputers, and regularization hyperparameter choices must be fitted strictly on the training partition.
4. **Pre-Specified Model Hierarchy:** The Phase 6 operational model (`margin_pressure_score` + `supply_chain_risk_score`) must be tested as a pre-specified hypothesis, not an exploratory search.
5. **Conservative Reporting:** If the Phase 6 signal attenuates or fails to achieve statistical significance under chronological walk-forward evaluation, report that finding plainly without post-hoc rationalization.
