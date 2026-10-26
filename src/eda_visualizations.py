"""
Publication-Grade Visualizations for Chapter 2 EDA:
1. 4-Line 24-Hour Diurnal Curve by Season with 25th-75th IQR Shaded Ribbons
2. Split Violin Plot: Weekday (Commercial/Industrial) vs Weekend (Residential)
3. Split Violin Plot: Regular Days vs US Federal Holidays
4. Dual Correlation Heatmap (Pearson Linear r vs Spearman Rank rho)
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import CLEANED_DATA_PATH, PLOTS_DIR, TARGET_COL

# Apply consistent publication aesthetic
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.size"] = 11
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["axes.labelsize"] = 12
plt.rcParams["figure.dpi"] = 300

SEASON_COLORS = {
    "Summer": "#EF4444",  # Crimson / Coral
    "Winter": "#3B82F6",  # Ice Blue
    "Autumn": "#F59E0B",  # Amber Gold
    "Spring": "#10B981",  # Emerald Green
}


def plot_diurnal_by_season(df: pd.DataFrame, output_path: Path):
    """Plot 24-hour diurnal profile by season with 25th-75th percentile IQR ribbons."""
    fig, ax = plt.subplots(figsize=(12, 6.5))
    
    hours = np.arange(24)
    
    for season in ["Summer", "Winter", "Autumn", "Spring"]:
        sub = df[df["season"] == season]
        grouped = sub.groupby("hour")[TARGET_COL]
        
        median = grouped.median().reindex(hours)
        q25 = grouped.quantile(0.25).reindex(hours)
        q75 = grouped.quantile(0.75).reindex(hours)
        
        color = SEASON_COLORS[season]
        
        # Plot solid median line
        ax.plot(hours, median, label=f"{season} (Median)", color=color, linewidth=2.5)
        
        # Fill IQR band
        ax.fill_between(hours, q25, q75, color=color, alpha=0.18, label=f"{season} IQR (Q1-Q3)")
        
    ax.set_title("PJM Interconnection Diurnal Electricity Demand Profile by Season", fontweight="bold", pad=15)
    ax.set_xlabel("Hour of Day (00:00 to 23:00)")
    ax.set_ylabel("Electricity Demand (Megawatts - MW)")
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45)
    ax.set_xlim(0, 23)
    
    # Annotations for peaks
    ax.annotate("Summer AC Peak\n(17:00 ~41,000 MW)", xy=(17, 41000), xytext=(12, 48000),
                arrowprops=dict(facecolor="#EF4444", shrink=0.08, width=1.5, headwidth=7),
                fontweight="bold", color="#EF4444")
    
    ax.annotate("Winter Morning Peak\n(08:00 ~36,000 MW)", xy=(8, 36000), xytext=(2, 42000),
                arrowprops=dict(facecolor="#3B82F6", shrink=0.08, width=1.5, headwidth=7),
                fontweight="bold", color="#3B82F6")

    # Clean legend
    handles, labels = ax.get_legend_handles_labels()
    # Keep only line labels in legend to prevent clutter
    line_handles = [h for i, h in enumerate(handles) if "Median" in labels[i]]
    line_labels = [l.replace(" (Median)", "") for l in labels if "Median" in l]
    ax.legend(line_handles, line_labels, title="Seasons", frameon=True, loc="lower right")
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_weekday_weekend_violin(df: pd.DataFrame, output_path: Path):
    """Split violin plot comparing weekday vs weekend demand distribution across seasons."""
    fig, ax = plt.subplots(figsize=(11, 6))
    
    df_plot = df.copy()
    df_plot["Day_Type"] = df_plot["is_weekend"].map({0: "Weekday (Commercial)", 1: "Weekend (Residential)"})
    
    palette = {"Weekday (Commercial)": "#2563EB", "Weekend (Residential)": "#F97316"}
    
    sns.violinplot(
        data=df_plot,
        x="season",
        y=TARGET_COL,
        hue="Day_Type",
        split=True,
        inner="quart",
        palette=palette,
        ax=ax,
        order=["Summer", "Winter", "Autumn", "Spring"],
        cut=0
    )
    
    ax.set_title("Structural Baseload Shift: Weekday vs. Weekend Distribution by Season", fontweight="bold", pad=15)
    ax.set_xlabel("Season")
    ax.set_ylabel("Electricity Demand (Megawatts - MW)")
    ax.legend(title="Day Classification", loc="upper right")
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_holiday_violin(df: pd.DataFrame, output_path: Path):
    """Violin plot comparing Regular Days vs Federal Holidays."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    df_plot = df.copy()
    df_plot["Holiday_Type"] = df_plot["is_holiday"].map({0: "Regular Day", 1: "Federal Holiday"})
    
    palette = {"Regular Day": "#0EA5E9", "Federal Holiday": "#E11D48"}
    
    sns.boxplot(
        data=df_plot,
        x="season",
        y=TARGET_COL,
        hue="Holiday_Type",
        palette=palette,
        ax=ax,
        order=["Summer", "Winter", "Autumn", "Spring"],
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "black"}
    )
    
    ax.set_title("Impact of US Federal Holidays on Electricity Demand by Season", fontweight="bold", pad=15)
    ax.set_xlabel("Season")
    ax.set_ylabel("Electricity Demand (Megawatts - MW)")
    ax.legend(title="Calendar Status", loc="upper right")
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_correlation_heatmap(df: pd.DataFrame, output_path: Path):
    """Dual heatmap comparing Pearson Linear (r) and Spearman Rank (rho) correlations."""
    df_corr = df.copy()
    df_corr["lag_1"] = df_corr[TARGET_COL].shift(1)
    df_corr["lag_24"] = df_corr[TARGET_COL].shift(24)
    df_corr["lag_168"] = df_corr[TARGET_COL].shift(168)
    df_corr["rolling_mean_24"] = df_corr[TARGET_COL].shift(1).rolling(24).mean()
    df_corr["rolling_std_24"] = df_corr[TARGET_COL].shift(1).rolling(24).std()
    
    df_corr["sin_hour"] = np.sin(2 * np.pi * df_corr["hour"] / 24)
    df_corr["cos_hour"] = np.cos(2 * np.pi * df_corr["hour"] / 24)
    df_corr["sin_doy"] = np.sin(2 * np.pi * df_corr["dayofyear"] / 365.25)
    df_corr["cos_doy"] = np.cos(2 * np.pi * df_corr["dayofyear"] / 365.25)
    
    cols = [
        TARGET_COL, "lag_1", "lag_24", "lag_168",
        "rolling_mean_24", "rolling_std_24",
        "hour", "is_weekend", "sin_hour", "cos_hour", "sin_doy", "cos_doy"
    ]
    
    sub = df_corr[cols].dropna()
    
    pearson_corr = sub.corr(method="pearson")
    spearman_corr = sub.corr(method="spearman")
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7.5))
    
    sns.heatmap(pearson_corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, ax=ax1, cbar_kws={"shrink": 0.8})
    ax1.set_title("Pearson Linear Correlation (r)", fontweight="bold", pad=12)
    
    sns.heatmap(spearman_corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, ax=ax2, cbar_kws={"shrink": 0.8})
    ax2.set_title("Spearman Monotonic Rank Correlation (ρ)", fontweight="bold", pad=12)
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {output_path}")


def generate_all_plots():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(CLEANED_DATA_PATH)
    
    plot_diurnal_by_season(df, PLOTS_DIR / "diurnal_load_by_season.png")
    plot_weekday_weekend_violin(df, PLOTS_DIR / "load_weekday_weekend_violin.png")
    plot_holiday_violin(df, PLOTS_DIR / "load_holiday_violin.png")
    plot_correlation_heatmap(df, PLOTS_DIR / "correlation_heatmap.png")
    print("All Chapter 2 diagnostic visualizations generated successfully!")


if __name__ == "__main__":
    generate_all_plots()
