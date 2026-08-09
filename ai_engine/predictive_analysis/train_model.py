"""
train_model.py — PriceGuard Phase 6, Step 2: Model Training & Feature Engineering

Trains a single, shared LSTM model across ALL commodities (rather than one
model per item) — this lets the model learn general price-dynamics patterns
(seasonality shapes, hoarding-spike shapes) that transfer across items, while
still knowing WHICH item it's looking at via a one-hot item identity vector
concatenated onto every timestep of the input sequence.

Key design choices (documented inline where they matter):
  - Scaling is done PER ITEM, not globally. Onion (~90 PKR) and Mutton
    (~1900 PKR) are on wildly different scales — a single global MinMaxScaler
    would squash Onion's variation into a tiny sliver of the 0-1 range.
    Each item gets its own MinMaxScaler; all scalers are saved together.
  - Sequences are built strictly within each item's own chronological series
    (grouped by item_name, sorted by date) — never bleeding one item's
    history into another's window.
  - Train/validation split is chronological (last ~15% of each item's weeks
    held out), not a random shuffle — random shuffling on time-series data
    leaks future information into training and gives misleadingly good
    validation loss.

Outputs (all needed by the FastAPI backend in the next phase):
  - priceguard_lstm.keras   — the trained model
  - item_scalers.joblib     — dict[item_name -> fitted MinMaxScaler]
  - model_config.joblib     — dict with WINDOW_SIZE, item list/order (for
                              reconstructing the one-hot vector at inference
                              time), and feature layout — without this, the
                              backend can't correctly rebuild inputs later.
  - training_loss_curve.png — quick visual sanity check for the report
"""

import json
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "historical_prices.csv"

WINDOW_SIZE = 8          # weeks of history used to predict the next week
VALIDATION_FRACTION = 0.15  # last N% of each item's weeks held out, chronologically
RANDOM_SEED = 42
EPOCHS = 100
BATCH_SIZE = 32
LSTM_UNITS_1 = 64
LSTM_UNITS_2 = 32
DENSE_UNITS = 16
DROPOUT_RATE = 0.2
LEARNING_RATE = 0.001

MODEL_OUTPUT_PATH = BASE_DIR / "priceguard_lstm.keras"
SCALERS_OUTPUT_PATH = BASE_DIR / "item_scalers.joblib"
CONFIG_OUTPUT_PATH = BASE_DIR / "model_config.joblib"
LOSS_PLOT_PATH = BASE_DIR / "training_loss_curve.png"

np.random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)


# ------------------------------------------------------------------
# STEP 1 — LOAD & PER-ITEM SCALING
# ------------------------------------------------------------------
def load_and_scale_data(csv_path: Path) -> tuple[pd.DataFrame, dict, list]:
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values(["item_name", "date"]).reset_index(drop=True)

    item_list = sorted(df["item_name"].unique().tolist())
    print(f"Loaded {len(df)} rows across {len(item_list)} items "
          f"({df['date'].min().date()} to {df['date'].max().date()})")

    scalers = {}
    scaled_prices = np.zeros(len(df))

    for item in item_list:
        mask = df["item_name"] == item
        prices = df.loc[mask, "price"].values.reshape(-1, 1)

        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(prices).flatten()

        scaled_prices[mask.values] = scaled
        scalers[item] = scaler

    df["scaled_price"] = scaled_prices
    return df, scalers, item_list


# ------------------------------------------------------------------
# STEP 2 — SEQUENCE WINDOWING (per item, item-identity one-hot appended)
# ------------------------------------------------------------------
def build_sequences(df: pd.DataFrame, item_list: list, window_size: int, val_fraction: float):
    """
    For each item, slides a window of `window_size` scaled prices to predict
    the next week's scaled price. Each timestep's feature vector is
    [scaled_price, one-hot item vector] — the one-hot is identical across all
    timesteps in a given sequence (it just tells the shared LSTM which item's
    dynamics it's looking at), and the target is the scaled price for the
    week immediately following the window.

    Returns train/val arrays already concatenated across all items, plus the
    one-hot column order (must be reused unchanged at inference time).
    """
    num_items = len(item_list)
    item_to_index = {item: i for i, item in enumerate(item_list)}

    X_train, y_train = [], []
    X_val, y_val = [], []

    for item in item_list:
        item_df = df[df["item_name"] == item].sort_values("date")
        prices = item_df["scaled_price"].values

        one_hot = np.zeros(num_items)
        one_hot[item_to_index[item]] = 1.0

        sequences_X, sequences_y = [], []
        for i in range(len(prices) - window_size):
            window = prices[i: i + window_size]
            target = prices[i + window_size]

            # Repeat the one-hot vector at every timestep, appended to the price
            features = np.column_stack([
                window,
                np.tile(one_hot, (window_size, 1))
            ])
            sequences_X.append(features)
            sequences_y.append(target)

        sequences_X = np.array(sequences_X)
        sequences_y = np.array(sequences_y)

        # Chronological split — last val_fraction of THIS ITEM's sequences
        # are held out, earlier ones are used for training. Keeps sequences
        # from the same time period out of both sets simultaneously.
        n_val = max(1, int(len(sequences_X) * val_fraction))
        n_train = len(sequences_X) - n_val

        X_train.append(sequences_X[:n_train])
        y_train.append(sequences_y[:n_train])
        X_val.append(sequences_X[n_train:])
        y_val.append(sequences_y[n_train:])

    X_train = np.concatenate(X_train, axis=0)
    y_train = np.concatenate(y_train, axis=0)
    X_val = np.concatenate(X_val, axis=0)
    y_val = np.concatenate(y_val, axis=0)

    return X_train, y_train, X_val, y_val


# ------------------------------------------------------------------
# STEP 3 — MODEL ARCHITECTURE
# ------------------------------------------------------------------
def build_model(input_shape: tuple) -> keras.Model:
    model = keras.Sequential([
        layers.Input(shape=input_shape),
        layers.LSTM(LSTM_UNITS_1, return_sequences=True),
        layers.Dropout(DROPOUT_RATE),
        layers.LSTM(LSTM_UNITS_2, return_sequences=False),
        layers.Dropout(DROPOUT_RATE),
        layers.Dense(DENSE_UNITS, activation="relu"),
        layers.Dense(1, activation="sigmoid"),  # sigmoid because targets are scaled to [0, 1]
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="mse",
        metrics=["mae"],
    )
    return model


# ------------------------------------------------------------------
# STEP 4 — TRAIN
# ------------------------------------------------------------------
def train(model, X_train, y_train, X_val, y_val):
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=10, restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6
        ),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1,
    )
    return history


# ------------------------------------------------------------------
# STEP 5 — SAVE ARTIFACTS
# ------------------------------------------------------------------
def save_artifacts(model, scalers, item_list, history):
    model.save(MODEL_OUTPUT_PATH)
    joblib.dump(scalers, SCALERS_OUTPUT_PATH)

    config = {
        "window_size": WINDOW_SIZE,
        "item_list": item_list,  # one-hot column order — MUST match at inference time
        "num_items": len(item_list),
        "feature_layout": "scaled_price + one_hot(item)",
    }
    joblib.dump(config, CONFIG_OUTPUT_PATH)

    # Also save a human-readable JSON copy of the item list — handy for
    # quickly checking/debugging without loading joblib in the backend.
    with open(BASE_DIR / "item_list.json", "w") as f:
        json.dump(item_list, f, indent=2)

    plt.figure(figsize=(10, 5))
    plt.plot(history.history["loss"], label="Training Loss")
    plt.plot(history.history["val_loss"], label="Validation Loss")
    plt.title("PriceGuard LSTM — Training vs Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss (MSE, scaled)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(LOSS_PLOT_PATH)
    plt.close()

    print(f"\nSaved artifacts:")
    print(f"  Model:          {MODEL_OUTPUT_PATH}")
    print(f"  Scalers:        {SCALERS_OUTPUT_PATH}")
    print(f"  Config:         {CONFIG_OUTPUT_PATH}")
    print(f"  Item list JSON: {BASE_DIR / 'item_list.json'}")
    print(f"  Loss curve:     {LOSS_PLOT_PATH}")


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    print("=" * 60)
    print("PriceGuard LSTM Training — Phase 6, Step 2")
    print("=" * 60)

    df, scalers, item_list = load_and_scale_data(CSV_PATH)

    print(f"\nBuilding sequences (window size = {WINDOW_SIZE} weeks)...")
    X_train, y_train, X_val, y_val = build_sequences(df, item_list, WINDOW_SIZE, VALIDATION_FRACTION)
    print(f"  Training sequences:   {X_train.shape}")
    print(f"  Validation sequences: {X_val.shape}")

    print(f"\nBuilding model...")
    model = build_model(input_shape=(WINDOW_SIZE, X_train.shape[2]))
    model.summary()

    print(f"\nTraining (up to {EPOCHS} epochs, early stopping on val_loss)...")
    history = train(model, X_train, y_train, X_val, y_val)

    final_train_loss = history.history["loss"][-1]
    final_val_loss = history.history["val_loss"][-1]
    print(f"\nFinal training loss (MSE):   {final_train_loss:.6f}")
    print(f"Final validation loss (MSE): {final_val_loss:.6f}")

    save_artifacts(model, scalers, item_list, history)
    print("\nDone.")


if __name__ == "__main__":
    main()