"""Cleaning operations for csv-doctor.

Each op is a small function on a DataFrame. clean() chains the requested ones
in a fixed order: strip -> lower -> smart_fill -> dropna -> fillna -> dedupe.
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
    # smart_fill runs before dropna so filled rows survive it. fillna stays
    # after dropna for backward compatibility — it only fills rows that
    # dropna would have removed anyway, i.e. it has an effect when dropna
    # was skipped or couldn't fill a column (e.g. all-missing).
    if ops.get("smart_fill"):
        df = smart_fill(df)
    if ops.get("dropna"):
        df = df.dropna()
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
    """Lowercase column names (and trim stray spaces while at it).

    Headers that collide after lowering ("Name" vs "name") get a numeric
    suffix so every column stays addressable — pandas allows duplicate
    labels, but they make df["name"] ambiguous.
    """
    seen = {}
    renamed = []
    for c in df.columns:
        name = str(c).strip().lower()
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        renamed.append(name)
    df.columns = renamed
    return df


def smart_fill(df):
    """Fill missing values from each column's own data.

    Numeric columns get their median; everything else gets its most common
    value. Columns that are entirely missing are left alone — there's no
    sensible value to fill them with.
    """
    df = df.copy()
    for col in df.columns:
        s = df[col]
        if s.isna().all():
            continue  # nothing to fill from — leave it missing
        if pd.api.types.is_numeric_dtype(s.dtype) and not pd.api.types.is_bool_dtype(
            s.dtype
        ):
            fill = s.median()
        else:
            modes = s.mode(dropna=True)
            fill = modes.iloc[0] if not modes.empty else None
        if pd.isna(fill):
            continue
        df[col] = s.fillna(fill)
    return df


def _coerce(value):
    """Turn a CLI string into int/float when it looks like one, else keep it."""
    for cast in (int, float):
        try:
            return cast(value)
        except (ValueError, TypeError):
            continue
    return value
