# Dataset Summary: PJM Hourly Energy Consumption (PJME)
**File:** `data/raw/PJME_hourly.csv`  
**Total Records / Hours:** 145,392  
**Time Span:** 2002-01-01 01:00 to 2018-08-03 00:00 (17 years)  
**Target Variable:** `PJME_MW` (Regional electricity demand in Megawatts)

---

## 1. Numerical Features Summary Statistics

| Column Name   |   Count (Non-Null) | Missing (%)   |     Mean |   Std Dev |   Min |   25% (Q1) |   50% (Median) |   75% (Q3) |   Max |    IQR |   Skewness |
|:--------------|-------------------:|:--------------|---------:|----------:|------:|-----------:|---------------:|-----------:|------:|-------:|-----------:|
| PJME_MW       |            145,392 | 0.00%         | 32078.9  |   6464.28 | 14544 |   27571    |        31420   |   35647    | 62009 | 8076   |       0.74 |
| hour          |            145,392 | 0.00%         |    11.5  |      6.92 |     0 |       5.75 |           11.5 |      17.25 |    23 |   11.5 |       0    |
| dayofweek     |            145,392 | 0.00%         |     3    |      2    |     0 |       1    |            3   |       5    |     6 |    4   |       0    |
| month         |            145,392 | 0.00%         |     6.44 |      3.44 |     1 |       3    |            6   |       9    |    12 |    6   |       0.03 |
| year          |            145,392 | 0.00%         |  2009.8  |      4.79 |  2002 |    2006    |         2010   |    2014    |  2018 |    8   |       0.01 |
| dayofyear     |            145,392 | 0.00%         |   180.46 |    105.14 |     1 |      90    |          179   |     271    |   366 |  181   |       0.04 |

---

## 2. Categorical & Binary Features Summary Statistics

| Column Name   |   Count | Missing   |   Unique Values | Mode (Top Value)   | Top Value Freq   | Value Distribution                                                                             |
|:--------------|--------:|:----------|----------------:|:-------------------|:-----------------|:-----------------------------------------------------------------------------------------------|
| season        | 145,392 | 0 (0.0%)  |               4 | Spring             | 25.82%           | Spring: 37,536 (25.8%), Summer: 36,841 (25.3%), Winter: 36,071 (24.8%), Autumn: 34,944 (24.0%) |
| is_weekend    | 145,392 | 0 (0.0%)  |               2 | 0                  | 71.44%           | 0: 103,872 (71.4%), 1: 41,520 (28.6%)                                                          |
| is_holiday    | 145,392 | 0 (0.0%)  |               2 | 0                  | 97.28%           | 0: 141,433 (97.3%), 1: 3,959 (2.7%)                                                            |

---

## 3. Season-Wise Electricity Demand (PJME_MW) Summary

| Season   |   Count (Hours) |   Mean (MW) |   Std Dev (MW) |   Min (MW) |   25% (Q1) |   50% (Median) |   75% (Q3) |   Max (MW) |     IQR |   Skewness |
|:---------|----------------:|------------:|---------------:|-----------:|-----------:|---------------:|-----------:|-----------:|--------:|-----------:|
| Summer   |          36,841 |     36112.5 |        7942.51 |      19695 |    29830   |          35505 |    41711   |      62009 | 11881   |       0.34 |
| Winter   |          36,071 |     33503.1 |        4665.88 |      19583 |    30168   |          33620 |    36777.5 |      49877 |  6609.5 |       0.01 |
| Autumn   |          34,944 |     29626.2 |        5183.27 |      14544 |    25752.8 |          29660 |    32621.2 |      56336 |  6868.5 |       0.66 |
| Spring   |          37,536 |     29034.9 |        4607.45 |      19247 |    25689   |          29221 |    31946   |      53057 |  6257   |       0.35 |

---

## 4. Key Descriptive Observations

1. **Missing Data & Continuity:**
   * After chronological alignment and resolving Daylight Savings Time (DST) transitions, the hourly series contains **0 missing values (0.00%)** across 145,392 continuous hours.
2. **Target Distribution Properties:**
   * Regional load ranges from a minimum of **14,544.0 MW** to an all-time peak of **62,009.0 MW**.
   * **Mean (32,078.9 MW)** is higher than **Median (31,420.0 MW)**, with a positive skewness of **+0.74**, indicating an extended upper tail caused by acute summer heatwaves and severe winter cold snaps.
3. **Seasonal Hierarchy:**
   * **Summer** exhibits the highest peak demand (62,009.0 MW) and greatest variability due to weather-driven air conditioning loads.
   * **Winter** shows the second-highest mean demand (33,503.1 MW) driven by space heating.
   * **Spring and Autumn** represent transitional "shoulder seasons" with the lowest baseline consumption (medians ~29,500 MW to 30,000 MW).
4. **Weekday vs. Weekend Structural Shift:**
   * Weekdays comprise 71.4% of readings with high industrial/commercial baseload, while weekends show noticeable baseload contraction.
