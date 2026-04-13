"""
Analytics Service
-----------------
• /analyze  – route to forecasting or statistical summary
• /forecast – time-series forecasting (Prophet / ARIMA)
• /stats    – descriptive statistics
• /summary  – natural-language summary of a dataset
"""

from __future__ import annotations
import sys
import time

sys.path.insert(0, "/app/shared")

import pandas as pd
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import AnalyticsSettings
from models.schemas import AnalyticsRequest, AnalyticsResponse, ForecastResult, HealthResponse
from models.forecaster import run_forecast
from models.summarizer import statistical_summary
from utils.logger import configure_logging, get_logger

settings = AnalyticsSettings()
configure_logging("analytics-service", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="Analytics Service", version="1.0.0")
Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def startup() -> None:
    log.info("Analytics service started")


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalyticsResponse)
async def analyze(req: AnalyticsRequest):
    t0 = time.perf_counter()

    op = req.operation.lower()
    if op == "forecast":
        result = await _handle_forecast(req)
    elif op in ("stats", "summary"):
        result = await _handle_stats(req)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown operation: {op}")

    return AnalyticsResponse(
        operation=op,
        result=result,
        latency_ms=(time.perf_counter() - t0) * 1000,
    )


async def _handle_forecast(req: AnalyticsRequest) -> dict:
    data    = req.params.get("data", [])           # list of {ds, y} dicts
    horizon = req.params.get("horizon", settings.FORECAST_HORIZON)

    if not data:
        raise HTTPException(status_code=422, detail="params.data is required for forecast")

    df     = pd.DataFrame(data)
    result = run_forecast(df, horizon)
    return result.model_dump()


async def _handle_stats(req: AnalyticsRequest) -> dict:
    data = req.params.get("data", [])
    if not data:
        raise HTTPException(status_code=422, detail="params.data is required for stats")

    df = pd.DataFrame(data)
    return statistical_summary(df)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="analytics-service")
