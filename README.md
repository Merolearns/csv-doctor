# csv-doctor

A small command-line tool that profiles a messy CSV and cleans it up. Point it at a file and you get a data-quality report; add a few flags and you get a cleaned CSV back.

I built this as a learning project — mostly to get more comfortable with pandas and to have something I actually reach for when a dataset looks sketchy before I start working with it. It's simple on purpose.

## Web UI

The same profiler and cleaner behind a web page — upload a CSV (or paste CSV text) and see the profile in the browser, then clean it with checkboxes and download the result.

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Upload a `.csv` file, paste CSV text, or click "Try the sample file". The profile page shows row/column/duplicate counts, a preview of the first 10 rows, and one card per column with its inferred type, null %, unique count, top values, and any IQR outliers. The cleaning form has checkboxes for strip, lowercase headers, smart fill, drop rows with missing values, and dedupe, plus a fill-missing-values field. After cleaning you get before/after row counts, a preview of the cleaned data, and buttons to download the cleaned CSV and a markdown profile report of it. Uploaded data stays in memory only — nothing is written to disk.

The bundled sample (`samples/messy.csv`) is 10 rows of customer data — names, ages, cities, and scores — with the usual mess: stray spaces in names and cities, two missing ages, one duplicated row, and a score of 999.0 that stands out from the rest. The profile shows 10 rows, 4 columns, 1 duplicate row, Age at 20% null, City with 3 unique values (" Irvine" and "Irvine" count separately until the spaces are stripped), and one IQR outlier on Score.

## Install

```bash
pip install -r requirements.txt
```

## Usage

Profile a file — prints a markdown report to stdout:

```bash
python csv_doctor.py profile messy.csv --out profile.md
```

Clean a file:

```bash
python csv_doctor.py clean messy.csv --out clean.csv --strip --lower --dropna --dedupe --report clean-profile.md
```

Cleaning flags:

| Flag | What it does |
|---|---|
| `--strip` | Strip leading/trailing whitespace from text values |
| `--lower` | Lowercase (and trim) column names |
| `--dropna` | Drop rows with any missing value |
| `--fillna VALUE` | Fill missing values with VALUE (parsed as a number when possible) |
| `--smart-fill` | Fill each column from its own data: median for numbers, most common value for text |
| `--dedupe` | Drop duplicate rows |
| `--report FILE` | Also write a profile report of the cleaned file |

## Example

Given `messy.csv`:

```csv
Name,Age,City
 Alice ,30, Irvine
Bob,,Newport
 Alice ,30, Irvine
```

Running the profile:

```bash
$ python csv_doctor.py profile messy.csv
```

```markdown
# csv-doctor profile: `messy.csv`

## Overview

- Rows: 3
- Columns: 3
- Duplicate rows: 1

## Columns

### Name

- Inferred type: `string`
- Null: 0.0%
- Unique values: 2
- Top values:

| value | count |
|---|---|
|  Alice  | 2 |
| Bob | 1 |

...
```

And cleaning it:

```bash
$ python csv_doctor.py clean messy.csv --out clean.csv --strip --lower --dropna --dedupe
wrote clean.csv: 1 rows x 3 cols
```

## Running the tests

```bash
pytest
```

## Limitations

- The whole file is read into memory, so very large CSVs will be slow or won't fit. Chunked reading is on the TODO list.
- Type inference is heuristic — a column of `1`s and `0`s is guessed as bool, and dates are whatever `pandas.to_datetime` accepts. Good enough for a first pass, not a validator.
- `--fillna` fills every column with the same value; `--smart-fill` fills each column from its own data instead (median for numbers, mode for text).
