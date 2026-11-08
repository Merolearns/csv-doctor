"""Tests for the csv-doctor CLI's file-reading errors — run with `pytest`."""

import csv_doctor


def test_non_utf8_file_is_clean_error(tmp_path, capsys):
    # latin-1 bytes (é as 0xe9) are not valid UTF-8 — used to die with a
    # bare UnicodeDecodeError traceback
    path = tmp_path / "latin.csv"
    path.write_bytes(b"name,city\ncaf\xe9,paris\n")
    assert csv_doctor.main(["profile", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err


def test_malformed_csv_is_clean_error(tmp_path, capsys):
    # a row with more fields than the header trips the C parser
    path = tmp_path / "bad.csv"
    path.write_text("a,b\n1,2\n3,4,5\n")
    assert csv_doctor.main(["profile", str(path)]) == 1
    err = capsys.readouterr().err
    assert "couldn't parse" in err


def _assert_clean_error(capsys, expected):
    err = capsys.readouterr().err
    assert err.startswith(f"error: {expected}")
    assert "Traceback" not in err


def test_clean_out_into_missing_directory_is_clean_error(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n")
    out = tmp_path / "missing" / "out.csv"
    assert csv_doctor.main(["clean", str(src), "--out", str(out)]) == 1
    _assert_clean_error(capsys, f"can't write {out}: ")


def test_profile_out_into_missing_directory_is_clean_error(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n")
    out = tmp_path / "missing" / "report.md"
    assert csv_doctor.main(["profile", str(src), "--out", str(out)]) == 1
    _assert_clean_error(capsys, f"can't write {out}: ")


def test_profiling_a_directory_is_clean_error(tmp_path, capsys):
    assert csv_doctor.main(["profile", str(tmp_path)]) == 1
    _assert_clean_error(capsys, f"can't read {tmp_path}: ")
