"""Profiling logic for csv-doctor.

profile_csv() reads a CSV and returns a plain-dict summary: shape, duplicates,
and per-column stats. Dicts on purpose — easy to dump to JSON later or hand to
the report renderer without dragging pandas along.
"""

import warnings

import pandas as pd

# Columns with at most this many distinct values get a "top values" breakdown.
LOW_CARDINALITY_CUTOFF = 12

_BOOL_WORDS = {"true", "false", "t", "f", "yes", "no", "y", "n", "1", "0"}


def profile_csv(path, top_n=5):
    """Profile the CSV at *path* and return a summary dict."""
    # TODO: read in chunks for files that don't fit in memory
    df = pd.read_csv(path)
    return {
        "path": str(path),
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": [_profile_column(df[col], top_n) for col in df.columns],
    }


def _profile_column(series, top_n):
    return {
        "name": series.name,
        "inferred_type": infer_type(series),
        "null_pct": round(float(series.isna().mean()) * 100, 2),
        "n_unique": int(series.nunique(dropna=True)),
        "top_values": _top_values(series, top_n),
        "outliers": _outlier_summary(series),
    }


def infer_type(series):
    """Best-effort type guess from the non-null values.

    Returns one of: bool, int, float, date, string, empty.
    """
    s = series.dropna()
    if s.empty:
        return "empty"

    # pandas reads int columns with missing values as float64 ("30" -> 30.0),
    # so check numeric dtypes before falling back to string parsing.
    if pd.api.types.is_bool_dtype(s.dtype):
        return "bool"
    if pd.api.types.is_integer_dtype(s.dtype):
        return "int"
    if pd.api.types.is_float_dtype(s.dtype):
        return "int" if (s % 1 == 0).all() else "float"
    if pd.api.types.is_datetime64_any_dtype(s.dtype):
        return "date"

    as_str = s.astype(str).str.strip()

    if as_str.str.lower().isin(_BOOL_WORDS).all():
        return "bool"

    # int before float — "30" is an int, "30.5" isn't.
    try:
        as_str.astype("int64")
        return "int"
    except (ValueError, TypeError):
        pass

    try:
        as_str.astype("float64")
        return "float"
    except (ValueError, TypeError):
        pass

    # dateutil's format-guessing is chatty; keep it quiet during the probe.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        try:
            pd.to_datetime(as_str, errors="raise")
            return "date"
        except (ValueError, TypeError):
            pass

    return "string"


def _top_values(series, n):
    """Most common values, but only for low-cardinality columns."""
    if series.nunique(dropna=True) > LOW_CARDINALITY_CUTOFF:
        return None
    counts = series.value_counts(dropna=True).head(n)
    return [(str(value), int(count)) for value, count in counts.items()]


def _outlier_summary(series):
    """IQR outlier count for numeric columns; None for everything else."""
    if infer_type(series) not in ("int", "float"):
        return None

    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 4:
        return {"count": 0, "pct": 0.0, "bounds": None}  # not enough data for IQR

    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return {"count": 0, "pct": 0.0, "bounds": None}

    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    flagged = ((s < lower) | (s > upper)).sum()
    return {
        "count": int(flagged),
        "pct": round(float(flagged) / len(s) * 100, 2),
        "bounds": (round(float(lower), 4), round(float(upper), 4)),
    }
