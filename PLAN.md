# PLAN.md: Step-by-Step Implementation Plan for Project 1

**Project:** Renewable Energy Grid Load & Curtailment Risk Forecasting  
**Spec Reference:** [SPEC.md](file:///C:/Users/aksha/DSAI_Projects/Project1_Energy_Grid_Forecasting/SPEC.md)

---

## Phase 1: Ingestion, Descriptive Statistics & Hypothesis Testing (Chapter 2)

- [x] **Task 1.1: Data Ingestion & Time-Series Cleaning (`src/data_loader.py`)**
  - Parse `Datetime` into a localized hourly index (handle duplicate daylight savings hours, sort chronologically).
  - Add calendar attributes: `hour`, `dayofweek`, `month`, `year`, `season`, `is_weekend`, `is_holiday`.
  - Write `tests/test_data_loader.py` to verify chronological monotonicity and zero missing timestamps.

- [x] **Task 1.2: Descriptive Summary Statistics Table (`data/processed/summary.md`)**
  - Compute full 11 metrics: Count, Missing %, Mean, Std Dev, Min, Q1, Median, Q3, Max, IQR, Skewness, Kurtosis.
  - Compute both overall and season-stratified statistical summaries.
  - Save as formatted Markdown table in `data/processed/summary.md`.

- [x] **Task 1.3: Statistical Hypothesis Testing Suite (`reports/statistical_tests.md`)**
  - **Pre-testing diagnostics:** D'Agostino-Pearson normality test and Levene's homoscedasticity test.
  - **Omnibus Kruskal-Wallis H-test:** Across 4 seasons (testing equality of medians) and across 24 hours. Report $H$, $p$-value, degrees of freedom, and $\eta_H^2$ effect size.
  - **Post-Hoc Pairwise Comparisons:** All 6 seasonal pairs via Mann-Whitney U test with Bonferroni correction and Cliff's Delta ($\delta$) effect sizes.
  - **Multi-Factor Interaction ANOVA:** Two-Way ANOVA ($\text{Season} \times \text{Hour}$) on log-transformed demand with HC3 robust standard errors.
  - Save full academic report to `reports/statistical_tests.md`.

- [x] **Task 1.4: Diagnostic & Publication-Grade Visualizations (`reports/plots/`)**
  - Figure 1: 4-Line 24-Hour Diurnal Curve by Season with 25th–75th percentile (IQR) shaded ribbons.
  - Figure 2: Split Violin Plot: Weekday (Commercial/Industrial) vs. Weekend (Residential).
  - Figure 3: Split Violin Plot: Holiday vs. Non-Holiday demand across hours.
  - Figure 4: Dual Correlation Heatmap (Pearson Linear $r$ vs. Spearman Monotonic $\rho$).

---

## Phase 2: Feature Engineering & Leakage Prevention (Chapter 4)

- [x] **Task 2.1: Feature Engineering Pipeline (`src/feature_engineering.py`)**
  - Lags: `lag_1`, `lag_2`, `lag_24`, `lag_168`.
  - Rolling window aggregates: 24h mean, std, max with strict historical shift.
  - Cyclical encoding: $\sin$ and $\cos$ for `hour` and `dayofyear`.
- [x] **Task 2.2: Leakage Verification Tests (`tests/test_features.py`)**
  - Unit test: Perturb future rows and assert that prior feature values remain unchanged.
  - Unit test: Assert no NaNs remain after warm-up row trimming.

---

## Phase 3: Model Architecture & Training (Chapters 3 & 4)

- [x] **Task 3.1: Chronological TimeSeriesSplit Cross-Validation (`src/model.py`)**
  - Implement 5-fold expanding-window cross-validation.
- [x] **Task 3.2: LightGBM Quantile Regressors**
  - Train 3 distinct LightGBM models with `objective="quantile"` at $\alpha \in \{0.10, 0.50, 0.90\}$.
  - Post-processing monotonicity enforcement ($\hat{y}_{0.10} \le \hat{y}_{0.50} \le \hat{y}_{0.90}$) via Chernozhukov rearrangement.
  - Write `tests/test_model.py` to verify quantile monotonicity, PICP coverage, point accuracy, and latency bounds.
- [x] **Task 3.3: Quantile Calibration & Failure Remediation Protocol**
  - Trigger Diagnostic Test D-1 if PICP < 78.0%: decompose tail exceedance into curtailment ($y < \hat{y}_{0.10}$) and blackout ($y > \hat{y}_{0.90}$).
  - Implement Remediation Procedure R-1: calibrate boundary regressors with shrinkage offsets $\tau \in [0.08, 0.50, 0.92]$ to achieve empirical $\text{PICP} \ge 78.0\%$ on out-of-sample test year without relaxing thresholds.
  - Re-run test suite to verify 100% test pass status.

---

## Phase 4: Quantitative Evaluation & TreeSHAP Attribution

- [x] **Task 4.1: Evaluation Metrics Engine (`src/evaluate.py`)**
  - Compute Pinball Loss for $\tau = 0.1, 0.5, 0.9$.
  - Compute interval metrics: PICP ($\ge 78\%$) and MPIW.
  - Compute median metrics: MAE ($\le 1200\text{ MW}$) and MAPE ($\le 4.5\%$).
- [x] **Task 4.2: TreeSHAP Interpretability (`src/explainability.py`)**
  - Compute TreeSHAP values for the 90th percentile peak risk model.
  - Generate global summary plot and local waterfall plot for the single highest peak load hour.

---

## Phase 5: Streamlit Operator Dashboard & Viva Defense

- [x] **Task 5.1: Interactive Streamlit Dashboard (`app.py`)**
  - Date range / horizon selector.
  - Plotly interactive fan-chart with shaded 80% uncertainty band.
  - Interactive SHAP waterfall explanation for any selected hour.
- [x] **Task 5.2: Design-Decision Walkthrough (`WALKTHROUGH.md`)**
  - Comprehensive viva interview defense guide answering all theoretical and empirical questions.
