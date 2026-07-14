"""
pipeline.py
------------
Most Visited Pages Finder — end-to-end pipeline.

Implements the six-stage pipeline described in the project proposal:

  1. Data Collection      -> read the raw access log file
  2. Data Preprocessing    -> regex-parse every line (log_parser.py)
  3. Data Cleaning         -> drop bots, duplicates, non-2xx responses
  4. Structured Storage    -> load cleaned records into a Pandas DataFrame
  5. Frequency Analysis    -> count visits per URL (collections.Counter)
  6. Ranking & Reporting   -> sort, take Top-N, save CSV + bar chart

Usage:
    python src/pipeline.py --log data/sample_access.log --top 10
"""

import argparse
import os
from collections import Counter

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
import seaborn as sns

from log_parser import parse_log_file


def clean_records(records):
    """
    Stage 3: Data Cleaning.

    Removes:
      - bot / crawler traffic (flagged during parsing)
      - duplicate hits (identical host + timestamp + url)
      - non-2xx HTTP responses (errors, redirects, not-modified)
    """
    before = len(records)

    # Drop bots
    records = [r for r in records if not r["is_bot"]]
    after_bots = len(records)

    # Drop duplicates (same client, same second, same resource)
    seen = set()
    deduped = []
    for r in records:
        key = (r["host"], r["timestamp"], r["url"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    after_dupes = len(deduped)

    # Keep only successful (2xx) responses
    cleaned = [r for r in deduped if 200 <= r["status"] < 300]
    after_status = len(cleaned)

    stats = {
        "raw_parsed_records": before,
        "after_removing_bots": after_bots,
        "after_removing_duplicates": after_dupes,
        "after_keeping_2xx_only": after_status,
    }
    return cleaned, stats


def to_dataframe(records):
    """Stage 4: Structured Storage — load cleaned records into a DataFrame."""
    df = pd.DataFrame(records)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], format="%d/%b/%Y:%H:%M:%S %z", errors="coerce"
        )
    return df


def frequency_analysis(df):
    """Stage 5: Frequency Analysis — count visits per URL."""
    counter = Counter(df["url"])
    return counter


def rank_and_report(counter, top_n, output_dir):
    """Stage 6: Ranking & Reporting — Top-N table, CSV, and bar chart."""
    os.makedirs(output_dir, exist_ok=True)

    ranked = counter.most_common(top_n)
    report_df = pd.DataFrame(ranked, columns=["Page URL", "Visits"])
    report_df.insert(0, "Rank", range(1, len(report_df) + 1))

    csv_path = os.path.join(output_dir, "top_pages.csv")
    report_df.to_csv(csv_path, index=False)

    # Visualisation
    sns.set_style("whitegrid")
    plt.figure(figsize=(10, 6))
    ax = sns.barplot(
        data=report_df,
        x="Visits",
        y="Page URL",
        hue="Page URL",
        palette="viridis",
        legend=False,
    )
    ax.set_title(f"Top {len(report_df)} Most Visited Pages", fontsize=14, weight="bold")
    ax.set_xlabel("Visit Count")
    ax.set_ylabel("Page URL")
    for i, v in enumerate(report_df["Visits"]):
        ax.text(v, i, f" {v:,}", va="center", fontsize=9)
    plt.tight_layout()

    chart_path = os.path.join(output_dir, "top_pages_chart.png")
    plt.savefig(chart_path, dpi=150)
    plt.close()

    return report_df, csv_path, chart_path


def run_pipeline(log_path, top_n=10, output_dir="output"):
    print(f"[1/6] Data Collection      : reading {log_path}")

    print("[2/6] Data Preprocessing   : parsing log lines with regex")
    records, n_malformed = parse_log_file(log_path)
    print(f"      parsed {len(records)} records, discarded {n_malformed} malformed lines")

    print("[3/6] Data Cleaning        : removing bots, duplicates, non-2xx responses")
    cleaned, stats = clean_records(records)
    for k, v in stats.items():
        print(f"      {k:28s}: {v}")

    print("[4/6] Structured Storage   : loading into a Pandas DataFrame")
    df = to_dataframe(cleaned)
    print(f"      DataFrame shape: {df.shape}")

    print("[5/6] Frequency Analysis   : counting visits per URL")
    counter = frequency_analysis(df)
    print(f"      {len(counter)} unique pages found")

    print(f"[6/6] Ranking & Reporting  : top {top_n} pages -> CSV + bar chart")
    report_df, csv_path, chart_path = rank_and_report(counter, top_n, output_dir)

    print("\n=== TOP PAGES ===")
    print(report_df.to_string(index=False))
    print(f"\nSaved report -> {csv_path}")
    print(f"Saved chart  -> {chart_path}")

    return report_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Most Visited Pages Finder")
    parser.add_argument("--log", default="data/sample_access.log", help="Path to access log file")
    parser.add_argument("--top", type=int, default=10, help="Number of top pages to report")
    parser.add_argument("--output", default="output", help="Output directory for report/chart")
    args = parser.parse_args()

    run_pipeline(args.log, top_n=args.top, output_dir=args.output)
