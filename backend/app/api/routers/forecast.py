# app/api/routers/forecast.py
#
# PriceGuard Phase 6, Step 3: Forecast API
#
# Loads the trained LSTM model, per-item scalers, and config ONCE at module
# import time (which happens once, when FastAPI starts up and main.py imports
# this router) — not per-request. All three are held in module-level
# variables and reused across every call to the endpoint below.

from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from tensorflow import keras
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forecast", tags=["Forecast"])

# ------------------------------------------------------------------
# ARTIFACT LOCATIONS
#
# For now this loads artifacts from a dedicated folder inside the backend
# itself (recommended: copy priceguard_lstm.keras, item_scalers.joblib,
# model_config.joblib, and historical_prices.csv into backend/app/ml_artifacts/
# rather than reaching across into the sibling ai_engine/predictive_analysis
# folder). Keeping the backend self-contained avoids a fragile relative path
# jumping outside its own directory tree, which matters if this ever gets
# deployed separately from the ai_engine folder.
# ------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "ml_artifacts"

MODEL_PATH = ARTIFACTS_DIR / "priceguard_lstm.keras"
SCALERS_PATH = ARTIFACTS_DIR / "item_scalers.joblib"
CONFIG_PATH = ARTIFACTS_DIR / "model_config.joblib"
HISTORICAL_CSV_PATH = ARTIFACTS_DIR / "historical_prices.csv"

FORECAST_WEEKS_AHEAD = 4


# ------------------------------------------------------------------
# LOAD ONCE AT STARTUP (module import time)
# ------------------------------------------------------------------
try:
    _model = keras.models.load_model(MODEL_PATH)
    _scalers: dict = joblib.load(SCALERS_PATH)
    _config: dict = joblib.load(CONFIG_PATH)
    _item_list: list = _config["item_list"]
    _window_size: int = _config["window_size"]
    _historical_df = pd.read_csv(HISTORICAL_CSV_PATH, parse_dates=["date"])
    _load_error = None
    logger.info(f"Loaded model, {len(_scalers)} scalers, "
            f"window_size={_window_size}, {len(_historical_df)} historical rows.")
except Exception as e:
    # Don't crash the whole app if artifacts are missing/misplaced — surface
    # a clear error on the endpoint itself instead, so the rest of the API
    # (complaints, rates, etc.) keeps working even if Phase 6 isn't wired up yet.
    _model = None
    _scalers = {}
    _config = {}
    _item_list = []
    _window_size = 8
    _historical_df = pd.DataFrame()
    _load_error = str(e)
    logger.error(f"Failed to load forecast artifacts: {_load_error}")


# ------------------------------------------------------------------
# RESPONSE SCHEMAS
# ------------------------------------------------------------------
class ForecastPoint(BaseModel):
    date: str
    predicted_price: float


class HistoryPoint(BaseModel):
    date: str
    price: float


class ForecastResponse(BaseModel):
    item_name: str
    category: str
    unit: str
    last_known_date: str
    last_known_price: float
    window_size_used: int
    history: list[HistoryPoint]
    forecast: list[ForecastPoint]
    generated_at: str


# ------------------------------------------------------------------
# CORE FORECASTING LOGIC
# ------------------------------------------------------------------
def _recursive_forecast(item_name: str, weeks_ahead: int) -> tuple[list, list]:
    """
    The model predicts exactly ONE week ahead from a window of past weeks.
    To forecast multiple weeks out, each new prediction is fed back into the
    window (dropping the oldest week) to predict the next one — standard
    recursive multi-step forecasting for a single-step-ahead model.

    Note: this means forecast accuracy degrades further out — week 4 is
    predicted partly from the model's own earlier predictions, not real
    data, so uncertainty compounds. Fine for an FYP demo; worth mentioning
    if asked about limitations.
    """
    item_df = _historical_df[_historical_df["item_name"] == item_name].sort_values("date")
    last_date = item_df["date"].max()
    scaler = _scalers[item_name]

    recent_prices = item_df["price"].values[-_window_size:].reshape(-1, 1)
    scaled_window = scaler.transform(recent_prices).flatten().tolist()

    one_hot = np.zeros(len(_item_list))
    one_hot[_item_list.index(item_name)] = 1.0

    working_window = list(scaled_window)
    forecast_dates = []
    forecast_prices = []

    for step in range(weeks_ahead):
        features = np.column_stack([
            working_window,
            np.tile(one_hot, (_window_size, 1)),
        ])
        X = features.reshape(1, _window_size, -1)

        pred_scaled = float(_model.predict(X, verbose=0)[0][0])
        pred_price = float(scaler.inverse_transform([[pred_scaled]])[0][0])

        forecast_prices.append(round(pred_price, 2))
        forecast_dates.append((last_date + pd.DateOffset(weeks=step + 1)).strftime("%Y-%m-%d"))

        working_window = working_window[1:] + [pred_scaled]

    return forecast_dates, forecast_prices


# ------------------------------------------------------------------
# ENDPOINT
# ------------------------------------------------------------------
@router.get("/")
def list_forecastable_items():
    """
    Returns the full list of items the model can forecast — independent of
    which items happen to have complaints filed against them. Used by the
    dashboard's Forecast Explorer dropdown so it isn't limited to whatever's
    in the complaints table.
    """
    if _model is None:
        raise HTTPException(status_code=503, detail=f"Forecast model not loaded: {_load_error}")
    return {"items": _item_list}


@router.get("/{item_name}", response_model=ForecastResponse)
def get_forecast(item_name: str, history_weeks: int = 12):
    if _model is None:
        raise HTTPException(
            status_code=503,
            detail=f"Forecast model not loaded: {_load_error}. "
                    f"Check that model artifacts exist at {ARTIFACTS_DIR}."
        )

    if item_name not in _item_list:
        raise HTTPException(
            status_code=404,
            detail=f"'{item_name}' is not a recognized item. "
                    f"Available items: {', '.join(_item_list)}"
        )

    item_df = _historical_df[_historical_df["item_name"] == item_name].sort_values("date")
    if len(item_df) < _window_size:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough historical data for '{item_name}': "
                    f"need at least {_window_size} weeks, found {len(item_df)}."
        )

    forecast_dates, forecast_prices = _recursive_forecast(item_name, FORECAST_WEEKS_AHEAD)

    last_row = item_df.iloc[-1]
    recent_history = item_df.tail(history_weeks)

    return ForecastResponse(
        item_name=item_name,
        category=str(last_row["category"]),
        unit=str(last_row["unit"]),
        last_known_date=last_row["date"].strftime("%Y-%m-%d"),
        last_known_price=float(last_row["price"]),
        window_size_used=_window_size,
        history=[
            HistoryPoint(date=row["date"].strftime("%Y-%m-%d"), price=float(row["price"]))
            for _, row in recent_history.iterrows()
        ],
        forecast=[
            ForecastPoint(date=d, predicted_price=p)
            for d, p in zip(forecast_dates, forecast_prices)
        ],
        generated_at=datetime.utcnow().isoformat(),
    )