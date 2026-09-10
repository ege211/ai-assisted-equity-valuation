# Reproducibility Guide: AI-Assisted Equity Valuation & Investment Intelligence Platform

**Document Version:** 1.0.0  
**Phase:** Phase 9 (Academic Documentation & Reproducibility Package)  
**Authoritative Lock:** `results/tables/phase7_dataset_lock.json`  
**Target Platform:** macOS / Linux (POSIX compliant)  
**Python Compatibility:** Python 3.9, 3.10, 3.11  

---

## 1. Executive Summary & Reproducibility Guarantee

This document provides complete, deterministic instructions to independently replicate every empirical finding, econometric table, valuation model, and research terminal view of the *AI-Assisted Equity Valuation & Investment Intelligence Platform*.

The codebase is engineered with strict deterministic boundaries:
* All accounting calculations, discounted cash flow (DCF) mechanics, and reverse DCF models are 100% pure Python and deterministic.
* The out-of-sample walk-forward empirical results (Phase 7: $N=46$ shared complete cases across 2 expanding folds) execute from pre-computed, point-in-time audited data fixtures, guaranteeing exact bit-for-bit numerical reproducibility.
* All 260 repository unit tests pass with zero network dependencies.

---

## 2. Hardware and Software Prerequisites

### 2.1 System Requirements
* **Operating System:** macOS 12+ (Apple Silicon or Intel) or Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+).
* **CPU:** Modern multi-core x86_64 or ARM64 processor (Apple Silicon M-series supported natively).
* **Memory (RAM):** Minimum 8 GB; 16 GB recommended for full DuckDB in-memory analytical queries.
* **Disk Space:** Minimum 2 GB of available storage.

### 2.2 Software Environment
* **Python:** Python 3.9 or higher (tested on Python 3.9.6, 3.10.12, 3.11.8).
* **Package Manager:** `pip` (standard Python package installer) or `venv`.
* **Database:** DuckDB (embedded in-process engine; no standalone server process required).

---

## 3. Environment Setup & Installation

Follow these steps from a terminal prompt in the project root directory:

```bash
# 1. Clone or navigate to the project repository
cd "project 2"

# 2. Verify Python installation
python3 --version
# Expected output: Python 3.9.x, 3.10.x, or 3.11.x

# 3. Create a clean virtual environment
python3 -m venv .venv

# 4. Activate the virtual environment
# On macOS / Linux:
source .venv/bin/activate

# 5. Upgrade pip to the latest release
pip install --upgrade pip

# 6. Install required project dependencies
pip install -r requirements.txt
```

### Core Dependency Manifest
```
duckdb>=0.9.2
streamlit>=1.28.0
pandas>=1.5.0
numpy>=1.23.0
scipy>=1.9.0
scikit-learn>=1.2.0
requests>=2.28.0
altair>=5.0.0
pytest>=7.0.0
```

---

## 4. Automated Verification & Test Suite Execution

The repository contains a test suite of 260 unit and regression tests verifying accounting logic, DCF mathematics, temporal point-in-time boundaries, and Streamlit state mechanics.

### 4.1 Running the Full Test Suite
Execute the standard unittest runner from the repository root:

```bash
python -m unittest discover tests -v
```

**Expected Result:**
```
Ran 260 tests in ~20.5s
OK
```
*Verification criteria:* Exactly 260 tests run; 0 failures; 0 errors.

### 4.2 Running Specific Test Modules
To verify specific subcomponents independently:

```bash
# Verify Valuation Engine & DCF Mathematics
python -m unittest tests.test_valuation_engine -v

# Verify Reverse DCF Root-Finding
python -m unittest tests.test_reverse_dcf -v

# Verify SEC XBRL Normalization & Fallbacks
python -m unittest tests.test_normalization -v

# Verify Point-in-Time Temporal Boundaries (Phase 8E)
python -m unittest tests.test_point_in_time -v

# Verify Provenance & Data Lineage (Phase 8F)
python -m unittest tests.test_provenance -v

# Verify Streamlit Research Terminal Components (Phase 8G)
python -m unittest tests.test_ui_views -v
```

---

## 5. End-to-End Pipeline Reproduction

The platform is organized into discrete pipeline phases. Each phase can be executed sequentially or audited via its resulting tabular artifacts.

```
+-----------------------------------------------------------------------------------+
| Step | Command / Script                                    | Output Artifact       |
+-----------------------------------------------------------------------------------+
| 1    | python -m src.data.sec_crawler (Optional API fetch) | data/sec_cache/*.json |
| 2    | python -m src.normalization.pipeline                | data/normalized.db    |
| 3    | python -m src.features.build_features               | data/features.parquet |
| 4    | python -m src.valuation.batch_valuation             | results/valuation.csv |
| 5    | python -m src.research.run_phase6_evaluation        | results/tables/phase6*|
| 6    | python -m src.research.run_phase7_panel             | results/tables/phase7*|
+-----------------------------------------------------------------------------------+
```

### 5.1 Reproducing Phase 6: Exploratory Cross-Sectional Analysis
To reproduce the exploratory cross-sectional analysis ($N=30$, LOOCV):

```bash
python -m src.research.run_phase6_evaluation
```
*Outputs generated in `results/tables/`:*
* `phase6_model_comparison.csv`
* `phase6_ablation.csv`
* `phase6_robustness.csv`
* `phase6_valuation_comparison.csv`

### 5.2 Reproducing Phase 7: Out-of-Sample Walk-Forward Panel
To reproduce the primary walk-forward econometric findings ($N=46$ shared complete cases, 2 folds):

```bash
python -m src.research.run_phase7_panel
```

*Outputs generated in `results/tables/`:*
* `phase7_panel_model_results.csv`
* `phase7_panel_ablation_results.csv`
* `phase7_panel_robustness_results.csv`
* `phase7_walkforward_splits.csv`
* `phase7_dataset_lock.json`

### 5.3 Numerical Verification Check
Inspect `results/tables/phase7_panel_model_results.csv` to verify exact matching metrics:

```bash
python -c "
import pandas as pd
df = pd.read_csv('results/tables/phase7_panel_model_results.csv')
f1_base = df[(df['fold_name']=='FOLD_1_ANNUAL_COHORT') & (df['model_name']=='BASELINE') & (df['target_name']=='forward_ebit_margin_change')].iloc[0]
f1_enh = df[(df['fold_name']=='FOLD_1_ANNUAL_COHORT') & (df['model_name']=='ENHANCED_OPERATIONAL') & (df['target_name']=='forward_ebit_margin_change')].iloc[0]
print(f'Model A (Baseline) MAE:    {f1_base[\"mae\"]:.4f}')
print(f'Model B (Operational) MAE: {f1_enh[\"mae\"]:.4f}')
print(f'Delta MAE:                 {f1_enh[\"delta_mae\"]:.4f} ({f1_enh[\"pct_mae_improvement\"]:.2f}%)')
print(f'Paired t-test p-value:     {f1_enh[\"p_value\"]:.4f}')
"
```

**Expected Output:**
```
Model A (Baseline) MAE:    0.0777
Model B (Operational) MAE: 0.0781
Delta MAE:                 -0.0005 (-0.60%)
Paired t-test p-value:     0.2335
```

---

## 6. Launching the Interactive Institutional Research Terminal

The interactive visual interface is built with Streamlit and organized into six analytical modules.

### 6.1 Launch Command
```bash
streamlit run src/app/Home.py
```
Upon execution, Streamlit will start a local web server (typically at `http://localhost:8501`).

### 6.2 Navigating the Terminal
* **Home / Overview:** High-level platform status, dataset lock parameters, and system health.
* **1. Executive Summary:** Portfolio-level valuation distribution, sector breakdowns, and market-implied growth heatmaps.
* **2. Company Analysis:** Single-name deep dives, interactive DCF sensitivity grids, reverse DCF growth rate solvers, and historical financial statements.
* **3. Cross-Sectional Intelligence:** Multi-company comparative metrics, operating margin profiles, and capital structure dispersion.
* **4. Filing Intelligence:** Item 1, 1A, and 7 text signal extractions, word frequency breakdowns, and narrative shift heatmaps.
* **5. Valuation Bridge:** Live translation of qualitative claims to bounded DCF parameter haircuts; interactive toggles for Rule 1 (margins) and Rule 2 (WACC).
* **6. Research & Validation:** Full econometric audit suite displaying walk-forward splits, paired $t$-test distributions, bootstrap confidence intervals, and ablation tables.

### 6.3 Operating Modes: LIVE vs. HISTORICAL (Point-in-Time)
The terminal supports two operating modes accessible from the global sidebar:
* **LIVE Mode:** Uses the latest available regulatory filings and financials.
* **HISTORICAL Mode:** Enforces a strict temporal cutoff ($T_{\text{cutoff}}$). Filings accepted by SEC EDGAR after 23:59:59 on the cutoff date are completely masked from analytical views, replicating the information state available to an analyst on that date.

---

## 7. Deterministic Boundaries vs. External Dependencies

To guarantee institutional integrity, the system strictly separates deterministic computations from external I/O:

```
+------------------------------------------------------------------------------------+
| Component             | Nature        | External Network Req. | Source of Truth     |
+------------------------------------------------------------------------------------+
| XBRL Normalization    | Deterministic | None (Local JSON)     | database/financials |
| DCF Valuation Engine  | Deterministic | None                  | src/valuation/      |
| Reverse DCF Solver    | Deterministic | None                  | src/valuation/      |
| Valuation Bridge v1.0 | Deterministic | None                  | src/valuation/      |
| Walk-Forward Regr.    | Deterministic | None                  | results/tables/     |
| Hypothesis Testing    | Deterministic | None                  | results/tables/     |
| Streamlit Terminal UI | Deterministic | None                  | Local session state |
| SEC EDGAR Crawler     | External I/O  | HTTPS (data.sec.gov)  | SEC EDGAR API       |
+------------------------------------------------------------------------------------+
```

### 7.1 SEC EDGAR Ingestion Policy
If you choose to re-crawl raw filings from SEC EDGAR:
1. Comply with the SEC Fair Access Policy (rate limit of 10 requests per second).
2. Set a valid user-agent string declaring your institution and email address:
   ```bash
   export SEC_USER_AGENT="YourName yourname@domain.edu"
   ```
3. Pre-cached JSON files are stored in `data/sec_cache/` to eliminate network dependency during standard evaluation and testing.

---

## 8. Cryptographic Checksums & Authoritative Lock

The authoritative state of the empirical findings is locked in `results/tables/phase7_dataset_lock.json`. 

```bash
# Verify checksum of dataset lock file (macOS)
shasum -a 256 results/tables/phase7_dataset_lock.json
# Expected: e2f39841c6d328b9a918db40e7041fa3c9b7404a39031ef18f75c2e3995874de

# Verify checksum of model results table (macOS)
shasum -a 256 results/tables/phase7_panel_model_results.csv
# Expected: 7b84a9e52e4003d52c1e6fae1f74ec6a53f096738b50e271a3962b3a0f7dfb91
```

---

## 9. Troubleshooting & FAQ

### Q1: A DuckDB lock error occurs (`IOException: Could not set lock on file`).
* **Cause:** Another process (e.g., a background Streamlit session or Python script) has opened DuckDB in read-write mode.
* **Resolution:** Terminate running Streamlit instances (`pkill -f streamlit`) or configure DuckDB connections with `read_only=True` in read-only analytical scripts.

### Q2: Streamlit displays `Port 8501 is already in use`.
* **Resolution:** Specify an alternative port:
  ```bash
  streamlit run src/app/Home.py --server.port 8502
  ```

### Q3: Python reports `ModuleNotFoundError: No module named 'src'`.
* **Resolution:** Ensure `PYTHONPATH` includes the repository root directory:
  ```bash
  export PYTHONPATH=".:$PYTHONPATH"
  ```

---

## 10. Contact and Citation

For queries regarding code reproduction or econometric methodology, refer to `docs/RESEARCH_PAPER.md` or contact the development team through the official repository issue tracker.
