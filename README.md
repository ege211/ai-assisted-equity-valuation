# AI-Assisted Equity Valuation & Investment Intelligence Platform

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 260 Passing](https://img.shields.io/badge/tests-260%20passing-brightgreen.svg)](tests/)
[![Status: Release Candidate v1.0.0](https://img.shields.io/badge/version-v1.0.0-success.svg)](docs/RESEARCH_PAPER.md)

An institutional quantitative finance research platform and open-source econometric laboratory combining SEC regulatory disclosures, automated five-tier XBRL normalization, immutable deterministic discounted cash flow (DCF) valuation, point-in-time (PIT) filing intelligence, and chronological walk-forward out-of-sample predictive evaluation.

> **Research Description:**  
> A reproducible equity research and valuation platform combining SEC financial data, deterministic valuation, point-in-time filing intelligence, evidence validation, and chronological out-of-sample research.

---

## 1. Research Motivation & Core Question

The rapid expansion of natural language processing (NLP) and large language models (LLMs) in asset management has generated aggressive commercial claims regarding the predictive power of corporate disclosure text. Practitioner literature frequently asserts that quantifying annual SEC Form 10-K filings yields substantial forecasting "alpha" over standard financial statement metrics.

However, many supporting studies rely on static cross-sectional panels or randomized cross-validation (e.g., $K$-fold or LOOCV) that violate the causal direction of time, suffering from lookahead leakage, cross-cohort contamination, and regime-shift bias.

This platform and its accompanying academic study address this central empirical question:

> **Primary Research Question:**  
> *Do quantitative textual features extracted from SEC Form 10-K narrative disclosures provide statistically significant, out-of-sample incremental predictive power over standardized trailing accounting fundamentals when forecasting forward operating performance and informing fundamental equity valuation?*

---

## 2. Platform Architecture & System Principles

The platform decouples qualitative textual intelligence from pure quantitative valuation to guarantee fiduciary auditability:

```
[SEC EDGAR XBRL Facts & Form 10-K Submissions]
                      ↓
[Automated 5-Tier Concept Normalization Engine]
                      ↓
[DuckDB Point-in-Time Data Store (acceptance_datetime <= cutoff)]
                      ↓
[100% Deterministic Valuation Engine] ←→ [Pre-Specified NLP Pipeline]
    (Structural DCF & Reverse DCF)           (Items 1, 1A, 7 Text)
                      ↓                              ↓
             [Baseline Model A]            [The Valuation Bridge v1.0]
                      \                              /
                       ↓                            ↓
               [Interactive Institutional Research Terminal]
                   (Streamlit 6-Page Analytical Suite)
```

### Core Design Principles
1. **Mathematical Determinism:** Intrinsic valuation models (DCF, WACC, Reverse DCF) are implemented in pure Python and are 100% deterministic. No stochastic AI outputs directly modify cash flow projections.
2. **Point-in-Time (PIT) Temporal Integrity:** Every regulatory statement and filing is governed by its microsecond SEC EDGAR acceptance timestamp (`acceptance_datetime <= cutoff 23:59:59`). In HISTORICAL mode, lookahead leakage is structurally impossible.
3. **Auditable Valuation Bridge (`valuation_bridge_v1.0`):** Narrative disclosures cannot hallucinate arbitrary valuation adjustments. Qualitative claims are mapped to bounded, pre-specified parameter shifts (e.g., margin haircuts $\Delta m \in [-120\text{ bps}, 0\text{ bps}]$; WACC penalties $\Delta WACC \in [0\text{ bps}, +50\text{ bps}]$).
4. **End-to-End Data Lineage:** Every analytical metric and claim displayed in the terminal links directly back to its primary source accession number and SEC EDGAR archive URL.

---

## 3. Data Universe & Ingestion Pipeline

The empirical laboratory evaluates 30 U.S. large-cap non-financial equities spanning six Global Industry Classification Standard (GICS) sectors over the 2014–2024 reporting decade:

* **Technology:** AAPL, MSFT, NVDA, GOOGL, META
* **Consumer Discretionary:** AMZN, TSLA, HD, NKE, MCD
* **Consumer Staples:** PG, KO, PEP, WMT, COST
* **Health Care:** JNJ, UNH, PFE, ABBV, MRK
* **Industrials:** CAT, UNP, HON, BA, GE
* **Energy:** XOM, CVX, COP, SLB, EOG

### Automated 5-Tier XBRL Cascade
To handle heterogeneous reporting taxonomies across registrants, the normalization engine applies a prioritized five-tier tag resolution cascade for all core statement items (Revenues, COGS, EBIT, Net Income, Operating Cash Flow, Total Assets, Debt, Cash, Working Capital, and CapEx).

---

## 4. Pre-Specified Filing Intelligence Pipeline

Form 10-K filings are parsed into three statutory sections:
* **Item 1:** Business Description
* **Item 1A:** Risk Factors
* **Item 7:** Management’s Discussion and Analysis (MD&A)

Twelve pre-specified linguistic dimensions are extracted across four distinct clusters:
1. **Operational Risks:** Margin Pressure, Supply Chain Risk, Competitive Pressure, Demand Uncertainty.
2. **Legal & Regulatory:** Regulatory Risk, Litigation Risk, Liquidity Risk.
3. **Managerial Outlook:** Guidance Direction, Management Outlook Tone, Capital Allocation Shift.
4. **Structural Shifts:** Strategic Reorganization, Material Business Changes.

---

## 5. Main Empirical Findings (Phase 7 Walk-Forward Study)

The primary empirical investigation evaluated out-of-sample forward operating margin change ($\Delta \text{EBIT Margin}_{t \to t+1}$) under a strict, expanding-window walk-forward design across $N = 46$ shared complete cases:

### Table: Primary Econometric Results (Walk-Forward Fold 1, $N=20$ Test Obs)
```
+---------------------------------------------------------------------------------------+
| Metric                     | Model A (Baseline) | Model B (Operational) | Difference   |
+---------------------------------------------------------------------------------------+
| Mean Absolute Error (MAE)  | 0.0777             | 0.0781                | -0.0005      |
| Relative MAE Change        | —                  | —                     | -0.60%       |
| Root Mean Squared Error    | 0.1431             | 0.1424                | +0.0007      |
| Coefficient of Det. (R²)   | -0.1095            | -0.0988               | +0.0107      |
| Pearson Correlation (r)    | 0.0037             | 0.0473                | +0.0436      |
| Paired t-Statistic         | —                  | —                     | -1.1913      |
| Paired t-Test p-Value      | —                  | —                     | 0.2335       |
| Permutation Test p-Value   | —                  | —                     | 0.2458       |
| Bootstrap 95% CI (ΔMAE)    | —                  | —                     | [-0.0011,    |
|                            |                    |                       |  +0.0003]    |
| Econometric Decision       | —                  | —                     | FAIL TO      |
|                            |                    |                       | REJECT H₀    |
+---------------------------------------------------------------------------------------+
```

### Key Scientific Takeaways
1. **No Incremental Predictive Power:** Under strict chronological walk-forward out-of-sample testing, Model B (Baseline + Operational Text) fails to reject the null hypothesis of equal forecast accuracy ($p = 0.2335$; bootstrap 95% CI crosses zero).
2. **Failure of Cross-Sectional Alpha to Replicate:** In Phase 6 exploratory cross-sectional testing ($N=30$, LOOCV), operational risk features showed suggestive predictive gains ($\Delta\text{MAE} = -4.3\%$, $p=0.0409$). However, this apparent advantage completely vanished when subjected to chronological walk-forward barriers.
3. **Severe Degradation from High-Dimensional Text:** Adding broader text features strictly degrades out-of-sample performance. The Management Group worsens MAE by $-7.62\%$ ($p = 0.0080$), and the Omnibus 12-feature model worsens MAE by $-13.14\%$ ($p = 0.0045$, $\text{RMSE} = 0.1541$).
4. **Filing-Only Parity:** A model conditioned *only* on filing text features achieves an MAE of $0.0771$ ($p = 0.8714$), achieving parity with, but zero incremental value over, trailing accounting ratios.

---

## 6. Interactive Institutional Research Terminal

The visual presentation layer is built with Streamlit and organized into six institutional analytical modules:

```bash
streamlit run src/app/Home.py
```

* **1. Executive Overview:** Global valuation summary, PIT coverage status banner, fundamental snapshot, and frozen Phase 7 academic disclosures.
* **2. Valuation Terminal:** Multi-scenario DCF projections (Base, Bull, Bear), analyst sandbox with in-memory overrides, 2D WACC × Terminal Growth sensitivity matrix, and reverse DCF implied growth solver.
* **3. Accounting Fundamentals:** Standardized Income Statements, Balance Sheets, Cash Flow Statements, and normalized accounting quality ratios with strict units.
* **4. Audited SEC Filings:** Interactive chronological filing catalog, section extractor, and verbatim narrative explorer with EDGAR accession links.
* **5. Qualitative Evidence Audit:** Audited evidence cards with 4-part provenance (Source, Context, Verbatim Quote, Validation Governance) and quarantined disclosure viewer.
* **6. What Changed? / Research Intelligence:** Longitudinal financial deltas, valuation model adjustments, accession metadata shifts, and qualitative narrative evolution timelines.

---

## 7. Installation & Quick Start

### 7.1 Environment Setup
```bash
# Clone repository
git clone https://github.com/institution/ai-assisted-equity-valuation.git
cd ai-assisted-equity-valuation

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 7.2 Run Test Suite
```bash
python -m unittest discover tests -v
```
*Expected Output:* `Ran 260 tests in ~20s ... OK (0 failures, 0 errors)`.

### 7.3 Launch Research Terminal
```bash
streamlit run src/app/Home.py
```

---

## 8. Repository Structure

```
.
├── LICENSE                                # MIT Open-Source License
├── README.md                              # Institutional Overview & Quick Start
├── requirements.txt                       # Python dependencies
├── app/                                   # Presentation Layer (Streamlit Pages & Components)
│   ├── components/                        # Headers, KPI cards, selectors, temporal context
│   └── pages/                             # 6 Institutional Analytical Views
├── config/                                # Universe configuration and company mappings
├── data/                                  # Data stores and public evaluation datasets
│   └── evaluation/                        # Public filing evaluation fixtures
├── docs/                                  # Academic Paper & Reproducibility Documentation
│   ├── INDEX.md                           # Comprehensive Documentation Index
│   ├── RESEARCH_PAPER.md                  # 18-Section Academic Working Paper + Appendices A-F
│   ├── REPRODUCIBILITY_GUIDE.md           # Step-by-step CLI replication instructions
│   ├── EXPERIMENT_REGISTRY.md             # Immutable registry of all 7 empirical experiments
│   ├── DATA_PROVENANCE.md                 # Data lineage, schemas, and PIT rules
│   └── PHASE_*_REPORT.md                  # Detailed phase implementation reports (Phases 0-10)
├── results/                               # Authoritative tabular empirical outputs
│   └── tables/                            # Locked CSV and JSON experiment tables
├── src/                                   # Core Analytical Engines
│   ├── data/                              # SEC Crawler & pipeline orchestrators
│   ├── filing_intelligence/               # Section parsing, feature extraction, evidence validation
│   ├── normalization/                     # [FROZEN] 5-tier XBRL concept cascades
│   ├── research/                          # [FROZEN] Walk-forward panel regressions & tests
│   ├── service/                           # Decoupled PlatformService facade & DTO contracts
│   └── valuation/                         # [FROZEN] Pure-Python deterministic DCF & Reverse DCF
└── tests/                                 # 260 Unit, Regression, and Integration Tests
```

---

## 9. Academic Documentation Package

The complete academic package is available in the `docs/` directory:
* [**`docs/RESEARCH_PAPER.md`**](docs/RESEARCH_PAPER.md): *Empirical Limits of Textual Intelligence in Structural Equity Valuation* (Full 18-section paper).
* [**`docs/REPRODUCIBILITY_GUIDE.md`**](docs/REPRODUCIBILITY_GUIDE.md): Complete instructions to replicate all tables and models.
* [**`docs/EXPERIMENT_REGISTRY.md`**](docs/EXPERIMENT_REGISTRY.md): Comprehensive log of all 7 empirical experiments.
* [**`docs/DATA_PROVENANCE.md`**](docs/DATA_PROVENANCE.md): Data origin, schema definitions, and timestamp logic.
* [**`docs/INDEX.md`**](docs/INDEX.md): Master documentation sitemap.

---

## 10. Research Disclaimers & Limitations

> ### IMPORTANT RESEARCH DISCLAIMER
> 1. **Academic Research Only:** This platform is an academic research laboratory and quantitative demonstration. It does not provide investment advice, financial planning, or fiduciary analysis.
> 2. **No Stock Recommendations:** The platform produces **NO BUY, SELL, OR HOLD RECOMMENDATIONS**.
> 3. **Model-Dependent Fair Value:** All intrinsic valuation calculations (e.g., DCF target prices) are mathematical outputs strictly dependent on user-selected or formulaic inputs (WACC, terminal growth, reinvestment assumptions). They do not represent objective market values.
> 4. **No Promotional Claims:** This project rejects all claims of "AI stock picking," "algorithmic market beating," or "automated textual alpha."
> 5. **Empirical Limitations:** The empirical findings are based on a 30-firm large-cap universe over two walk-forward folds ($N=46$ shared complete cases). Results are subject to survivorship bias and small-sample constraints.
