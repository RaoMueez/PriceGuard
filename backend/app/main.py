from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import users, admin

app = FastAPI(title="PriceGuard API", version="1.0.0")

# --- CORS Middleware ---
# Allows the React Native app and Streamlit dashboard (running on different origins) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict this to specific origins before production deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(users.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"message": "PriceGuard API is running."}