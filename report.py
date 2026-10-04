"""Render a profile dict (from profiler.profile_csv) as Markdown."""


def render_report(profile):
    lines = [
        f"# csv-doctor profile: `{profile['path']}`",
        "",
        "## Overview",
        "",
        f"- Rows: {profile['n_rows']:,}",
        f"- Columns: {profile['n_columns']}",
        f"- Duplicate rows: {profile['duplicate_rows']:,}",
        "",
        "## Columns",
        "",
    ]

    for col in profile["columns"]:
        lines.append(f"### {col['name']}")
        lines.append("")
        lines.append(f"- Inferred type: `{col['inferred_type']}`")
        lines.append(f"- Null: {col['null_pct']}%")
        lines.append(f"- Unique values: {col['n_unique']}")

        if col["top_values"]:
            lines.append("- Top values:")
            lines.append("")
            lines.append("| value | count |")
            lines.append("|---|---|")
            for value, count in col["top_values"]:
                lines.append(f"| {value} | {count} |")
            lines.append("")

        outliers = col["outliers"]
        if outliers and outliers["count"]:
            lo, hi = outliers["bounds"]
            lines.append(
                f"- Outliers (IQR): {outliers['count']} "
                f"({outliers['pct']}%), outside [{lo}, {hi}]"
            )

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
