# Chapter 2 EDA & Statistical Hypothesis Testing Report
**Project:** Renewable Energy Grid Load & Curtailment Risk Forecasting  
**Dataset:** PJM East Interconnection (`PJME_hourly.csv`, 145,392 hourly readings, 2002–2018)  
**Academic Reference:** Chapter 2 (EDA and Statistical Foundations) - Prof. Deepak Subramani, IISc CDS

---

## 1. Executive Summary & Distributional Diagnostics

Before conducting any modeling or testing, we empirically examine the distributional assumptions of the regional load data:

| Metric / Diagnostic Test | Computed Value | Interpretation |
| :--- | :--- | :--- |
| **Total Observations ($N$)** | 145,392 | Unbroken hourly historical record across 17 years |
| **Missing Values** | 0 (0.00%) | Verified continuous frequency after DST alignment |
| **Mean / Median Load** | 32,078.9 MW / 31,420.0 MW | Positive skewness (+0.74) reflects extreme peak demand tails |
| **D'Agostino-Pearson ($K^2$)** | $K^2 = 12,473.86$ ($p < 10^{-300}$) | **Normality decisively rejected**; parametric tests invalid |
| **Levene's Test for Homoscedasticity** | $W = 5,958.52$ ($p < 10^{-300}$) | **Equal variance assumption rejected** (heteroscedastic) |

> **Methodological Consequence:** Because both normality and homoscedasticity are decisively rejected, standard One-Way ANOVA is statistically invalid. We strictly apply **non-parametric rank-based hypothesis tests (Kruskal-Wallis and Mann-Whitney U)**.

---

## 2. Diurnal Demand Profiles by Season

![Diurnal Demand Profile by Season](C:\Users\aksha\.gemini\antigravity-cli\brain\4b431040-04de-42c8-8695-cad0e8c140a1\diurnal_load_by_season.png)

### Key Analytical Findings:
* **The Summer AC Surge (Red Curve):** Summer displays the highest peak electricity demand of the entire year, cresting at **17:00 (5:00 PM) at ~41,000 MW** (with peak outlier hours exceeding **62,000 MW**). The wide translucent IQR ribbon reflects extreme thermal sensitivity: cooling demand swings dramatically based on temperature.
* **The Winter Dual Commute/Heating Peaks (Blue Curve):** Winter exhibits a distinctive bimodal diurnal signature:
  1. *Morning Wake-up / Space Heating Peak:* **08:00 AM (~36,000 MW)**.
  2. *Evening Return Commute / Heating Peak:* **19:00 PM (~35,500 MW)**.
* **Spring & Autumn Shoulder Seasons (Green & Gold Curves):** Exhibit stable, predictable baseline demand (~26,000 MW to 32,000 MW) due to mild temperatures where neither air conditioning nor space heating is heavily engaged.

---

## 3. Structural Baseload Shift: Commercial vs. Residential

![Weekday vs Weekend Split Violin](C:\Users\aksha\.gemini\antigravity-cli\brain\4b431040-04de-42c8-8695-cad0e8c140a1\load_weekday_weekend_violin.png)

### Statistical Confirmation:
* **Weekday Mean:** 32,996.1 MW vs. **Weekend Mean:** 29,784.4 MW ($\Delta = \mathbf{3,211.8\text{ MW}}$).
* **Mann-Whitney U Test:** $U = 2.82 \times 10^9, \mathbf{p < 10^{-300}}$.
* **Cliff's Delta Effect Size:** $\mathbf{\delta = +0.307}$ (Medium-to-Large Effect).
* **Diagnosis:** Industrial and commercial factory shutdowns on Saturdays and Sundays cause a persistent structural contraction of over 3,200 MW across all seasons, proving that `is_weekend` is a critical non-linear feature for machine learning models.

---

## 4. Impact of US Federal Holidays

![Federal Holiday vs Regular Day Demand](C:\Users\aksha\.gemini\antigravity-cli\brain\4b431040-04de-42c8-8695-cad0e8c140a1\load_holiday_violin.png)

### Analytical Insights:
* On Federal Holidays (Thanksgiving, Christmas, Memorial Day, Independence Day), commercial offices and manufacturing plants close, depressing electricity demand toward weekend levels.
* This holiday suppression is particularly stark in Winter (Christmas/New Year shutdowns) and Summer (July 4th), preventing acute grid strain.

---

## 5. Formal Seasonal Hypothesis Testing Suite

### Step 1: The Omnibus Gatekeeper Test
* **Test:** Kruskal-Wallis H-Test across 4 Seasons.
* **Hypothesis:** $H_0: \text{Median}_{\text{Summer}} = \text{Median}_{\text{Winter}} = \text{Median}_{\text{Autumn}} = \text{Median}_{\text{Spring}}$.
* **Result:** $H = 27,143.61, df = 3, \mathbf{p < 10^{-300}}$.
* **Effect Size ($\eta_H^2$):** **0.1867 (18.7%)** of total rank variance is explained solely by seasonality.

### Step 2: Post-Hoc Pairwise Comparisons (Bonferroni Corrected, $m = 6$)

| Pairwise Comparison | Mann-Whitney U | Raw $p$-value | Bonferroni Adj. $p$ | Cliff's Delta ($\delta$) | Conclusion ($\alpha = 0.05$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Summer vs. Winter** | $7.82 \times 10^8$ | $< 10^{-300}$ | $< 10^{-300}$ | $\mathbf{+0.177}$ (Small) | **Summer > Winter ($p < 0.001$)** |
| **Summer vs. Autumn** | $9.55 \times 10^8$ | $< 10^{-300}$ | $< 10^{-300}$ | $\mathbf{+0.484}$ (Large) | **Summer > Autumn ($p < 0.001$)** |
| **Summer vs. Spring** | $1.06 \times 10^9$ | $< 10^{-300}$ | $< 10^{-300}$ | $\mathbf{+0.530}$ (Large) | **Summer > Spring ($p < 0.001$)** |
| **Winter vs. Autumn** | $9.09 \times 10^8$ | $< 10^{-300}$ | $< 10^{-300}$ | $\mathbf{+0.442}$ (Medium) | **Winter > Autumn ($p < 0.001$)** |
| **Winter vs. Spring** | $1.02 \times 10^9$ | $< 10^{-300}$ | $< 10^{-300}$ | $\mathbf{+0.506}$ (Large) | **Winter > Spring ($p < 0.001$)** |
| **Autumn vs. Spring** | $6.93 \times 10^8$ | $2.64 \times 10^{-39}$ | $1.58 \times 10^{-38}$ | $\mathbf{+0.056}$ (Negligible) | Autumn $\approx$ Spring (Negligible) |

### Strict Seasonal Hierarchy:
$$\mathbf{Summer \gg Winter > Autumn \approx Spring}$$

---

## 6. Correlation & Multicollinearity Analysis

![Dual Correlation Heatmap](C:\Users\aksha\.gemini\antigravity-cli\brain\4b431040-04de-42c8-8695-cad0e8c140a1\correlation_heatmap.png)

### Key Feature Engineering Takeaways:
1. **Autoregressive Strength:** 
   * `lag_1` ($t-1$) exhibits near-perfect linear correlation ($r = +0.98, \rho = +0.98$), confirming high inertia in physical power grids.
   * `lag_24` ($t-24$, same hour yesterday) displays $r = +0.89$, capturing the persistent 24-hour diurnal cycle.
   * `lag_168` ($t-168$, same hour last week) displays $r = +0.80$, capturing weekly business schedules.
2. **Cyclical Transforms ($\sin / \cos$):**
   * Encodes `hour` and `dayofyear` into continuous geometric coordinates, enabling tree models to cleanly separate diurnal and seasonal phases.
