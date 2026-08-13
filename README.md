# PriceGuard

**PriceGuard** is an AI-powered market price transparency system for Pakistan. Citizens report suspected overpricing and short-weighing by submitting a receipt photo, a price, and their location. Each report is automatically checked for authenticity (GPS geo-fencing, OpenCV receipt validation, OCR price cross-checking) before being routed to administrators for review. A predictive analytics module forecasts near-term commodity prices and flags reports that deviate sharply from expected trends — a signal consistent with hoarding-driven price hikes.

Built as a Final Year Project.

## Features

- **Citizen mobile app** — submit reports with a receipt photo, GPS-verified location, and support for fractional purchases and short-weight complaints
- **Automated fraud pipeline** — GPS geo-fencing, OpenCV-based receipt authenticity checks, OCR price verification, submission velocity tracking (anti-spam)
- **Admin dashboard** — review and action reports, geospatial complaint map, LSTM-based price forecasting, automated hoarding alerts
- **Predictive analytics** — LSTM model trained across all tracked commodities, forecasting near-term prices and flagging abnormal deviations

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL (hosted on Neon) |
| Admin Dashboard | Streamlit |
| Predictive Analytics | TensorFlow/Keras (LSTM), scikit-learn |
| Mobile App | React Native (Expo) |
| Auth | JWT (python-jose), bcrypt |
| Computer Vision / OCR | OpenCV, Tesseract |

## Project Structure

```
PriceGuard/
├── backend/            # FastAPI backend
├── admin_dashboard/    # Streamlit admin dashboard
├── ai_engine/          # LSTM training pipeline & model artifacts
├── mobile_app/         # React Native (Expo) mobile app
└── docs/
```

## Setup — Backend

**Prerequisites:** Python 3.11+, a PostgreSQL database (this project uses [Neon](https://neon.tech)), Tesseract OCR installed locally.

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your real values:

```powershell
copy .env.example .env
```

Required environment variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `EMAIL_SENDER` | Gmail address used to send OTP verification emails |
| `EMAIL_PASSWORD` | Gmail [App Password](https://support.google.com/accounts/answer/185833) (not your regular password) |
| `TESSERACT_PATH` | Full path to your local Tesseract OCR executable |

Run the backend:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`.

**Run tests:**

```powershell
pip install pytest
pytest tests/ -v
```

## Setup — Admin Dashboard

```powershell
cd admin_dashboard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Requires the backend to be running — set the Backend URL on the login screen (defaults to `http://localhost:8000`).

## Setup — Mobile App

```powershell
cd mobile_app
npm install
npx expo start
```

Update `BASE_URL` in `src/services/api.js` to match your backend's local network address (not `localhost`, since the app runs on a physical device/emulator). Scan the QR code with Expo Go, or run on an emulator.

## Predictive Analytics — Training the Model

```powershell
cd ai_engine/predictive_analysis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python data_generator.py     # generates historical_prices.csv
python train_model.py        # trains the LSTM, saves model artifacts
python evaluate_model.py     # prints RMSE/MAE/MAPE per item
```

Copy the resulting model files (`priceguard_lstm.keras`, `item_scalers.joblib`, `model_config.joblib`, `historical_prices.csv`) into `backend/app/ml_artifacts/` for the backend's forecast endpoint to load them.

## License

Academic project — Final Year Project submission.