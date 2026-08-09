"""
data_generator.py — PriceGuard Phase 6, Step 1: Data Preparation

Generates a synthetic 3-year weekly historical price dataset for the 31
commodities PriceGuard tracks, with:
  - a gradual inflation trend
  - per-item seasonality (e.g. mangoes cheaper in summer, eggs pricier in winter)
  - random weekly noise
  - injected "hoarding" anomaly events (sudden multi-week spikes) for a subset
    of items known for artificial hikes, flagged via an `is_anomaly` column
    so this dataset can double as labeled training data for anomaly detection.

IMPORTANT: Base prices below are ILLUSTRATIVE approximations for demo/training
purposes only — they are NOT sourced from real PBS/market data. Before using
this for anything beyond model-architecture testing, replace them with actual
historical rates (e.g. from PBS weekly SPI bulletins) if your committee expects
real-world-grounded numbers.

Output: historical_prices.csv (long format — one row per item per week)
"""

import numpy as np
import pandas as pd
import zlib
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
RANDOM_SEED = 42
YEARS_OF_HISTORY = 3
ANNUAL_INFLATION_RATE = 0.18  # ~18%/year, roughly in line with recent Pakistan CPI trends — adjust as needed

rng = np.random.default_rng(RANDOM_SEED)

# name -> (base_price_pkr, unit, category, seasonal_amplitude, seasonal_peak_month, weekly_noise_pct)
# seasonal_amplitude: fraction of base price the seasonal swing adds/subtracts (e.g. 0.20 = ±20%)
# seasonal_peak_month: month (1-12) where price peaks (highest); trough is 6 months opposite
# weekly_noise_pct: random week-to-week jitter, as a fraction of price
COMMODITIES = {
    # Vegetables
    "Onion":         (90,  "kg",    "Vegetables", 0.15, 9,  0.06),
    "Potato":        (70,  "kg",    "Vegetables", 0.10, 3,  0.05),
    "Cabbage":       (60,  "kg",    "Vegetables", 0.15, 1,  0.06),
    "Capsicum":      (140, "kg",    "Vegetables", 0.20, 7,  0.07),
    "Carrot":        (90,  "kg",    "Vegetables", 0.15, 1,  0.06),
    "Cauliflower":   (80,  "kg",    "Vegetables", 0.20, 1,  0.07),
    "Cucumber":      (70,  "kg",    "Vegetables", 0.25, 6,  0.08),
    "Garlic":        (400, "kg",    "Vegetables", 0.15, 9,  0.07),
    "Ginger":        (350, "kg",    "Vegetables", 0.15, 9,  0.06),
    "Green Chili":   (160, "kg",    "Vegetables", 0.30, 7,  0.09),
    "Tomato":        (110, "kg",    "Vegetables", 0.30, 8,  0.10),
    "Spinach":       (60,  "kg",    "Vegetables", 0.20, 1,  0.07),
    # Fruits
    "Apple":         (250, "kg",    "Fruits",     0.15, 11, 0.05),
    "Banana":        (140, "dozen", "Fruits",     0.10, 5,  0.04),
    "Grapes":        (300, "kg",    "Fruits",     0.20, 8,  0.06),
    "Guava":         (150, "kg",    "Fruits",     0.20, 11, 0.06),
    "Mango":         (200, "kg",    "Fruits",     0.35, 6,  0.08),   # cheapest in summer -> peak_month set opposite below
    "Melon":         (100, "kg",    "Fruits",     0.30, 6,  0.07),
    "Orange":        (180, "kg",    "Fruits",     0.20, 1,  0.05),
    "Papaya":        (170, "kg",    "Fruits",     0.15, 5,  0.05),
    "Peach":         (220, "kg",    "Fruits",     0.25, 6,  0.07),
    "Plum":          (220, "kg",    "Fruits",     0.25, 6,  0.07),
    "Pomegranate":   (350, "kg",    "Fruits",     0.20, 10, 0.06),
    "Watermelon":    (80,  "kg",    "Fruits",     0.30, 6,  0.07),
    # Dairy & Eggs
    "Eggs":          (300, "dozen", "Dairy",      0.10, 1,  0.04),   # pricier in winter
    "Milk":          (220, "liter", "Dairy",      0.05, 1,  0.02),
    "Yoghurt":        (240, "liter", "Dairy",      0.05, 1,  0.02),
    # Poultry & Meat
    "Chicken (Farm Gate Rate)":   (350, "kg", "Poultry & Meat", 0.15, 4, 0.09),
    "Chicken (Processed Rate)":   (450, "kg", "Poultry & Meat", 0.15, 4, 0.08),
    "Beef Meat":     (1000, "kg", "Poultry & Meat", 0.08, 6,  0.04),
    "Mutton":        (1900, "kg", "Poultry & Meat", 0.08, 6,  0.04),
}

# Mango and Melon are genuinely CHEAPEST at their harvest peak (summer), so their
# "seasonal_peak_month" above is set to the CHEAP month and we invert the curve
# for these specific items rather than adding a separate config field.
INVERTED_SEASONALITY_ITEMS = {"Mango", "Melon", "Watermelon"}

# Items prone to artificial hoarding-driven spikes — matches the real-world
# pattern PriceGuard is designed to catch (onion/tomato/garlic price hikes
# are recurring news stories in Pakistan).
HOARDING_PRONE_ITEMS = ["Onion", "Tomato", "Potato", "Garlic", "Chicken (Farm Gate Rate)"]

OUTPUT_FILE = "historical_prices.csv"


# ------------------------------------------------------------------
# GENERATION LOGIC
# ------------------------------------------------------------------
def build_weekly_date_range(years: int) -> pd.DatetimeIndex:
    end_date = datetime.today()
    start_date = end_date - timedelta(weeks=years * 52)
    return pd.date_range(start=start_date, end=end_date, freq="W-MON")


def seasonal_multiplier(week_dates: pd.DatetimeIndex, peak_month: int, amplitude: float, invert: bool) -> np.ndarray:
    """
    Returns a per-week multiplier oscillating around 1.0 using a cosine wave
    aligned so the peak falls in `peak_month`. Smoothly continuous across the
    year boundary (no seasonal "jump" from Dec to Jan).
    """
    day_of_year = week_dates.dayofyear.values
    peak_day = pd.Timestamp(year=2001, month=peak_month, day=15).dayofyear  # non-leap reference year
    phase = (day_of_year - peak_day) / 365.25 * 2 * np.pi
    wave = np.cos(phase)  # +1 at peak, -1 at trough
    if invert:
        wave = -wave
    return 1 + amplitude * wave


def inflation_multiplier(week_dates: pd.DatetimeIndex, annual_rate: float) -> np.ndarray:
    """Compounding weekly inflation applied from the start of the series."""
    weeks_elapsed = np.arange(len(week_dates))
    weekly_rate = (1 + annual_rate) ** (1 / 52) - 1
    return (1 + weekly_rate) ** weeks_elapsed


def generate_hoarding_anomalies(week_dates: pd.DatetimeIndex, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """
    Injects 3-6 hoarding events across the series for a hoarding-prone item.
    Each event: a sharp spike over 1-2 weeks, elevated plateau for 1-3 weeks,
    then decay back to trend over 1-2 weeks — mimicking real hoarding-driven
    price hikes that build, hold, then ease off once supply catches up.

    Returns:
        multiplier: per-week multiplier array (1.0 = no anomaly effect)
        is_anomaly: boolean array flagging which weeks are affected
    """
    n_weeks = len(week_dates)
    multiplier = np.ones(n_weeks)
    is_anomaly = np.zeros(n_weeks, dtype=bool)

    n_events = rng.integers(3, 7)  # 3-6 events over 3 years
    # Keep events spaced out — pick non-overlapping start points with a cooldown gap
    min_gap = 8  # weeks
    possible_starts = list(range(4, n_weeks - 10))
    rng.shuffle(possible_starts)

    chosen_starts = []
    for start in possible_starts:
        if len(chosen_starts) >= n_events:
            break
        if all(abs(start - s) > min_gap for s in chosen_starts):
            chosen_starts.append(start)

    for start in chosen_starts:
        ramp_up = rng.integers(1, 3)      # weeks
        plateau = rng.integers(1, 4)      # weeks
        ramp_down = rng.integers(1, 3)    # weeks
        peak_intensity = rng.uniform(1.5, 3.0)  # 50%-200% above trend at peak

        idx = start
        # Ramp up
        for i in range(ramp_up):
            if idx >= n_weeks:
                break
            frac = (i + 1) / ramp_up
            multiplier[idx] = 1 + (peak_intensity - 1) * frac
            is_anomaly[idx] = True
            idx += 1
        # Plateau
        for i in range(plateau):
            if idx >= n_weeks:
                break
            multiplier[idx] = peak_intensity
            is_anomaly[idx] = True
            idx += 1
        # Ramp down
        for i in range(ramp_down):
            if idx >= n_weeks:
                break
            frac = 1 - (i + 1) / ramp_down
            multiplier[idx] = 1 + (peak_intensity - 1) * frac
            is_anomaly[idx] = True
            idx += 1

    return multiplier, is_anomaly


def generate_item_series(item_name: str, config: tuple, week_dates: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    base_price, unit, category, amplitude, peak_month, noise_pct = config
    invert = item_name in INVERTED_SEASONALITY_ITEMS

    seasonal = seasonal_multiplier(week_dates, peak_month, amplitude, invert)
    inflation = inflation_multiplier(week_dates, ANNUAL_INFLATION_RATE)
    noise = 1 + rng.normal(loc=0, scale=noise_pct, size=len(week_dates))
    noise = np.clip(noise, 1 - noise_pct * 3, 1 + noise_pct * 3)  # cap extreme noise outliers

    price = base_price * seasonal * inflation * noise

    is_anomaly = np.zeros(len(week_dates), dtype=bool)
    if item_name in HOARDING_PRONE_ITEMS:
        anomaly_mult, is_anomaly = generate_hoarding_anomalies(week_dates, rng)
        price = price * anomaly_mult

    price = np.round(price, 0)
    price = np.maximum(price, 1)  # floor — never allow zero/negative prices

    return pd.DataFrame({
        "date": week_dates,
        "item_name": item_name,
        "category": category,
        "unit": unit,
        "price": price,
        "is_anomaly": is_anomaly,
    })


def main():
    week_dates = build_weekly_date_range(YEARS_OF_HISTORY)
    print(f"Generating {len(week_dates)} weeks of data "
          f"({week_dates[0].date()} to {week_dates[-1].date()}) "
          f"for {len(COMMODITIES)} commodities...")

    all_series = []
    for item_name, config in COMMODITIES.items():
        item_rng = np.random.default_rng(RANDOM_SEED + zlib.crc32(item_name.encode()) % (2**32))
        df = generate_item_series(item_name, config, week_dates, item_rng)
        all_series.append(df)

    full_df = pd.concat(all_series, ignore_index=True)
    full_df = full_df.sort_values(["item_name", "date"]).reset_index(drop=True)
    full_df["date"] = full_df["date"].dt.strftime("%Y-%m-%d")

    full_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"Total rows: {len(full_df)}")
    print(f"\nAnomaly events injected per item:")
    anomaly_summary = full_df[full_df["is_anomaly"]].groupby("item_name").size()
    if anomaly_summary.empty:
        print("  (none)")
    else:
        for item, count in anomaly_summary.items():
            print(f"  {item}: {count} anomalous weeks")

    print("\nSample rows:")
    print(full_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()