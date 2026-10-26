"""
Unit tests for data loader (AC-1 verification).
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import CLEANED_DATA_PATH, TARGET_COL, DATETIME_COL


@pytest.fixture(scope="module")
def cleaned_df():
    assert CLEANED_DATA_PATH.exists(), f"Cleaned dataset missing at {CLEANED_DATA_PATH}"
    return pd.read_parquet(CLEANED_DATA_PATH)


def test_chronological_monotonicity(cleaned_df):
    """Verify that datetimes are strictly monotonically increasing."""
    assert cleaned_df[DATETIME_COL].is_monotonic_increasing, "Dataset is not sorted chronologically!"


def test_zero_duplicate_timestamps(cleaned_df):
    """Verify no duplicate timestamps exist."""
    duplicates = cleaned_df[DATETIME_COL].duplicated().sum()
    assert duplicates == 0, f"Found {duplicates} duplicate timestamps!"


def test_hourly_continuity(cleaned_df):
    """Verify unbroken 1-hour frequency without skipped gaps."""
    diffs = cleaned_df[DATETIME_COL].diff().dropna()
    expected_step = pd.Timedelta(hours=1)
    irregular_steps = (diffs != expected_step).sum()
    assert irregular_steps == 0, f"Found {irregular_steps} irregular time steps!"


def test_no_null_target(cleaned_df):
    """Verify target column contains zero null/NaN values."""
    nulls = cleaned_df[TARGET_COL].isna().sum()
    assert nulls == 0, f"Target column has {nulls} missing values!"


def test_calendar_columns_exist(cleaned_df):
    """Verify enriched calendar columns are present."""
    required_cols = {"year", "month", "day", "hour", "dayofweek", "dayofyear", "season", "is_weekend", "is_holiday"}
    assert required_cols.issubset(cleaned_df.columns), f"Missing columns: {required_cols - set(cleaned_df.columns)}"
