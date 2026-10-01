# AI-Assisted Equity Valuation & Financial Analysis Platform
### Independent High-School Student Quantitative Research Project

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 260 Passing](https://img.shields.io/badge/tests-260%20passing-brightgreen.svg)](tests/)
[![Academic Level](https://img.shields.io/badge/Level-High%20School%20Student%20Research-blue.svg)](#)

> **An independent high-school student quantitative research platform combining SEC Form 10-K filings, deterministic Discounted Cash Flow (DCF) valuation, and natural language processing to empirically test whether AI text analysis can forecast corporate operating performance.**

---

## Student Note: Why I Built This and What the Process Taught Me

### 1. The Spark: Trying to Understand How Real Funds Pick Stocks
In today's AI era, everyone talks about automating everything. What genuinely fascinated me, though, was how real-world asset management companies and portfolio managers actually make decisions. When a fund manager sits down to build a portfolio, what specific factors do they weigh? How do they value a company when there are thousands of moving parts? Having an interest in AI development, I started wondering: could an AI valuation engine analyze all these corporate factors faster and more objectively than a human analyst, without missing the nuances of company reports? That curiosity was the foundation of this entire project.

### 2. My First Battle: The Deceptive Mountain of SEC Filings
My first major shock had nothing to do with building models—it was the sheer chaos of raw financial disclosures. When I started pulling SEC Form 10-K annual reports to build a clean database, I was completely overwhelmed by the volume of information. Over 800,000 raw financial facts across 30 major companies, each tagged with slightly different accounting labels. At first, when things didn't line up, I panicked. I assumed I had made a rookie programming error: I spent days combing through my Python scripts line by line, thinking my parser was broken. Then I looked at the AI outputs, searching for glitches. It took me weeks to realize that the code wasn't the problem—the real world of corporate reporting is simply messy, inconsistent, and fragmented. Taming that data into a reliable, structured pipeline was the hardest engineering hurdle I faced.

### 3. The Strict Reality: You Cannot Cheat the Clock
As I designed the engine, I realized another trap: in real portfolio management, you can never look ahead. If you value a company on December 31, 2022, you cannot use an annual report filed in February 2023. I had to build a strict Point-in-Time rule to ensure the system only ever saw documents that were publicly available at that exact second. Furthermore, I decided that the core valuation shouldn't be an unconstrained AI guess; it had to come from deterministic Discounted Cash Flow (DCF) fundamentals. The role of AI was strictly to parse management narratives and risk disclosures, not to make up share prices out of thin air.

### 4. What the Numbers Taught Me (The Reality Check)
When I tested whether processing corporate text could actually predict future operating profit margins better than standard accounting ratios, I got a humbling result. Under a strict chronological walk-forward test, narrative text signals provided no statistically meaningful forecasting edge over simple historical numbers ($p = 0.2335$). In fact, throwing too many text signals into the model actually degraded accuracy. The AI wasn't finding secret trading signals in management letters; it was just absorbing corporate buzzwords and legal boilerplate.

### 5. My Main Takeaway: A First Step into Modern Finance
If an admissions tutor or professor asks me what I learned from this project, my answer is simple: I see this valuation engine not as a magic black box, but as my personal first step into the intersection of modern AI, macroeconomics, and asset management. I learned how institutional portfolios are actually bounded by financial realities, why data engineering is 80% of any quantitative problem, and why disciplined accounting discipline still beats flashy tech hype. Discovering where algorithms fail under real-world constraints was the most valuable lesson of my high school career.

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
