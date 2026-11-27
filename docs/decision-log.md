# Decision log

Purpose: record choices made while implementing the study, and distinguish
**proposals** from decisions confirmed by the researcher/adviser. Nothing here
claims experimental findings. The protocol was approved on 2026-11-26, amended
as v2 the same day, and amended again as v2.1 on 2026-11-27; README section 12
records the current confirmed values.

| Item | Choice implemented | Status |
| --- | --- | --- |
| Simulator language | Plain C11, one shared CLI `build/simulator` with `--algorithm fifo\|lru\|clock`; each policy lives in its own `src/*.c` | Approved 2026-11-26 (§12 CLI) |
| Trace input format | One non-negative integer page id per line; blank lines and `#` comments ignored; duplicates allowed; empty trace is valid with 0 references | Approved 2026-11-26; documented for reproducibility (§7) |
| Invalid input handling | Non-zero exit (2 bad arguments, 3 bad input, 4 simulation error, 5 output error) with a message on stderr | Follows README §7 |
| Timing boundary | `CLOCK_MONOTONIC` starts after trace parsing and stops after the last policy call; trace I/O and generation excluded | Follows README §5/§8 |
| Result record v1 | JSON with algorithm, frames, trace path, reference count, hits, simulated faults, fault rate, time ns, throughput, run id | Schema approved 2026-11-26 (§12); raw records enriched by the runner |
| Trace generation | `sequential`, `random`, `looping`, `mixed`, `locality` rules in `scripts/generate_trace.py` (generator v2.1 resets mixed segments); seeded `random.Random`, parameters and SHA-256 written to a `.metadata.json` beside each trace | v1/v2 rules superseded; v2.1 approved 2026-11-27 |
| Experimental factor values | Frames 3/5/8/10/15, length 100,000, 10 repetitions — current values in `configs/experiment-v2.1.json` | Approved 2026-11-26; v2.1 supersedes v2 and v1 for reporting |
| Fair comparison | One trace per workload/repetition shared by all algorithms/frames; seed = base + workload index × 1000 + repetition; algorithm order rotated and recorded | Follows README §4; rotation added and approved 2026-11-27 |
| Docker execution | All 750 v2.1 runs in `page-replacement-study:latest`, base `ubuntu:26.04`, digest `sha256:0430529978c7517adaee53cb47234fa94c181d7977b7ea7e03339a5f264bab6f`, `--memory=512m --cpus=1`; in-image GCC 15.2.0 / Python 3.14.4 | Approved fixed environment setting, not an experimental factor; v1/v2 local runs superseded |
| OS/cgroup measurements | Not collected by default; `os_fault_counters: false` in configs | Approved 2026-11-26 (§12); must not be conflated with simulated faults |
| Statistical analysis | Per-condition paired tests with Holm correction and ML interaction test; mixed-effects models supplementary (`scripts/infer.py`) | Revised model approved 2026-11-27 and executed on v2.1; see "Inferential model" below |
| Demo results | `results/demo/` is sample/test data, labeled `is_demo: true` and excluded from research claims | Fixed rule, not a research result |

## Run status

The full 600-run set was executed on 2026-11-26 with `configs/experiment.json`:
600 records, 0 failed runs. Every record passed the `hits + faults ==
references` invariant, the fault-rate check, and a trace SHA-256 check. Output
is in `results/proposed-full-experiment/`. The configuration used is the
**approved protocol** confirmed by the researcher on 2026-11-26; approval is
recorded in `results/proposed-full-experiment/approval.json`. The directory
name predates approval and is kept unchanged for traceability.

Interpretation boundary (an operational check, not a research finding): with
`span = 1000` and frame capacities 3–15, sequential and looping traces fault
on essentially every reference (~100%), and random/mixed stay near 98.5–100%
with algorithm differences around 0.001–0.003 percentage points. The primary
outcome is saturated in these conditions, so any interpretation must stay
within the measured scope (README §10) and must not claim an algorithm is
universally best. The v1 run is retained unchanged but **superseded** by the
v2 run described below.

## Protocol amendment (v2) and re-run

Approved by the researcher on 2026-11-26 (recorded in
`results/experiment-v2/amendment.json`):

- Added the `locality` workload: 80% of references come from a 4-page hot set,
  the rest are uniform over a 40-page space (generator rules v2.0).
- Reduced spans/loop sizes: sequential 10, random 12, looping 8, mixed 20.
- Kept algorithms, frame capacities, trace length, repetitions, seed rule,
  execution settings and measurement definitions unchanged.

Pilot at 10,000 references confirmed the fix: fault rates now span ~0% to
100%, and the locality workload separates the algorithms by 2.8–8.4
percentage points, with LRU lowest and FIFO highest.

The full v2 experiment was executed on 2026-11-26: 750 runs (3 algorithms ×
5 workloads × 5 frame counts × 10 repetitions), 0 failures. All records
passed the invariant, fault-rate and trace SHA-256 checks. Output is in
`results/experiment-v2/`; descriptive summaries cover 75 groups. This run and
its local execution mode are now superseded by v2.1 below; the v1/v2 datasets
and their approval records remain untouched for traceability.

## Protocol amendment (v2.1) and re-run

Approved by the researcher on 2026-11-27 after a review found that no v2 run
had used Docker, that git provenance was missing, and that run order was fixed.
Recorded in `configs/experiment-v2.1.json` and
`results/experiment-v2.1/amendment.json`.

- `execution.mode = docker`: all 750 runs executed in
  `page-replacement-study:latest` with `--memory=512m --cpus=1`; image digest
  and git commit/tag appear in every record.
- Algorithm order rotated by `(workload_index + repetition + frame_index) mod 3`;
  three distinct orders occurred (249, 249, 252 runs).
- Generator v2.1 resets mixed-segment sequential/looping state at each boundary.
- Code state: commit `a4f37d6b59dc6a539523231e648c5f94991bdcde`, tag `v2.1.2`.
- Result: 750 Docker runs, 0 failures; all invariant, trace-hash, image and
  provenance checks passed. v1 and v2 are superseded and remain only for
  traceability.
- **Retroactive provenance:** the git repository was initialized after the v1
  and v2 runs, so their 1,350 records carry `git_commit = not-a-git-repo`. No
  commit identifies the code that produced them; they must not be reported.

## Inferential model (revised 2026-11-27)

The original pooled REML-contrast approach and the REML likelihood-ratio test
were retired. The approved revised specification, executed on v2.1:

- **Primary:** per-condition paired t-tests on the 10 independent traces per
  workload × frame cell, with 95% CI and Cohen's dz. Holm correction is applied
  across all 42 tested comparisons in one family. Cells whose repetitions share
  one trace hash are boundary cells (effective n = 1) and are not tested:
  sequential and looping (30 comparisons) plus three zero-variance cells.
- **Supplementary model:** `page_fault_rate_percent ~ algorithm * workload *
  frames + (1 | trace_id)` fitted by REML for fixed-effect estimates only.
- **Interaction test:** likelihood ratio between full and additive models, both
  fitted by **ML** (`reml=False`), because REML is invalid for comparing
  different fixed effects. χ² = 3440.38, df = 64, p ≈ 0.
- Outputs in `results/experiment-v2.1/processed/inferential/`: `paired_by_condition.csv`,
  `paired_timing_by_condition.csv`, `boundary_cells.csv`, `diagnostics.json`,
  `model_spec.json`, and REML summaries.
- Diagnostics: all fits converged; residual Shapiro-Wilk W = 0.567, p ≈ 1.9e−39,
  so the single-variance model is a poor fit — the primary per-condition
  analysis uses separate variances.

## Remaining items

- Re-record the image digest after any Dockerfile or source change (`docker/build.sh`).
- Keep raw records in `results/*/raw/` and summaries in `results/*/processed/`; never overwrite raw runs silently.
- OPT baseline, phased-locality workloads and further robustness analyses were deferred and need separate approval.

