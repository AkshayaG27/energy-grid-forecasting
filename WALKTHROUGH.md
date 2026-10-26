# Project 1: Hourly Electrical Grid Demand & Probabilistic Dispatch Risk Forecasting
## Comprehensive Architectural Walkthrough & Viva Defense Guide
*(Quantile Pinball LightGBM with Over-Forecast Curtailment Proxy and Peak Brownout Margins)*

**Course:** Applied Data Science and Artificial Intelligence (UMC301)  
**Institution:** Indian Institute of Science (IISc), Computational and Data Sciences (CDS)  
**Dataset:** PJM Interconnection (PJM East Grid, 145,392 hourly readings, 2002–2018)  
**Target:** Hourly Electrical Grid Demand (`PJME_MW`, Megawatts)  

---

## 1. Executive Summary & Problem Formulation

Modern power grids face a severe operational dilemma: **asymmetric operational risk**.
* **Under-predicting peak demand ($y > \hat{y}$):** Leads to catastrophic blackout events, unscheduled peaker turbine firing ($10\times$ higher generation costs), or forced load shedding.
* **Over-predicting base demand ($y < \hat{y}$):** Leads to excess baseload generation, forcing renewable energy curtailment (dumping solar/wind generation), negative locational marginal pricing (LMP), and inefficient thermal ramping.

Conventional machine learning approaches (e.g. OLS, MSE-trained XGBoost/Neural Networks) optimize symmetric Mean Squared Error ($L_2$ loss), which estimates the **conditional mean** $E[Y|X]$. This fails in grid dispatch because an error of $+1,000\text{ MW}$ (over-generation) does **not** carry the same economic or societal cost as $-1,000\text{ MW}$ (grid collapse).

### The Asymmetric Solution: Quantile Regression & The Newsvendor Derivation
We formulate the problem under **Pinball (Quantile) Loss** $\mathcal{L}_\tau(y, \hat{y})$ for nominal quantiles $\tau \in \{0.10, 0.50, 0.90\}$:
$$\mathcal{L}_\tau(y, \hat{y}) = (y - \hat{y}) \cdot \Big(\tau - \mathbb{I}(y < \hat{y})\Big) = \begin{cases} \tau (y - \hat{y}) & \text{if } y \ge \hat{y} \\ (1 - \tau)(\hat{y} - y) & \text{if } y < \hat{y} \end{cases}$$

Under the classic **Newsvendor Critical Fractile**, the optimal asymmetric quantile $\tau^*$ is derived from the ratio of unit under-prediction cost ($C_{\text{under}}$) to over-prediction cost ($C_{\text{over}}$):
$$\tau^* = \frac{C_{\text{under}}}{C_{\text{under}} + C_{\text{over}}}$$
Assuming an empirical $10:1$ operational penalty ratio ($C_{\text{under}} = 10, C_{\text{over}} = 1$), the optimal safety margin is $\tau^* = \frac{10}{11} \approx 0.909$, mathematically justifying the choice of $\tau = 0.90$ for the peak brownout reserve ceiling.

* **$\tau = 0.90$ (Peak / Blackout Risk Margin):** Under-prediction is penalized $9\times$ more heavily than over-prediction. Grid operators dispatch spinning reserves based on this upper ceiling.
* **$\tau = 0.50$ (Conditional Median):** Minimizes Mean Absolute Error ($L_1$ loss), robust to extreme outlier spikes.
* **$\tau = 0.10$ (Dispatch Floor / Curtailment Risk Proxy):** Over-prediction is penalized $9\times$ more heavily than under-prediction. Defines the non-curtailable baseload floor.

> **Data Integrity & Framing Note:** The PJM East dataset records aggregate electrical load demand (`PJME_MW`). It does not contain direct solar/wind generation or curtailment time-series. The lower quantile $\hat{y}_{0.10}$ serves as an operational proxy for minimum dispatchable thermal baseload capacity ($P_{\min}$). When actual demand falls below this floor ($y < \hat{y}_{0.10}$), must-run baseload congestion occurs, which is the primary operational trigger for renewable curtailment in grid systems.

Together, $[\hat{y}_{0.10}, \hat{y}_{0.90}]$ provides an **80% central uncertainty envelope** that enables probabilistic dispatch planning.

---

## 2. Statistical Pre-Conditions & Rigorous EDA

Before training models, Chapter 2 discipline requires validating statistical assumptions. Standard ANOVA and linear regression require normality and homoscedasticity. We empirically tested both:

### 2.1 Normality Diagnostic (D'Agostino-Pearson $K^2$ Test)
$$K^2 = s^2 + k^2 \sim \chi^2_2$$
* **Observed Statistic:** $K^2 = 12,473.86$, $p < 10^{-300}$.
* **Skewness:** $+0.320$ | **Kurtosis:** $-0.442$.
* **Conclusion:** The empirical load distribution is heavily non-normal, decisively rejecting Gaussian modeling assumptions.

### 2.2 Homoscedasticity Diagnostic (Levene's Test)
$$W = \frac{(N - k)}{(k - 1)} \cdot \frac{\sum_{i=1}^k N_i (\bar{Z}_{i\cdot} - \bar{Z}_{\cdot\cdot})^2}{\sum_{i=1}^k \sum_{j=1}^{N_i} (Z_{ij} - \bar{Z}_{i\cdot})^2}$$
* **Observed Statistic:** $W = 5,958.52$, $p < 10^{-300}$.
* **Conclusion:** Severe heteroscedasticity across seasonal groups, invalidating Ordinary Least Squares (OLS) and homoscedastic Gaussian processes.

### 2.3 Non-Parametric Omnibus Hypothesis Testing (Kruskal-Wallis $H$-Test)
Because normality and equal variance fail, we applied the non-parametric Kruskal-Wallis test across the 4 seasons:
$$H = \frac{12}{N(N+1)} \sum_{j=1}^k \frac{R_j^2}{n_j} - 3(N+1)$$
* **$H$-Statistic:** $27,143.61$ ($p < 10^{-300}$, $\text{df}=3$).
* **Effect Size ($\eta_H^2$):** $18.67\%$ of the total variance in load ranks is attributable solely to seasonal shift.
* **Post-Hoc Pairwise Tests (Bonferroni-Corrected Mann-Whitney U):**
  * All 6 pairwise comparisons significant at $p_{\text{adj}} < 10^{-200}$.
  * Largest effect: Summer vs. Spring ($\Delta = 4,879\text{ MW}$, Cliff's $\delta = +0.387$).

---

## 3. Empirical Feature Selection Architecture

Rather than arbitrary feature generation, all 20 features were mathematically selected via 4 formal statistical experiments:

| Experiment | Tool / Metric | Statistical Finding | Feature Engineered |
| :--- | :--- | :--- | :--- |
| **Autoregressive Memory** | Partial Autocorrelation (PACF) | Lags 1 (+0.975), 2 (-0.856), 24 (-0.525), and 168 (-0.232) pierced Bartlett's 95% noise bounds ($\pm 0.0051$). Intermediate lags collapsed to zero. | `lag_1`, `lag_2`, `lag_24`, `lag_168` |
| **Resonant Frequencies** | Fast Fourier Transform (Periodogram) | Dominant spectral power at $f = 0.04167\text{ h}^{-1}$ (period 24.0h), $f = 0.0833\text{ h}^{-1}$ (period 12.0h), and $f = 0.00595\text{ h}^{-1}$ (period 168.0h). | `sin_hour`, `cos_hour`, `sin_doy`, `cos_doy` |
| **Multicollinearity Elimination** | Variance Inflation Factor (VIF) | Using all 24 individual hourly lags caused severe multicollinearity ($\text{VIF} > 140\text{ to }930$). Replacing them with a single 24-hour shifted rolling window reduced collinearity to $\text{VIF} = 3.2$. | `rolling_mean_24`, `rolling_std_24`, `rolling_max_24` |
| **Non-Linear Dynamics** | Mutual Information (MI / Kraskov) | Lags 1 (1.55 nats) and 2 (0.92 nats) carried highest mutual information. Rate of change carries rapid shock information. | `load_velocity_1_2`, `load_ratio_1_24` |

### Zero Data Leakage Guarantee
To prevent lookahead contamination:
1. Every rolling window computation is strictly shifted:
   ```python
   shifted_series = df[TARGET_COL].shift(1)
   df["rolling_mean_24"] = shifted_series.rolling(24).mean()
   ```
2. Unit tests (`test_features.py`) perturb future timestamps ($t + 100$) by $99,999,999\text{ MW}$ and mathematically assert that past features ($t$) remain bit-for-bit identical (`atol=1e-6`).

---

## 4. Model Architecture & The Quantile Crossing Resolution

### 4.1 Why Independent Quantile Trees Cross
Because $\hat{f}_{0.10}(X)$, $\hat{f}_{0.50}(X)$, and $\hat{f}_{0.90}(X)$ are optimized independently, stochastic tree partition boundaries can produce instances where $\hat{y}_{0.10}(X) > \hat{y}_{0.50}(X)$ or $\hat{y}_{0.50}(X) > \hat{y}_{0.90}(X)$ (crossing rate $\approx 9.7\%$ on raw test data).
In physical reality, a cumulative distribution function must be monotonically non-decreasing: $F^{-1}(\tau_1) \le F^{-1}(\tau_2)$ for $\tau_1 < \tau_2$.

### 4.2 Chernozhukov Monotone Rearrangement (2010)
We implement the post-processing monotone rearrangement theorem established by **Chernozhukov, Fernández-Val, & Galichon (Econometrica, 2010)**:
$$\hat{q}^*(\tau) = \text{Sort}\Big(\begin{bmatrix} \hat{q}_{0.10}(X) \\ \hat{q}_{0.50}(X) \\ \hat{q}_{0.90}(X) \end{bmatrix}\Big)$$
**Theorem:** Sorting the estimated quantile functions along the quantile axis strictly reduces (or maintains) the estimation error under any $L_p$ norm ($p \ge 1$):
$$\|\hat{q}^* - q_0\|_p \le \|\hat{q} - q_0\|_p$$
Post-rearrangement, the test quantile crossing rate is **0.000% across all 8,760 hours**.

---

## 5. TreeSHAP Attribution & Peak Risk Deconstruction

Linear feature importance (e.g. split counts) is non-additive and biased toward high-cardinality continuous features. We implement **TreeSHAP** (Lundberg et al., *Nature Machine Intelligence* 2020), which satisfies:
1. **Local Accuracy (Additivity):** $\sum_{i=1}^M \phi_i(x) = f(x) - E[f(X)]$.
2. **Missingness:** Features with no impact receive zero attribution.
3. **Consistency:** If a feature's marginal contribution increases, its Shapley value cannot decrease.

### Key Attribution Findings
1. **`lag_1` and `rolling_mean_24` dominate global attribution:** High recent load pushes the 90th percentile forecast up by up to $+6,000\text{ MW}$.
2. **Local Peak Waterfall Analysis:** During the extreme summer peak event ($49,566\text{ MW}$), the model elevated its base prediction of $32,150\text{ MW}$ up to $48,200\text{ MW}$, driven primarily by:
   * `rolling_max_24` ($+5,240\text{ MW}$)
   * `lag_1` ($+4,120\text{ MW}$)
   * `sin_hour` / `cos_hour` afternoon peak alignment ($+2,380\text{ MW}$)
   * `month` summer cooling degree penalty ($+1,890\text{ MW}$).

---

## 6. Viva Defense & Interview Master Q&A

### Q1: Why not just use an LSTM or Prophet for this time series task?
**Answer:**
1. **Empirical Performance on Dense Tabular Time Series:** On hourly tabular grid datasets with strong autoregressive anchors, gradient boosted trees (LightGBM) consistently outperform LSTMs in both training speed (seconds vs. hours) and predictive accuracy without requiring GPU infrastructure.
2. **Direct Asymmetric Loss Optimization:** Prophet assumes Gaussian or additive errors and does not optimize asymmetric pinball loss directly. LightGBM allows direct optimization of custom non-smooth quantile objectives via piecewise gradients: $g_i = \tau - \mathbb{I}(y_i < \hat{y}_i)$.
3. **Exact TreeSHAP Interpretability:** Grid dispatchers cannot deploy "black-box" models. TreeSHAP provides exact polynomial-time ($O(TLD^2)$) Shapley attributions, whereas recurrent deep networks require noisy approximations (Integrated Gradients or KernelSHAP).

### Q2: What is the exact mathematical gradient of the Pinball Loss in LightGBM?
**Answer:**
The pinball loss $\mathcal{L}_\tau(y, \hat{y}) = (y - \hat{y})(\tau - \mathbb{I}(y < \hat{y}))$ is non-differentiable at $y = \hat{y}$.
Its subgradient with respect to $\hat{y}$ is:
$$\frac{\partial \mathcal{L}_\tau}{\partial \hat{y}} = \mathbb{I}(y < \hat{y}) - \tau = \begin{cases} -\tau & \text{if } y > \hat{y} \text{ (under-prediction)} \\ 1 - \tau & \text{if } y < \hat{y} \text{ (over-prediction)} \end{cases}$$
Because the second derivative (Hessian) is 0 everywhere (or undefined at 0), LightGBM substitutes a constant pseudo-Hessian $h_i = 1.0$ (or Huber-approximated quantile loss) to enable Newton-Raphson tree splitting.

### Q3: Why did you use expanding-window TimeSeriesSplit rather than random K-Fold CV?
**Answer:**
Random K-Fold cross-validation shuffles observations independently, allowing training folds to observe future timestamps ($t+1$) while predicting past timestamps ($t$). Because electric grid demand has strong autoregressive memory (autocorrelation $> 0.95$), random CV results in catastrophic optimistic data leakage.
Expanding-window `TimeSeriesSplit` strictly enforces temporal causality: Fold $k$ is trained exclusively on $\{1, \dots, T_k\}$ and evaluated on the subsequent out-of-sample block $\{T_k+1, \dots, T_{k+1}\}$.

### Q4: How did you prevent the Quantile Crossing problem?
**Answer:**
Training independent quantile regressors $\hat{f}_{0.10}$ and $\hat{f}_{0.90}$ can yield $\hat{q}_{0.10}(x) > \hat{q}_{0.90}(x)$ on rare feature vectors. We implemented **Chernozhukov et al. (2010) Monotone Rearrangement**, which sorts the predicted quantiles along the quantile axis for each observation. Mathematically, monotone rearrangement is proven to strictly reduce or maintain $L_p$ estimation error while guaranteeing $100\%$ monotonic compliance ($0.000\%$ crossing rate).

### Q5: What is the physical meaning of Prediction Interval Coverage Probability (PICP) and Mean Prediction Interval Width (MPIW)?
**Answer:**
* **PICP:** $\frac{1}{N} \sum_{i=1}^N \mathbb{I}(\hat{y}_{0.10}^{(i)} \le y_i \le \hat{y}_{0.90}^{(i)})$. For an 80% nominal interval, PICP measures the empirical proportion of actual grid demand that falls safely within the dispatch corridor.
* **MPIW:** $\frac{1}{N} \sum_{i=1}^N (\hat{y}_{0.90}^{(i)} - \hat{y}_{0.10}^{(i)})$. Measures the sharpness (information content) of the uncertainty band. An excessively wide interval trivially achieves high coverage but is useless for dispatch operators. Optimal forecasting minimizes MPIW subject to $\text{PICP} \ge 1 - \alpha$.

### Q6: Why did raw quantile trees under-cover the nominal 80% interval (~76%), and how did you resolve it under Spec-Driven Development?
**Answer:**
Gradient boosted trees apply shrinkage regularization (learning rate $\eta = 0.04$, subsampling, and leaf regularization). Because of this regularization, extreme quantile leaves are pulled slightly toward the sample median, making the raw predicted interval $[q_{10}, q_{90}]$ slightly too narrow and leading to ~76% empirical coverage.
Under Spec-Driven Development (SDD), instead of relaxing the acceptance threshold from 78% down to 75%, we executed **Diagnostic Test D-1** (confirming symmetric tail exceedance) and implemented **Remediation Procedure R-1**: training calibrated boundary regressors at $\tau \in [0.08, 0.50, 0.92]$. This offset compensates for leaf shrinkage and elevates empirical out-of-sample coverage safely above the strict $\ge 78.0\%$ acceptance threshold without compromising point accuracy.

---

## 7. How to Reproduce All Results

```powershell
# 1. Activate course environment
conda activate umc301

# 2. Run automated test suite (15/15 tests)
pytest Project1_Energy_Grid_Forecasting/tests/ -v

# 3. Re-train models and run 5-fold expanding-window CV
python Project1_Energy_Grid_Forecasting/src/model.py

# 4. Generate evaluation metrics and markdown report
python Project1_Energy_Grid_Forecasting/src/evaluate.py

# 5. Generate TreeSHAP beeswarm and peak waterfall plots
python Project1_Energy_Grid_Forecasting/src/explainability.py

# 6. Launch interactive operator Streamlit dashboard
streamlit run Project1_Energy_Grid_Forecasting/app.py
```
