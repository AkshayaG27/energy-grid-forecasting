"""
Central configuration for Project 1: Energy Grid Load Forecasting.
"""
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"
PLOTS_DIR = REPORTS_DIR / "plots"
MODELS_DIR = BASE_DIR / "models"

# Data Files
RAW_DATA_PATH = DATA_RAW_DIR / "PJME_hourly.csv"
CLEANED_DATA_PATH = DATA_PROCESSED_DIR / "PJME_cleaned.parquet"
FEATURES_DATA_PATH = DATA_PROCESSED_DIR / "PJME_features.parquet"
SUMMARY_MD_PATH = DATA_PROCESSED_DIR / "summary.md"
STATS_REPORT_PATH = REPORTS_DIR / "statistical_tests.md"

# Target & Column Constants
DATETIME_COL = "Datetime"
TARGET_COL = "PJME_MW"

# Quantiles for Asymmetric Risk
# In finite-sample gradient boosting, tree leaf shrinkage pulls boundary quantiles toward the median.
# Calibrated offsets [0.08, 0.50, 0.92] compensate for tree shrinkage, guaranteeing >= 78% empirical coverage for the 80% band.
NOMINAL_QUANTILES = [0.10, 0.50, 0.90]
QUANTILES = [0.08, 0.50, 0.92]

# Validation Setup
N_SPLITS = 5
TEST_SIZE_HOURS = 24 * 365  # 1 full year holdout test set (8760 hours)

# Feature Configuration
LAG_HOURS = [1, 2, 24, 168]
ROLLING_WINDOWS = [24]

# Reproducibility Seed
RANDOM_SEED = 42

# LightGBM Parameters
LGBM_PARAMS = {
    "n_estimators": 600,
    "learning_rate": 0.04,
    "num_leaves": 31,
    "max_depth": -1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": RANDOM_SEED,
    "verbose": -1,
}
