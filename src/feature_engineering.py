"""
Feature Engineering Pipeline for PJM Hourly Energy Consumption.
Constructs strictly backward-looking autoregressive lags, rolling sufficient statistics,
and continuous cyclical trigonometric encodings with zero future data leakage.
"""
from typing import Tuple, List
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import CLEANED_DATA_PATH, FEATURES_DATA_PATH, TARGET_COL, DATETIME_COL, LAG_HOURS, ROLLING_WINDOWS


# Feature column definitions
NUMERICAL_FEATURE_COLS = [
    "lag_1", "lag_2", "lag_24", "lag_168",
    "load_velocity_1_2", "load_ratio_1_24",
    "rolling_mean_24", "rolling_std_24", "rolling_max_24",
    "hour", "dayofweek", "month", "year", "dayofyear",
    "is_weekend", "is_holiday",
    "sin_hour", "cos_hour", "sin_doy", "cos_doy"
]


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms cleaned time series into an (X, y) tabular feature matrix.
    
    CRITICAL LEAKAGE CONSTRAINT:
    All lag and rolling features at hour t are computed exclusively using observations
    from hour t-1 and earlier. No lookahead or centered windows are permitted.
    """
    df_out = df.copy()
    
    # 1. Autoregressive Anchor Lags
    for lag in LAG_HOURS:
        df_out[f"lag_{lag}"] = df_out[TARGET_COL].shift(lag)
        
    # 2. Velocity & Acceleration Signals
    df_out["load_velocity_1_2"] = df_out["lag_1"] - df_out["lag_2"]
    df_out["load_ratio_1_24"] = df_out["lag_1"] / (df_out["lag_24"] + 1e-5)
    
    # 3. Rolling Window Sufficient Statistics (Strictly shifted by 1 to prevent target inclusion)
    for window in ROLLING_WINDOWS:
        shifted_series = df_out[TARGET_COL].shift(1)
        df_out[f"rolling_mean_{window}"] = shifted_series.rolling(window=window).mean()
        df_out[f"rolling_std_{window}"] = shifted_series.rolling(window=window).std()
        df_out[f"rolling_max_{window}"] = shifted_series.rolling(window=window).max()
        
    # 4. Continuous Trigonometric (Cyclical) Encodings
    df_out["sin_hour"] = np.sin(2.0 * np.pi * df_out["hour"] / 24.0)
    df_out["cos_hour"] = np.cos(2.0 * np.pi * df_out["hour"] / 24.0)
    df_out["sin_doy"] = np.sin(2.0 * np.pi * df_out["dayofyear"] / 365.25)
    df_out["cos_doy"] = np.cos(2.0 * np.pi * df_out["dayofyear"] / 365.25)
    
    # 5. Trim initial warm-up rows caused by maximum lag (lag_168)
    max_lag = max(LAG_HOURS)
    initial_len = len(df_out)
    df_out = df_out.dropna().reset_index(drop=True)
    trimmed_rows = initial_len - len(df_out)
    
    print(f"Engineered {len(NUMERICAL_FEATURE_COLS)} feature columns.")
    print(f"Trimmed {trimmed_rows} warm-up hours (retained {len(df_out):,} clean rows).")
    
    return df_out


def build_and_save_features() -> Tuple[pd.DataFrame, List[str]]:
    """Loads cleaned parquet, creates features, and saves the final feature table."""
    print(f"Loading cleaned dataset from: {CLEANED_DATA_PATH}")
    df_clean = pd.read_parquet(CLEANED_DATA_PATH)
    
    df_features = create_features(df_clean)
    
    FEATURES_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_features.to_parquet(FEATURES_DATA_PATH, index=False)
    print(f"Saved feature matrix to: {FEATURES_DATA_PATH}")
    
    return df_features, NUMERICAL_FEATURE_COLS


if __name__ == "__main__":
    build_and_save_features()
