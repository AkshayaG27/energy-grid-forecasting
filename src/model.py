"""
Quantile Regression Forecasting Pipeline for Energy Grid Load.
Implements 3 asymmetric LightGBM models (tau in {0.10, 0.50, 0.90}) with
expanding-window TimeSeriesSplit cross-validation, out-of-fold pinball loss tracking,
and Chernozhukov post-processing monotone rearrangement.
"""
from typing import Dict, List, Tuple, Optional
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_pinball_loss

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import (
    MODELS_DIR,
    FEATURES_DATA_PATH,
    TARGET_COL,
    DATETIME_COL,
    QUANTILES,
    N_SPLITS,
    TEST_SIZE_HOURS,
    LGBM_PARAMS,
    RANDOM_SEED,
    DATA_PROCESSED_DIR
)
from src.feature_engineering import NUMERICAL_FEATURE_COLS


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
    """
    Computes the empirical pinball (quantile) loss:
    L_alpha(y, y_hat) = max(alpha * (y - y_hat), (alpha - 1) * (y - y_hat))
    """
    return float(mean_pinball_loss(y_true, y_pred, alpha=alpha))


def enforce_quantile_monotonicity(
    q10: np.ndarray, q50: np.ndarray, q90: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Enforces the mathematical monotonicity property F^-1(0.10) <= F^-1(0.50) <= F^-1(0.90)
    using Chernozhukov, Fernández-Val, & Galichon (2010) monotone rearrangement.
    
    Rearranges the predicted quantiles at each timestamp by sorting along the quantile axis.
    Guaranteed to decrease or maintain the estimation error of the quantile function.
    """
    stacked = np.column_stack([q10, q50, q90])
    sorted_stacked = np.sort(stacked, axis=1)
    return sorted_stacked[:, 0], sorted_stacked[:, 1], sorted_stacked[:, 2]


def calculate_crossing_rate(q10: np.ndarray, q50: np.ndarray, q90: np.ndarray) -> float:
    """Calculates the proportion of timestamps with quantile crossing violations."""
    violations = (q10 > q50) | (q50 > q90)
    return float(np.mean(violations))


class QuantileForecastPipeline:
    """
    Ensemble of 3 asymmetric Gradient Boosted Quantile Regressors.
    Estimates the 10th percentile (Curtailment Risk), 50th percentile (Median),
    and 90th percentile (Blackout / Peak Risk).
    """
    def __init__(
        self,
        quantiles: List[float] = QUANTILES,
        feature_cols: List[str] = NUMERICAL_FEATURE_COLS,
        params: Optional[Dict] = None
    ):
        self.quantiles = quantiles
        self.feature_cols = feature_cols
        self.params = params or LGBM_PARAMS.copy()
        # Ensure bagging frequency is active for subsample
        if "subsample" in self.params and self.params["subsample"] < 1.0:
            self.params["subsample_freq"] = 1
        self.params["n_jobs"] = -1
        
        self.models: Dict[float, lgb.LGBMRegressor] = {}
        for q in self.quantiles:
            self.models[q] = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                **self.params
            )

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Trains all 3 quantile regressors on training features."""
        X_sub = X_train[self.feature_cols]
        for q in self.quantiles:
            print(f"  Training LightGBM Quantile Regressor (alpha={q:.2f})...")
            self.models[q].fit(X_sub, y_train)

    def predict(
        self,
        X: pd.DataFrame,
        enforce_monotonicity: bool = True
    ) -> Dict[str, np.ndarray]:
        """
        Generates quantile predictions and applies monotone rearrangement.
        Returns dictionary containing raw and adjusted quantile arrays.
        """
        X_sub = X[self.feature_cols]
        sorted_q = sorted(self.quantiles)
        q_low, q_med, q_high = sorted_q[0], sorted_q[1], sorted_q[2]
        
        q10_raw = self.models[q_low].predict(X_sub)
        q50_raw = self.models[q_med].predict(X_sub)
        q90_raw = self.models[q_high].predict(X_sub)
        
        crossing_rate_raw = calculate_crossing_rate(q10_raw, q50_raw, q90_raw)
        
        if enforce_monotonicity:
            q10_adj, q50_adj, q90_adj = enforce_quantile_monotonicity(q10_raw, q50_raw, q90_raw)
        else:
            q10_adj, q50_adj, q90_adj = q10_raw, q50_raw, q90_raw
            
        crossing_rate_adj = calculate_crossing_rate(q10_adj, q50_adj, q90_adj)
        
        return {
            "q10_raw": q10_raw,
            "q50_raw": q50_raw,
            "q90_raw": q90_raw,
            "q10_adj": q10_adj,
            "q50_adj": q50_adj,
            "q90_adj": q90_adj,
            "crossing_rate_raw": crossing_rate_raw,
            "crossing_rate_adj": crossing_rate_adj,
        }

    def save_models(self, save_dir: Path = MODELS_DIR) -> None:
        """Saves trained booster models to disk in LightGBM native text format."""
        save_dir.mkdir(parents=True, exist_ok=True)
        sorted_q = sorted(self.quantiles)
        mapping = {sorted_q[0]: "lgb_q10.txt", sorted_q[1]: "lgb_q50.txt", sorted_q[2]: "lgb_q90.txt"}
        for q, filename in mapping.items():
            model_path = save_dir / filename
            self.models[q].booster_.save_model(str(model_path))
            print(f"  Saved booster for alpha={q:.2f} ({filename}) to {model_path}")

    def load_models(self, load_dir: Path = MODELS_DIR) -> None:
        """Loads booster models from disk."""
        sorted_q = sorted(self.quantiles)
        mapping = {sorted_q[0]: "lgb_q10.txt", sorted_q[1]: "lgb_q50.txt", sorted_q[2]: "lgb_q90.txt"}
        for q, filename in mapping.items():
            model_path = load_dir / filename
            if not model_path.exists():
                raise FileNotFoundError(f"Model file missing: {model_path}")
            booster = lgb.Booster(model_file=str(model_path))
            reg = lgb.LGBMRegressor(objective="quantile", alpha=q, **self.params)
            reg._Booster = booster
            reg.fitted_ = True
            self.models[q] = reg
            print(f"  Loaded booster for alpha={q:.2f} ({filename}) from {model_path}")


def run_cross_validation(
    df: pd.DataFrame,
    n_splits: int = N_SPLITS
) -> pd.DataFrame:
    """
    Executes expanding-window TimeSeriesSplit cross-validation on historical training data.
    Evaluates out-of-fold Pinball loss across each temporal fold to ensure no time leakage.
    """
    print(f"\n{'='*70}")
    print(f"Running {n_splits}-Fold Expanding-Window TimeSeriesSplit Cross-Validation")
    print(f"{'='*70}")
    
    # Exclude holdout test set from CV
    train_df = df.iloc[:-TEST_SIZE_HOURS].copy().reset_index(drop=True)
    X_full = train_df[NUMERICAL_FEATURE_COLS]
    y_full = train_df[TARGET_COL]
    
    tscv = TimeSeriesSplit(n_splits=n_splits)
    cv_records = []
    
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X_full), 1):
        X_tr, y_tr = X_full.iloc[train_idx], y_full.iloc[train_idx]
        X_val, y_val = X_full.iloc[val_idx], y_full.iloc[val_idx]
        
        val_start = train_df.iloc[val_idx[0]][DATETIME_COL]
        val_end = train_df.iloc[val_idx[-1]][DATETIME_COL]
        
        print(f"\nFold {fold}/{n_splits}:")
        print(f"  Train Size: {len(train_idx):,} hours | Val Size: {len(val_idx):,} hours")
        print(f"  Validation Window: {val_start} --> {val_end}")
        
        fold_pipeline = QuantileForecastPipeline()
        fold_pipeline.train(X_tr, y_tr)
        preds = fold_pipeline.predict(X_val, enforce_monotonicity=True)
        
        loss_q10 = pinball_loss(y_val.values, preds["q10_adj"], alpha=0.10)
        loss_q50 = pinball_loss(y_val.values, preds["q50_adj"], alpha=0.50)
        loss_q90 = pinball_loss(y_val.values, preds["q90_adj"], alpha=0.90)
        mae = float(np.mean(np.abs(y_val.values - preds["q50_adj"])))
        
        picp = float(np.mean(
            (preds["q10_adj"] <= y_val.values) & (y_val.values <= preds["q90_adj"])
        ))
        
        print(f"  Fold {fold} Results:")
        print(f"    Pinball Loss (q10): {loss_q10:.2f} MW")
        print(f"    Pinball Loss (q50): {loss_q50:.2f} MW (Median MAE: {mae:.2f} MW)")
        print(f"    Pinball Loss (q90): {loss_q90:.2f} MW")
        print(f"    Interval Coverage (PICP): {picp*100:.2f}% (Target: 80.0%)")
        print(f"    Raw Quantile Crossing Rate: {preds['crossing_rate_raw']*100:.3f}%")
        
        cv_records.append({
            "fold": fold,
            "val_start": val_start,
            "val_end": val_end,
            "train_hours": len(train_idx),
            "val_hours": len(val_idx),
            "pinball_q10": loss_q10,
            "pinball_q50": loss_q50,
            "pinball_q90": loss_q90,
            "mae_median": mae,
            "picp_coverage": picp,
            "crossing_rate_raw": preds["crossing_rate_raw"]
        })
        
    cv_summary_df = pd.DataFrame(cv_records)
    print(f"\n{'='*70}")
    print("TimeSeriesSplit Cross-Validation Summary (Mean +/- Std across folds):")
    print(f"  Pinball q10: {cv_summary_df['pinball_q10'].mean():.2f} +/- {cv_summary_df['pinball_q10'].std():.2f} MW")
    print(f"  Pinball q50: {cv_summary_df['pinball_q50'].mean():.2f} +/- {cv_summary_df['pinball_q50'].std():.2f} MW")
    print(f"  Pinball q90: {cv_summary_df['pinball_q90'].mean():.2f} +/- {cv_summary_df['pinball_q90'].std():.2f} MW")
    print(f"  Median MAE:  {cv_summary_df['mae_median'].mean():.2f} +/- {cv_summary_df['mae_median'].std():.2f} MW")
    print(f"  PICP (80%):  {cv_summary_df['picp_coverage'].mean()*100:.2f}% +/- {cv_summary_df['picp_coverage'].std()*100:.2f}%")
    print(f"{'='*70}\n")
    
    return cv_summary_df


def train_and_evaluate_holdout(
    df: pd.DataFrame
) -> Tuple[QuantileForecastPipeline, pd.DataFrame]:
    """
    Trains final quantile regression models on all training history (2002 to mid-2017)
    and evaluates out-of-sample predictions on the untouched 1-year holdout test set (8,760 hours).
    Saves trained models and test prediction parquet.
    """
    print(f"\n{'='*70}")
    print(f"Training Final Quantile Models & Evaluating on 1-Year Holdout Test Set")
    print(f"{'='*70}")
    
    train_df = df.iloc[:-TEST_SIZE_HOURS].copy().reset_index(drop=True)
    test_df = df.iloc[-TEST_SIZE_HOURS:].copy().reset_index(drop=True)
    
    print(f"Training Period: {train_df[DATETIME_COL].min()} --> {train_df[DATETIME_COL].max()} ({len(train_df):,} hours)")
    print(f"Test Period:     {test_df[DATETIME_COL].min()} --> {test_df[DATETIME_COL].max()} ({len(test_df):,} hours)")
    
    # Train pipeline
    pipeline = QuantileForecastPipeline()
    pipeline.train(train_df[NUMERICAL_FEATURE_COLS], train_df[TARGET_COL])
    
    # Save booster models
    pipeline.save_models(MODELS_DIR)
    
    # Predict on test set
    preds = pipeline.predict(test_df[NUMERICAL_FEATURE_COLS], enforce_monotonicity=True)
    
    # Assemble test predictions dataframe
    test_results_df = pd.DataFrame({
        DATETIME_COL: test_df[DATETIME_COL],
        "y_true": test_df[TARGET_COL],
        "q10_raw": preds["q10_raw"],
        "q50_raw": preds["q50_raw"],
        "q90_raw": preds["q90_raw"],
        "q10_adj": preds["q10_adj"],
        "q50_adj": preds["q50_adj"],
        "q90_adj": preds["q90_adj"],
    })
    
    # Save test predictions for evaluation and dashboard
    test_pred_path = DATA_PROCESSED_DIR / "test_predictions.parquet"
    test_results_df.to_parquet(test_pred_path, index=False)
    print(f"Saved holdout test predictions to: {test_pred_path}")
    
    # Print key holdout metrics
    loss_q10 = pinball_loss(test_results_df["y_true"].values, test_results_df["q10_adj"].values, 0.10)
    loss_q50 = pinball_loss(test_results_df["y_true"].values, test_results_df["q50_adj"].values, 0.50)
    loss_q90 = pinball_loss(test_results_df["y_true"].values, test_results_df["q90_adj"].values, 0.90)
    mae = float(np.mean(np.abs(test_results_df["y_true"] - test_results_df["q50_adj"])))
    mape = float(np.mean(np.abs((test_results_df["y_true"] - test_results_df["q50_adj"]) / test_results_df["y_true"]))) * 100
    picp = float(np.mean(
        (test_results_df["q10_adj"] <= test_results_df["y_true"]) &
        (test_results_df["y_true"] <= test_results_df["q90_adj"])
    )) * 100
    mpiw = float(np.mean(test_results_df["q90_adj"] - test_results_df["q10_adj"]))
    
    print(f"\nHoldout Test Performance (8,760 hours / 1 Full Year):")
    print(f"  Pinball Loss (q10 - Curtailment): {loss_q10:.2f} MW")
    print(f"  Pinball Loss (q50 - Median):      {loss_q50:.2f} MW")
    print(f"  Pinball Loss (q90 - Blackout):    {loss_q90:.2f} MW")
    print(f"  Median Point MAE:                 {mae:.2f} MW (Target <= 1200 MW)")
    print(f"  Median Point MAPE:                {mape:.2f}% (Target <= 4.5%)")
    print(f"  Interval Coverage (PICP):         {picp:.2f}% (Target >= 78.0%)")
    print(f"  Mean Prediction Interval Width:   {mpiw:.2f} MW")
    print(f"  Raw Quantile Crossing Rate:       {preds['crossing_rate_raw']*100:.3f}%")
    print(f"  Adjusted Quantile Crossing Rate:  {preds['crossing_rate_adj']*100:.3f}%")
    
    return pipeline, test_results_df


if __name__ == "__main__":
    if not FEATURES_DATA_PATH.exists():
        raise FileNotFoundError(f"Feature parquet missing at: {FEATURES_DATA_PATH}")
        
    df_feat = pd.read_parquet(FEATURES_DATA_PATH)
    cv_summary = run_cross_validation(df_feat, n_splits=N_SPLITS)
    pipeline, test_results = train_and_evaluate_holdout(df_feat)
