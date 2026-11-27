# Decision log

Purpose: record choices made while implementing the study, and distinguish
**proposals** from decisions confirmed by the researcher/adviser. Nothing here
claims experimental findings. The protocol values were approved by the
researcher on 2026-11-26, then amended and re-approved the same day; README
section 12 records the current confirmed values.

| Item | Choice implemented | Status |
| --- | --- | --- |
| Simulator language | Plain C11, one shared CLI `build/simulator` with `--algorithm fifo\|lru\|clock`; each policy lives in its own `src/*.c` | Approved 2026-11-26 (§12 CLI) |
| Trace input format | One non-negative integer page id per line; blank lines and `#` comments ignored; duplicates allowed; empty trace is valid with 0 references | Approved 2026-11-26; documented for reproducibility (§7) |
| Invalid input handling | Non-zero exit (2 bad arguments, 3 bad input, 4 simulation error, 5 output error) with a message on stderr | Follows README §7 |
| Timing boundary | `CLOCK_MONOTONIC` starts after trace parsing and stops after the last policy call; trace I/O and generation excluded | Follows README §5/§8 |
| Result record v1 | JSON with algorithm, frames, trace path, reference count, hits, simulated faults, fault rate, time ns, throughput, run id | Schema approved 2026-11-26 (§12); raw records enriched by the runner |
| Trace generation | `sequential`, `random`, `looping`, `mixed`, `locality` rules in `scripts/generate_trace.py` (generator v2.0); seeded `random.Random`, parameters and SHA-256 written to a `.metadata.json` beside each trace | v1 rules approved 2026-11-26; locality + revised spans approved as v2 amendment the same day |
| Experimental factor values | Frames 3/5/8/10/15, length 100,000, 10 repetitions — current values in `configs/experiment-v2.json` | Approved 2026-11-26 (§4/§12); v2 supersedes v1 for reporting |
| Fair comparison | One trace per workload/repetition, shared by all algorithms and frame counts; seed = base + workload index × 1000 + repetition | Follows README §4; seed rule approved 2026-11-26 |
| Docker image | `docker/Dockerfile` uses `ubuntu:26.04` (matches host/WSL); tag `page-replacement-study:latest`, memory limit `512m`, `cpus=1`. Built digest `sha256:0430529978c7517adaee53cb47234fa94c181d7977b7ea7e03339a5f264bab6f`; in-image GCC 15.2.0 / Python 3.14.4; container run verified | Image settings approved 2026-11-26 as a fixed environment setting, not an experimental factor |
| OS/cgroup measurements | Not collected by default; `os_fault_counters: false` in configs | Approved 2026-11-26 (§12); must not be conflated with simulated faults |
| Statistical analysis | Descriptive outputs plus approved mixed-effects inference (`scripts/infer.py`) | Model approved by the researcher 2026-11-26 and executed; see "Inferential model" below |
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
`results/experiment-v2/`; descriptive summaries cover 75 groups. The current
approved protocol is `configs/experiment-v2.json`; the v1 dataset and its
approval record remain untouched for traceability.

## Inferential model

Approved by the researcher on 2026-11-26 and executed on the v2 dataset:

- Primary model: `page_fault_rate_percent ~ algorithm * workload * frames + (1 | trace_id)`, where `trace_id` is workload × repetition. FIFO and sequential are the reference levels; frames are categorical. All three algorithms and five frame counts share a trace, so the pairing is preserved.
- Pairwise algorithm contrasts are estimated from the fitted model and Holm-corrected, both as averages over all conditions and separately within each workload × frame cell. Paired mean differences, 95% CIs and Cohen's dz are also reported.
- Secondary model: same structure on `log(algorithm_time_ns)`.
- Outputs: `results/experiment-v2/processed/inferential/` (specification, model summaries, fixed effects, interaction terms, pairwise tables, effect sizes, diagnostics).
- Fit status: all three models converged (the timing model required the Powell fallback). The additive comparison model has a near-zero random-effect variance, so its likelihood-ratio interaction test is recorded as approximate.
- Caveats recorded in `diagnostics.json`: residuals fail Shapiro-Wilk (ceiling/floor effects), so model p-values are approximate; the significant 3-way interaction means overall algorithm averages dilute condition-specific effects — interpret `pairwise_by_condition.csv` instead.

## Remaining items

- Re-record the image digest after any Dockerfile or source change (`docker/build.sh`).
- Keep raw records in `results/*/raw/` and summaries in `results/*/processed/`; never overwrite raw runs silently.
- If residuals remain a concern, a robust or transformation-based sensitivity analysis would be a further model change and needs separate approval.
