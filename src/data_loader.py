"""
Data ingestion and cleaning pipeline for PJM Hourly Energy Consumption.
Handles chronological sorting, daylight savings duplicates/gaps, and calendar feature enrichment.
"""
from typing import Optional
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Ensure src can be imported
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import RAW_DATA_PATH, CLEANED_DATA_PATH, DATETIME_COL, TARGET_COL


def get_season(month: int) -> str:
    """Map month number (1-12) to meteorological season."""
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    else:
        return "Autumn"


def is_us_federal_holiday(dates: pd.DatetimeIndex) -> pd.Series:
    """
    Flag US Federal Holidays without external dependencies.
    Covers New Year's Day, MLK Day, Washington's Bday, Memorial Day,
    Independence Day, Labor Day, Columbus Day, Veterans Day, Thanksgiving, Christmas.
    """
    holidays = set()
    years = dates.year.unique()
    
    for y in years:
        # Fixed-date holidays
        holidays.add(pd.Timestamp(f"{y}-01-01"))  # New Year
        holidays.add(pd.Timestamp(f"{y}-07-04"))  # Independence Day
        holidays.add(pd.Timestamp(f"{y}-11-11"))  # Veterans Day
        holidays.add(pd.Timestamp(f"{y}-12-25"))  # Christmas
        
        # Martin Luther King Jr. Day: 3rd Monday in Jan
        jan = pd.date_range(f"{y}-01-01", f"{y}-01-31", freq="D")
        mondays_jan = [d for d in jan if d.dayofweek == 0]
        if len(mondays_jan) >= 3:
            holidays.add(mondays_jan[2])
            
        # Washington's Birthday (Presidents Day): 3rd Monday in Feb
        feb = pd.date_range(f"{y}-02-01", f"{y}-02-28", freq="D")
        mondays_feb = [d for d in feb if d.dayofweek == 0]
        if len(mondays_feb) >= 3:
            holidays.add(mondays_feb[2])
            
        # Memorial Day: Last Monday in May
        may = pd.date_range(f"{y}-05-01", f"{y}-05-31", freq="D")
        mondays_may = [d for d in may if d.dayofweek == 0]
        if mondays_may:
            holidays.add(mondays_may[-1])
            
        # Labor Day: 1st Monday in Sep
        sep = pd.date_range(f"{y}-09-01", f"{y}-09-30", freq="D")
        mondays_sep = [d for d in sep if d.dayofweek == 0]
        if mondays_sep:
            holidays.add(mondays_sep[0])
            
        # Columbus Day: 2nd Monday in Oct
        oct_days = pd.date_range(f"{y}-10-01", f"{y}-10-31", freq="D")
        mondays_oct = [d for d in oct_days if d.dayofweek == 0]
        if len(mondays_oct) >= 2:
            holidays.add(mondays_oct[1])
            
        # Thanksgiving: 4th Thursday in Nov
        nov = pd.date_range(f"{y}-11-01", f"{y}-11-30", freq="D")
        thursdays_nov = [d for d in nov if d.dayofweek == 3]
        if len(thursdays_nov) >= 4:
            holidays.add(thursdays_nov[3])
            
    date_normalized = pd.to_datetime(dates.date)
    return pd.Series(date_normalized.isin(holidays).astype(int), index=dates)


def load_and_clean_data(raw_path: Path = RAW_DATA_PATH) -> pd.DataFrame:
    """
    Ingests raw PJME hourly CSV, resolves duplicate timestamps,
    reindexes to an unbroken hourly frequency, and appends calendar columns.
    """
    print(f"Loading raw data from: {raw_path}")
    df = pd.read_csv(raw_path)
    
    # Parse datetimes
    df[DATETIME_COL] = pd.to_datetime(df[DATETIME_COL])
    
    # Sort chronologically
    df = df.sort_values(DATETIME_COL).reset_index(drop=True)
    
    # Handle duplicate timestamps (Daylight Savings fall-back) by averaging load
    df = df.groupby(DATETIME_COL, as_index=False)[TARGET_COL].mean()
    
    # Set DatetimeIndex
    df = df.set_index(DATETIME_COL)
    
    # Reindex to strict continuous hourly frequency to catch missing hours
    full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="h", name=DATETIME_COL)
    df = df.reindex(full_idx)
    
    # Interpolate missing values (e.g. spring forward 1-hour gap)
    missing_count = df[TARGET_COL].isna().sum()
    if missing_count > 0:
        print(f"Interpolating {missing_count} missing hourly values...")
        df[TARGET_COL] = df[TARGET_COL].interpolate(method="time")
        
    # Reset index for feature creation
    df = df.reset_index()
    
    # Enrich with calendar attributes
    df["year"] = df[DATETIME_COL].dt.year
    df["month"] = df[DATETIME_COL].dt.month
    df["day"] = df[DATETIME_COL].dt.day
    df["hour"] = df[DATETIME_COL].dt.hour
    df["dayofweek"] = df[DATETIME_COL].dt.dayofweek
    df["dayofyear"] = df[DATETIME_COL].dt.dayofyear
    df["season"] = df["month"].apply(get_season)
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    
    # Holiday detection
    df["is_holiday"] = is_us_federal_holiday(pd.DatetimeIndex(df[DATETIME_COL])).values
    
    # Save cleaned copy
    CLEANED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CLEANED_DATA_PATH, index=False)
    print(f"Cleaned dataset saved: {CLEANED_DATA_PATH} ({len(df):,} hourly rows)")
    
    return df


if __name__ == "__main__":
    load_and_clean_data()
