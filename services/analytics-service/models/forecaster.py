"""
Time-series forecaster.
Primary:  Prophet (facebook/prophet)
Fallback: statsmodels ARIMA
"""

from __future__ import annotations
from typing import List

import pandas as pd

from models.schemas import ForecastResult


def run_forecast(df: pd.DataFrame, horizon: int = 30) -> ForecastResult:
    """
    Expects a DataFrame with columns ['ds', 'y']:
      ds – date strings (ISO 8601)
      y  – numeric target values

    Returns a ForecastResult with dates, predicted values, and 80% CI.
    """
    df = df.copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"]  = pd.to_numeric(df["y"], errors="coerce")
    df.dropna(subset=["ds", "y"], inplace=True)

    if len(df) < 2:
        raise ValueError("Need at least 2 data points to forecast")

    try:
        return _prophet_forecast(df, horizon)
    except Exception:
        return _arima_forecast(df, horizon)


def _prophet_forecast(df: pd.DataFrame, horizon: int) -> ForecastResult:
    from prophet import Prophet

    model = Prophet(interval_width=0.8, yearly_seasonality="auto", weekly_seasonality="auto")
    model.fit(df)

    future = model.make_future_dataframe(periods=horizon)
    fc     = model.predict(future).tail(horizon)

    return ForecastResult(
        dates=[str(d.date()) for d in fc["ds"]],
        values=fc["yhat"].round(4).tolist(),
        lower_ci=fc["yhat_lower"].round(4).tolist(),
        upper_ci=fc["yhat_upper"].round(4).tolist(),
        model_used="prophet",
    )


def _arima_forecast(df: pd.DataFrame, horizon: int) -> ForecastResult:
    from statsmodels.tsa.arima.model import ARIMA
    import numpy as np

    model  = ARIMA(df["y"].values, order=(1, 1, 1))
    fitted = model.fit()
    fc_res = fitted.get_forecast(steps=horizon)
    mean   = fc_res.predicted_mean
    ci     = fc_res.conf_int(alpha=0.20)

    last_date = df["ds"].max()
    dates = [
        str((last_date + pd.Timedelta(days=i + 1)).date())
        for i in range(horizon)
    ]

    return ForecastResult(
        dates=dates,
        values=mean.round(4).tolist(),
        lower_ci=ci.iloc[:, 0].round(4).tolist(),
        upper_ci=ci.iloc[:, 1].round(4).tolist(),
        model_used="arima",
    )
