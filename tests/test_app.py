"""Smoke tests for app.py — Flask test client, no server needed."""

import io
import os
import re

import pytest

from app import app

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "samples", "messy.csv")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _sample_bytes():
    with open(SAMPLE_PATH, "rb") as f:
        return f.read()


def _profile_sample(client):
    """Upload the sample CSV and return (response, file_id)."""
    resp = client.post(
        "/profile",
        data={"csv": (io.BytesIO(_sample_bytes()), "messy.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    match = re.search(r"/clean/([0-9a-f]+)", resp.get_data(as_text=True))
    assert match, "results page should link the clean form"
    return resp, match.group(1)


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"csv-doctor" in resp.data
    assert b"Try the sample file" in resp.data


def test_profile_upload_shows_real_numbers(client):
    resp, _ = _profile_sample(client)
    # 10 rows, 4 columns, 1 duplicate row — straight from the sample file
    assert b'<span class="stat-value">10</span>' in resp.data
    assert b"Duplicate rows" in resp.data
    assert b"Name" in resp.data
    assert b"Age" in resp.data
    assert b"999" in resp.data  # the score outlier shows up in the preview


def test_profile_sample_button(client):
    resp = client.post("/profile", data={"use_sample": "1"})
    assert resp.status_code == 200
    assert b"messy.csv" in resp.data
    assert b"Duplicate rows" in resp.data


def test_profile_pasted_text(client):
    resp = client.post("/profile", data={"pasted": "a,b\n1,2\n3,4\n"})
    assert resp.status_code == 200
    assert b"Rows" in resp.data


def test_profile_empty_file_returns_400(client):
    resp = client.post(
        "/profile",
        data={"csv": (io.BytesIO(b""), "empty.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert b"empty" in resp.data.lower()


def test_profile_garbage_returns_400(client):
    resp = client.post(
        "/profile",
        data={"csv": (io.BytesIO(b"\xff\xfe\x00\x01not a csv"), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert b"error" in resp.data.lower() or b"not valid" in resp.data.lower()


def test_profile_non_csv_extension_returns_400(client):
    resp = client.post(
        "/profile",
        data={"csv": (io.BytesIO(b"a,b\n1,2\n"), "data.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert b"not a CSV" in resp.data


def test_clean_flow_and_downloads(client):
    _, file_id = _profile_sample(client)
    resp = client.post(
        f"/clean/{file_id}",
        data={"strip": "on", "lower": "on", "dedupe": "on"},
    )
    assert resp.status_code == 200
    assert b"Cleaned result" in resp.data
    # 10 rows in, 9 out: strip makes the two Alice rows identical, dedupe drops one
    assert b"10 rows" in resp.data
    assert b"9 rows" in resp.data
    assert b"<th>name</th>" in resp.data  # headers lowercased
    assert b"<td>Alice</td>" in resp.data  # stray spaces stripped

    resp = client.get(f"/download/{file_id}")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"name,age,city,score" in resp.data
    assert b"Alice,30.0,Irvine,88.5" in resp.data  # age stays float — it had missing values

    resp = client.get(f"/report/{file_id}")
    assert resp.status_code == 200
    assert b"csv-doctor profile" in resp.data


def test_download_before_clean_returns_404(client):
    _, file_id = _profile_sample(client)
    assert client.get(f"/download/{file_id}").status_code == 404
    assert client.get(f"/report/{file_id}").status_code == 404


def test_clean_unknown_file_returns_404(client):
    resp = client.post("/clean/nope", data={})
    assert resp.status_code == 404
