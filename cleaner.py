"""Cleaning operations for csv-doctor.

Each op is a small function on a DataFrame. clean() chains the requested ones
in a fixed order: strip -> lower -> dropna -> fillna -> dedupe.
"""

import pandas as pd


def clean(df, ops):
    """Apply cleaning ops to *df* and return a new DataFrame.

    *ops* is a dict, e.g.
        {"strip": True, "lower": True, "dropna": True, "fillna": "0", "dedupe": True}
    Missing keys are treated as off. fillna=None means don't fill.
    """
    df = df.copy()

    if ops.get("strip"):
        df = strip_whitespace(df)
    if ops.get("lower"):
        df = lowercase_columns(df)
    if ops.get("dropna"):
        df = df.dropna()
    # FIXME: fillna runs after dropna, so it only has an effect when the user
    # skipped --dropna. That's the documented behavior, but a per-column
    # fill (median for numerics, mode for strings) would be friendlier.
    if ops.get("fillna") is not None:
        df = df.fillna(_coerce(ops["fillna"]))
    if ops.get("dedupe"):
        df = df.drop_duplicates()

    return df


def strip_whitespace(df):
    """Strip leading/trailing whitespace from text values in place-ish."""
    for col in df.columns:
        if str(df[col].dtype) in ("object", "string"):
            df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def lowercase_columns(df):
    """Lowercase column names (and trim stray spaces while at it)."""
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _coerce(value):
    """Turn a CLI string into int/float when it looks like one, else keep it."""
    for cast in (int, float):
        try:
            return cast(value)
        except (ValueError, TypeError):
            continue
    return value
