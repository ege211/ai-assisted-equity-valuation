# PHASE 8F — IMPLEMENTATION REPORT
## Provenance, Data Lineage & "What Changed?" Research Intelligence

**Document Version:** 1.0.0  
**Phase Status:** Phase 8F Complete & Formally Verified  
**Prior Phase Status:** Phase 1–7 Permanently Frozen (Academic Audit Verified); Phase 8A, 8B, 8C, 8D, 8E Frozen  
**Date:** September 2026  
**Repository:** Project 2 Only (`/Users/macbookair/Desktop/project 2`)

---

## 1. Executive Summary

Phase 8F upgrades the AI-Assisted Equity Valuation & Investment Intelligence Platform from a temporal-aware research interface into an institutional-grade, fully auditable equity research terminal.

Under Phase 8F, every analytical output displayed to the analyst—whether quantitative valuation figures or qualitative disclosure signals—is accompanied by mathematical data lineage, primary source attribution, and form-over-form "What Changed?" intelligence.

### Epistemological & Engineering Principles Enforced
1. **End-to-End Auditability:**
   - Numerical metrics trace deterministically: $\text{PRIMARY SEC XBRL FACT} \to \text{NORMALIZED STATEMENT} \to \text{FORECAST ASSUMPTION} \to \text{DISCOUNTED CASH FLOW} \to \text{FAIR VALUE BRIDGE}$.
   - Qualitative insights trace deterministically: $\text{SEC FILING} \to \text{SECTION} \to \text{PASSAGE} \to \text{EXTRACTION} \to \text{VALIDATION} \to \text{SIGNAL} \to \text{VALUATION BRIDGE}$.
2. **Deterministic Mathematical Lineage:** Zero LLM hallucinations or unsupported narratives. All "Why this number?" drilldowns are reconstructed directly from verified financial statements, CAPM formulas, and Gordon Growth terminal value mathematics.
3. **Authoritative SEC EDGAR Primary Source Linking:** Direct accession tracking and automated URL generation linking to official SEC EDGAR archives for all 10-K and 10-Q filings.
4. **Dual-Accession Point-in-Time Lock:** In `HISTORICAL` mode, longitudinal comparisons between Period $T$ and Period $T-1$ strictly require both accessions to satisfy $\text{acceptance\_datetime} \le \text{as\_of\_date } 23:59:59$. Comparisons breaching this lock are unconditionally rejected.
5. **Noise Threshold Filtering:** Micro-fluctuations within rounding noise ($|\Delta\%| < 0.1\%$ or $|\Delta| < \$1,000$) are explicitly flagged as noise to prevent false signal escalation.

---

## 2. Architecture & Data Flow

```mermaid
flowchart TD
    subgraph UI_Presentation [Streamlit Presentation Layer (app/)]
        OV[Overview Page]
        VAL[Valuation Page]
        FND[Fundamentals Page]
        FLG[Filings Page]
        EVD[Evidence Audit Page]
        CHG[What Changed Page]
        COMP[Reusable Provenance Components: app/components/provenance.py]
    end

    subgraph Service_Contracts [Service & Contracts Layer (src/service/)]
        PS[PlatformService: platform_service.py]
        DTO[Provenance & Lineage DTOs: provenance.py, contracts.py]
        WCE[What Changed Engine: get_company_changes]
        VLE[Valuation Lineage Engine: get_valuation_lineage, get_wacc_lineage]
        ELE[Evidence Lineage Engine: get_evidence_lineage]
    end

    subgraph Frozen_Domains [Frozen Deterministic Domain Engines (src/)]
        DCF[Deterministic DCF Engine: src/valuation/]
        CAPM[CAPM WACC Calibrator: src/valuation/]
        NORM[Financial Normalizer: src/normalization/]
    end

    subgraph Storage [Audited Analytical Database (DuckDB)]
        DB[(data/processed/financials.duckdb)]
        F_TBL[filings]
        S_TBL[annual_financials & quarterly_financials]
        E_TBL[filing_extractions]
        C_TBL[filing_change_signals]
        V_TBL[valuation_comparison_results]
    end

    OV & VAL & FND & FLG & EVD & CHG --> COMP
    COMP --> PS
    PS --> DTO
    PS --> WCE & VLE & ELE
    WCE & VLE & ELE --> DCF & CAPM & NORM
    WCE & VLE & ELE --> DB
    DB --> F_TBL & S_TBL & E_TBL & C_TBL & V_TBL
```

---

## 3. Structured Provenance Contracts & Data Lineage DTOs

The contract module [`src/service/provenance.py`](file:///Users/macbookair/Desktop/project%202/src/service/provenance.py) defines frozen, immutable dataclasses that guarantee structural integrity and type safety across all platform tiers:

```
src/service/provenance.py
├── SourceProvenanceDTO             # Primary source identification, accession, and EDGAR link
├── LineageStepDTO                  # Discrete transformation step in a calculation pipeline
├── DataLineageDTO                  # Complete end-to-end mathematical lineage pipeline
├── QualitativeEvidenceLineageDTO   # 6-stage qualitative disclosure lineage
├── ValuationBridgeLineageDTO       # Traceability linking qualitative signal to valuation delta
├── FundamentalChangeDTO            # Form-over-form metric delta with noise threshold
└── WhatChangedResponse             # Multi-period change intelligence report
```

### 3.1 `SourceProvenanceDTO`
- Encapsulates: `source_name`, `source_type` (`FILING_XBRL`, `FILING_NARRATIVE`, `MACRO_TREASURY`, `MARKET_PRICE`, `DERIVED_MODEL`), `accession_number`, `form`, `filing_date`, `acceptance_datetime`, `concept`, `unit`, `observation_date`, `is_pit_compliant`, `pit_rejection_reason`.
- Helper methods: `get_primary_source()` and `get_sec_url()`.

### 3.2 `LineageStepDTO` & `DataLineageDTO`
- `LineageStepDTO` models individual transformation stages: `step_number`, `step_name`, `description`, `input_values` (dictionary of input variables), `output_value` (calculated intermediate), `transformation_rule` (exact mathematical formula).
- `DataLineageDTO` packages the full pipeline: `entity_ticker`, `target_metric`, `final_value`, `unit`, `steps`, `calculation_summary`, and `source_provenance`.

### 3.3 `FundamentalChangeDTO` & `WhatChangedResponse`
- `FundamentalChangeDTO` captures statement delta between periods: `metric_name`, `category`, `current_period`, `current_value`, `previous_period`, `previous_value`, `absolute_change`, `percent_change`, `direction` (`INCREASED`, `DECREASED`, `UNCHANGED`), `is_meaningful`, `explanation`.
- `WhatChangedResponse` consolidates fundamental changes, valuation changes, qualitative disclosure signals, and strict Point-in-Time validity markers (`is_pit_valid`, `is_longitudinal_valid`, `rejection_reason`).

---

## 4. Authoritative SEC EDGAR Primary Source Linking

Primary source citations resolve directly to official SEC EDGAR archival documents.

`SourceProvenanceDTO.get_sec_url()` reconstructs the canonical EDGAR URL format:
$$\text{EDGAR URL} = \text{https://www.sec.gov/Archives/edgar/data/}\{\text{CIK}\}/\{\text{AccessionWithoutHyphens}\}/\{\text{AccessionNumber}\}\text{.txt}$$

For any verified financial statement line item (Balance Sheet, Income Statement, Cash Flow) or qualitative extraction, the platform captures:
- Exact SEC Accession Number (e.g., `0000789019-24-000021`)
- Form Type (`10-K` or `10-Q`)
- Filing Date (`filing_date`)
- Official Acceptance Timestamp (`acceptance_datetime`, e.g., `2024-07-30 20:06:22+00`)

---

## 5. Deterministic Numerical Calculation Lineage (DCF & WACC)

### 5.1 Fair Value per Share 4-Stage Pipeline
Reconstructed deterministically via `PlatformService.get_valuation_lineage()`:

1. **Step 1: `RAW_SEC_EXTRACTION`**
   - *Inputs:* Ticker, Mode, Point-in-Time Cutoff
   - *Outputs:* Cash & Equivalents, Total Debt, Net Debt, Diluted Shares Outstanding
   - *Rule:* Point-in-time extraction of balance sheet items; $\text{Net Debt} = \text{Total Debt} - \text{Cash}$.
2. **Step 2: `FCFF_NORMALIZATION`**
   - *Inputs:* Forecast Years (5), Revenue Growth Profile, EBIT Margin Profile
   - *Outputs:* 5-year Free Cash Flow schedule, $\sum \text{PV(FCFF)}$
   - *Rule:* $\text{NOPAT} = \text{EBIT} \times (1 - \text{TaxRate})$; $\text{FCFF} = \text{NOPAT} + \text{D\&A} - \text{Capex} - \Delta\text{NWC}$.
3. **Step 3: `DISCOUNTING_AND_WACC`**
   - *Inputs:* WACC, Cost of Equity, Cost of Debt, Risk-Free Rate, Beta
   - *Outputs:* Discounted cash flows PV, Discount factors
   - *Rule:* $\text{PV}(\text{FCFF}_t) = \frac{\text{FCFF}_t}{(1 + \text{WACC})^t}$ for forecast years $t \in [1, 5]$.
4. **Step 4: `TERMINAL_VALUE_AND_EQUITY_BRIDGE`**
   - *Inputs:* Terminal Growth Rate ($g$), WACC, Enterprise Value, Net Debt, Diluted Shares
   - *Outputs:* Enterprise Value, Equity Value, Fair Value per Share
   - *Rule:* $\text{TV} = \frac{\text{FCFF}_5 \times (1 + g)}{\text{WACC} - g}$; $\text{EV} = \sum \text{PV}(\text{FCFF}) + \text{PV}(\text{TV})$; $\text{Equity} = \text{EV} - \text{Net Debt}$; $\text{Fair Value} = \frac{\text{Equity}}{\text{Diluted Shares}}$.

### 5.2 WACC Derivation 4-Stage Pipeline
Reconstructed deterministically via `PlatformService.get_wacc_lineage()`:

1. **Step 1: `COST_OF_EQUITY_CAPM`**
   - *Rule:* $K_e = R_f + (\beta \times \text{ERP})$
2. **Step 2: `COST_OF_DEBT`**
   - *Rule:* $K_{d,\text{after-tax}} = K_{d,\text{pre-tax}} \times (1 - \text{TaxRate})$
3. **Step 3: `CAPITAL_STRUCTURE_WEIGHTS`**
   - *Rule:* $W_e = \frac{\text{Equity}}{\text{Equity} + \text{Debt}}$; $W_d = \frac{\text{Debt}}{\text{Equity} + \text{Debt}}$
4. **Step 4: `WACC_COMBINATION`**
   - *Rule:* $\text{WACC} = (W_e \times K_e) + (W_d \times K_{d,\text{after-tax}})$

---

## 6. 6-Stage Qualitative Evidence Lineage

Every verified qualitative disclosure traces through 6 discrete stages in `PlatformService.get_evidence_lineage()`:

```
[1. SEC FILING]        Form, Filing Date, Acceptance Datetime, Accession Number
      ↓
[2. SECTION]           Section Name (e.g. Item 7. MD&A), Source Identifier, Evidence Location
      ↓
[3. PASSAGE]           Passage ID, Verbatim Text Quote
      ↓
[4. EXTRACTION]        Extracted Claim, Confidence Score, Direction, Severity, Extraction Model
      ↓
[5. VALIDATION]        Validation Status (VALIDATED), Audit Reason, Exact Match Verification
      ↓
[6. SIGNAL]            Category (REVENUE_GROWTH, MARGIN_EXPANSION, etc.), Materiality, Valuation Link
```

---

## 7. Valuation Bridge Lineage

The Valuation Bridge links qualitative disclosure signals to quantitative DCF adjustments:
- Reconstructed via `PlatformService.get_valuation_bridge_lineage()`.
- Captures: `comparison_id`, `valuation_date`, `primary_signal_category`, `key_assumption_adjusted`, `adjustment_magnitude`, `baseline_fair_value` (Model A), `enhanced_fair_value` (Model B), `fair_value_pct_change`, and `evidence_citation`.

---

## 8. "What Changed?" Engine Architecture & Form-over-Form Comparison

Implemented via `PlatformService.get_company_changes()`:
- Automatically resolves the latest period (Period $T$) and preceding period (Period $T-1$) from annual statements (`annual_financials`), or falls back to quarterly statements (`quarterly_financials`).
- Computes mathematical deltas across 8 canonical financial metrics:
  1. Revenue
  2. Gross Profit
  3. Operating Income (EBIT)
  4. Net Income
  5. Cash & Cash Equivalents
  6. Total Debt
  7. Capital Expenditures (Capex)
  8. Free Cash Flow (FCF)

---

## 9. Dual-Accession Point-in-Time Lock Enforcement & Historical Integrity

In `HISTORICAL` mode, both accessions must satisfy the point-in-time acceptance deadline:
$$\text{Current Accession Acceptance} \le \text{as\_of\_date } 23:59:59 \quad \land \quad \text{Prior Accession Acceptance} \le \text{as\_of\_date } 23:59:59$$

### Rejection Protocol
If either accession post-dates the cutoff, or if fewer than 2 statements exist prior to the cutoff:
- `is_pit_valid = False`
- `is_longitudinal_valid = False`
- `rejection_reason` explicitly explains the breach (e.g., *"Insufficient statements available on or before point-in-time cutoff 1995-01-01 23:59:59 (found 0, need at least 2 for longitudinal comparison)."*)
- The UI displays an explicit warning and suppresses delta tables. Zero fallback to live data.

---

## 10. Deterministic Noise Threshold Filtering

To eliminate distracting rounding artifacts:
$$\text{is\_meaningful} = \left(|\text{percent\_change}| \ge 0.1\%\right) \land \left(|\text{absolute\_change}| \ge \$1,000\right)$$

- When `is_meaningful` is `False`: The metric is flagged with badge `⚪ Noise` and explanation `"Flat / within rounding noise threshold (<0.1% change)"`.
- When `is_meaningful` is `True`: The metric is flagged with badge `✅ YES` and full dollar/percentage change details.

---

## 11. Reusable Presentation Components (`app/components/provenance.py`)

A suite of 4 presentation components delivers dense, institutional terminal interfaces:

1. **`render_source_provenance_badge(prov, st_client)`:**
   - Displays `🛡️ [SOURCE DATA]`, Form, CIK, Accession, Acceptance Datetime, and link to SEC EDGAR.
   - For non-compliant historical records, renders `⚠️ [POINT-IN-TIME EXCLUSION]`.
   - For missing provenance, renders `"Source provenance unavailable"`.
2. **`render_lineage_pipeline(lineage, st_client)`:**
   - Renders calculation methodology summary and vertical pipeline of discrete calculation steps with rules, inputs, and intermediate outputs.
3. **`render_why_this_number_expander(title, lineage, st_client)`:**
   - Renders expandable audit panel (`"Why this Fair Value?"`, `"Why this WACC?"`) embedding the provenance badge and lineage pipeline.
4. **`render_what_changed_table(changes, st_client)`:**
   - Renders form-over-form comparison table with prior value, current value, absolute delta, percentage delta, noise badge, and analytical interpretation.
   - Displays dual-accession PIT lock verification metadata.
   - Renders valuation model comparison adjustments (Model A vs Model B).

---

## 12. Page Views Integration Audit

| Page View | Component Integration | Verification Status |
| :--- | :--- | :--- |
| [`app/pages/overview.py`](file:///Users/macbookair/Desktop/project%202/app/pages/overview.py) | Freshness banner & top-level statement provenance badge | Verified |
| [`app/pages/valuation.py`](file:///Users/macbookair/Desktop/project%202/app/pages/valuation.py) | "Why this Fair Value?" & "Why this WACC?" expanders | Verified |
| [`app/pages/fundamentals.py`](file:///Users/macbookair/Desktop/project%202/app/pages/fundamentals.py) | Statement header provenance badges & accession links | Verified |
| [`app/pages/filings.py`](file:///Users/macbookair/Desktop/project%202/app/pages/filings.py) | Filing inspector accession provenance & EDGAR linking | Verified |
| [`app/pages/evidence.py`](file:///Users/macbookair/Desktop/project%202/app/pages/evidence.py) | 6-stage qualitative lineage (Filing $\to$ Section $\to$ Passage $\to$ Extraction $\to$ Validation $\to$ Signal) | Verified |
| [`app/pages/changes.py`](file:///Users/macbookair/Desktop/project%202/app/pages/changes.py) | What Changed longitudinal table, dual-accession PIT lock, noise filtering | Verified |

---

## 13. Adversarial Anti-Leakage Verification

The platform was subjected to adversarial temporal leakage tests:

1. **Synthetic Future Filing Exclusion:**
   - Synthetic filing accepted at `2024-02-01 09:15:00+00` tested against historical cutoff `2024-01-01 23:59:59`.
   - Result: Future filing strictly excluded; only pre-cutoff filing returned.
2. **Synthetic Future Qualitative Evidence Exclusion:**
   - Extracted evidence from future filings tested against historical cutoffs.
   - Result: All returned evidence records strictly satisfy `acceptance_datetime <= cutoff`.
3. **Adversarial Dual-Accession Breach:**
   - Tested scenario where current accession post-dates cutoff while previous accession is pre-cutoff.
   - Result: Comparison is rejected with `is_pit_valid = False` and explicit rejection message.

---

## 14. Empirical Phase 7 Research Invariant Preservation

Phase 7 research conclusions remain permanently frozen and untampered:
- Dataset: $N=46$ complete cases across 2 walk-forward folds
- Model A Baseline: $\text{MAE} = 0.0777$
- Model B Pre-Specified Operational: $\text{MAE} = 0.0781$, $\text{RMSE} = 0.1424$, $\Delta \text{MAE} = -0.0005$ ($-0.60\%$), paired t-test $p = 0.2335$, bootstrap 95% CI = $[-0.0011, +0.0003]$, Decision = "Fail to reject $H_0$"
- Terminology: Strictly NO "Diebold-Mariano"; designated exclusively as paired t-test with bootstrap CI.

---

## 15. Automated Test Suite & Forensic Verification Results

The entire platform test suite was executed via `.venv/bin/python -m unittest discover tests -v`:

```
Ran 238 tests in 20.394s
OK (0 failures, 0 errors)
```

### Test Count Breakdown by Phase
- Phase 8B Application Foundation: 36 tests
- Phase 8C Interactive Dashboards: 18 tests
- Phase 8D Filing Intelligence & Evidence: 22 tests
- Phase 8E Historical / Point-in-Time Temporal Interface: 23 tests
- **Phase 8F Provenance, Lineage & What Changed (NEW): 25 tests**
- PlatformService, Contracts & Domain Engine Regression: 114 tests
- **Total Passing Tests: 238 tests**

### Code Hygiene & Compilation
- `python -m py_compile` across all service, app, and test files: **100% CLEAN (Exit Code 0)**
- `git diff --check`: **100% CLEAN (0 whitespace/formatting errors)**
- `git diff -- src/valuation src/normalization src/research`: **0 lines changed (PERFECT DOMAIN FREEZE)**
- Git commits & pushes: **0 (Strictly avoided per protocol)**

---

## 16. Operational Runbook, Freeze Certification & Next Phase Gate

### 16.1 Operational Execution
To launch the auditable research terminal locally:
```bash
.venv/bin/streamlit run app/main.py
```
To run the automated Phase 8F test suite:
```bash
.venv/bin/python -m unittest tests/test_phase8f_provenance.py -v
```

### 16.2 Formal Freeze Certification
Phase 8F is hereby certified complete, fully verified, and ready for formal freeze.
All domain engines remain untouched, all 238 tests are green, and data lineage is 100% auditable.

**NEXT PHASE GATE:** STOP. Do NOT proceed to Phase 8G without explicit user authorization.
