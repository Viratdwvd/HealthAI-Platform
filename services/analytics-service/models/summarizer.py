"""
Statistical summary generator.
Returns descriptive stats for a DataFrame.
"""

from __future__ import annotations
from typing import Any, Dict

import pandas as pd


def statistical_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns a dict with:
      - shape: (rows, cols)
      - columns: list of column names
      - numeric_stats: per-column describe() output
      - missing: count of nulls per column
      - dtypes: column data types
    """
    numeric_df = df.select_dtypes(include="number")
    desc = numeric_df.describe().round(4).to_dict() if not numeric_df.empty else {}

    return {
        "shape":         {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns":       df.columns.tolist(),
        "dtypes":        {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing":       df.isnull().sum().to_dict(),
        "numeric_stats": desc,
        "sample_rows":   df.head(5).fillna("").to_dict(orient="records"),
    }
