"""Profiling logic for csv-doctor.

load_csv() reads a CSV (comma, semicolon, or tab separated). profile_csv()
returns a plain-dict summary: shape, duplicates, and per-column stats. Dicts on purpose — easy to dump to JSON later or hand to
the report renderer without dragging pandas along.
"""

import os
import warnings
from collections import Counter

import pandas as pd

# Columns with at most this many distinct values get a "top values" breakdown.
LOW_CARDINALITY_CUTOFF = 12

# Rows per chunk when profiling a file path — the whole file is never in
# memory at once, only one chunk plus the per-column counters.
CHUNK_ROWS = 100_000

_BOOL_WORDS = {"true", "false", "t", "f", "yes", "no", "y", "n", "1", "0"}

# Stands in for NaN in row tuples when counting duplicates — NaN != NaN,
# so two identical rows with a missing value would otherwise never match.
_NAN = object()


def load_csv(source):
    """Read a CSV path or file-like object into a DataFrame.

    Read as comma-separated first. Only if that gives one column whose name
    contains ';' or a tab, re-read with delimiter sniffing — sniffing a
    genuinely single-column file directly mis-splits it.
    """
    df = pd.read_csv(source)
    if len(df.columns) == 1 and any(d in str(df.columns[0]) for d in ";\t"):
        if hasattr(source, "seek"):
            source.seek(0)
        df = pd.read_csv(source, sep=None, engine="python")
    return df


def profile_csv(source, top_n=5, path=None):
    """Profile the CSV at *source* and return a summary dict.

    *source* is a file path, or an already-loaded DataFrame — pass the
    frame when you have one, to avoid reading the same file twice
    (e.g. profiling the cleaned frame right after `clean`).
    *path* overrides the reported source, handy when a DataFrame came
    from a known file.
    """
    if isinstance(source, pd.DataFrame):
        df = source
    elif _is_path(source):
        # a file path streams in chunks; file-like objects still go
        # through load_csv() (can't rewind a chunk reader reliably)
        return _profile_csv_chunked(source, top_n, path)
    else:
        df = load_csv(source)
        if path is None:
            path = str(source)
    return {
        "path": path,
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": [_profile_column(df[col], top_n) for col in df.columns],
    }


def _is_path(source):
    return isinstance(source, (str, os.PathLike))


def _sniff_sep(path):
    """Delimiter for a path, using the same rule as load_csv()."""
    head = pd.read_csv(path, nrows=0)
    if len(head.columns) == 1 and any(d in str(head.columns[0]) for d in ";\t"):
        return None  # let the python engine sniff it
    return ","


def _is_nan(value):
    return isinstance(value, float) and value != value


def _profile_csv_chunked(source, top_n, path):
    """Profile a file path in chunks instead of loading it whole.

    Accumulates per-column value counts, null counts, and one hash per
    distinct row, then rebuilds each column's stats from those counts
    through the same _profile_column() as the in-memory path — so a
    chunked profile matches a full-file one. Peak memory is one chunk
    plus the counters, not the whole file. The trade-off is the
    counters: a column where nearly every value is different (like an
    ID column) still keeps one entry per distinct value.
    """
    sep = _sniff_sep(source)
    kwargs = {"chunksize": CHUNK_ROWS}
    if sep is None:
        kwargs.update({"sep": None, "engine": "python"})

    columns = None
    counts, nulls = {}, {}
    n_rows = 0
    seen_rows, duplicates = set(), 0

    for chunk in pd.read_csv(source, **kwargs):
        if columns is None:
            columns = list(chunk.columns)
            for col in columns:
                counts[col] = Counter()
                nulls[col] = 0
        n_rows += len(chunk)
        for row in chunk.itertuples(index=False, name=None):
            key = tuple(_NAN if _is_nan(v) else v for v in row)
            if key in seen_rows:
                duplicates += 1
            else:
                seen_rows.add(key)
            for col, value in zip(columns, row):
                if _is_nan(value):
                    nulls[col] += 1
                else:
                    counts[col][value] += 1

    if columns is None or n_rows == 0:
        # header-only file: no rows to accumulate from — profile the
        # (tiny) frame through the normal path so it matches exactly
        df = load_csv(source)
        if path is None:
            path = str(source)
        return {
            "path": path,
            "n_rows": len(df),
            "n_columns": len(df.columns),
            "duplicate_rows": int(df.duplicated().sum()),
            "columns": [_profile_column(df[col], top_n) for col in df.columns],
        }

    profiled = []
    for col in columns:
        # rebuild one column from its value counts — the nulls were
        # counted separately, so fix up null_pct afterwards
        values = []
        for value, count in counts[col].items():
            values.extend([value] * count)
        column = _profile_column(pd.Series(values, name=col), top_n)
        column["null_pct"] = round(nulls[col] / n_rows * 100, 2)
        profiled.append(column)

    return {
        "path": path if path is not None else str(source),
        "n_rows": n_rows,
        "n_columns": len(columns),
        "duplicate_rows": duplicates,
        "columns": profiled,
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
