"""
test_forecast_api.py — Sanity check for GET /api/forecast/{item_name}

Calls the running FastAPI backend for two very differently-scaled items
(Onion ~90-200 PKR vs Mutton ~1900-3400 PKR) and plots both 4-week
forecasts side by side, so you can visually confirm the predictions are
smooth, continuous with the last known price, and in the right ballpark —
not wildly diverging or discontinuous.

Run this AFTER starting the backend (uvicorn app.main:app --reload --host 0.0.0.0 --port 8000).
"""

import json
import requests
import matplotlib.pyplot as plt

BASE_URL = "http://localhost:8000"
ITEMS_TO_TEST = ["Onion", "Mutton"]


def fetch_forecast(item_name: str) -> dict:
    url = f"{BASE_URL}/api/forecast/{item_name}"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()


def main():
    results = {}

    for item in ITEMS_TO_TEST:
        print(f"\n{'=' * 60}")
        print(f"Fetching forecast for: {item}")
        print("=" * 60)
        try:
            data = fetch_forecast(item)
        except requests.exceptions.RequestException as e:
            print(f"  FAILED: {e}")
            continue

        print(json.dumps(data, indent=2))
        results[item] = data

    if not results:
        print("\nNo successful responses — check that the backend is running "
              "and the forecast artifacts loaded correctly.")
        return

    # Plot side by side — separate subplots because Onion and Mutton are on
    # wildly different price scales (a shared axis would flatten Onion's
    # trend to a near-invisible line next to Mutton's).
    fig, axes = plt.subplots(1, len(results), figsize=(7 * len(results), 5))
    if len(results) == 1:
        axes = [axes]

    for ax, (item, data) in zip(axes, results.items()):
        last_date = data["last_known_date"]
        last_price = data["last_known_price"]

        dates = [last_date] + [pt["date"] for pt in data["forecast"]]
        prices = [last_price] + [pt["predicted_price"] for pt in data["forecast"]]

        ax.plot(dates, prices, marker="o", linestyle="-", color="steelblue")
        ax.axvline(x=0, color="gray", linestyle="--", alpha=0.3)  # marks "today"
        ax.scatter([dates[0]], [prices[0]], color="black", zorder=5, label="Last known price")
        ax.set_title(f"{item} — 4-Week Forecast")
        ax.set_xlabel("Date")
        ax.set_ylabel(f"Price (PKR / {data['unit']})")
        ax.tick_params(axis="x", rotation=45)
        ax.legend()
        ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("forecast_sanity_check.png")
    print("\nSaved plot: forecast_sanity_check.png")
    plt.show()


if __name__ == "__main__":
    main()