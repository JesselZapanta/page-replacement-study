#!/usr/bin/env python3
"""Known-answer correctness tests for the FIFO, LRU and Clock simulators.

Expected counts are derived by hand from small traces and cross-checked with an
independent reference model. All three algorithms must agree on hits/faults
except in the cases that intentionally distinguish their policies.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ALGORITHMS = ("fifo", "lru", "clock")

# name -> (trace lines, frames, {algorithm: (hits, simulated_page_faults)})
CASES = {
    # No references: 0 hits, 0 faults, rate defined as 0.
    "empty_trace": ([], 3, {a: (0, 0) for a in ALGORITHMS}),
    # First reference faults; the other three are hits.
    "one_unique_page_repeated": (["1", "1", "1", "1"], 3,
                                 {a: (3, 1) for a in ALGORITHMS}),
    # Three frames, four distinct pages: every reference faults.
    "more_pages_than_frames": (["1", "2", "3", "4", "1", "2", "3", "4"], 3,
                               {a: (0, 8) for a in ALGORITHMS}),
    # The reuse of 1 makes LRU keep it; FIFO still evicts the oldest resident.
    "fifo_vs_lru": (["1", "2", "3", "1", "4", "1"], 3,
                    {"fifo": (1, 5), "lru": (2, 4), "clock": (1, 5)}),
    # Clock's reference bit gives page 1 a second chance: fewer faults than FIFO.
    "clock_second_chance": (["0", "1", "2", "3", "1", "0", "1"], 3,
                            {"fifo": (1, 6), "lru": (2, 5), "clock": (2, 5)}),
    # A single frame means no hits once a different page is referenced.
    "frame_capacity_one": (["1", "2", "1", "3", "1"], 1,
                           {a: (0, 5) for a in ALGORITHMS}),
    # Consecutive duplicates count as hits, not as new faults.
    "duplicate_pages": (["7", "7", "7"], 3, {a: (2, 1) for a in ALGORITHMS}),
    # Zero and non-sequential page ids are valid; comments and blanks are ignored.
    "mixed_ids_and_comments": (["# sample", "0", "5", "", "0", "5", "9"], 2,
                               {a: (2, 3) for a in ALGORITHMS}),
}

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
        print(f"  FAIL: {message}")


def run_simulator(simulator, trace, frames, algorithm, extra=None):
    cmd = [str(simulator), "--algorithm", algorithm, "--frames", str(frames),
           "--trace", str(trace)]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True)


def reference_count(lines):
    """Blank lines and # comments are not references."""
    return sum(1 for line in lines if line.strip() and not line.lstrip().startswith("#"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator", required=True, type=Path)
    args = parser.parse_args()
    simulator = args.simulator.resolve()
    if not simulator.is_file():
        parser.error(f"simulator not found: {simulator}")

    with tempfile.TemporaryDirectory(prefix="page-replacement-tests-") as tmp:
        tmpdir = Path(tmp)
        for name, (lines, frames, expected) in CASES.items():
            trace = tmpdir / f"{name}.trace"
            trace.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            n_refs = reference_count(lines)
            print(f"[case] {name} (frames={frames}, references={n_refs})")
            for algorithm in ALGORITHMS:
                proc = run_simulator(simulator, trace, frames, algorithm)
                check(proc.returncode == 0,
                      f"{name}/{algorithm}: exit {proc.returncode}: {proc.stderr.strip()}")
                if proc.returncode != 0:
                    continue
                try:
                    record = json.loads(proc.stdout)
                except json.JSONDecodeError as exc:
                    check(False, f"{name}/{algorithm}: invalid JSON: {exc}")
                    continue

                want_hits, want_faults = expected[algorithm]
                check(record["algorithm"] == algorithm,
                      f"{name}/{algorithm}: wrong algorithm in record")
                check(record["hits"] == want_hits,
                      f"{name}/{algorithm}: hits {record['hits']} != {want_hits}")
                check(record["simulated_page_faults"] == want_faults,
                      f"{name}/{algorithm}: faults "
                      f"{record['simulated_page_faults']} != {want_faults}")
                check(record["total_references"] == n_refs,
                      f"{name}/{algorithm}: wrong reference count")
                check(record["hits"] + record["simulated_page_faults"]
                      == record["total_references"],
                      f"{name}/{algorithm}: hits+faults invariant broken")
                expected_rate = 100.0 * want_faults / n_refs if n_refs else 0.0
                check(abs(record["page_fault_rate_percent"] - expected_rate) < 1e-5,
                      f"{name}/{algorithm}: wrong fault rate")
                print(f"  ok: {algorithm:5s} hits={record['hits']} "
                      f"faults={record['simulated_page_faults']}")

        print("[case] invalid inputs must exit non-zero")
        good = tmpdir / "good.trace"
        good.write_text("1\n2\n3\n", encoding="utf-8")
        bad = tmpdir / "bad.trace"
        bad.write_text("1\nnot-a-page\n2\n", encoding="utf-8")
        negative = [
            ("malformed trace", ["--algorithm", "fifo", "--frames", "3",
                                 "--trace", str(bad)]),
            ("missing trace file", ["--algorithm", "fifo", "--frames", "3",
                                    "--trace", str(tmpdir / "missing.trace")]),
            ("zero frames", ["--algorithm", "fifo", "--frames", "0",
                             "--trace", str(good)]),
            ("negative frames", ["--algorithm", "fifo", "--frames", "-2",
                                 "--trace", str(good)]),
            ("unknown algorithm", ["--algorithm", "optimum", "--frames", "3",
                                   "--trace", str(good)]),
            ("missing --frames", ["--algorithm", "fifo", "--trace", str(good)]),
            ("unknown argument", ["--algorithm", "fifo", "--frames", "3",
                                  "--trace", str(good), "--bogus"]),
        ]
        for label, args_list in negative:
            proc = subprocess.run([str(simulator), *args_list],
                                  capture_output=True, text=True)
            check(proc.returncode != 0, f"{label}: expected non-zero exit")
            print(f"  ok: {label} -> exit {proc.returncode}")

    if failures:
        print(f"\nFAILED: {len(failures)} assertion(s)")
        return 1
    print("\nPASS: all known-answer and invalid-input tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
