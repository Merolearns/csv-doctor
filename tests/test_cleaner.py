"""Tests for cleaner.py — inline CSV parsed through StringIO."""

import io

import pandas as pd
import pytest

from cleaner import clean

SAMPLE = """Name,Age,City
 Alice ,30, Irvine
Bob,,Newport
 Alice ,30, Irvine
"""


@pytest.fixture
def df():
    return pd.read_csv(io.StringIO(SAMPLE))


def test_strip_and_lower(df):
    out = clean(df, {"strip": True, "lower": True})
    assert list(out.columns) == ["name", "age", "city"]
    assert out["name"].tolist() == ["Alice", "Bob", "Alice"]
    assert out["city"].tolist() == ["Irvine", "Newport", "Irvine"]


def test_dropna(df):
    out = clean(df, {"dropna": True})
    assert len(out) == 2
    assert out["Age"].notna().all()


def test_fillna_numeric_string_becomes_number(df):
    out = clean(df, {"fillna": "0"})
    assert out["Age"].isna().sum() == 0
    assert out["Age"].iloc[1] == 0


def test_fillna_non_numeric_stays_string(df):
    out = clean(df, {"fillna": "unknown"})
    assert out["Age"].iloc[1] == "unknown"


def test_dedupe(df):
    out = clean(df, {"dedupe": True})
    assert len(out) == 2


def test_full_pipeline(df):
    out = clean(
        df,
        {"strip": True, "lower": True, "dropna": True, "fillna": None, "dedupe": True},
    )
    assert len(out) == 1
    assert list(out.columns) == ["name", "age", "city"]
    assert out.iloc[0].tolist() == ["Alice", 30.0, "Irvine"]


def test_no_ops_leaves_frame_unchanged(df):
    pd.testing.assert_frame_equal(clean(df, {}), df)
