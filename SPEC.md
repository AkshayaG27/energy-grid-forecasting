# SPEC.md: Hourly Electrical Grid Demand & Probabilistic Dispatch Risk Forecasting
*(Quantile Pinball LightGBM with Over-Forecast Curtailment Proxy and Peak Brownout Margins)*
**Course:** UMC301 - Applied Data Science and Artificial Intelligence  
**Instructor:** Prof. Deepak Subramani, CDS, IISc Bengaluru  
**Paradigm:** Spec-Driven Development (SDD) - Chapter 13  
**Target Milestone:** Project 1 (Tabular Data Science Workflow: Chapter 2 EDA/Statistics + Chapter 4 Machine Learning)

---

## 1. Goal
Build, verify, and deploy an end-to-end tabular data science project combining:
1. **Rigorous Descriptive, Diagnostic, and Statistical Hypothesis Testing (Chapter 2):** Comprehensive summary statistics, distribution diagnostics, omnibus Kruskal-Wallis tests, post-hoc Bonferroni-corrected pairwise tests with effect sizes, and diurnal IQR ribbon visualizations.
2. **Probabilistic Predictive Machine Learning (Chapters 3 & 4):** LightGBM quantile regression ($\tau \in \{0.10, 0.50, 0.90\}$) with strict chronological `TimeSeriesSplit` cross-validation to predict electric grid load (Megawatts) and quantify asymmetric peak-demand (brownout) ceiling and minimum dispatch floor (curtailment risk proxy) on the PJM East interconnection.
3. **Interpretability & Deployment:** TreeSHAP feature attribution explaining peak load events, hosted in an interactive Streamlit operator dashboard.

---

## 2. Constraints
* **Language & Runtime:** Python 3.10+.
* **Core Libraries:** `pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`, `lightgbm`, `shap`, `matplotlib`, `seaborn`, `plotly`, `streamlit`, `pytest`.
* **Statistical Rigor Constraint (Chapter 2):**
  * Check assumptions before testing: Normality (D'Agostino-Pearson / Shapiro-Wilk) and Homoscedasticity (Levene's test).
  * Enforce Omnibus test gatekeeper (Kruskal-Wallis $H$-test) before running any pairwise tests to bound family-wise error rate ($\alpha = 0.05$).
  * Enforce Bonferroni or False Discovery Rate (FDR) adjustment on all post-hoc pairwise comparisons ($p_{\text{adj}} = p \times m$).
  * Report non-parametric effect sizes (**Cliff's Delta $\delta$** and **Eta-squared $\eta_H^2$**) alongside $p$-values.
* **Validation Constraint (Chapter 4):** Strict chronological `TimeSeriesSplit` (5 folds). Random shuffling or standard K-Fold is strictly forbidden to prevent temporal auto-correlation data leakage.
* **Feature Leakage Constraint:** Rolling features and lag operators must use strictly historical observations ($t-1$ and earlier). No forward-looking windows (`center=True` is forbidden).
* **Testing Constraint:** 100% pass rate on automated `pytest` test suite verifying data transformations, feature shapes, no NaNs in training matrices, monotonic quantile outputs ($\hat{y}_{0.10} \le \hat{y}_{0.50} \le \hat{y}_{0.90}$), and inference latency.

---

## 3. Analytical Framework (Chapter 2: EDA & Statistical Testing)

### 3.1 Descriptive Analytics (`summary.md`)
Full 11-metric statistical profile of all numerical and temporal features:
* `Count (Non-Null)`
* `Missing (%)`
* `Mean`
* `Std Dev`
* `Min`
* `25% (Q1)`
* `50% (Median)`
* `75% (Q3)`
* `Max`
* `IQR (Q3 - Q1)`
* `Skewness (Fisher-Pearson coefficient)`
* `Kurtosis (excess)`

### 3.2 Diagnostic Visualizations
1. **Diurnal 24-Hour Profile by Season (`plots/diurnal_load_by_season.png`):**
   * 4-line curves (Spring, Summer, Autumn, Winter) showing mean/median hourly demand across the 24-hour cycle.
   * Translucent shaded ribbons displaying the 25th–75th percentile (IQR) range for every hour to show intra-seasonal variance.
   * Annotations highlighting the dual commute/activity peaks (morning ramp vs. evening peak).
2. **Split Violin Plot: Weekday vs. Weekend (`plots/load_weekday_weekend_violin.png`):**
   * Comparing regular commercial/industrial workdays (Monday–Friday) vs. weekends (Saturday–Sunday) to quantify structural base-load drops.
3. **Split Violin Plot: Holiday vs. Non-Holiday (`plots/load_holiday_violin.png`):**
   * Testing whether US Federal Holidays collapse peak demand.
4. **Dual Correlation Heatmap (`plots/correlation_heatmap.png`):**
   * Comparing **Pearson Linear Correlation ($r$)** vs. **Spearman Monotonic Rank Correlation ($\rho$)** across target load, lags, rolling statistics, and cyclical time encodings.
   * Variance Inflation Factor (**VIF**) analysis to diagnose multicollinearity.

### 3.3 Statistical Hypothesis Testing Framework
* **Pre-Testing Diagnostics:**
  * Normality: D'Agostino-Pearson $K^2$ test on raw load and residuals.
  * Homoscedasticity: Levene's test / Brown-Forsythe test across 4 seasons and 24 hours.
* **Hypothesis 1: Seasonal Differences (Omnibus Kruskal-Wallis H-Test):**
  * $H_0: \text{Median}_{\text{Spring}} = \text{Median}_{\text{Summer}} = \text{Median}_{\text{Autumn}} = \text{Median}_{\text{Winter}}$
  * Metric output: Degrees of freedom, $H$-statistic, $p$-value, and effect size $\eta_H^2 = \frac{H - k + 1}{N - k}$.
* **Hypothesis 2: Post-Hoc Pairwise Seasonal Comparisons:**
  * All $\binom{4}{2} = 6$ pairwise comparisons via Mann-Whitney U test with Bonferroni correction ($p_{\text{adj}} = p \times 6$) and Cliff's Delta ($\delta$).
* **Hypothesis 3: Weekday vs. Weekend Commercial Shift:**
  * Mann-Whitney U test across peak hours (08:00 to 18:00) with Cohen's $d$ / Cliff's $\delta$.
* **Hypothesis 4: Two-Way Factorial ANOVA with Interaction:**
  * Model: $\text{Load} \sim \text{Season} + \text{Hour} + (\text{Season} \times \text{Hour})$ on log-transformed load to determine if the diurnal profile shape depends on the season ($F$-test $p$-value).

---

## 4. Machine Learning Framework (Chapters 3 & 4: Predictive Tabular ML)

### 4.1 Feature Engineering Pipeline
1. **Lags:** `lag_1` ($t-1$), `lag_2` ($t-2$), `lag_24` ($t-24$, same hour yesterday), `lag_168` ($t-168$, same hour last week).
2. **Rolling Windows:** `rolling_mean_24` (mean of past 24 hours), `rolling_std_24` (std of past 24 hours), `rolling_max_24` (peak of past 24 hours).
3. **Calendar & Cyclical:**
   * `hour` (0–23), `dayofweek` (0–6), `month` (1–12), `dayofyear` (1–365).
   * `sin_hour`, `cos_hour`: $\sin(2\pi \cdot h / 24)$, $\cos(2\pi \cdot h / 24)$.
   * `sin_dayofyear`, `cos_dayofyear`: $\sin(2\pi \cdot d / 365.25)$, $\cos(2\pi \cdot d / 365.25)$.
   * `is_weekend`: Binary (1 if Saturday/Sunday, else 0).
   * `is_holiday`: Binary (1 if US Federal Holiday, else 0).

### 4.2 Quantile / Pinball Loss Formulation
For quantile $\tau \in (0, 1)$, ground truth $y$, and prediction $\hat{y}$:
$$\mathcal{L}_\tau(y, \hat{y}) = \max\Big(\tau(y - \hat{y}), (1 - \tau)(\hat{y} - y)\Big) = (y - \hat{y}) \cdot \Big(\tau - \mathbb{I}(y < \hat{y})\Big)$$
* $\tau = 0.90$: Under-prediction penalized $9\times$ more heavily than over-prediction (Peak risk).
* $\tau = 0.50$: Median forecast (MAE).
* $\tau = 0.10$: Over-prediction penalized $9\times$ more heavily than under-prediction (Curtailment risk).

### 4.3 Evaluation Metrics
* **PICP (Prediction Interval Coverage Probability):** $\text{PICP} = \frac{1}{N} \sum_{i=1}^{N} \mathbb{I}(\hat{y}_{0.10}^{(i)} \le y_i \le \hat{y}_{0.90}^{(i)})$. Strict Target $\ge 78.0\%$ (nominal 80.0% band).
* **MPIW (Mean Prediction Interval Width):** $\text{MPIW} = \frac{1}{N} \sum_{i=1}^{N} (\hat{y}_{0.90}^{(i)} - \hat{y}_{0.10}^{(i)})$.
* **Median Point Accuracy:** MAE $\le 1200\text{ MW}$ and MAPE $\le 4.5\%$.
* **Quantile Monotonicity Violation Rate:** Proportion of points where $\hat{y}_{0.10} > \hat{y}_{0.50}$ or $\hat{y}_{0.50} > \hat{y}_{0.90}$. Must be strictly $0.000\%$ after Chernozhukov rearrangement.

### 4.4 Diagnostic & Failure Remediation Protocol
In Spec-Driven Development, if an automated test fails during model evaluation, the following diagnostic tests and remediation procedures must be executed rather than relaxing thresholds:

1. **Diagnostic Test D-1: Asymmetric Tail Exceedance Audit**
   * *Trigger:* Out-of-sample $\text{PICP} < 78.0\%$.
   * *Diagnostic Calculation:* Decompose non-coverage ($1 - \text{PICP}$) into lower tail exceedance $P(y < \hat{y}_{0.10})$ and upper tail exceedance $P(y > \hat{y}_{0.90})$.
   * *Evaluation:* If both tails exceed $10.0\%$ symmetrically (e.g. $\approx 11.5\% - 12\%$), the failure is caused by tree leaf shrinkage pulling extreme quantiles toward the median, rather than model bias.
2. **Remediation Procedure R-1: Shrinkage Compensation via Nominal Quantile Offsets**
   * *Mechanism:* Train boundary regressors with calibrated nominal offsets $\tau_{\text{lower}} = 0.08$ and $\tau_{\text{upper}} = 0.92$ (or via disjoint out-of-fold Conformalized Quantile Regression).
   * *Acceptance Standard:* The adjusted interval $[\hat{y}_{0.08}, \hat{y}_{0.92}]$ serves as the empirical 80% uncertainty envelope and must achieve out-of-sample $\text{PICP} \ge 78.0\%$ on the holdout year while maintaining $\text{MAE} \le 1200\text{ MW}$.
3. **Diagnostic Test D-2: Quantile Crossing Surface Audit**
   * *Diagnostic Calculation:* Quantify raw crossing rate across TimeSeriesSplit cross-validation folds.
   * *Evaluation:* Raw crossing rates of $8\% - 14\%$ are mathematically expected from independently partitioned gradient boosted trees. Verify that post-processing Chernozhukov monotone rearrangement strictly resolves $100\%$ of crossing instances ($\text{Crossing Rate}_{\text{adjusted}} = 0.000\%$).

---

## 5. Acceptance Criteria (Verifiable Pass/Fail)

| ID | Criterion | Verification Mechanism | Pass Threshold |
| :--- | :--- | :--- | :--- |
| **AC-1** | Comprehensive EDA Summary | `data/processed/summary.md` | Full 11-statistic table for numerical & temporal features. |
| **AC-2** | Statistical Hypothesis Testing | `reports/statistical_tests.md` | Pre-test diagnostics, omnibus Kruskal-Wallis, Bonferroni post-hoc tests, effect sizes. |
| **AC-3** | Publication-Grade Visualizations | `reports/plots/` | 4 high-res figures: Diurnal seasonal ribbons, split violins (weekday/weekend), correlation heatmap. |
| **AC-4** | No Future Data Leakage | `pytest tests/test_features.py` | All features strictly backward-looking; zero lookahead. |
| **AC-5** | Monotonicity of Quantiles | `pytest tests/test_model.py` | $\hat{y}_{0.10} \le \hat{y}_{0.50} \le \hat{y}_{0.90}$ for $100.0\%$ of points after rearrangement. |
| **AC-6** | Median & Interval Accuracy | Evaluation script | $\text{MAE} \le 1200\text{ MW}$, $\text{PICP} \ge 78.0\%$ on test year. |
| **AC-7** | TreeSHAP Explainability | `reports/plots/shap_summary_q90.png` | Waterfall & summary plots explaining peak load drivers. |
| **AC-8** | Interactive Deployment | `streamlit run app.py` | App loads within 3 seconds, displays live fan charts and dynamic SHAP breakdown. |

---

## 6. Output Files Manifest

```
Project1_Energy_Grid_Forecasting/
├── data/
│   ├── raw/
│   │   └── PJME_hourly.csv
│   └── processed/
│       └── summary.md             # Full 11-metric statistical summary table
├── reports/
│   ├── statistical_tests.md       # Complete hypothesis test results & interpretations
│   └── plots/
│       ├── diurnal_load_by_season.png
│       ├── load_weekday_weekend_violin.png
│       ├── load_holiday_violin.png
│       ├── correlation_heatmap.png
│       └── shap_peak_waterfall.png
├── src/
│   ├── __init__.py
│   ├── config.py                  # Paths, constants, parameters
│   ├── data_loader.py             # Ingestion, cleaning, datetime alignment
│   ├── eda_statistics.py          # Summary statistics & hypothesis test calculations
│   ├── eda_visualizations.py      # Publication-grade plotting routines
│   ├── feature_engineering.py     # Lags, rolling stats, cyclical encoding
│   ├── model.py                   # LightGBM Quantile Regressors (0.1, 0.5, 0.9)
│   ├── evaluate.py                # Pinball loss, PICP, MPIW, MAE, MAPE
│   └── explainability.py          # TreeSHAP waterfall and summary
├── tests/
│   ├── __init__.py
│   ├── test_data_loader.py
│   ├── test_features.py
│   └── test_model.py
├── app.py                         # Interactive Streamlit dashboard
├── SPEC.md                        # This document
├── PLAN.md                        # Step-by-step execution plan
├── WALKTHROUGH.md                 # Design-decision walkthrough & viva guide
└── requirements.txt
```
