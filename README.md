# csv-doctor

A small command-line tool that profiles a messy CSV and cleans it up. Point it at a file and you get a data-quality report; add a few flags and you get a cleaned CSV back.

I built this as a learning project — mostly to get more comfortable with pandas and to have something I actually reach for when a dataset looks sketchy before I start working with it. It's simple on purpose.

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
- `--fillna` fills every column with the same value; per-column fills (median for numerics, mode for strings) would be nicer.
