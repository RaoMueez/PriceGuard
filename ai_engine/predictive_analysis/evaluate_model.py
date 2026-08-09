"""
evaluate_model.py — PriceGuard Phase 6: Model Evaluation

Computes proper accuracy metrics (RMSE, MAE, MAPE) on the held-out
VALIDATION set — the same chronological split used during training, reused
directly from train_model.py so these numbers are guaranteed to reflect
genuinely unseen data, not a re-shuffled or leaked sample.

Reports per-item metrics (since items are on very different price scales,
a single blended RMSE across all items would be dominated by high-value
items like Mutton and would understate accuracy on cheap items like Onion),
plus overall summary statistics suitable for a thesis defense table.

Run this AFTER train_model.py has produced priceguard_lstm.keras,
item_scalers.joblib, and model_config.joblib in the same folder.
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from tensorflow import keras

from train_model import load_and_scale_data, build_sequences, CSV_PATH, WINDOW_SIZE, VALIDATION_FRACTION

BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "priceguard_lstm.keras"
SCALERS_PATH = BASE_DIR / "item_scalers.joblib"
CONFIG_PATH = BASE_DIR / "model_config.joblib"
RESULTS_CSV_PATH = BASE_DIR / "evaluation_results.csv"


def evaluate():
    print("Loading model and artifacts...")
    model = keras.models.load_model(MODEL_PATH)
    scalers = joblib.load(SCALERS_PATH)
    config = joblib.load(CONFIG_PATH)
    item_list = config["item_list"]

    print("Rebuilding the exact same train/validation split used during training...")
    df, _, _ = load_and_scale_data(CSV_PATH)
    _, _, X_val, y_val = build_sequences(df, item_list, WINDOW_SIZE, VALIDATION_FRACTION)
    print(f"Validation set: {X_val.shape[0]} sequences\n")

    # Every sample's one-hot item identity is embedded in its own feature
    # vector (identical across all timesteps within that sequence) — extract
    # it from timestep 0 to know which item each prediction/target belongs to,
    # so each one can be inverse-transformed with its OWN item's scaler.
    item_onehot_per_sample = X_val[:, 0, 1:]
    item_index_per_sample = np.argmax(item_onehot_per_sample, axis=1)

    print("Running predictions on the validation set...")
    predictions_scaled = model.predict(X_val, verbose=0).flatten()
    actuals_scaled = y_val.flatten()

    # Overall scaled-space metrics — scale-invariant (0-1 range for every
    # item), directly comparable to the val_loss/val_mae printed during
    # training as a consistency check.
    overall_scaled_mse = float(np.mean((predictions_scaled - actuals_scaled) ** 2))
    overall_scaled_rmse = float(np.sqrt(overall_scaled_mse))
    overall_scaled_mae = float(np.mean(np.abs(predictions_scaled - actuals_scaled)))

    print(f"Overall (scaled 0-1 space) — RMSE: {overall_scaled_rmse:.4f}, "
          f"MAE: {overall_scaled_mae:.4f}")
    print("(Compare this MAE/sqrt(MSE) against the final val_loss/val_mae "
          "printed by train_model.py — they should be close, confirming "
          "this evaluation is consistent with training.)\n")

    # Per-item metrics in REAL PKR — this is what's actually defensible and
    # interpretable in a thesis committee ("the model is off by ~Rs. 8 on
    # average for Onion" means something; "MSE = 0.003" does not).
    results = []
    for idx, item in enumerate(item_list):
        mask = item_index_per_sample == idx
        if mask.sum() == 0:
            continue

        scaler = scalers[item]
        pred_real = scaler.inverse_transform(predictions_scaled[mask].reshape(-1, 1)).flatten()
        actual_real = scaler.inverse_transform(actuals_scaled[mask].reshape(-1, 1)).flatten()

        rmse = float(np.sqrt(np.mean((pred_real - actual_real) ** 2)))
        mae = float(np.mean(np.abs(pred_real - actual_real)))
        # MAPE — guard against near-zero actuals to avoid divide-by-huge-number blowups
        nonzero_mask = np.abs(actual_real) > 1e-6
        mape = float(np.mean(np.abs((actual_real[nonzero_mask] - pred_real[nonzero_mask]) / actual_real[nonzero_mask])) * 100) if nonzero_mask.any() else float("nan")

        results.append({
            "item_name": item,
            "n_samples": int(mask.sum()),
            "rmse_pkr": round(rmse, 2),
            "mae_pkr": round(mae, 2),
            "mape_pct": round(mape, 2),
        })

    results_df = pd.DataFrame(results).sort_values("mape_pct")
    results_df.to_csv(RESULTS_CSV_PATH, index=False)

    print("Per-item metrics (sorted by MAPE, best to worst):")
    print(results_df.to_string(index=False))

    print(f"\n{'=' * 60}")
    print("SUMMARY (for thesis defense)")
    print("=" * 60)
    print(f"Overall scaled RMSE:        {overall_scaled_rmse:.4f}")
    print(f"Overall scaled MAE:         {overall_scaled_mae:.4f}")
    print(f"Mean per-item RMSE (PKR):   {results_df['rmse_pkr'].mean():.2f}")
    print(f"Mean per-item MAE (PKR):    {results_df['mae_pkr'].mean():.2f}")
    print(f"Mean per-item MAPE (%):     {results_df['mape_pct'].mean():.2f}%")
    print(f"Median per-item MAPE (%):   {results_df['mape_pct'].median():.2f}%")
    print(f"Best item (lowest MAPE):    {results_df.iloc[0]['item_name']} ({results_df.iloc[0]['mape_pct']}%)")
    print(f"Worst item (highest MAPE):  {results_df.iloc[-1]['item_name']} ({results_df.iloc[-1]['mape_pct']}%)")
    print(f"\nSaved full per-item results to: {RESULTS_CSV_PATH}")


if __name__ == "__main__":
    evaluate()