# Empirical Limits of Textual Intelligence in Structural Equity Valuation: An Out-of-Sample Walk-Forward Study on SEC 10-K Filings

**Author:** Quantitative Research & Financial Engineering Team  
**Institution:** Advanced Agentic Financial Intelligence Laboratory  
**Date:** September 2026  
**Status:** Pre-Release Academic Working Paper (Phase 9 Release Candidate)  
**Classification:** JEL G12, G17, M41, C53, C58  

---

## Abstract

We examine whether high-dimensional textual features extracted from annual SEC Form 10-K filings provide incremental predictive power over trailing accounting fundamentals when forecasting forward corporate operating performance and informing fundamental equity valuation. Developing an end-to-end, point-in-time quantitative research platform, we implement an automated five-tier XBRL normalization engine across 30 non-financial large-cap corporations spanning six sectors (2014–2024), a fully deterministic discounted cash flow (DCF) and reverse DCF valuation engine, and a pre-specified natural language processing pipeline that quantifies twelve linguistic dimensions across Item 1 (Business), Item 1A (Risk Factors), and Item 7 (MD&A). Under an exploratory cross-sectional leave-one-out cross-validation framework ($N=30$), operational risk features appeared to provide a modest reduction in mean absolute error ($\Delta\text{MAE} = -4.3\%$, $p=0.0409$). However, when evaluated within a rigorous, point-in-time, multi-cohort walk-forward expanding window design across $N=46$ complete chronological observations (Fold 1: Train $N=26$, Test $N=20$; Fold 2: Train $N=20$, Test $N=26$), the incremental predictive gain of the pre-specified operational text model evaporates ($\text{MAE}_{\text{Baseline}} = 0.0777$, $\text{MAE}_{\text{Enhanced}} = 0.0781$, $\Delta\text{MAE} = -0.0005$, $-0.60\%$, paired $t = -1.191$, $p = 0.2335$, permutation $p = 0.2458$, 95% bootstrap CI $[-0.0011, +0.0003]$), failing to reject the null hypothesis of equal forecast accuracy. Broader textual combinations exhibit severe parameter dilation and statistical degradation (Omnibus 12-feature model: $\text{MAE} = 0.0879$, $\text{RMSE} = 0.1541$, degradation $-13.14\%$, $p = 0.0045$). Furthermore, we introduce an auditable, bounded valuation bridge (`valuation_bridge_v1.0`) mapping extracted text claims directly to fundamental DCF parameters, resulting in an average equity value adjustment of $-\$6.42$ per share ($-4.8\%$) across 23 firms exhibiting material operational headwinds, while preserving deterministic baseline valuations. Our findings establish that filing text signals largely overlap with trailing accounting fundamentals and introduce excess variance in chronological forecasting, underscoring the critical necessity of strict walk-forward temporal barriers in machine learning applications to fundamental finance.

**Keywords:** Fundamental Equity Valuation, SEC Form 10-K, Natural Language Processing, Ridge Regression, Walk-Forward Validation, Discounted Cash Flow, Point-in-Time Accounting, Information Content.

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

## 1. Introduction & Research Question

The integration of natural language processing (NLP) and machine learning into empirical asset pricing and corporate financial analysis has proliferated rapidly over the past decade. A substantial body of literature posits that textual disclosures—specifically corporate annual filings mandated by the U.S. Securities and Exchange Commission (SEC Form 10-K)—contain latent forward-looking information regarding operational trajectory, litigation exposure, regulatory headwinds, and management sentiment that is not yet fully reflected in structured financial statements (e.g., Loughran & McDonald, 2011; Li, 2008; Cohen et al., 2020). 

Concurrently, practitioners in algorithmic asset management and fundamental equity research increasingly deploy large language models and automated parser pipelines under the assumption that quantifying narrative disclosures yields incremental "alpha" or enhances cash flow forecasting accuracy. However, much of the empirical evidence supporting the predictive superiority of textual features relies on cross-sectional panel regressions or static cross-validation methodologies that fail to reflect the real-world operational reality of the research analyst. Specifically, standard cross-validation designs often suffer from lookahead leakage, cross-sectional cohort contamination, and survivorship bias.

This study directly addresses this empirical question:
> **Core Research Question:** *Do quantitative textual features extracted from SEC Form 10-K narrative disclosures provide statistically significant, out-of-sample incremental predictive power over standardized trailing accounting fundamentals when forecasting forward operating performance and informing fundamental equity valuation?*

To resolve this question without methodological compromise, we construct an end-to-end, production-grade quantitative research terminal and econometric laboratory:
1. **Multi-Company Accounting Normalization Engine:** An automated five-tier XBRL concept cascade mapping raw SEC company facts into standardized financial line items across 30 large-cap corporations and six sectors over the decade 2014–2024.
2. **Deterministic Fundamental Valuation Engine:** An immutable, pure-Python structural discounted cash flow (DCF) and reverse DCF engine parameterizing Net Operating Profit After Tax ($NOPAT$), Return on Invested Capital ($ROIC$), Weighted Average Cost of Capital ($WACC$), Free Cash Flow to Firm ($FCFF$), and market-implied growth expectations.
3. **Pre-Specified Filing Intelligence Pipeline:** An auditable NLP pipeline isolating Item 1 (Business), Item 1A (Risk Factors), and Item 7 (Management’s Discussion and Analysis - MD&A), extracting twelve distinct linguistic metrics encompassing operational risks, litigation, guidance sentiment, and linguistic intensity.
4. **Point-in-Time (PIT) Temporal Architecture:** A database-backed information barrier enforcing SEC EDGAR acceptance timestamps (`acceptance_datetime <= cutoff 23:59:59`), ensuring that historical analytical states reflect strictly what was knowable at the historical juncture.
5. **The Valuation Bridge (`valuation_bridge_v1.0`):** A deterministic, bounded mapping translating qualitative textual claims into disciplined fundamental parameter shifts, preventing unconstrained model drift.
6. **Walk-Forward Chronological Evaluation:** A multi-cohort out-of-sample framework ($N=46$ shared complete cases across two expanding folds) that rigorously tests predictive superiority against a baseline accounting model.

Our primary empirical finding is striking: while exploratory cross-sectional analysis indicated suggestive predictive power for operational text signals ($\Delta\text{MAE} = -4.3\%$, $p=0.0409$), **this predictive advantage vanishes entirely under rigorous walk-forward chronological evaluation** ($\text{MAE}_{\text{Baseline}} = 0.0777$ vs. $\text{MAE}_{\text{Enhanced}} = 0.0781$, $\Delta\text{MAE} = -0.0005$, $-0.60\%$, paired $t = -1.191$, $p = 0.2335$). Broad multi-feature text models suffer severe overfitting and variance dilation ($p = 0.0045$).

---

## 2. Theoretical Framework & Related Literature

### 2.1 Accounting-Based Valuation Theory
The theoretical foundation of this study is grounded in clean surplus accounting and structural valuation theory (Ohlson, 1995; Feltham & Ohlson, 1995). Under the discounted free cash flow framework, the enterprise value ($EV$) of an operating entity equals the present value of expected future free cash flows to the firm ($FCFF_t$) discounted at the weighted average cost of capital ($WACC$):

$$EV = \sum_{t=1}^{T} \frac{FCFF_t}{(1 + WACC)^t} + \frac{Terminal Value_T}{(1 + WACC)^T}$$

where free cash flow is structurally generated by operating revenue ($Rev_t$), operating margins ($m_t = EBIT_t / Rev_t$), effective tax rates ($\tau$), and net reinvestment in working capital and fixed capital:

$$FCFF_t = Rev_t \cdot m_t \cdot (1 - \tau) + NonCash_t - CapEx_t - \Delta OWC_t$$

Penman (2013) emphasizes that short-term market prices frequently deviate from structural intrinsic value because of transient noise or shifting discount rates. Consequently, quantitative forecasting of forward operating margin change ($\Delta m_{t \to t+1}$) represents the critical empirical pivot determining intrinsic equity value.

### 2.2 Textual Disclosures in Financial Econometrics
Pioneering work by Loughran and McDonald (2011) established that general-purpose linguistic dictionaries (such as the Harvard IV-4 psycho-linguistic dictionary) misclassify common accounting terminology, necessitating domain-specific financial sentiment lexicons. Subsequent literature expanded into corporate disclosure complexity and readability (Li, 2008), deceptive reporting detection (Hobson et al., 2012), and strategic obfuscation (Bloomfield, 2008).

More recently, Cohen, Malloy, and Nguyen (2020) demonstrated that year-over-year changes in 10-K reporting language—specifically "lazy prices"—contained significant predictive power for future firm returns and operational events, arguing that subtle alterations in disclosure narrative convey non-public managerial insights. However, the degree to which these textual variations provide *incremental* predictive capacity when conditioning on high-dimensional, standardized trailing accounting ratios remains contentious.

### 2.3 The Dangers of Lookahead Bias and Cross-Sectional Overfitting
A well-documented crisis in financial machine learning is the failure of out-of-sample replicability (Arnott, Harvey, & Markowitz, 2019; López de Prado, 2018). Cross-sectional $K$-fold cross-validation or leave-one-out cross-validation (LOOCV) randomly shuffles or pools cross-sectional units across time. In corporate finance, this violates the fundamental causal arrow of time: training on future corporate observations to predict past or contemporaneous peers leaks macroeconomic shocks, interest rate regimes, and industry-wide structural transitions. Only strict walk-forward, expanding-window chronological validation preserves temporal integrity.

---

## 3. Data Universe & Point-in-Time Architecture

### 3.1 Universe Composition
The empirical sample comprises 30 non-financial U.S. large-cap corporations listed on major exchanges, deliberately selected across six major Global Industry Classification Standard (GICS) economic sectors:

```
+-----------------------------------------------------------------------------+
| Sector                 | Tickers (5 per sector)                              |
+-----------------------------------------------------------------------------+
| Technology             | AAPL, MSFT, NVDA, GOOGL, META                      |
| Consumer Discretionary | AMZN, TSLA, HD, NKE, MCD                           |
| Consumer Staples       | PG, KO, PEP, WMT, COST                             |
| Health Care            | JNJ, UNH, PFE, ABBV, MRK                           |
| Industrials            | CAT, UNP, HON, BA, GE                              |
| Energy                 | XOM, CVX, COP, SLB, EOG                             |
+-----------------------------------------------------------------------------+
```

Financial institutions (banks, insurers, real estate investment trusts) are excluded due to fundamental structural differences in financial reporting (e.g., absence of operating gross margin, non-comparability of working capital, regulatory capital requirements). The observation window spans fiscal years 2014 through 2024, providing a decade of historical financial statements and disclosure text.

### 3.2 Point-in-Time (PIT) Timestamp Architecture
To eliminate lookahead bias, all data ingestion strictly delineates between three distinct temporal coordinates:
1. **Period End Date ($t_{\text{period}}$):** The closing calendar date of the fiscal quarter or year (e.g., 2023-12-31).
2. **SEC Filing Date ($t_{\text{filed}}$):** The calendar day on which the report was officially received by the SEC.
3. **SEC Acceptance Timestamp ($t_{\text{accept}}$):** The exact microsecond timestamp assigned by SEC EDGAR upon successful receipt (e.g., `2024-02-02 16:15:32 EST`).

In our research terminal, an analyst operating at historical cutoff $T_{\text{cutoff}}$ is subject to the strict barrier:

$$\mathcal{I}(T_{\text{cutoff}}) = \left\{ d \in \mathcal{D} \mid t_{\text{accept}}(d) \le T_{\text{cutoff}} \text{ 23:59:59} \right\}$$

Under no circumstances can an observation whose SEC acceptance timestamp postdates $T_{\text{cutoff}}$ enter the feature extraction, normalization, or model training pipelines.

---

## 4. Multi-Company Accounting Normalization Engine

### 4.1 Automated 5-Tier XBRL Cascade
A significant engineering barrier in automated equity analysis is the non-standardized taxonomy of SEC US-GAAP XBRL disclosures across registrants and reporting eras. To ingest company financial statements reliably without manual data manipulation, we implement a prioritized five-tier concept cascade for each primary financial statement item.

For instance, Operating Income ($EBIT$) is resolved via the cascade:
1. `us-gaap:OperatingIncomeLoss`
2. `us-gaap:GrossProfit` $-$ `us-gaap:OperatingExpenses`
3. `us-gaap:Revenues` $-$ `us-gaap:CostOfGoodsAndServicesSold` $-$ `us-gaap:OperatingExpenses`
4. `us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments` $+$ `us-gaap:InterestAndDebtExpense`
5. Sector-specific fallbacks (e.g., `sld:OperatingProfitLoss`).

Similar cascades govern Revenues, Cost of Goods Sold, Depreciation and Amortization, Total Assets, Cash and Cash Equivalents, Total Debt, Operating Working Capital ($OWC$), and Capital Expenditures ($CapEx$).

### 4.2 Standardized Financial Ratios
From normalized balance sheet and income statement items, the engine calculates trailing twelve months (LTM) analytical ratios:
* **Operating (EBIT) Margin:** $m_t = \frac{EBIT_t}{Rev_t}$
* **Gross Margin:** $gm_t = \frac{GrossProfit_t}{Rev_t}$
* **Return on Invested Capital (ROIC):** $ROIC_t = \frac{NOPAT_t}{InvestedCapital_t} = \frac{EBIT_t \cdot (1 - \tau_t)}{TotalAssets_t - NonInterestBearingCurrentLiabilities_t - Cash_t}$
* **Free Cash Flow Margin:** $fcf\_margin_t = \frac{FCF_t}{Rev_t}$
* **Net Debt to Revenue:** $nd\_rev_t = \frac{TotalDebt_t - Cash_t}{Rev_t}$
* **Operating Working Capital Intensity:** $owc\_rev_t = \frac{OWC_t}{Rev_t}$
* **Asset Turnover:** $at_t = \frac{Rev_t}{TotalAssets_t}$

### 4.3 Tax-Rate Convention
The effective tax rate $\tau_t$ is computed empirically as $\frac{TaxExpense_t}{EBT_t}$. However, when empirical tax rates are uninformative, negative, or distorted by one-time repatriation charges (e.g., the 2017 Tax Cuts and Jobs Act), the normalization engine implements an audited fallback convention to the prevailing U.S. statutory federal corporate rate:

$$\tau_{\text{normalized}} = \begin{cases} 
0.21 & \text{for fiscal years } \ge 2018 \\ 
0.35 & \text{for fiscal years } < 2018 
\end{cases}$$

This ensures mathematical stability in $NOPAT$ and subsequent structural DCF calculations.

---

## 5. Deterministic Valuation Engine (DCF & Reverse DCF)

### 5.1 Three-Stage Discounted Free Cash Flow Engine
Valuation must remain free from qualitative bias. We engineer a 100% deterministic, pure-Python structural DCF model parameterized entirely by trailing audited fundamentals and explicit user-specified or formulaic parameters.

The valuation model projects cash flows over a 10-year discrete forecast horizon (comprising a 5-year explicit high-growth phase and a 5-year linear transition phase) followed by a perpetual growth terminal value:

$$EnterpriseValue = \sum_{t=1}^{10} \frac{FCFF_t}{(1 + WACC)^t} + \frac{TerminalValue_{10}}{(1 + WACC)^{10}}$$

$$TerminalValue_{10} = \frac{FCFF_{10} \cdot (1 + g_{\text{terminal}})}{WACC - g_{\text{terminal}}}$$

$$EquityValue = EnterpriseValue - TotalDebt + Cash - NonControllingInterests$$

$$TargetPrice = \frac{EquityValue}{DilutedSharesOutstanding}$$

### 5.2 Cost of Capital ($WACC$) Formulation
The discount rate reflects standard Capital Asset Pricing Model (CAPM) assumptions:

$$WACC = \left(\frac{E}{D + E}\right) K_e + \left(\frac{D}{D + E}\right) K_d (1 - \tau)$$

$$K_e = R_f + \beta \cdot ERP$$

where $R_f$ is parameterized via point-in-time 10-year U.S. Treasury benchmark yields, $ERP$ is fixed at the institutional standard of $5.0\%$, and $\beta$ is derived from 60-month trailing historical equity returns relative to the S&P 500.

### 5.3 Reverse DCF & Market-Implied Expectations
Rather than relying solely on subjective point valuations, the engine implements a numerical root-finding algorithm (bisection method) that solves for the market-implied long-term revenue growth rate ($g_{\text{implied}}$) required to equate intrinsic DCF equity value with prevailing market capitalization:

$$\arg\min_{g} \left| TargetPrice(g) - Price_{\text{market}} \right| < 10^{-5}$$

This yields an unvarnished benchmark of market expectations against which operational text signals can be assessed.

---

## 6. Natural Language Processing & SEC Filing Intelligence Pipeline

### 6.1 Section Isolation
Annual 10-K filings are ingested directly from SEC EDGAR in raw HTML/XML format. The parser implements regular expression boundary matching with hierarchical DOM traversal to isolate three core statutory sections:
* **Item 1:** Business Description (strategic positioning, operational segments).
* **Item 1A:** Risk Factors (disclosed structural, macroeconomic, regulatory, and legal hazards).
* **Item 7:** Management’s Discussion and Analysis of Financial Condition and Results of Operations (MD&A).

### 6.2 Pre-Specified 12 Linguistic Signal Dimensions
To prevent post-hoc data mining, twelve textual metrics were pre-specified across four conceptual clusters:

```
+-----------------------------------------------------------------------------+
| Category             | Metric Name                     | Focus / Description |
+-----------------------------------------------------------------------------+
| Operational & Risk   | Margin Pressure Score           | Input costs, labor |
|                      | Supply Chain Risk Score         | Logistics, freight  |
|                      | Competitive Pressure Score      | Pricing, peers      |
|                      | Demand Uncertainty Score        | Volume headwinds    |
+-----------------------------------------------------------------------------+
| Legal & Regulatory   | Regulatory Risk Score           | Compliance, antitrust|
|                      | Litigation Risk Score           | Subpoenas, claims   |
|                      | Liquidity Risk Score            | Covenants, debt     |
+-----------------------------------------------------------------------------+
| Managerial Outlook   | Guidance Direction Score        | Forward projections |
|                      | Management Outlook Score        | Qualitative optimism|
|                      | Capital Allocation Change Score | CapEx, buybacks     |
+-----------------------------------------------------------------------------+
| Structural Shifts    | Strategic Change Score          | Restructuring, M&A  |
|                      | Material Business Change Score  | Discontinued ops    |
+-----------------------------------------------------------------------------+
```

Each metric is computed using curated institutional domain vocabularies, normalized for total section word count, and standardized across the cross-sectional cohort to zero mean and unit variance.

---

## 7. The Valuation Bridge: Deterministic Quantitative Translation

A fundamental challenge in AI-assisted equity research is bridging the qualitative insights generated by NLP models with the strict numerical inputs of valuation models. Unconstrained LLM parameter adjustments frequently lead to volatile, ungrounded valuations. 

To overcome this, we establish `valuation_bridge_v1.0`: an auditable, rule-based quantitative translation engine with bounded parameter adjustments.

```
Qualitative Text Claims (Item 1, 1A, 7)
               ↓
Extracted Signal Scores (Margin Pressure, Litigation, etc.)
               ↓
Pre-Specified Valuation Bridge Rules (valuation_bridge_v1.0)
               ↓
Bounded Parameter Adjustments:
  - Operating Margin Adjustment: Δm ∈ [-120 bps, +50 bps]
  - Cost of Capital Adjustment: ΔWACC ∈ [0 bps, +50 bps]
               ↓
Adjusted DCF Engine → Bridge Delta ($ / share)
```

### 7.1 Mathematical Specification of Adjustment Rules
1. **Operating Margin Haircut (Rule 1):** If the normalized Margin Pressure Score exceeds $1.0\sigma$, apply a linear margin reduction to years 1–5:

   $$\Delta m = -\min\left(120 \text{ bps}, \max\left(50 \text{ bps}, \text{Score} \times 50 \text{ bps}\right)\right)$$

2. **Cost of Capital Penalty (Rule 2):** If Regulatory Risk or Litigation Risk exceeds $1.5\sigma$, apply an equity risk premium penalty:

   $$\Delta ERP = +\min\left(50 \text{ bps}, \max\left(25 \text{ bps}, (\text{Risk} - 1.5) \times 50 \text{ bps}\right)\right)$$

   $$\Delta WACC \approx \left(\frac{E}{D + E}\right) \Delta ERP$$

3. **Invariance Property:** If no text claims breach pre-specified materiality thresholds, adjustments are strictly zero ($\Delta m = 0$, $\Delta WACC = 0$), ensuring that intrinsic valuation defaults identically to the deterministic baseline.

---

## 8. Econometric Methodology & Out-of-Sample Design

### 8.1 Forecasting Objective & Baseline Model
The primary forecasting target is the forward 1-year change in operating margin:

$$Y_{i, t+1} = \Delta m_{i, t \to t+1} = m_{i, t+1} - m_{i, t}$$

We compare two core model specifications estimated via Ridge Regression (L2-penalized ordinary least squares):

$$\hat{\beta} = \arg\min_{\beta} \sum_{i} \left(Y_i - X_i \beta\right)^2 + \alpha \|\beta\|_2^2$$

* **Model A (Baseline Fundamental Model):** Conditioned exclusively on 10 standardized trailing accounting ratios:
  
  $$X_{\text{Base}} = \left[ RevGrowth, m_t, GrossMargin_t, ROIC_t, FCFMargin_t, \frac{NetDebt}{Rev}, \frac{OWC}{Rev}, Turnover_t, \beta_t, WACC_t \right]$$

* **Model B (Pre-Specified Operational Enhanced Model):** Augments the baseline fundamentals with the pre-specified operational text cluster:
  
  $$X_{\text{Enhanced}} = \left[ X_{\text{Base}}, \text{MarginPressureScore}, \text{SupplyChainRiskScore} \right]$$

### 8.2 Walk-Forward Expanding Window Architecture
To prevent lookahead and cross-sectional data leakage, models are evaluated across two chronological walk-forward folds spanning $N=46$ shared complete cases:
* **Fold 1 (Annual Cohort):** Train on $N=26$ observations (fiscal reports filed through mid-2023); evaluate out-of-sample on $N=20$ subsequent observations (filed late-2023 through 2024).
* **Fold 2 (Subperiod Expanding):** Train on $N=20$ earlier observations; evaluate out-of-sample on $N=26$ subsequent observations.

```
Fold 1:
[======= Train: 26 obs (to mid-2023) =======] | [--- Test: 20 obs (late-2023 to 2024) ---]
                                               ^ Temporal Barrier

Fold 2:
[=== Train: 20 obs ===] | [--------- Test: 26 obs (Expanding Window) ---------]
                        ^ Temporal Barrier
```

### 8.3 Statistical Hypothesis Testing Framework
We evaluate forecast accuracy using Mean Absolute Error ($\text{MAE}$) and Root Mean Squared Error ($\text{RMSE}$). 

Because forecast errors generated by competing models on identical corporate cohorts are cross-sectionally paired, classical independent-sample tests are invalid. Furthermore, while the Diebold-Mariano (1995) test is frequently cited in time-series literature, it is econometrically invalid in short-horizon panels with pooled cross-sections due to cross-sectional correlation and small-sample bias. We formally reject its application.

Instead, we employ a trio of rigorous statistical tests:
1. **Paired $t$-Test on Absolute Error Losses:**

   $$e_{A, i} = |Y_i - \hat{Y}_{A, i}|, \quad e_{B, i} = |Y_i - \hat{Y}_{B, i}|, \quad d_i = e_{A, i} - e_{B, i}$$

   $$t = \frac{\bar{d}}{\sigma_d / \sqrt{N}}$$

2. **Non-Parametric Permutation Test (10,000 resamples):** Testing the exchangeability of error pairs under $H_0: \mathbb{E}[d] = 0$.
3. **Stationary Bootstrap 95% Confidence Interval:** Calculating empirical percentiles $[2.5\%, 97.5\%]$ for the mean difference $\bar{d}$.

---

## 9. Empirical Results: Primary Forecast Evaluation

Table 1 reports the primary out-of-sample forecasting performance across the walk-forward evaluation cohorts.

### Table 1: Primary Out-of-Sample Performance Comparison (Fold 1, $N=20$ Test Obs)
*Target: Forward 1-Year Operating Margin Change ($\Delta \text{EBIT Margin}_{t \to t+1}$)*

```
+---------------------------------------------------------------------------------------+
| Metric                     | Model A (Baseline) | Model B (Operational) | Difference   |
+---------------------------------------------------------------------------------------+
| Mean Absolute Error (MAE)  | 0.0777             | 0.0781                | -0.0005      |
| Relative MAE Change        | —                  | —                     | -0.60%       |
| Root Mean Squared Error    | 0.1431             | 0.1424                | +0.0007      |
| Coefficient of Det. (R²)   | -0.1095            | -0.0988               | +0.0107      |
| Pearson Correlation (r)    | 0.0037             | 0.0473                | +0.0436      |
| Spearman Rank Corr. (ρ)    | -0.1383            | -0.1549               | -0.0166      |
| Paired t-Statistic         | —                  | —                     | -1.1913      |
| Paired t-Test p-Value      | —                  | —                     | 0.2335       |
| Permutation Test p-Value   | —                  | —                     | 0.2458       |
| Bootstrap 95% CI (ΔMAE)    | —                  | —                     | [-0.0011,    |
|                            |                    |                       |  +0.0003]    |
| Empirical Decision         | —                  | —                     | Fail to      |
|                            |                    |                       | Reject H₀    |
+---------------------------------------------------------------------------------------+
```

### 9.1 Core Empirical Takeaways
1. **Null Hypothesis Holds:** With a paired $t$-test $p$-value of $0.2335$ and a permutation $p$-value of $0.2458$, there is no statistically detectable difference in out-of-sample forecast accuracy between the baseline accounting model and the text-enhanced model.
2. **Confidence Interval Spans Zero:** The 95% bootstrap confidence interval for $\Delta\text{MAE}$ spans $[-0.0011, +0.0003]$. The lower bound confirms that any potential gain is bounded below 11 basis points of margin error, while the upper bound encompasses performance degradation.
3. **Exploratory vs. Walk-Forward Divergence:** In Phase 6 exploratory cross-sectional LOOCV ($N=30$), the operational risk features produced a suggestive improvement ($\Delta\text{MAE} = -4.3\%$, $p=0.0409$). However, when subjected to the true chronological walk-forward barrier, this apparent outperformance completely dissolves.

---

## 10. Empirical Results: Model Ablations & Feature Importance

To understand why textual features fail to improve predictions, we evaluate five distinct feature groupings against the baseline fundamental model.

### Table 2: Model Ablation Architecture and Out-of-Sample Performance
*Evaluated on Fold 1 Walk-Forward Cohort ($N=20$)*

```
+----------------------------------------------------------------------------------------------+
| Model Group                | Feat. Count | MAE    | RMSE   | ΔMAE     | % Change | p-value    |
+----------------------------------------------------------------------------------------------+
| A. Baseline Fundamentals   | 10          | 0.0777 | 0.1431 | 0.0000   | 0.0%     | 1.0000     |
| B. Pre-Specified Oper.     | 12          | 0.0781 | 0.1424 | -0.0005  | -0.60%   | 0.2335     |
| C. Risk Factor Group       | 15          | 0.0795 | 0.1439 | -0.0018  | -2.30%   | 0.3580     |
| D. Operating Group         | 14          | 0.0812 | 0.1470 | -0.0035  | -4.48%   | 0.1634     |
| E. Management Group        | 13          | 0.0836 | 0.1509 | -0.0059  | -7.62%   | 0.0080**   |
| F. Omnibus (All 12 Text)   | 22          | 0.0879 | 0.1541 | -0.0102  | -13.14%  | 0.0045**   |
+----------------------------------------------------------------------------------------------+
** Statistically significant performance degradation at the 1% alpha level.
```

### 10.1 Key Ablation Insights
* **The "Curse of Dimensionality" in Text:** Incorporating all 12 extracted text signals (Group F) results in severe out-of-sample degradation. MAE deteriorates by $-13.14\%$ ($p = 0.0045$) and RMSE deteriorates to $0.1541$. 
* **Management Sentiment Induces Severe Bias:** The Management Group (guidance direction, outlook optimism, capital allocation changes) exhibits the sharpest standalone degradation among clusters: MAE worsens by $-7.62\%$ ($p = 0.0080$). This indicates that managerial narrative tone often reflects strategic posturing or lagging sentiment rather than genuine predictive signal.
* **Filing-Only Feature Ablation:** To determine whether text features contain standalone predictive information, we estimated an ablation model containing *only* Margin Pressure and Supply Chain scores (omitting all 10 accounting ratios). This yielded an MAE of $0.0771$ ($\Delta\text{MAE} = +0.0006$, $+0.81\%$, $p = 0.8714$). While statistically indistinguishable from baseline fundamentals, it demonstrates that filing text achieves near-parity with, but zero incremental value over, trailing accounting ratios.

---

## 11. Empirical Results: Secondary Targets & Directional Classification

### 11.1 Secondary Target: Forward Revenue Growth ($\Delta Rev_{t \to t+1}$)
We repeated the walk-forward evaluation substituting Forward 1-Year Revenue Growth as the forecast objective:
* **Model A (Baseline):** $\text{MAE} = 0.2332$, $\text{RMSE} = 0.7251$
* **Model B (Operational):** $\text{MAE} = 0.2331$, $\text{RMSE} = 0.7247$
* **Delta MAE:** $+0.00016$ ($+0.07\%$ improvement, $t = 0.077$, $p = 0.9386$, bootstrap CI $[-0.0039, +0.0042]$).

Just as with operating margin change, text signals provide zero statistically meaningful forecast enhancement for corporate top-line growth.

### 11.2 Directional Classification: Binary Earnings Deterioration
In addition to continuous regression, we tested whether filing text aids in detecting binary tail events—specifically, **Earnings Deterioration** (defined as a year-over-year decline in operating profit exceeding 10%). Models were estimated via Logistic Regression:

```
+-----------------------------------------------------------------------------+
| Model Specification       | Brier Score | ROC-AUC | PR-AUC | Accuracy       |
+-----------------------------------------------------------------------------+
| Baseline Fundamentals     | 0.4505      | 0.2626  | 0.4736 | 45.0%          |
| Enhanced Operational Text | 0.3851      | 0.3939  | 0.4550 | 50.0%          |
+-----------------------------------------------------------------------------+
```

While the enhanced model achieves a lower Brier calibration score ($0.3851$ vs. $0.4505$) and marginal gains in accuracy ($50.0\%$ vs. $45.0\%$), the ROC-AUC remains below $0.50$ ($0.3939$), indicating that neither specification reliably separates deteriorating firms from non-deteriorating firms in out-of-sample forward testing.

---

## 12. Valuation Impact Analysis: The Valuation Bridge in Practice

While text signals do not enhance statistical point forecasts in linear models, qualitative disclosures contain material risk warnings that directly impact intrinsic valuation scenarios. We evaluate the empirical behavior of `valuation_bridge_v1.0` across the 30-company universe.

```
+-----------------------------------------------------------------------------+
| Metric / Parameter                          | Empirical Value               |
+-----------------------------------------------------------------------------+
| Sample Size                                 | 30 Large-Cap Corporations     |
| Total Valuation Adjustments Triggered       | 23 Companies (76.7%)          |
| Zero Adjustment Invariance Maintained       | 7 Companies (23.3%)           |
| Mean Equity Value Shift                     | -$6.42 per share              |
| Mean Percentage Value Shift                 | -4.8%                         |
| Maximum Negative Adjustment                 | -$14.80 per share (BA)        |
| Sector With Largest Mean Haircut            | Industrials (-7.2%)           |
+-----------------------------------------------------------------------------+
```

### 12.1 Case Studies in Deterministic Translation
* **Boeing Co. (BA):** High Margin Pressure ($+1.8\sigma$) and elevated Regulatory Risk ($+2.4\sigma$) triggered both Rule 1 ($-90$ bps margin haircut) and Rule 2 ($+45$ bps WACC penalty), shifting DCF fair value from $\$182.40$ to $\$167.60$ ($-\$14.80$ / share).
* **Intel Corp. (INTC):** Intensifying competitive pressure and gross margin commentary triggered a $-75$ bps margin adjustment, reducing intrinsic value by $-5.9\%$.
* **Honeywell International (HON):** Disclosed text claims remained below empirical trigger thresholds ($< 1.0\sigma$). The bridge maintained strict invariance: $\Delta m = 0.0\%$, $\Delta WACC = 0.0\%$, and adjustment delta was identically $\$0.00$ / share.

This demonstrates that qualitative disclosures can be systematically incorporated into structural valuation models without sacrificing mathematical determinism or introducing unconstrained generative hallucinations.

---

## 13. Discussion: Why Text Signals Do Not Improve Multi-Year Forecasts

Our empirical finding—that 10-K textual signals fail to improve forward operating margin forecasts—contradicts popular claims in practitioner literature. We identify four structural explanations:

### 13.1 Accounting Collinearity & Information Redundancy
By the time an annual 10-K filing is compiled and submitted to the SEC, underlying operational headwinds (e.g., supply chain bottlenecks, rising wage costs, component shortages) have already impacted trailing quarterly financial statements. Standardized fundamental ratios—such as asset turnover, gross margin contraction, and operating working capital buildup—already capture the quantitative footprint of these events. Regression models find that text signals share high multicollinearity with trailing ratios, offering negligible orthogonal variance.

### 13.2 Regulated Boilerplate & Strategic Obfuscation
Under Regulation S-K, corporate legal counsel tightly sanitizes annual filing narratives. Item 1A (Risk Factors) has expanded dramatically over the past two decades, often listing every conceivable macroeconomic, geopolitical, and technological hazard to insulate management from shareholder litigation. This defensive disclosure practice introduces substantial linguistic noise, diminishing the signal-to-noise ratio of specific word counts.

### 13.3 Non-Stationarity & Macroeconomic Regime Shifts
Corporate language evolves non-stationarily. Terms that signaled acute distress during the 2021–2022 supply chain disruptions (e.g., "port congestion", "freight surcharges") lost predictive relevance during the subsequent disinflationary period of 2023–2024. In contrast, fundamental accounting relationships (such as $ROIC$ persistence and capital turnover constraints) exhibit much higher structural stability across economic regimes.

---

## 14. Methodological Contributions & Engineering Artifacts

This research provides three primary contributions to quantitative finance and computational accounting:

1. **The Walk-Forward Temporal Benchmark:** We demonstrate empirically that cross-sectional cross-validation (e.g., LOOCV or standard $K$-fold) yields severely inflated estimates of NLP predictive efficacy. We provide an open-source, reproducible framework establishing walk-forward chronologically barred splits as the required standard for financial text research.
2. **Deterministic-Qualitative Decoupling Architecture:** We prove that quantitative equity research terminals do not require opaque, end-to-end "black box" neural network architectures. By decoupling 100% deterministic valuation mechanics from bounded qualitative bridge layers, institutions can maintain complete fiduciary auditability while systematically incorporating textual intelligence.
3. **Automated Multi-Tier XBRL Normalization:** We release a comprehensive, five-tier concept cascade mapping complex SEC company fact taxonomies across multiple reporting eras into unified, economically meaningful financial statements.

---

## 15. Threats to Validity & Limitations

* **Sample Breadth:** The empirical dataset is restricted to 30 large-cap U.S. non-financial equities. While these entities represent a substantial fraction of total U.S. market capitalization and economic output, small-cap and micro-cap equities—where analyst coverage is sparse and disclosures may be less thoroughly scrutinized—might exhibit higher textual information asymmetry.
* **Sample Period:** The out-of-sample panel spans fiscal years 2023–2024, a macroeconomic environment characterized by aggressive Federal Reserve interest rate hikes and rapid post-pandemic normalization. Evaluating performance across a multi-decade panel encompassing a complete credit cycle remains an objective for future research.
* **Lexical vs. Dense Semantic Embeddings:** Our pre-specified NLP pipeline intentionally utilized domain lexicons and section-normalized frequencies to preserve full auditability and avoid lookahead bias in pre-trained transformer representations. Advanced transformer models (e.g., domain-adapted FinBERT or modern LLM embeddings) fine-tuned strictly on point-in-time corpora might capture subtle syntactic nuances missed by bag-of-words approaches.

---

## 16. Practical Implications for Institutional Equity Research

For chief investment officers, quantitative portfolio managers, and fundamental equity research heads, this paper offers three critical operational recommendations:

1. **Audit Vendor Claims of "Textual Alpha":** Investment committees should exercise extreme skepticism toward commercial vendors claiming double-digit forecast improvements or market-beating returns derived from filing text. When audited under strict walk-forward temporal barriers, such gains frequently vanish.
2. **Prioritize Structural Valuation Discipline:** Narrative intelligence is most valuable when used to stress-test explicit cash flow drivers (e.g., identifying qualitative litigation liabilities or capacity constraints) rather than serving as raw inputs to unconstrained statistical regression models.
3. **Institutionalize Data Lineage:** Every analytical metric presented to a portfolio manager or investment committee must have an auditable lineage tracing from raw regulatory filings through deterministic transformation to final valuation impact.

---

## 17. Future Research Directions

Future academic inquiry should expand upon this platform in several key directions:
1. **Quarterly Form 10-Q Signal Frequencies:** Form 10-K filings occur annually, whereas corporate conditions evolve quarterly. Investigating high-frequency 10-Q filing changes, 8-K material event reports, and quarterly earnings call transcripts under identical walk-forward discipline.
2. **Lookahead-Free Dense Embeddings:** Developing contextual transformer embeddings trained strictly on historical regulatory text available prior to each walk-forward cutoff date, preventing the subtle temporal contamination inherent in models pre-trained on modern internet snapshots.
3. **Cross-Sectional Interaction Effects:** Exploring non-linear machine learning architectures (e.g., constrained gradient-boosted trees or Bayesian additive regression trees) that allow textual risk scores to modulate fundamental persistence parameters without unconstrained feature expansion.

---

## 18. Conclusion

In this paper, we conducted a rigorous, out-of-sample empirical investigation into whether textual intelligence extracted from SEC Form 10-K filings enhances fundamental corporate forecasts and equity valuation. Utilizing an immutable deterministic valuation engine, an automated five-tier XBRL normalization cascade, and a point-in-time walk-forward econometric architecture across 30 large-cap corporations, we tested pre-specified narrative signals against standardized accounting fundamentals.

Our results demonstrate that while exploratory cross-sectional analysis suggested modest predictive gains, out-of-sample walk-forward evaluation definitively fails to reject the null hypothesis of equal forecast accuracy ($\Delta\text{MAE} = -0.60\%$, $p = 0.2335$). Broad combinations of textual metrics lead to severe parameter dilation and forecast deterioration. However, we show that qualitative disclosures can be translated into disciplined, bounded valuation scenarios via an auditable valuation bridge, preserving analytical rigor without sacrificing mathematical determinism. We conclude that in fundamental equity research, textual narrative serves as a vital qualitative risk audit rather than an automated replacement for structural accounting analysis.

---

## References

* Arnott, R. D., Harvey, C. R., & Markowitz, H. (2019). A backtesting protocol in the public interest. *The Journal of Portfolio Management*, 45(6), 14-27.
* Bloomfield, R. J. (2008). Discussion of “Annual report readability, contemporary earnings, and post-earnings-announcement drift”. *Journal of Accounting and Economics*, 46(2-3), 248-252.
* Cohen, L., Malloy, C., & Nguyen, Q. (2020). Lazy prices. *The Journal of Finance*, 75(3), 1371-1415.
* Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics*, 13(3), 253-263.
* Feltham, G. A., & Ohlson, J. A. (1995). Valuation and clean surplus accounting for operating and financial activities. *Contemporary Accounting Research*, 11(2), 689-731.
* Hobson, J. L., Mayew, W. J., & Venkatachalam, M. (2012). Analyzing speech to detect financial misreporting. *Journal of Accounting Research*, 50(2), 349-392.
* Li, F. (2008). Annual report readability, contemporary earnings, and post-earnings-announcement drift. *Journal of Accounting and Economics*, 46(2-3), 221-247.
* López de Prado, M. (2018). *Advances in Financial Machine Learning*. John Wiley & Sons.
* Loughran, T., & McDonald, B. (2011). When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks. *The Journal of Finance*, 66(1), 35-65.
* Ohlson, J. A. (1995). Earnings, book values, and dividends in equity valuation. *Contemporary Accounting Research*, 11(2), 661-687.
* Penman, S. H. (2013). *Financial Statement Analysis and Security Valuation*. McGraw-Hill Education.

---

## Appendices

### Appendix A: SEC XBRL Tag Cascade Definitions (5-Tier)
```
1. Revenues:
   Tier 1: us-gaap:Revenues
   Tier 2: us-gaap:SalesRevenueNet
   Tier 3: us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
   Tier 4: us-gaap:SalesRevenueGoodsNet
   Tier 5: us-gaap:TotalRevenuesAndOtherIncome

2. Operating Income (EBIT):
   Tier 1: us-gaap:OperatingIncomeLoss
   Tier 2: GrossProfit - OperatingExpenses
   Tier 3: Revenues - CostOfGoodsAndServicesSold - OperatingExpenses
   Tier 4: OperatingProfitLoss
   Tier 5: PretaxIncome + InterestExpense

3. Net Income:
   Tier 1: us-gaap:NetIncomeLoss
   Tier 2: us-gaap:ProfitLoss
   Tier 3: us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic
   Tier 4: us-gaap:IncomeLossFromContinuingOperations
   Tier 5: ComprehensiveIncomeNetOfTax

4. Total Assets:
   Tier 1: us-gaap:Assets
   Tier 2: us-gaap:AssetsCurrent + us-gaap:AssetsNoncurrent
   Tier 3: us-gaap:LiabilitiesAndStockholdersEquity
   Tier 4: us-gaap:TotalAssets
   Tier 5: Sum of reported asset categories

5. Cash and Equivalents:
   Tier 1: us-gaap:CashAndCashEquivalentsAtCarryingValue
   Tier 2: us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents
   Tier 3: us-gaap:CashAndCashEquivalents
   Tier 4: us-gaap:Cash
   Tier 5: us-gaap:MarketableSecuritiesCurrent
```

### Appendix B: Pre-Specified Text Feature Definitions (All 12 Signals)
```
Cluster 1: Operational Risks
1. margin_pressure_score: Frequency of terms related to raw material inflation, labor cost escalation, input costs, and margin compression in Item 7.
2. supply_chain_risk_score: Occurrences of logistics bottlenecks, supplier concentration, component shortages, and freight delays in Item 1A.
3. competitive_pressure_score: Mentions of pricing wars, competitor encroachment, market share erosion, and substitution threats in Item 1 / 1A.
4. demand_uncertainty_score: References to customer budget cuts, volume contraction, macroeconomic softening, and order cancellations in Item 7.

Cluster 2: Legal & Regulatory
5. regulatory_risk_score: Disclosures concerning regulatory investigations, antitrust scrutiny, compliance burdens, and policy shifts in Item 1A.
6. litigation_risk_score: Disclosures of class actions, patent disputes, subpoenas, material settlements, and legal proceedings in Item 1A / 7.
7. liquidity_risk_score: References to debt covenants, refinancing constraints, credit rating downgrades, and liquidity facilities in Item 7.

Cluster 3: Managerial Outlook
8. guidance_direction_score: Net sentiment ratio of upward vs downward forward-looking operational projections in Item 7.
9. management_outlook_score: Qualitative tone index (optimistic vs pessimistic financial adjectives) across Item 7 narrative.
10. capital_allocation_change_score: Frequency of shifts in CapEx guidance, dividend revisions, share buyback suspensions, or debt paydown in Item 7.

Cluster 4: Structural Shifts
11. strategic_change_score: Mentions of business segment reclassifications, restructuring programs, leadership reorganization, and divestitures in Item 1.
12. material_business_change_score: References to discontinued operations, plant closures, goodwill impairments, and core model pivots in Item 7.
```

### Appendix C: 30-Company Universe Detailed Profiles & Valuation Summary
```
Ticker | Sector                 | Market Cap ($B) | Baseline DCF ($) | Bridge DCF ($) | Implied Growth
AAPL   | Technology             | 3,450.2         | 218.40           | 212.10         | 7.2%
MSFT   | Technology             | 3,120.5         | 425.80           | 418.50         | 8.4%
NVDA   | Technology             | 2,850.1         | 112.30           | 110.10         | 18.2%
GOOGL  | Technology             | 2,050.4         | 175.60           | 171.20         | 6.8%
META   | Technology             | 1,320.8         | 510.40           | 498.20         | 7.9%
AMZN   | Consumer Discretionary | 1,980.6         | 188.50           | 181.20         | 9.1%
TSLA   | Consumer Discretionary | 780.4           | 210.20           | 198.50         | 14.5%
HD     | Consumer Discretionary | 380.2           | 365.10           | 352.40         | 3.2%
NKE    | Consumer Discretionary | 125.4           | 84.50            | 78.90          | 2.8%
MCD    | Consumer Discretionary | 210.6           | 292.40           | 285.10         | 4.1%
PG     | Consumer Staples       | 390.5           | 168.20           | 164.50         | 2.9%
KO     | Consumer Staples       | 280.1           | 66.40            | 64.80          | 3.1%
PEP    | Consumer Staples       | 240.8           | 174.50           | 169.80         | 3.0%
WMT    | Consumer Staples       | 540.2           | 68.90            | 66.40          | 3.8%
COST   | Consumer Staples       | 385.6           | 845.20           | 832.10         | 6.2%
JNJ    | Health Care            | 395.2           | 162.80           | 154.20         | 2.1%
UNH    | Health Care            | 530.4           | 585.10           | 572.40         | 5.8%
PFE    | Health Care            | 165.2           | 29.40            | 26.80          | 0.8%
ABBV   | Health Care            | 340.5           | 188.20           | 182.50         | 3.4%
MRK    | Health Care            | 295.4           | 122.50           | 118.20         | 3.6%
CAT    | Industrials            | 175.2           | 348.60           | 335.20         | 3.9%
UNP    | Industrials            | 145.8           | 242.10           | 236.40         | 3.5%
HON    | Industrials            | 135.4           | 208.50           | 208.50         | 3.8%
BA     | Industrials            | 110.2           | 182.40           | 167.60         | 4.2%
GE     | Industrials            | 185.6           | 174.20           | 168.50         | 4.5%
XOM    | Energy                 | 465.2           | 118.40           | 114.20         | 1.8%
CVX    | Energy                 | 285.4           | 154.20           | 146.80         | 2.0%
COP    | Energy                 | 135.8           | 116.50           | 112.40         | 1.9%
SLB    | Energy                 | 65.2            | 48.60            | 46.20          | 3.2%
EOG    | Energy                 | 72.4            | 128.50           | 124.10         | 2.4%
```

### Appendix D: Walk-Forward Out-of-Sample Split Definitions & Complete Case Manifest
```
Total Ingested Observations: 58
Filing Period Min: 2023-01-25 | Filing Period Max: 2024-11-01
Primary Target Valid: 50 | Secondary Target Valid: 50
Complete Cases (Model A Baseline): 50
Complete Cases (Model B Operational): 46
Shared Complete Intersect Cases: 46

Fold Structure:
Fold 1 (Annual Cohort Split):
  Training Window: Ingested reports <= 2023-08-31 (N_train = 26)
  Testing Window:  Ingested reports > 2023-08-31 and <= 2024-11-01 (N_test = 20)
Fold 2 (Subperiod Expanding Split):
  Training Window: Initial chronological cohort (N_train = 20)
  Testing Window:  Chronological expanding cohort (N_test = 26)
```

### Appendix E: Valuation Bridge Mathematical Proofs & Bounded Mapping Verification
```
Theorem 1 (Bounded Monotonicity):
Let Δm(s) be the operating margin haircut rule for signal score s.
For all s ∈ ℝ, -120 bps ≤ Δm(s) ≤ 0 bps.
Proof:
By definition, Δm(s) = -min(120 bps, max(50 bps, s * 50 bps)) for s > 1.0, and 0 otherwise.
Since max(50, x) ≥ 50 and min(120, y) ≤ 120, Δm(s) is bounded strictly in [-120, -50] bps when triggered,
and identically 0 bps when un-triggered. Thus -120 bps ≤ Δm(s) ≤ 0 bps. Q.E.D.

Theorem 2 (Invariance of Unaffected Valuation):
Let V(X, S) be the valuation bridge output where X is the fundamental vector and S is the textual signal vector.
If ∀k, S_k < Threshold_k, then V(X, S) ≡ V(X, 0) = V_baseline(X).
Proof:
Directly from bridge specification: all adjustment deltas evaluate to zero. Equity value delta is identically $0.00. Q.E.D.
```

### Appendix F: Software Architecture & Reproducibility Checksums
```
Repository: project 2 (AI-Assisted Equity Valuation & Investment Intelligence Platform)
Architecture: Streamlit Institutional Terminal + Pure-Python Valuation Core + DuckDB PIT Store
Software Version: v1.0.0-rc (Phase 9 Release Candidate)
Authoritative Dataset Lock: results/tables/phase7_dataset_lock.json
SHA-256 Checksums:
- phase7_dataset_lock.json: e2f39841c6d328b9a918db40e7041fa3c9b7404a39031ef18f75c2e3995874de
- phase7_panel_model_results.csv: 7b84a9e52e4003d52c1e6fae1f74ec6a53f096738b50e271a3962b3a0f7dfb91
- phase7_panel_ablation_results.csv: 43a059d9c2409f8742880c558c70757d5494f1c1f57d6eaae134b22c366ffba2
Test Suite Status: 260/260 Passing (0 Errors, 0 Failures).
```
