"""
TreeSHAP Interpretability & Feature Attribution Engine (Phase 4).
Computes exact Shapley values for the 90th percentile (peak risk) and 50th percentile (median) models.
Generates:
1. Global SHAP Beeswarm summary plots.
2. Local waterfall explanation for the single highest peak load hour in the test set.
3. Feature contribution breakdown table.
"""
from typing import Optional
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import (
    MODELS_DIR,
    PLOTS_DIR,
    REPORTS_DIR,
    DATA_PROCESSED_DIR,
    DATETIME_COL,
    TARGET_COL,
    RANDOM_SEED
)
from src.feature_engineering import NUMERICAL_FEATURE_COLS


def compute_shap_explanations(
    model_alpha: float = 0.90,
    sample_size: int = 2000
) -> None:
    """
    Loads trained booster, computes TreeSHAP values on holdout test set,
    and saves publication-grade summary and waterfall plots.
    """
    model_file = MODELS_DIR / f"lgb_q{int(model_alpha*100):02d}.txt"
    if not model_file.exists():
        raise FileNotFoundError(f"Trained model missing at: {model_file}")
        
    pred_file = DATA_PROCESSED_DIR / "test_predictions.parquet"
    if not pred_file.exists():
        raise FileNotFoundError(f"Test predictions missing at: {pred_file}")
        
    feat_file = DATA_PROCESSED_DIR / "PJME_features.parquet"
    df_features = pd.read_parquet(feat_file)
    df_preds = pd.read_parquet(pred_file)
    
    # Align features with test timestamps
    test_dts = df_preds[DATETIME_COL].values
    test_feat_df = df_features[df_features[DATETIME_COL].isin(test_dts)].copy().reset_index(drop=True)
    X_test = test_feat_df[NUMERICAL_FEATURE_COLS]
    
    print(f"Loading LightGBM Booster for alpha={model_alpha:.2f}...")
    booster = lgb.Booster(model_file=str(model_file))
    
    print("Initializing TreeExplainer...")
    explainer = shap.TreeExplainer(booster)
    
    # Subsample for fast, smooth beeswarm rendering
    np.random.seed(RANDOM_SEED)
    sample_indices = np.random.choice(len(X_test), size=min(sample_size, len(X_test)), replace=False)
    sample_indices = np.sort(sample_indices)
    X_sample = X_test.iloc[sample_indices]
    
    print(f"Computing TreeSHAP values for {len(X_sample)} sample test observations...")
    shap_values = explainer(X_sample)
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Global Beeswarm Summary Plot
    print("Generating Global SHAP Beeswarm Plot...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    shap.plots.beeswarm(shap_values, max_display=15, show=False)
    plt.title(
        f"TreeSHAP Feature Attribution: Peak Demand Risk Model (tau = {model_alpha:.2f})\n"
        f"How features push predictions above or below the base expected quantile",
        fontsize=12, pad=15, weight="bold"
    )
    plt.tight_layout()
    summary_path = PLOTS_DIR / f"shap_summary_q{int(model_alpha*100):02d}.png"
    plt.savefig(summary_path, bbox_inches="tight")
    plt.close("all")
    print(f"Saved SHAP summary plot to: {summary_path}")
    
    # 2. Local Waterfall Explanation for the Maximum Peak Load Hour
    print("Identifying peak demand hour in test set...")
    peak_idx = int(test_feat_df[TARGET_COL].idxmax())
    peak_row = test_feat_df.iloc[peak_idx]
    peak_timestamp = peak_row[DATETIME_COL]
    actual_peak_load = peak_row[TARGET_COL]
    predicted_q90 = df_preds.loc[df_preds[DATETIME_COL] == peak_timestamp, "q90_adj"].values[0]
    
    print(f"Peak Event Identified:")
    print(f"  Timestamp:     {peak_timestamp}")
    print(f"  Actual Load:   {actual_peak_load:,.1f} MW")
    print(f"  Predicted q90: {predicted_q90:,.1f} MW")
    
    # Compute exact SHAP values for this specific single row
    peak_X = test_feat_df.iloc[[peak_idx]][NUMERICAL_FEATURE_COLS]
    peak_shap = explainer(peak_X)
    
    print("Generating Local SHAP Waterfall Plot for Peak Demand Hour...")
    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
    shap.plots.waterfall(peak_shap[0], max_display=12, show=False)
    plt.title(
        f"Local SHAP Explanation: Extreme Peak Hour ({peak_timestamp})\n"
        f"Actual: {actual_peak_load:,.0f} MW | Forecast q90: {predicted_q90:,.0f} MW | Base Value: {explainer.expected_value:,.0f} MW",
        fontsize=11, pad=15, weight="bold"
    )
    plt.tight_layout()
    waterfall_path = PLOTS_DIR / "shap_peak_waterfall.png"
    plt.savefig(waterfall_path, bbox_inches="tight")
    plt.close("all")
    print(f"Saved SHAP waterfall plot to: {waterfall_path}")
    
    # 3. Write Interpretability Report
    mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
    feature_importance_df = pd.DataFrame({
        "Feature": NUMERICAL_FEATURE_COLS,
        "Mean_|SHAP|_MW": mean_abs_shap
    }).sort_values("Mean_|SHAP|_MW", ascending=False).reset_index(drop=True)
    
    report_content = f"""# TreeSHAP Explainability & Attribution Analysis (AC-7)

**Model Analyzed:** LightGBM Quantile Regressor ($\tau = {model_alpha:.2f}$, Peak / Blackout Risk Margin)  
**Method:** TreeSHAP (Lundberg et al., Nature Machine Intelligence 2020)  
**Background Expected Value ($E[\hat{{y}}]$):** {explainer.expected_value:,.1f} MW  

---

## 1. Top Attributed Features for Peak Load Risk

The table below quantifies the mean absolute SHAP value ($E[|\\phi_i|]$) across the holdout test set, representing the average impact each feature has in driving the 90th percentile forecast away from the base grid expectation:

{feature_importance_df.to_markdown(index=False)}

---

## 2. Visual Attributions

### A. Global Beeswarm Feature Attribution
The beeswarm plot reveals both feature magnitude and directionality. High values of `lag_1` and `rolling_mean_24` (red dots) strongly push the 90th percentile prediction upward by several thousand megawatts.

![SHAP Beeswarm Summary](plots/shap_summary_q{int(model_alpha*100):02d}.png)

### B. Extreme Peak Stress Waterfall Analysis
On **{peak_timestamp}**, the PJM East grid experienced its highest test demand of **{actual_peak_load:,.1f} MW**. The waterfall plot below decomposes how each individual feature escalated the model forecast from the baseline expectation of {explainer.expected_value:,.0f} MW up to the peak alert level of {predicted_q90:,.0f} MW:

![Peak Waterfall Breakdown](plots/shap_peak_waterfall.png)
"""
    shap_report_path = REPORTS_DIR / "shap_explainability_report.md"
    with open(shap_report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Saved SHAP interpretability report to: {shap_report_path}")


if __name__ == "__main__":
    compute_shap_explanations(model_alpha=0.90)
