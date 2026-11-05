"""csv-doctor web UI: upload or paste a CSV, see its data-quality profile,
then clean it in the browser and download the result.

Thin layer over profiler.py / cleaner.py / report.py — the CLI in
csv_doctor.py is untouched and still the same code underneath.
Uploaded data lives in memory only and is never written to disk.
"""

import io
import os
import uuid
from collections import OrderedDict

import pandas as pd
from flask import Flask, Response, abort, render_template, request, send_file

from cleaner import clean
from profiler import profile_csv
from report import render_report

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB uploads

# Resolve relative to this file so the app works from any working directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PATH = os.path.join(BASE_DIR, "samples", "messy.csv")

# file_id -> {"name", "df", "profile", "cleaned_df", "cleaned_profile",
#             "applied"}. Bounded so the process can't grow without limit
# while the dev server runs.
FILE_STORE = OrderedDict()
MAX_STORED_FILES = 10

PREVIEW_ROWS = 10


def store_file(name, df):
    file_id = uuid.uuid4().hex
    FILE_STORE[file_id] = {
        "name": name,
        "df": df,
        "profile": profile_csv(df, path=name),
        "cleaned_df": None,
        "cleaned_profile": None,
        "applied": {},
    }
    while len(FILE_STORE) > MAX_STORED_FILES:
        FILE_STORE.popitem(last=False)
    return file_id


def get_file(file_id):
    entry = FILE_STORE.get(file_id)
    if entry is None:
        abort(404)
    return entry


def read_csv_bytes(data, filename):
    """Parse uploaded/pasted CSV bytes into a DataFrame.

    Raises ValueError with a plain-English message for anything the user
    can fix themselves (empty file, not UTF-8, not parseable, no rows).
    """
    if not data or not data.strip():
        raise ValueError("That file is empty — upload a CSV with some rows in it.")
    try:
        df = pd.read_csv(io.BytesIO(data))
    except pd.errors.EmptyDataError:
        raise ValueError("That file is empty — upload a CSV with some rows in it.")
    except UnicodeDecodeError:
        raise ValueError(
            "That file is not valid UTF-8 text — convert it to UTF-8 and retry."
        )
    except pd.errors.ParserError:
        raise ValueError(
            "Could not parse that as a CSV file — check the quoting and delimiters."
        )
    if df.empty or len(df.columns) == 0:
        raise ValueError("That CSV has no data rows — upload a file with a header and rows.")
    return df


def _cell(value):
    """One preview cell as a string: blanks for missing, no trailing .0."""
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def preview(df):
    """First PREVIEW_ROWS rows of *df*, ready for the template."""
    rows = [[_cell(v) for v in row] for row in df.head(PREVIEW_ROWS).itertuples(index=False, name=None)]
    return {
        "columns": [str(c) for c in df.columns],
        "rows": rows,
        "n_rows": len(df),
        "truncated": len(df) > PREVIEW_ROWS,
    }


def _results(entry, file_id):
    return render_template(
        "results.html",
        filename=entry["name"],
        file_id=file_id,
        profile=entry["profile"],
        preview=preview(entry["df"]),
        cleaned=entry["cleaned_profile"],
        cleaned_preview=preview(entry["cleaned_df"]) if entry["cleaned_df"] is not None else None,
        applied=entry["applied"],
    )


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/profile", methods=["POST"])
def profile():
    if request.form.get("use_sample"):
        filename = "messy.csv"
        try:
            with open(SAMPLE_PATH, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return render_template("index.html", error="The sample file is missing."), 500
    else:
        upload = request.files.get("csv")
        pasted = (request.form.get("pasted") or "").strip()
        if upload is not None and upload.filename:
            filename = upload.filename
            if not filename.lower().endswith(".csv"):
                return render_template(
                    "index.html", error="That file is not a CSV — pick a .csv file."
                ), 400
            data = upload.read()
        elif pasted:
            filename = "pasted.csv"
            data = pasted.encode("utf-8")
        else:
            return render_template(
                "index.html",
                error="Upload a CSV file or paste CSV text — or try the sample file.",
            ), 400

    try:
        df = read_csv_bytes(data, filename)
    except ValueError as exc:
        return render_template("index.html", error=str(exc)), 400

    file_id = store_file(filename, df)
    return _results(FILE_STORE[file_id], file_id)


@app.route("/clean/<file_id>", methods=["POST"])
def clean_file(file_id):
    entry = get_file(file_id)
    fillna = (request.form.get("fillna") or "").strip()
    ops = {
        "strip": bool(request.form.get("strip")),
        "lower": bool(request.form.get("lower")),
        "dropna": bool(request.form.get("dropna")),
        "smart_fill": bool(request.form.get("smart_fill")),
        "fillna": fillna if fillna else None,
        "dedupe": bool(request.form.get("dedupe")),
    }
    cleaned = clean(entry["df"], ops)
    entry["cleaned_df"] = cleaned
    entry["cleaned_profile"] = profile_csv(cleaned, path=f"{entry['name']} (cleaned)")
    entry["applied"] = ops
    return _results(entry, file_id)


@app.route("/download/<file_id>")
def download(file_id):
    entry = get_file(file_id)
    if entry["cleaned_df"] is None:
        abort(404)
    buf = io.StringIO()
    entry["cleaned_df"].to_csv(buf, index=False)
    base = entry["name"].rsplit(".", 1)[0]
    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{base}_clean.csv",
    )


@app.route("/report/<file_id>")
def report(file_id):
    entry = get_file(file_id)
    if entry["cleaned_profile"] is None:
        abort(404)
    base = entry["name"].rsplit(".", 1)[0]
    return Response(
        render_report(entry["cleaned_profile"]),
        mimetype="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={base}_clean_profile.md"
        },
    )


if __name__ == "__main__":
    app.run(debug=True)
