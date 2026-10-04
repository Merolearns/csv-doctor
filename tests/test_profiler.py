"""Tests for profiler.py — one small inline CSV via the tmp_path fixture."""

import pandas as pd
import pytest

from profiler import profile_csv, infer_type

SAMPLE = """name,age,city,score,active,joined
Alice,30,Irvine,95.5,yes,2024-01-15
Bob,,Irvine,80.0,no,2024-02-01
Carol,25,Newport,9999.0,yes,2024-01-20
Dave,30,Irvine,88.0,yes,2024-03-10
Bob,,Irvine,80.0,no,2024-02-01
"""


@pytest.fixture
def sample_csv(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(SAMPLE)
    return path


def _col(profile, name):
    return next(c for c in profile["columns"] if c["name"] == name)


def test_shape_and_duplicates(sample_csv):
    p = profile_csv(sample_csv)
    assert p["n_rows"] == 5
    assert p["n_columns"] == 6
    assert p["duplicate_rows"] == 1


def test_null_pct(sample_csv):
    assert _col(profile_csv(sample_csv), "age")["null_pct"] == 40.0


def test_inferred_types(sample_csv):
    got = {c["name"]: c["inferred_type"] for c in profile_csv(sample_csv)["columns"]}
    assert got == {
        "name": "string",
        "age": "int",
        "city": "string",
        "score": "float",
        "active": "bool",
        "joined": "date",
    }


def test_top_values_low_cardinality(sample_csv):
    city = _col(profile_csv(sample_csv), "city")
    assert city["n_unique"] == 2
    assert city["top_values"][0] == ("Irvine", 4)


def test_top_values_skipped_for_high_cardinality(tmp_path):
    path = tmp_path / "wide.csv"
    path.write_text("id\n" + "\n".join(str(i) for i in range(30)))
    col = profile_csv(path)["columns"][0]
    assert col["top_values"] is None


def test_outliers_iqr(sample_csv):
    score = _col(profile_csv(sample_csv), "score")
    assert score["outliers"]["count"] == 1
    assert score["outliers"]["pct"] == 20.0


def test_outliers_none_for_non_numeric(sample_csv):
    assert _col(profile_csv(sample_csv), "name")["outliers"] is None


def test_infer_type_empty_column():
    assert infer_type(pd.Series([None, None], dtype=object)) == "empty"
