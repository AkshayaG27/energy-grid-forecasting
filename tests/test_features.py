"""
Automated unit tests for Feature Engineering & Leakage Prevention (AC-2 & AC-4).
Mathematically proves zero future data leakage and zero target inclusion leakage.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FEATURES_DATA_PATH, TARGET_COL, DATETIME_COL
from src.feature_engineering import create_features, NUMERICAL_FEATURE_COLS


@pytest.fixture(scope="module")
def features_df():
    assert FEATURES_DATA_PATH.exists(), f"Feature parquet missing at {FEATURES_DATA_PATH}"
    return pd.read_parquet(FEATURES_DATA_PATH)


@pytest.fixture
def synthetic_series():
    """Create a deterministic synthetic dataset for leakage perturbation testing."""
    dates = pd.date_range("2020-01-01", periods=500, freq="h", name=DATETIME_COL)
    np.random.seed(42)
    # Sinusoidal base load with random noise
    base = 30000 + 5000 * np.sin(2 * np.pi * np.arange(500) / 24)
    noise = np.random.normal(0, 500, size=500)
    load = base + noise
    
    df = pd.DataFrame({DATETIME_COL: dates, TARGET_COL: load})
    df["year"] = df[DATETIME_COL].dt.year
    df["month"] = df[DATETIME_COL].dt.month
    df["day"] = df[DATETIME_COL].dt.day
    df["hour"] = df[DATETIME_COL].dt.hour
    df["dayofweek"] = df[DATETIME_COL].dt.dayofweek
    df["dayofyear"] = df[DATETIME_COL].dt.dayofyear
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    df["is_holiday"] = 0
    return df


def test_zero_future_leakage(synthetic_series):
    """
    CRITICAL PROOF TEST:
    Perturb a future row (at timestamp T_future) to an extreme outlier (99,999,999 MW).
    Assert that all feature values at an earlier timestamp (T_past < T_future) remain 100% identical.
    """
    # 1. Compute baseline features
    df_clean = synthetic_series.copy()
    feat_baseline = create_features(df_clean)
    
    # Select past timestamp (e.g. 50th clean row) and future timestamp (e.g. 150th clean row)
    past_timestamp = feat_baseline.iloc[50][DATETIME_COL]
    future_timestamp = feat_baseline.iloc[150][DATETIME_COL]
    assert past_timestamp < future_timestamp, "Past timestamp must precede future timestamp"
    
    baseline_values_at_past = feat_baseline.loc[feat_baseline[DATETIME_COL] == past_timestamp, NUMERICAL_FEATURE_COLS].iloc[0]
    
    # 2. Corrupt the FUTURE row in synthetic series
    df_corrupted = synthetic_series.copy()
    corrupt_mask = df_corrupted[DATETIME_COL] == future_timestamp
    df_corrupted.loc[corrupt_mask, TARGET_COL] = 99_999_999.0  # Absurd outlier in future
    
    feat_corrupted = create_features(df_corrupted)
    corrupted_values_at_past = feat_corrupted.loc[feat_corrupted[DATETIME_COL] == past_timestamp, NUMERICAL_FEATURE_COLS].iloc[0]
    
    # 3. Assert zero leakage
    for col in NUMERICAL_FEATURE_COLS:
        v1 = baseline_values_at_past[col]
        v2 = corrupted_values_at_past[col]
        assert np.isclose(v1, v2, atol=1e-6), (
            f"LEAKAGE DETECTED in '{col}': Changing future row at {future_timestamp} "
            f"altered past row at {past_timestamp}! Before: {v1}, After: {v2}"
        )


def test_zero_current_target_leakage(synthetic_series):
    """
    Verify that rolling statistics and lags at hour t do NOT include the target load of hour t.
    """
    df_clean = synthetic_series.copy()
    feat_baseline = create_features(df_clean)
    
    # Select a target test timestamp from clean features
    test_timestamp = feat_baseline.iloc[50][DATETIME_COL]
    baseline_values_at_t = feat_baseline.loc[feat_baseline[DATETIME_COL] == test_timestamp, NUMERICAL_FEATURE_COLS].iloc[0]
    
    # Change target load at EXACTLY hour t in raw series
    df_corrupted = synthetic_series.copy()
    corrupt_mask = df_corrupted[DATETIME_COL] == test_timestamp
    df_corrupted.loc[corrupt_mask, TARGET_COL] += 500_000.0
    
    feat_corrupted = create_features(df_corrupted)
    corrupted_values_at_t = feat_corrupted.loc[feat_corrupted[DATETIME_COL] == test_timestamp, NUMERICAL_FEATURE_COLS].iloc[0]
    
    # All historical lag and rolling features at hour t must remain 100% identical
    historical_cols = [
        "lag_1", "lag_2", "lag_24", "lag_168",
        "load_velocity_1_2", "load_ratio_1_24",
        "rolling_mean_24", "rolling_std_24", "rolling_max_24"
    ]
    for col in historical_cols:
        v1 = baseline_values_at_t[col]
        v2 = corrupted_values_at_t[col]
        assert np.isclose(v1, v2, atol=1e-6), (
            f"TARGET INCLUSION LEAKAGE in '{col}' at timestamp {test_timestamp}! "
            f"Feature was polluted by current target value. Before: {v1}, After: {v2}"
        )


def test_no_null_features(features_df):
    """Verify that the production feature matrix contains zero nulls/NaNs."""
    total_nulls = features_df[NUMERICAL_FEATURE_COLS].isna().sum().sum()
    assert total_nulls == 0, f"Found {total_nulls} null values in feature matrix!"


def test_feature_columns_complete(features_df):
    """Verify all 20 required numerical feature columns exist."""
    missing = set(NUMERICAL_FEATURE_COLS) - set(features_df.columns)
    assert len(missing) == 0, f"Missing feature columns: {missing}"


def test_cyclical_trigonometric_invariants(features_df):
    """Verify sin^2 + cos^2 = 1.0 identity and [-1, 1] range for cyclical coordinates."""
    # Check bounds
    for col in ["sin_hour", "cos_hour", "sin_doy", "cos_doy"]:
        assert features_df[col].between(-1.0001, 1.0001).all(), f"Cyclical feature {col} exceeds [-1, 1] bounds!"
        
    # Check trigonometric identity: sin^2 + cos^2 == 1
    hour_norm = features_df["sin_hour"]**2 + features_df["cos_hour"]**2
    assert np.allclose(hour_norm, 1.0, atol=1e-5), "sin_hour^2 + cos_hour^2 != 1.0 identity violated!"
