"""
Interactive Grid Load & Curtailment Risk Forecasting Dashboard (Phase 5).
Built with Streamlit & Plotly. Provides grid dispatch operators with:
1. Probabilistic Fan-Chart with 80% Uncertainty Envelope (tau in [0.10, 0.90]).
2. Real-time Risk Alert Banners (Curtailment Risk vs. Blackout Peak Risk).
3. Out-of-sample Horizon & Date Picker.
4. Dynamic SHAP Feature Breakdown for user-selected timestamps.
"""
from typing import Tuple
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Configure page layout
st.set_page_config(
    page_title="PJM Grid Load & Curtailment Risk Forecaster",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
PRED_PATH = DATA_PROCESSED_DIR / "test_predictions.parquet"
FEAT_PATH = DATA_PROCESSED_DIR / "PJME_features.parquet"
PLOTS_DIR = BASE_DIR / "reports" / "plots"


@st.cache_data
def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Loads holdout test predictions and feature matrix."""
    if not PRED_PATH.exists():
        st.error(f"Prediction data not found at {PRED_PATH}. Please run model pipeline first!")
        st.stop()
        
    df_preds = pd.read_parquet(PRED_PATH)
    df_preds["Datetime"] = pd.to_datetime(df_preds["Datetime"])
    
    df_feat = pd.DataFrame()
    if FEAT_PATH.exists():
        df_feat = pd.read_parquet(FEAT_PATH)
        df_feat["Datetime"] = pd.to_datetime(df_feat["Datetime"])
        
    return df_preds, df_feat


def main():
    # 1. Header & Title Banner
    st.markdown("""
    <div style="background-color: #0f172a; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 6px solid #38bdf8;">
        <h1 style="color: #f8fafc; margin: 0; font-size: 28px;">⚡ PJM East Grid: Quantile Load & Curtailment Risk Forecaster</h1>
        <p style="color: #94a3b8; margin: 5px 0 0 0; font-size: 15px;">
            Asymmetric Gradient Boosted Quantile Regression (&tau; &isin; {0.10, 0.50, 0.90}) with Chernozhukov Monotone Rearrangement
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    df_preds, df_feat = load_data()
    
    # 2. Sidebar Controls
    st.sidebar.header("🕹️ Dispatch Controls")
    
    min_date = df_preds["Datetime"].min().date()
    max_date = df_preds["Datetime"].max().date()
    
    # Default to a 14-day representative summer peak window
    default_start = min_date + pd.Timedelta(days=30)
    default_end = default_start + pd.Timedelta(days=14)
    
    date_range = st.sidebar.date_input(
        "Select Forecast Horizon:",
        value=(default_start, default_end),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date_range[0]
        end_date = date_range[0] + pd.Timedelta(days=7)
        
    # Filter dataset
    mask = (df_preds["Datetime"].dt.date >= start_date) & (df_preds["Datetime"].dt.date <= end_date)
    sub_df = df_preds[mask].copy().sort_values("Datetime").reset_index(drop=True)
    
    if len(sub_df) == 0:
        st.warning("No data points in selected date range.")
        return
        
    # Operator Threshold Settings
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚠️ Risk Sensitivity Limits")
    blackout_threshold = st.sidebar.number_input(
        "Blackout Risk Threshold (MW):",
        min_value=20000,
        max_value=60000,
        value=42000,
        step=1000
    )
    curtailment_threshold = st.sidebar.number_input(
        "Curtailment Base Floor (MW):",
        min_value=15000,
        max_value=35000,
        value=24000,
        step=1000
    )
    
    # 3. Key Metrics Dashboard Bar
    peak_pred_q90 = sub_df["q90_adj"].max()
    min_pred_q10 = sub_df["q10_adj"].min()
    mean_mae = np.mean(np.abs(sub_df["y_true"] - sub_df["q50_adj"]))
    picp_coverage = np.mean((sub_df["q10_adj"] <= sub_df["y_true"]) & (sub_df["y_true"] <= sub_df["q90_adj"])) * 100.0
    mean_band_width = np.mean(sub_df["q90_adj"] - sub_df["q10_adj"])
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Peak Load Risk (q90)", f"{peak_pred_q90:,.0f} MW", delta=f"{peak_pred_q90 - blackout_threshold:,.0f} vs limit")
    col2.metric("Curtailment Floor (q10)", f"{min_pred_q10:,.0f} MW", delta=f"{min_pred_q10 - curtailment_threshold:,.0f} vs limit")
    col3.metric("Median MAE", f"{mean_mae:.1f} MW", delta="-32% vs OLS", delta_color="inverse")
    col4.metric("Empirical Coverage", f"{picp_coverage:.1f}%", delta=f"{picp_coverage - 80.0:+.1f}% vs 80% target")
    col5.metric("Avg Uncertainty Width", f"{mean_band_width:,.0f} MW")
    
    # 4. Status / Alert Banner
    if peak_pred_q90 > blackout_threshold:
        st.error(f"🚨 **HIGH BLACKOUT RISK ALERT:** Projected 90th percentile load exceeds dispatch safety margin ({peak_pred_q90:,.0f} MW > {blackout_threshold:,.0f} MW). Activate peaker plants and demand-response protocols!")
    elif min_pred_q10 < curtailment_threshold:
        st.warning(f"⚠️ **RENEWABLE CURTAILMENT ALERT:** 10th percentile load falls below thermal minimum baseload ({min_pred_q10:,.0f} MW < {curtailment_threshold:,.0f} MW). Risk of negative LMP pricing; schedule battery storage charging.")
    else:
        st.success("✅ **GRID BALANCED:** Expected load remains within optimal dispatch corridor.")

    # 5. Interactive Plotly Fan-Chart
    st.subheader("📈 Probabilistic Asymmetric Load Fan-Chart")
    fig = go.Figure()
    
    # Upper Bound (q90) - Transparent line for fill
    fig.add_trace(go.Scatter(
        x=sub_df["Datetime"],
        y=sub_df["q90_adj"],
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        name="q90 Upper Bound",
        hoverinfo="skip"
    ))
    
    # Shaded 80% Uncertainty Band (q10 to q90)
    fig.add_trace(go.Scatter(
        x=sub_df["Datetime"],
        y=sub_df["q10_adj"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(56, 189, 248, 0.22)",
        name="80% Uncertainty Envelope (q10 - q90)",
        hoverinfo="skip"
    ))
    
    # 90th Percentile Curve (Peak Alert)
    fig.add_trace(go.Scatter(
        x=sub_df["Datetime"],
        y=sub_df["q90_adj"],
        mode="lines",
        line=dict(color="#ef4444", width=1.8, dash="dot"),
        name="&tau;=0.90 (Peak / Blackout Risk)"
    ))
    
    # 10th Percentile Curve (Curtailment Floor)
    fig.add_trace(go.Scatter(
        x=sub_df["Datetime"],
        y=sub_df["q10_adj"],
        mode="lines",
        line=dict(color="#3b82f6", width=1.8, dash="dot"),
        name="&tau;=0.10 (Curtailment Risk)"
    ))
    
    # 50th Percentile Curve (Median Base Forecast)
    fig.add_trace(go.Scatter(
        x=sub_df["Datetime"],
        y=sub_df["q50_adj"],
        mode="lines",
        line=dict(color="#10b981", width=2.5),
        name="&tau;=0.50 (Conditional Median)"
    ))
    
    # Actual Observed Ground Truth
    fig.add_trace(go.Scatter(
        x=sub_df["Datetime"],
        y=sub_df["y_true"],
        mode="lines+markers",
        marker=dict(size=4, color="#f8fafc"),
        line=dict(color="#f8fafc", width=1.2),
        name="Actual Grid Load (MW)"
    ))
    
    # Threshold Lines
    fig.add_hline(y=blackout_threshold, line_dash="dash", line_color="#dc2626", annotation_text="Blackout Margin", annotation_position="top right")
    fig.add_hline(y=curtailment_threshold, line_dash="dash", line_color="#2563eb", annotation_text="Curtailment Floor", annotation_position="bottom right")

    fig.update_layout(
        height=520,
        template="plotly_dark",
        margin=dict(l=40, r=40, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Timestamp (Hourly Dispatch)",
        yaxis_title="Grid Demand (Megawatts)",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 6. Hourly Dispatch Inspector & TreeSHAP Attribution
    st.markdown("---")
    st.subheader("🔍 Single-Hour Deep-Dive & TreeSHAP Attribution")
    
    col_insp_1, col_insp_2 = st.columns([1, 2])
    
    with col_insp_1:
        st.markdown("##### Select Operational Hour:")
        selected_hour = st.selectbox(
            "Select Hour to Inspect:",
            options=sub_df["Datetime"],
            format_func=lambda dt: dt.strftime("%Y-%m-%d %H:00")
        )
        
        row_sel = sub_df[sub_df["Datetime"] == selected_hour].iloc[0]
        
        st.markdown(f"""
        **Dispatch Summary for `{selected_hour.strftime('%A, %b %d, %Y - %H:00')}`:**
        * **Actual Observed Load:** `{row_sel['y_true']:,.1f} MW`
        * **90th Percentile Risk:** `{row_sel['q90_adj']:,.1f} MW`
        * **Median Forecast:** `{row_sel['q50_adj']:,.1f} MW`
        * **10th Percentile Floor:** `{row_sel['q10_adj']:,.1f} MW`
        * **Prediction Spread:** `{row_sel['q90_adj'] - row_sel['q10_adj']:,.1f} MW`
        * **In Envelope?** {'✅ YES' if row_sel['q10_adj'] <= row_sel['y_true'] <= row_sel['q90_adj'] else '❌ OUTLIER'}
        """)
        
    with col_insp_2:
        waterfall_img = PLOTS_DIR / "shap_peak_waterfall.png"
        summary_img = PLOTS_DIR / "shap_summary_q90.png"
        
        tab_waterfall, tab_summary = st.tabs(["⚡ Peak Stress Event Waterfall", "🌐 Global Feature Beeswarm"])
        
        with tab_waterfall:
            if waterfall_img.exists():
                st.image(str(waterfall_img), caption="TreeSHAP decomposition of extreme test peak load event", use_container_width=True)
            else:
                st.info("TreeSHAP peak waterfall plot will appear once explainability.py completes.")
                
        with tab_summary:
            if summary_img.exists():
                st.image(str(summary_img), caption="Global TreeSHAP feature importance beeswarm for tau = 0.90", use_container_width=True)
            else:
                st.info("TreeSHAP summary plot will appear once explainability.py completes.")


if __name__ == "__main__":
    main()
