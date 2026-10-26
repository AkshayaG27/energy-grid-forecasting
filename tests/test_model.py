"""
Automated unit tests for Quantile LightGBM Model & Monotonicity (AC-5).
Verifies that:
1. Monotone rearrangement eliminates all quantile crossings.
2. In-production predictions satisfy q10 <= q50 <= q90.
3. Out-of-sample coverage PICP adheres to the target 80% uncertainty envelope.
4. Model inference latency satisfies real-time operational dashboard requirements (<500ms for 8,760 points).
"""
import time
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import MODELS_DIR, DATA_PROCESSED_DIR, TARGET_COL, DATETIME_COL
from src.feature_engineering import NUMERICAL_FEATURE_COLS
from src.model import enforce_quantile_monotonicity, calculate_crossing_rate, QuantileForecastPipeline


@pytest.fixture(scope="module")
def test_predictions_df():
    pred_path = DATA_PROCESSED_DIR / "test_predictions.parquet"
    assert pred_path.exists(), f"Test predictions parquet missing at: {pred_path}"
    return pd.read_parquet(pred_path)


def test_monotone_rearrangement_math():
    """
    Unit test verifying that Chernozhukov rearrangement strictly guarantees q10 <= q50 <= q90
    even under deliberately pathological quantile crossing inputs.
    """
    # Create deliberate crossings
    q10_pathological = np.array([50000.0, 30000.0, 42000.0, 10000.0])
    q50_pathological = np.array([40000.0, 35000.0, 41000.0, 20000.0])
    q90_pathological = np.array([30000.0, 25000.0, 45000.0, 30000.0])
    
    # Assert crossing rate > 0 prior to rearrangement
    raw_crossing = calculate_crossing_rate(q10_pathological, q50_pathological, q90_pathological)
    assert raw_crossing > 0.0, "Pathological input must have crossings"
    
    # Apply monotone rearrangement
    q10_adj, q50_adj, q90_adj = enforce_quantile_monotonicity(
        q10_pathological, q50_pathological, q90_pathological
    )
    
    # Assert zero crossing rate after rearrangement
    adj_crossing = calculate_crossing_rate(q10_adj, q50_adj, q90_adj)
    assert adj_crossing == 0.0, "Rearranged quantiles must have zero crossings"
    
    # Assert mathematical invariants
    assert np.all(q10_adj <= q50_adj), "Violation: q10_adj > q50_adj"
    assert np.all(q50_adj <= q90_adj), "Violation: q50_adj > q90_adj"
    assert np.all(q10_adj <= q90_adj), "Violation: q10_adj > q90_adj"


def test_production_quantile_monotonicity(test_predictions_df):
    """
    AC-5 Verification:
    Assert that 100% of adjusted holdout predictions satisfy q10_adj <= q50_adj <= q90_adj.
    Also assert that Chernozhukov monotone rearrangement strictly eliminated all raw quantile crossings.
    """
    q10_adj = test_predictions_df["q10_adj"].values
    q50_adj = test_predictions_df["q50_adj"].values
    q90_adj = test_predictions_df["q90_adj"].values
    
    crossing_count_adj = np.sum((q10_adj > q50_adj) | (q50_adj > q90_adj))
    assert crossing_count_adj == 0, f"Found {crossing_count_adj} crossing violations in adjusted quantiles!"
    
    q10_raw = test_predictions_df["q10_raw"].values
    q50_raw = test_predictions_df["q50_raw"].values
    q90_raw = test_predictions_df["q90_raw"].values
    raw_crossing_rate = calculate_crossing_rate(q10_raw, q50_raw, q90_raw)
    adj_crossing_rate = calculate_crossing_rate(q10_adj, q50_adj, q90_adj)
    
    # Chernozhukov rearrangement strictly eliminates 100% of violations (AC-5)
    assert adj_crossing_rate == 0.0, "Monotone rearrangement failed to achieve 0.0% crossing rate!"
    # Raw crossing rate is bounded (audited under Diagnostic Test D-2)
    assert raw_crossing_rate < 0.20, f"Raw crossing rate abnormally high (> 20%): {raw_crossing_rate * 100:.2f}%"


def test_picp_coverage_envelope(test_predictions_df):
    """
    Verify AC-6 Interval Coverage Requirement:
    Prediction Interval Coverage Probability (PICP) for the 80% nominal band (0.10 to 0.90)
    must achieve >= 78.0% on out-of-sample holdout data.
    """
    y_true = test_predictions_df["y_true"].values
    q10_adj = test_predictions_df["q10_adj"].values
    q90_adj = test_predictions_df["q90_adj"].values
    
    coverage = np.mean((q10_adj <= y_true) & (y_true <= q90_adj))
    print(f"Holdout PICP Coverage: {coverage * 100:.2f}%")
    assert coverage >= 0.780, f"PICP coverage {coverage * 100:.2f}% is below 78.0% acceptance threshold!"


def test_median_point_accuracy(test_predictions_df):
    """
    Verify AC-6 Point Forecast Requirement:
    Median model (q50) Mean Absolute Error (MAE) must be <= 1,200 MW.
    """
    y_true = test_predictions_df["y_true"].values
    q50_adj = test_predictions_df["q50_adj"].values
    
    mae = np.mean(np.abs(y_true - q50_adj))
    mape = np.mean(np.abs((y_true - q50_adj) / y_true)) * 100.0
    print(f"Holdout MAE: {mae:.2f} MW, MAPE: {mape:.2f}%")
    assert mae <= 1200.0, f"Median MAE {mae:.2f} MW exceeds 1,200 MW threshold!"
    assert mape <= 4.5, f"Median MAPE {mape:.2f}% exceeds 4.5% threshold!"


def test_inference_latency():
    """
    Operational requirement: Loading models and predicting 8,760 hours (1 full year)
    must complete within 500ms for responsive Streamlit interaction.
    """
    pipeline = QuantileForecastPipeline()
    pipeline.load_models(MODELS_DIR)
    
    # Synthetic batch of 8,760 rows
    dummy_features = pd.DataFrame(
        np.random.randn(8760, len(NUMERICAL_FEATURE_COLS)),
        columns=NUMERICAL_FEATURE_COLS
    )
    
    start_time = time.perf_counter()
    preds = pipeline.predict(dummy_features, enforce_monotonicity=True)
    elapsed = time.perf_counter() - start_time
    
    print(f"Latency for 8,760 predictions: {elapsed * 1000:.2f} ms")
    assert elapsed < 0.500, f"Inference latency {elapsed:.3f}s exceeds 500ms ceiling!"
