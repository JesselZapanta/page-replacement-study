#!/usr/bin/env python3
"""Descriptive summaries of raw run records.

Deliberately no hypothesis tests: README section 6 defers the final model to
adviser/statistician review after pilot data, and requires preserving the
matched/repeated structure. If any input record is demo data, the output is
labeled as sample data and must not be reported as a research finding.
"""

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from common import utc_now


def quantile(values, q):
    """Linear-interpolation percentile; values must be sorted."""
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    low = int(pos)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (pos - low)


def summarize(groups):
    rows = []
    for (algorithm, workload, frames), records in sorted(groups.items()):
        rates = sorted(r["page_fault_rate_percent"] for r in records)
        faults = [r["simulated_page_faults"] for r in records]
        times = [r["algorithm_time_ns"] for r in records]
        rows.append({
            "algorithm": algorithm,
            "workload": workload,
            "frames": frames,
            "n": len(records),
            "fault_rate_mean": statistics.fmean(rates),
            "fault_rate_sd": statistics.stdev(rates) if len(rates) > 1 else 0.0,
            "fault_rate_median": statistics.median(rates),
            "fault_rate_q1": quantile(rates, 0.25),
            "fault_rate_q3": quantile(rates, 0.75),
            "faults_mean": statistics.fmean(faults),
            "faults_sd": statistics.stdev(faults) if len(faults) > 1 else 0.0,
            "time_ns_mean": statistics.fmean(times),
            "time_ns_sd": statistics.stdev(times) if len(times) > 1 else 0.0,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="raw results.jsonl")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    input_path = args.input.resolve()
    if not input_path.is_file():
        parser.error(f"input not found: {input_path}")

    records = []
    skipped = 0
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") != "ok":
            skipped += 1
            continue
        records.append(record)
    if not records:
        parser.error("no successful records to analyze")

    is_demo = any(r.get("is_demo") for r in records)
    groups = defaultdict(list)
    for record in records:
        groups[(record["algorithm"], record["workload"], record["frames"])].append(record)

    rows = summarize(groups)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "descriptive_stats.csv"
    with open(csv_path, "w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_path = output_dir / "descriptive_summary.json"
    summary = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "source": str(input_path),
        "is_demo": is_demo,
        "record_count": len(records),
        "skipped_error_records": skipped,
        "group_count": len(rows),
        "methods": "mean/sd/median/Q1/Q3 only; matched structure preserved; no hypothesis tests",
        "warning": ("DEMO / SAMPLE DATA ONLY - not research findings."
                    if is_demo else
                    "Descriptive only; final statistical model pending adviser approval (README section 6)."),
        "groups": rows,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {csv_path} and {summary_path} "
          f"({len(records)} runs, {len(rows)} groups, {skipped} errors skipped)")
    if is_demo:
        print("DEMO DATA ONLY - do not present these numbers as research findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
