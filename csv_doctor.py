#!/usr/bin/env python3
"""csv-doctor: profile messy CSVs and clean them up from the command line."""

import argparse
import sys

import pandas as pd

from profiler import profile_csv
from cleaner import clean
from report import render_report


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="csv-doctor",
        description="Profile a CSV file, or clean one up and write the result.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_profile = sub.add_parser("profile", help="Print a data-quality profile of FILE.")
    p_profile.add_argument("file", help="CSV file to profile")
    p_profile.add_argument(
        "--out", metavar="REPORT.md", help="Also write the markdown report to this file"
    )

    p_clean = sub.add_parser("clean", help="Clean FILE and write the result.")
    p_clean.add_argument("file", help="CSV file to clean")
    p_clean.add_argument(
        "--out", required=True, metavar="CLEAN.csv", help="Where to write the cleaned CSV"
    )
    p_clean.add_argument("--dropna", action="store_true", help="Drop rows with any missing value")
    p_clean.add_argument(
        "--fillna",
        metavar="VALUE",
        default=None,
        help="Fill missing values with VALUE (parsed as a number when possible)",
    )
    p_clean.add_argument("--dedupe", action="store_true", help="Drop duplicate rows")
    p_clean.add_argument(
        "--strip", action="store_true", help="Strip leading/trailing whitespace from text values"
    )
    p_clean.add_argument(
        "--lower", action="store_true", help="Lowercase (and trim) column names"
    )
    p_clean.add_argument(
        "--report", metavar="REPORT.md", help="Also write a profile report of the cleaned file"
    )

    args = parser.parse_args(argv)

    try:
        df = pd.read_csv(args.file)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 1
    except pd.errors.EmptyDataError:
        print(f"error: file is empty: {args.file}", file=sys.stderr)
        return 1

    if args.command == "profile":
        report = render_report(profile_csv(args.file))
        print(report, end="")
        if args.out:
            with open(args.out, "w") as f:
                f.write(report)
            print(f"wrote {args.out}", file=sys.stderr)
        return 0

    # clean
    ops = {
        "strip": args.strip,
        "lower": args.lower,
        "dropna": args.dropna,
        "fillna": args.fillna,
        "dedupe": args.dedupe,
    }
    cleaned = clean(df, ops)
    cleaned.to_csv(args.out, index=False)
    print(
        f"wrote {args.out}: {len(cleaned)} rows x {len(cleaned.columns)} cols",
        file=sys.stderr,
    )

    if args.report:
        report = render_report(profile_csv(args.out))
        with open(args.report, "w") as f:
            f.write(report)
        print(f"wrote {args.report}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
