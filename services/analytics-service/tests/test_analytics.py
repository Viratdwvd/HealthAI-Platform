"""
Unit tests – Analytics Service
Run with: pytest tests/ -v
"""

import sys
from datetime import date, timedelta

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

import pandas as pd
import pytest


# ─── Statistical Summarizer ───────────────────────────────────────────────────

def test_summary_shape():
    from models.summarizer import statistical_summary

    df     = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    result = statistical_summary(df)

    assert result["shape"]["rows"]    == 3
    assert result["shape"]["columns"] == 2
    assert "a" in result["columns"]
    assert "b" in result["columns"]


def test_summary_missing_counts():
    from models.summarizer import statistical_summary

    df     = pd.DataFrame({"x": [1, None, 3], "y": [None, None, 1]})
    result = statistical_summary(df)

    assert result["missing"]["x"] == 1
    assert result["missing"]["y"] == 2


def test_summary_numeric_stats_keys():
    from models.summarizer import statistical_summary

    df     = pd.DataFrame({"val": [10.0, 20.0, 30.0, 40.0]})
    result = statistical_summary(df)

    assert "val" in result["numeric_stats"]
    assert "mean" in result["numeric_stats"]["val"]
    assert "std"  in result["numeric_stats"]["val"]


def test_summary_no_numeric_cols():
    from models.summarizer import statistical_summary

    df     = pd.DataFrame({"name": ["Alice", "Bob"]})
    result = statistical_summary(df)

    assert result["numeric_stats"] == {}


def test_summary_sample_rows_count():
    from models.summarizer import statistical_summary

    df     = pd.DataFrame({"n": range(100)})
    result = statistical_summary(df)

    assert len(result["sample_rows"]) == 5


# ─── Forecaster ───────────────────────────────────────────────────────────────

def _make_ts(days: int = 60) -> pd.DataFrame:
    """Synthetic daily time-series."""
    start = date(2024, 1, 1)
    return pd.DataFrame({
        "ds": [(start + timedelta(days=i)).isoformat() for i in range(days)],
        "y":  [100 + i * 0.5 + (i % 7) * 2 for i in range(days)],
    })


def test_forecast_arima_returns_correct_horizon():
    """ARIMA fallback should return exactly `horizon` rows."""
    from models.forecaster import _arima_forecast

    df     = _make_ts(60)
    df["ds"] = pd.to_datetime(df["ds"])
    result = _arima_forecast(df, horizon=14)

    assert len(result.dates)     == 14
    assert len(result.values)    == 14
    assert len(result.lower_ci)  == 14
    assert len(result.upper_ci)  == 14
    assert result.model_used     == "arima"


def test_forecast_arima_ci_ordering():
    """Lower CI should always be ≤ predicted value ≤ upper CI."""
    from models.forecaster import _arima_forecast

    df     = _make_ts(90)
    df["ds"] = pd.to_datetime(df["ds"])
    result = _arima_forecast(df, horizon=7)

    for lo, val, hi in zip(result.lower_ci, result.values, result.upper_ci):
        assert lo <= hi, f"CI inverted: [{lo}, {hi}]"


def test_forecast_raises_on_insufficient_data():
    from models.forecaster import run_forecast

    df = pd.DataFrame({"ds": ["2024-01-01"], "y": [42.0]})
    with pytest.raises(ValueError, match="at least 2"):
        run_forecast(df, horizon=7)


def test_forecast_arima_future_dates():
    """Forecast dates must be strictly after the last training date."""
    from models.forecaster import _arima_forecast

    df     = _make_ts(30)
    df["ds"] = pd.to_datetime(df["ds"])
    result = _arima_forecast(df, horizon=5)

    last_train = df["ds"].max().date()
    first_fc   = date.fromisoformat(result.dates[0])
    assert first_fc > last_train
