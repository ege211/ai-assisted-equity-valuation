# Experiment Registry: AI-Assisted Equity Valuation & Investment Intelligence Platform

**Document Version:** 1.0.0  
**Status:** Authoritative Empirical Record (Phase 9 Release Candidate)  
**Authoritative Lock Reference:** `results/tables/phase7_dataset_lock.json`  
**Dataset Universe:** 30 U.S. Large-Cap Non-Financial Equities (2014–2024)  

---

## 1. Registry Architecture & Scientific Standards

This registry tracks every empirical econometric experiment executed across the research program. To eliminate post-hoc outcome selection and publication bias, all experiments are cataloged with pre-specified hypotheses, exact feature definitions, sample boundaries, validation protocols, numerical outcomes, and scientific conclusions.

```
+-----------------------------------------------------------------------------------------------+
| Experiment ID           | Phase   | Design Type              | Target Variable                |
+-----------------------------------------------------------------------------------------------+
| EXP-P6-CROSSSECTIONAL   | Phase 6 | Cross-Sectional LOOCV    | Forward EBIT Margin Change     |
| EXP-P7-PANEL-PRIMARY    | Phase 7 | Walk-Forward Chron. Folds| Forward EBIT Margin Change     |
| EXP-P7-PANEL-SECONDARY  | Phase 7 | Walk-Forward Chron. Folds| Forward Revenue Growth         |
| EXP-P7-PANEL-BINARY     | Phase 7 | Walk-Forward Logistic    | Earnings Deterioration (>10%)  |
| EXP-P7-ABLATION         | Phase 7 | Walk-Forward Ablation    | Forward EBIT Margin Change     |
| EXP-P7-ROBUSTNESS       | Phase 7 | Walk-Forward Sensitivity | Forward EBIT Margin Change     |
| EXP-P5-FILING-EVIDENCE  | Phase 5 | NLP Feature Verification | Statutory Text Signal Extraction|
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Experiment Catalog

---

### Experiment ID: `EXP-P6-CROSSSECTIONAL`
* **Phase:** Phase 6 (Exploratory Empirical Evaluation)
* **Date Completed:** September 8, 2026
* **Status:** Historical Benchmark (Exploratory Only — Superseded by Phase 7)
* **Underlying File:** `results/tables/phase6_model_comparison.csv`, `docs/PHASE_6_EMPIRICAL_EVALUATION_REPORT.md`

#### Hypothesis
Augmenting trailing fundamental accounting ratios with 10-K textual risk and sentiment signals reduces mean absolute prediction error for next-year operating margin changes in cross-sectional estimation.

#### Dataset & Sample Size
* $N = 30$ firms (single cross-sectional snapshot across 30 large-cap equities).
* Cross-validation scheme: Leave-One-Out Cross-Validation (LOOCV).
* Target Variable: Forward 1-Year Operating Margin Change ($\Delta \text{EBIT Margin}_{t \to t+1}$).

#### Model Architecture
* **Baseline Model (Model A):** 9 trailing accounting metrics (Revenue Growth, EBIT Margin, Gross Margin, ROIC, FCF Margin, Net Debt/Revenue, OWC/Revenue, Asset Turnover, Beta).
* **Enhanced Operational Model (Model B):** Baseline fundamentals + Operational Risk Group (`margin_pressure_score`, `supply_chain_risk_score`).
* **Omnibus Model:** Baseline + All 20 extracted filing features.
* Estimator: Ridge Regression with fixed regularization penalty ($\alpha = 1.0$).

#### Exact Numerical Results
```
+-----------------------------------------------------------------------------------------------+
| Model Specification       | MAE     | RMSE    | R²      | ΔMAE vs Base | % Imp.   | p-value   |
+-----------------------------------------------------------------------------------------------+
| 1. Baseline Fundamentals  | 0.11371 | 0.18379 | -1.0077 | —            | —        | —         |
| 2. Operational Risks (B)  | 0.10884 | 0.15455 | -0.4198 | +0.00486     | +4.30%   | 0.0409*   |
| 3. Legal & Regulatory     | 0.11749 | 0.17630 | -0.8474 | -0.00379     | -3.33%   | 0.2841    |
| 4. Guidance & Capital     | 0.12239 | 0.19433 | -1.2447 | -0.00868     | -7.63%   | 0.1120    |
| 5. Macro & Intensity      | 0.13336 | 0.19504 | -1.2612 | -0.01965     | -17.28%  | 0.0210*   |
| 6. All Filing Features    | 0.14362 | 0.19190 | -1.1889 | -0.02991     | -26.30%  | 0.1613    |
+-----------------------------------------------------------------------------------------------+
* Statistically significant at the 5% level under cross-sectional LOOCV.
```

#### Conclusion & Limitations
In cross-sectional LOOCV, the operational risk cluster indicated a statistically significant reduction in forecast error ($\Delta\text{MAE} = -4.3\%$, $p=0.0409$). However, the omnibus model suffered heavy variance dilation ($-26.3\%$). Because cross-sectional LOOCV ignores chronological ordering and pools observations across time, these exploratory results required formal out-of-sample panel validation (Phase 7).

---

### Experiment ID: `EXP-P7-PANEL-PRIMARY`
* **Phase:** Phase 7 (Expanded Out-of-Sample Walk-Forward Research)
* **Date Completed:** September 9, 2026 (Authoritative Lock: September 10, 2026)
* **Status:** Authoritative Primary Finding
* **Underlying File:** `results/tables/phase7_panel_model_results.csv`, `results/tables/phase7_dataset_lock.json`

#### Hypothesis
Textual features pre-specified from SEC Form 10-K filings provide incremental predictive accuracy over standardized trailing accounting ratios when evaluated under strict chronological walk-forward out-of-sample barriers.

#### Dataset & Sample Size
* Universe: 30 large-cap non-financial equities.
* Panel: 58 total ingested observations spanning 2023-01-25 to 2024-11-01.
* Primary Target Coverage: 50 observations.
* Shared Complete Cases: $N = 46$ across both feature spaces.
* Walk-Forward Splits:
  * **Fold 1 (Annual Cohort Split):** Train $N = 26$ (filings $\le$ 2023-08-31); Test $N = 20$ (filings $>$ 2023-08-31 to 2024-11-01).
  * **Fold 2 (Subperiod Expanding Split):** Train $N = 20$; Test $N = 26$.
* Target: Forward 1-Year Operating Margin Change ($\Delta \text{EBIT Margin}_{t \to t+1}$).

#### Model Architecture
* **Model A (Baseline):** 10 standardized accounting ratios (Revenue Growth, EBIT Margin, Gross Margin, ROIC, FCF Margin, Net Debt/Revenue, OWC/Revenue, Asset Turnover, Beta, WACC).
* **Model B (Pre-Specified Operational):** Model A + `margin_pressure_score` + `supply_chain_risk_score`.
* Estimator: Ridge Regression ($\alpha = 100.0$, validated via cross-validation).

#### Exact Numerical Results (Fold 1 Primary Evaluation)
```
+-----------------------------------------------------------------------------------------------+
| Metric                            | Model A (Baseline) | Model B (Operational) | Difference   |
+-----------------------------------------------------------------------------------------------+
| Test Observations (N_test)        | 20                 | 20                    | —            |
| Mean Absolute Error (MAE)         | 0.07767            | 0.07814               | -0.00047     |
| Relative MAE Change               | —                  | —                     | -0.60%       |
| Root Mean Squared Error (RMSE)    | 0.14312            | 0.14243               | +0.00069     |
| Coefficient of Determination (R²) | -0.10947           | -0.09876              | +0.01071     |
| Pearson Correlation (r)           | 0.00373            | 0.04731               | +0.04358     |
| Spearman Rank Correlation (ρ)     | -0.13835           | -0.15489              | -0.01654     |
| Paired t-Statistic                | —                  | —                     | -1.19127     |
| Paired t-Test p-Value             | —                  | —                     | 0.23355      |
| Permutation Test p-Value (10k)    | —                  | —                     | 0.24575      |
| Bootstrap 95% CI (ΔMAE)           | —                  | —                     | [-0.00113,   |
|                                   |                    |                       |  +0.00033]   |
| Econometric Decision              | —                  | —                     | FAIL TO      |
|                                   |                    |                       | REJECT H0    |
+-----------------------------------------------------------------------------------------------+
```

#### Exact Numerical Results (Fold 2 Expanding Window Evaluation)
```
+-----------------------------------------------------------------------------------------------+
| Metric                            | Model A (Baseline) | Model B (Operational) | Difference   |
+-----------------------------------------------------------------------------------------------+
| Test Observations (N_test)        | 26                 | 26                    | —            |
| Mean Absolute Error (MAE)         | 0.07346            | 0.07408               | -0.00062     |
| Relative MAE Change               | —                  | —                     | -0.85%       |
| Root Mean Squared Error (RMSE)    | 0.12871            | 0.12914               | -0.00043     |
| Coefficient of Determination (R²) | -0.15344           | -0.16115              | -0.00772     |
| Paired t-Statistic                | —                  | —                     | -1.44095     |
| Paired t-Test p-Value             | —                  | —                     | 0.14960      |
| Permutation Test p-Value (10k)    | —                  | —                     | 0.13786      |
| Bootstrap 95% CI (ΔMAE)           | —                  | —                     | [-0.00152,   |
|                                   |                    |                       |  +0.00025]   |
| Econometric Decision              | —                  | —                     | FAIL TO      |
|                                   |                    |                       | REJECT H0    |
+-----------------------------------------------------------------------------------------------+
```

#### Conclusion
Under rigorous chronological walk-forward out-of-sample conditions, Model B yields no statistically significant improvement over Model A in either fold ($p = 0.2335$ in Fold 1, $p = 0.1496$ in Fold 2). The 95% bootstrap confidence interval crosses zero in both cases. We definitively fail to reject the null hypothesis of equal predictive accuracy.

---

### Experiment ID: `EXP-P7-PANEL-SECONDARY`
* **Phase:** Phase 7 (Expanded Out-of-Sample Walk-Forward Research)
* **Date Completed:** September 9, 2026
* **Status:** Authoritative Secondary Finding
* **Underlying File:** `results/tables/phase7_panel_model_results.csv`

#### Hypothesis
Textual features pre-specified from SEC Form 10-K filings enhance out-of-sample predictions of forward 1-year corporate revenue growth ($\Delta Rev_{t \to t+1}$).

#### Exact Numerical Results (Fold 1, $N=20$)
```
+-----------------------------------------------------------------------------------------------+
| Metric                            | Model A (Baseline) | Model B (Operational) | Difference   |
+-----------------------------------------------------------------------------------------------+
| Mean Absolute Error (MAE)         | 0.23325            | 0.23309               | +0.00016     |
| Relative MAE Change               | —                  | —                     | +0.07%       |
| Root Mean Squared Error (RMSE)    | 0.72510            | 0.72474               | +0.00036     |
| Paired t-Statistic                | —                  | —                     | +0.07699     |
| Paired t-Test p-Value             | —                  | —                     | 0.93863      |
| Permutation Test p-Value          | —                  | —                     | 0.93606      |
| Bootstrap 95% CI (ΔMAE)           | —                  | —                     | [-0.00387,   |
|                                   |                    |                       |  +0.00419]   |
| Econometric Decision              | —                  | —                     | FAIL TO      |
|                                   |                    |                       | REJECT H0    |
+-----------------------------------------------------------------------------------------------+
```

#### Conclusion
Textual features provide no detectable incremental forecast power for top-line revenue growth ($p = 0.9386$).

---

### Experiment ID: `EXP-P7-PANEL-BINARY`
* **Phase:** Phase 7 (Expanded Out-of-Sample Walk-Forward Research)
* **Date Completed:** September 9, 2026
* **Status:** Authoritative Binary Classification Finding
* **Underlying File:** `results/tables/phase7_panel_model_results.csv`

#### Hypothesis
Filing text improves the probability calibration and detection accuracy of acute corporate earnings deterioration ($>10\%$ decline in operating income).

#### Model Architecture
Logistic Regression comparing Baseline Accounting vs. Operational Enhanced text features.

#### Exact Numerical Results (Fold 1, $N=20$)
```
+-----------------------------------------------------------------------------------------------+
| Metric                            | Baseline Model     | Operational Enhanced  | Delta        |
+-----------------------------------------------------------------------------------------------+
| Brier Score (Calibration Loss)    | 0.45046            | 0.38509               | -0.06537     |
| ROC Area Under Curve (ROC-AUC)    | 0.26263            | 0.39394               | +0.13131     |
| Precision-Recall AUC (PR-AUC)     | 0.47355            | 0.45500               | -0.01855     |
| Out-of-Sample Accuracy            | 45.0%              | 50.0%                 | +5.0%        |
+-----------------------------------------------------------------------------------------------+
```

#### Conclusion
While probability calibration marginally improves (Brier score moves from 0.4505 to 0.3851), the ROC-AUC remains below the 0.50 random classification threshold (0.3939), demonstrating an absence of reliable directional classification alpha.

---

### Experiment ID: `EXP-P7-ABLATION`
* **Phase:** Phase 7 (Expanded Out-of-Sample Walk-Forward Research)
* **Date Completed:** September 9, 2026
* **Status:** Authoritative Feature Cluster Ablation
* **Underlying File:** `results/tables/phase7_panel_ablation_results.csv`

#### Exact Numerical Results (Fold 1, $N=20$)
```
+-----------------------------------------------------------------------------------------------+
| Model Group                | Feat. Count | MAE     | RMSE    | ΔMAE      | % Imp.   | p-value   |
+-----------------------------------------------------------------------------------------------+
| A. Baseline Fundamentals   | 10          | 0.07767 | 0.14312 | 0.00000   | 0.0%     | 1.00000   |
| B. Baseline + All 12 Text  | 22          | 0.08788 | 0.15407 | -0.01020  | -13.14%  | 0.00452** |
| C. Operational Risk Group  | 12          | 0.07814 | 0.14243 | -0.00047  | -0.60%   | 0.23355   |
| D. Risk Factor Group       | 15          | 0.07946 | 0.14392 | -0.00179  | -2.30%   | 0.35801   |
| E. Operating Group         | 14          | 0.08115 | 0.14698 | -0.00348  | -4.48%   | 0.16338   |
| F. Management Group        | 13          | 0.08359 | 0.15091 | -0.00592  | -7.62%   | 0.00796** |
+-----------------------------------------------------------------------------------------------+
** Statistically significant degradation at the 1% alpha level.
```

#### Conclusion
Increasing textual dimensionality strictly degrades out-of-sample forecast accuracy. The Management Group ($p = 0.0080$) and Omnibus Group ($p = 0.0045$) both induce severe parameter distortion and statistically significant degradation.

---

### Experiment ID: `EXP-P7-ROBUSTNESS`
* **Phase:** Phase 7 (Expanded Out-of-Sample Walk-Forward Research)
* **Date Completed:** September 9, 2026
* **Status:** Authoritative Robustness and Sensitivity Record
* **Underlying File:** `results/tables/phase7_panel_robustness_results.csv`

#### 1. Regularization Penalty Sensitivity ($\alpha$ from 0.01 to 100.0)
```
+-----------------------------------------------------------------------------------------------+
| Alpha Value | Baseline MAE | Enhanced MAE | Delta MAE | % Improvement | p-value | Conclusion  |
+-----------------------------------------------------------------------------------------------+
| Alpha=0.01  | 0.09859      | 0.10123      | -0.00263  | -2.67%        | 0.0919  | Sensitive   |
| Alpha=0.1   | 0.09857      | 0.10078      | -0.00222  | -2.25%        | 0.1362  | Sensitive   |
| Alpha=1.0   | 0.09812      | 0.09745      | +0.00068  | +0.69%        | 0.6610  | Robust/Flat |
| Alpha=10.0  | 0.09506      | 0.09395      | +0.00110  | +1.16%        | 0.1477  | Robust/Flat |
| Alpha=50.0  | 0.08175      | 0.08204      | -0.00029  | -0.35%        | 0.5456  | Robust/Flat |
| Alpha=100.0 | 0.07767      | 0.07814      | -0.00047  | -0.60%        | 0.2335  | Primary Lock|
+-----------------------------------------------------------------------------------------------+
```

#### 2. Sector Subsample Evaluations
```
+-----------------------------------------------------------------------------------------------+
| Sector                 | N_obs | Baseline MAE | Enhanced MAE | Delta MAE  | p-value | Status  |
+-----------------------------------------------------------------------------------------------+
| Consumer Discretionary | 3     | 0.01564      | 0.01666      | -0.00102   | 0.0271  | Degraded|
| Consumer Staples       | 2     | 0.02921      | 0.03102      | -0.00181   | 1.0000  | Degraded|
| Energy                 | 5     | 0.02552      | 0.02621      | -0.00069   | 0.2271  | Degraded|
| Health Care            | 5     | 0.10442      | 0.10419      | +0.00022   | 0.6449  | Neutral |
| Industrials            | 4     | 0.14086      | 0.14150      | -0.00064   | 0.6771  | Degraded|
+-----------------------------------------------------------------------------------------------+
```

#### 3. Outlier Trimming & Filing-Only Feature Test
* **Outlier Trimming (Top 2 Outliers Excluded, $N=18$):** Baseline MAE $= 0.04263$, Enhanced MAE $= 0.04338$, $\Delta\text{MAE} = -0.00075$ ($-1.76\%$, $p = 0.0354$). Text features degrade performance even more when extreme outliers are removed.
* **Filing-Only Features (No Financials, $N=20$):** Baseline MAE $= 0.07767$, Filing-Only MAE $= 0.07714$, $\Delta\text{MAE} = +0.00053$ ($+0.68\%$, $p = 0.8714$). Achieves parity with fundamentals, but zero incremental additive power.

---

### Experiment ID: `EXP-P5-FILING-EVIDENCE`
* **Phase:** Phase 5 (SEC Filing Intelligence Pipeline)
* **Date Completed:** September 8, 2026
* **Status:** Extraction Quality Verified
* **Underlying File:** `results/tables/phase5_signal_summary.csv`, `docs/PHASE_5_FILING_INTELLIGENCE_REPORT.md`

#### Objective
Validate section parser boundary extraction and signal extraction completeness across all 30 target entities over 10-K filings from 2014 to 2024.

#### Quality Metrics
* Section extraction success rate: 100.0% for Item 1, Item 1A, and Item 7 across all 30 entities.
* Signal coverage: 12 pre-specified linguistic dimensions populated for all valid filings.
* Total extracted raw textual records audited: 330 filings.
* Zero null or NaN signal outputs generated across the production corpus.
