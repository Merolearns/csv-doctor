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
