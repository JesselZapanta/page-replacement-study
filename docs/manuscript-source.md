# Manuscript source notes — FIFO, LRU and Clock under memory-constrained simulated workloads

> **Purpose.** A single, verified source for drafting the manuscript. It is not
> the paper itself and makes no claim beyond what was actually run. Every
> number below comes from files in this repository, listed in §8.
>
> **Status.** Approved protocol v2 (`configs/experiment-v2.json`), executed
> 2026-11-26. The v1 run is retained but superseded. Model approved and
> executed 2026-11-26. Compiled: 2026-11-27.

---

## 1. Research identity, objective and scope

**Working title.** An Experimental Evaluation of FIFO, LRU, and Clock Page
Replacement Algorithms under Memory-Constrained Containerized Workloads.

**Area.** Operating systems, memory management, algorithm evaluation,
containerized experimentation, performance measurement.

**Core idea.** Implement FIFO, LRU and Clock as user-space simulators in C,
generate deterministic memory-reference traces, run identical traces through
each algorithm at controlled logical frame capacities, and compare simulated
page-fault behaviour with a documented container environment.

**General objective.** Compare the three algorithms under controlled workloads
and logical capacities using a repeatable execution environment.

**Research questions.**

1. How do FIFO, LRU and Clock compare in simulated page-fault count and rate
   across the selected workloads?
2. Does relative performance vary with logical frame capacity?
3. How do workload access patterns affect observed differences?
4. What execution-time differences are observed in the selected environment?

### 1.1 Conceptual distinction — must be preserved in the paper

| Term | Meaning | Role |
|---|---|---|
| Simulated page fault | Fault recorded by the user-space simulator when a referenced page is absent from its logical frames | **Primary outcome** |
| Logical page frames | Number of frame slots configured inside the simulator (3–15) | Direct capacity factor |
| Docker memory limit | Container resource constraint (512 MiB here) | Environment only; **not** a frame count |
| Linux minor/major faults | OS counters for the real process | Not simulated faults |
| Container/cgroup memory events | Docker resource measurements | Environmental observations, not simulated faults |

The study does **not** modify, select or evaluate the Linux kernel's actual
page-replacement policy. Docker is used only for a repeatable execution
environment. Do not state or imply otherwise.

---

## 2. Methods

### 2.1 Algorithms

- **FIFO** — evict the page resident longest; insertion order tracked by a
  monotonic sequence number.
- **LRU** — evict the page whose last access is farthest in the past.
- **Clock** — circular scan with a reference bit; a referenced page gets a
  second chance (bit cleared, hand advanced) before eviction.

All three are implemented as independent policy functions in `src/fifo.c`,
`src/lru.c`, `src/clock.c`, with shared trace parsing, state and output in
`src/common.c`. Each receives the same parsed reference sequence and frame
capacity. Invariant enforced and tested:
`hits + simulated_page_faults = total_references`.

### 2.2 Workloads and trace generation

Generator: `scripts/generate_trace.py`, rules version 2.0. All rules use
`random.Random(seed)` so traces are reproducible from seed + parameters.

| Workload | Generation rule | Parameters (v2) |
|---|---|---|
| Sequential | page = (start_page + i) mod span | span = 10 |
| Random | one seeded `randrange(span)` draw per reference | span = 12 |
| Looping | page = (start_page + i mod loop_size) mod span | span = 12, loop_size = 8 |
| Mixed | segments of `segment_length`; each segment's pattern chosen by seeded RNG from sequential/random/looping | span = 20, loop_size = 8, segment_length = 2000 |
| Locality | with probability `hot_prob`, draw from a hot set of `hot_set_size` pages; otherwise draw uniformly from span | span = 40, hot_set_size = 4, hot_prob = 0.8 |

`start_page = 0` for all workloads. Each trace contains 100,000 page IDs, one
per line. Blank lines and `#` comments are ignored by the simulator.

### 2.3 Experimental design

- Algorithms: FIFO, LRU, Clock (3).
- Workloads: sequential, random, looping, mixed, locality (5).
- Logical frame capacities: 3, 5, 8, 10, 15 (5).
- Repetitions: 10.
- Total runs: 3 × 5 × 5 × 10 = **750**.
- Seed rule: `seed = base_seed + workload_index × 1000 + repetition`, with
  `base_seed = 20261126`, repetitions 1-based.
- One trace is generated per workload × repetition and shared by **all**
  algorithms and **all** frame capacities — this is the matched/paired unit.

Fair-comparison rules applied: identical traces per condition; fixed recorded
seeds; no algorithm-specific easier trace; identical trace length and frame
count within a matched condition; algorithm, workload, frames, trace hash,
seed, repetition, versions and container settings recorded with each run;
simulator correctness tests passed before data collection; no results dropped.

### 2.4 Outcome measures

**Primary outcome**

```
page_fault_rate_percent = simulated_page_faults / total_references × 100
```

Raw simulated fault counts are also preserved.

**Secondary outcome** — algorithm execution time. Timing uses
`CLOCK_MONOTONIC` and wraps only the policy loop; trace reading, generation and
file I/O are excluded. Throughput (references/s) is derived from time and
reference count. Units are recorded in every run record (ns; refs/s).

No OS minor/major fault counters and no cgroup metrics were collected
(`os_fault_counters: false`), so no OS-level paging claim can be made.

### 2.5 Implementation and environment

- Simulator: C11, compiled with `gcc -Wall -Wextra -Wpedantic` (GCC 15.2.0).
- CLI: `build/simulator --algorithm NAME --frames N --trace FILE [--run-id ID] [--output FILE]`.
- Exit codes: 0 ok; 2 bad arguments; 3 bad input; 4 simulation error; 5 output error.
- Invalid frame counts (≤0) and malformed trace lines exit non-zero.
- Environment: Windows 11 host, WSL2, Ubuntu 26.04.1, Python 3.14.4, Git 2.53.0,
  Docker Desktop 29.9.3 with WSL2 integration; `docker` without `sudo`.
- Image: `page-replacement-study:latest`, base `ubuntu:26.04`, digest
  `sha256:0430529978c7517adaee53cb47234fa94c181d7977b7ea7e03339a5f264bab6f`;
  in-image GCC 15.2.0 / Python 3.14.4. Memory limit 512 MiB and `cpus=1` are
  fixed environment settings, **not** an experimental factor.
- Analysis packages (in `.venv/`): numpy 2.5.5, pandas 3.1.1, scipy 1.18.1,
  statsmodels 0.15.0.

### 2.6 Reproducibility and data handling

Each raw JSONL record includes: run ID, UTC timestamp, label, execution mode,
Docker image/limit (or null), git commit, algorithm, workload, frames, trace
path, trace SHA-256, trace length, seed, repetition, hits, simulated faults,
fault rate, time ns, throughput, status, and Python version. Each trace has a
`.metadata.json` with generator version, seed, parameters and its SHA-256.

Raw run records are in `results/<label>/raw/`, traces in
`results/<label>/traces/`, processed summaries in
`results/<label>/processed/`. The runner refuses to overwrite an existing
`results.jsonl` unless `--force` is given. The approval/amendment records are
JSON files in the result directories.

### 2.7 Correctness testing

`make test` runs 8 known-answer cases × 3 algorithms plus 7 invalid-input
checks: empty trace; one repeated page; more pages than frames; FIFO vs LRU
distinguishing trace; Clock second-chance trace; frame capacity one; duplicate
pages; comments/blanks/mixed IDs; malformed trace; missing file; zero/negative
frames; unknown algorithm; missing argument; unknown argument. All passed.

---

## 3. Protocol history and approvals

1. **v1 (approved 2026-11-26).** `configs/experiment.json`: span = 1000,
   frames 3–15, 100,000 references, 10 repetitions, four workloads. Executed:
   600 runs, 0 failures, data retained in `results/proposed-full-experiment/`.
2. **Design problem found in v1.** With span 1000 far above frame capacities,
   sequential and looping faulted on ~100% of references; random 99.7→98.5%
   and mixed 99.9→99.5% across frames; algorithm differences only
   0.001–0.003 percentage points. The primary outcome was saturated and could
   not discriminate the policies. This is an operational check, not a result.
3. **v2 amendment (approved 2026-11-26).** `configs/experiment-v2.json`:
   added `locality`, reduced spans/loop sizes; all other factors unchanged.
   A 10,000-reference pilot showed fault rates from ~0% to 100% and locality
   algorithm spreads of 2.8–8.4 percentage points.
4. **Full v2 run (2026-11-26).** 750 runs, 0 failures; all records passed the
   fault invariant, fault-rate check and trace SHA-256 verification.
5. **Statistical model (approved 2026-11-26).** Mixed-effects model specified
   in §5; executed on the v2 dataset.

Approval is recorded in `docs/decision-log.md`,
`results/proposed-full-experiment/approval.json`,
`results/experiment-v2/amendment.json` and
`results/experiment-v2/processed/inferential/model_spec.json`.

---

## 4. Descriptive results (approved v2 run)

All tables: mean fault rate (%) with SD in parentheses, n = 10 repetitions
per cell. Full machine-readable table:
`results/experiment-v2/processed/descriptive_stats.csv`.

### Sequential

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 100.000 (0.000) | 100.000 (0.000) | 100.000 (0.000) |
| 5 | 100.000 (0.000) | 100.000 (0.000) | 100.000 (0.000) |
| 8 | 100.000 (0.000) | 100.000 (0.000) | 100.000 (0.000) |
| 10 | 0.010 (0.000) | 0.010 (0.000) | 0.010 (0.000) |
| 15 | 0.010 (0.000) | 0.010 (0.000) | 0.010 (0.000) |

### Looping

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 100.000 (0.000) | 100.000 (0.000) | 100.000 (0.000) |
| 5 | 100.000 (0.000) | 100.000 (0.000) | 100.000 (0.000) |
| 8 | 0.008 (0.000) | 0.008 (0.000) | 0.008 (0.000) |
| 10 | 0.008 (0.000) | 0.008 (0.000) | 0.008 (0.000) |
| 15 | 0.008 (0.000) | 0.008 (0.000) | 0.008 (0.000) |

Sequential and looping provide boundary
conditions: the working set is either much larger than or fits inside the
frame capacity, so no eviction choice is required and the algorithms coincide.

### Random

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 75.002 (0.133) | 74.985 (0.135) | 74.995 (0.132) |
| 5 | 58.240 (0.169) | 58.280 (0.236) | 58.252 (0.128) |
| 8 | 33.293 (0.142) | 33.256 (0.146) | 33.248 (0.163) |
| 10 | 16.648 (0.085) | 16.617 (0.123) | 16.631 (0.128) |
| 15 | 0.012 (0.000) | 0.012 (0.000) | 0.012 (0.000) |

### Mixed

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 95.208 (0.679) | 95.219 (0.677) | 95.206 (0.680) |
| 5 | 92.012 (1.114) | 92.006 (1.096) | 92.005 (1.121) |
| 8 | 53.865 (7.887) | 53.839 (7.890) | 53.845 (7.891) |
| 10 | 50.626 (7.571) | 50.636 (7.578) | 50.642 (7.574) |
| 15 | 27.724 (4.771) | 42.596 (6.785) | 42.056 (6.692) |

### Locality

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 54.255 (0.247) | 51.875 (0.251) | 53.789 (0.240) |
| 5 | 36.901 (0.281) | 28.986 (0.255) | 33.957 (0.278) |
| 8 | 26.065 (0.214) | 17.306 (0.191) | 20.542 (0.213) |
| 10 | 22.206 (0.214) | 15.212 (0.156) | 16.757 (0.191) |
| 15 | 16.253 (0.166) | 12.449 (0.127) | 12.625 (0.131) |

### Execution time, locality workload (mean ms; 1 ms = 1,000,000 ns)

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 0.861 | 0.879 | 1.053 |
| 5 | 1.113 | 1.102 | 1.296 |
| 8 | 1.392 | 1.320 | 1.430 |
| 10 | 1.459 | 1.364 | 1.526 |
| 15 | 1.680 | 1.503 | 1.696 |

Full timing values (ns, SD, throughput) are in `descriptive_stats.csv` and
`descriptive_summary.json`. Timing reflects scan/loop overhead under the
measured miss patterns; it is not a measure of policy quality in general.

---

## 5. Inferential analysis

### 5.1 Model and why it was chosen

```
page_fault_rate_percent ~ algorithm * workload * frames + (1 | trace_id)
```

- Fixed effects: algorithm, workload, frame capacity (categorical) and all
  interactions. FIFO and sequential are reference levels.
- Random effect: intercept by `trace_id` (workload × repetition). All three
  algorithms and five frame capacities share a trace, so runs are paired,
  not independent; treating 750 runs as independent would be pseudo-
  replication and would inflate significance.
- Fitted by REML with a Powell fallback for the secondary timing model.
  Rate-model random-effect variance ≈ 3.059 (percentage-points²).
- A repeated-measures ANOVA would be an alternative but requires sphericity
  and handles missing runs less flexibly. The mixed model was approved by the
  researcher before execution.

### 5.2 How the numbers are calculated

1. For each algorithm pair, build the model design matrix over all workload ×
   frame cells, average rows for each algorithm, subtract to obtain contrast
   vector **c**, then estimate **c′β** with SE = √(**c′Vc**), where **V** is the
   fixed-effect covariance matrix; z = estimate/SE; p from the normal distribution.
2. Holm correction across the three pairs: sorted p-values are multiplied by
   3, 2, 1 with a running maximum, capped at 1.
3. Condition-specific contrasts repeat step 1 within one workload × frame
   cell; Holm is applied within that cell's three comparisons.
4. Paired effect sizes use the 250 (trace, frame) differences per pair: mean,
   SD, 95% CI = mean ± t₀.₉₇₅,₂₄₉ × SD/√250, and Cohen's dz = mean/SD.
5. Interaction test: likelihood ratio between the full 3-way model and an
   additive model, LR = 2(ℓ_full − ℓ_additive), df = 64.

### 5.3 Overall algorithm contrasts (averaged over all 25 conditions)

| Comparison | Difference (pp) | SE | z | p | Holm p | 95% CI (pp) |
|---|---|---|---|---|---|---|
| LRU − FIFO | −0.601 | 0.163 | −3.690 | 0.000225 | 0.000674 | [−0.921, −0.282] |
| Clock − FIFO | −0.150 | 0.163 | −0.919 | 0.358010 | 0.358010 | [−0.469, 0.170] |
| Clock − LRU | +0.452 | 0.163 | 2.770 | 0.005598 | 0.011196 | [0.132, 0.771] |

These averages are diluted by boundary conditions where all policies coincide.

### 5.4 Condition-specific contrasts — locality workload

| Frames | LRU − FIFO (pp) | Holm p | Clock − FIFO (pp) | Holm p | Clock − LRU (pp) | Holm p |
|---|---|---|---|---|---|---|
| 3 | −2.380 | 0.0105 | −0.466 | 0.568 | +1.915 | 0.0376 |
| 5 | −7.915 | 8.07e−22 | −2.944 | 3.03e−4 | +4.971 | 2.13e−9 |
| 8 | −8.759 | 1.83e−26 | −5.522 | 2.47e−11 | +3.237 | 7.15e−5 |
| 10 | −6.994 | 2.81e−17 | −5.449 | 4.59e−11 | +1.545 | 0.0580 |
| 15 | −3.805 | 9.11e−6 | −3.628 | 1.70e−5 | +0.177 | 0.829 |

Full 75-row table: `pairwise_by_condition.csv`.

### 5.5 Paired effect sizes across all conditions

| Comparison | n paired | Mean diff (pp) | SD (pp) | 95% CI (pp) | Cohen's dz |
|---|---|---|---|---|---|
| LRU − FIFO | 250 | −0.601 | 4.159 | [−1.119, −0.083] | −0.145 |
| Clock − FIFO | 250 | −0.150 | 3.449 | [−0.579, 0.280] | −0.043 |
| Clock − LRU | 250 | +0.452 | 1.221 | [0.300, 0.604] | +0.370 |

### 5.6 Model diagnostics

- 750 runs, 50 traces; all three models converged (timing via Powell fallback).
- Random-effect variance: rate 3.059; timing 0.000181; additive comparison
  model 4.85e−8 (boundary fit — its LR test is approximate).
- Interaction likelihood ratio: χ² = 3473.66, df = 64, p ≈ 0 → effects depend
  strongly on workload and frame capacity; condition-specific results should
  be used rather than overall averages.
- Residual Shapiro-Wilk: W = 0.567, p ≈ 1.9e−39 → residuals are not normal
  because fault rates cluster at 0% and 100%. **Model p-values are therefore
  approximate** and should be read with the effect sizes.
- Secondary timing model results: `timing_model_summary.txt` and
  `timing_pairwise.csv`.

---

## 6. Interpretation boundaries and limitations

- The study evaluates user-space simulations; it does not model page tables,
  TLB, swapping, kernel reclaim, file-backed page cache or storage I/O, and it
  does not establish which policy the Linux kernel or Docker uses internally.
- Synthetic traces are controlled inputs and may not represent real workloads.
- The primary outcome is a simulated fault count/rate, not Linux minor/major
  faults or Docker/cgroup memory events.
- Do not claim any algorithm is universally best. Within the approved v2
  conditions, LRU had the lowest simulated fault rates in the locality
  workload at moderate capacities (about 7–9 percentage points below FIFO),
  with Clock intermediate; these are condition-specific, approximate model
  results.
- Sequential and looping workloads produce ceiling/floor rates by design in
  this protocol; they serve as boundary conditions, not discriminating tests.
- v1 is superseded; do not report its saturated numbers as the study result.
- A robustness/transformation-based sensitivity analysis would be a further
  model change requiring approval before execution.

---

## 7. Reproduction

```bash
cd ~/projects/page-replacement-study

make                       # build build/simulator with warnings enabled
make test                  # known-answer correctness suite

# One run
build/simulator --algorithm fifo --frames 5 \
  --trace results/experiment-v2/traces/locality_rep1.trace

# Full approved experiment
python3 scripts/run_experiment.py --config configs/experiment-v2.json
python3 scripts/analyze.py \
  --input results/experiment-v2/raw/results.jsonl \
  --output-dir results/experiment-v2/processed

# Approved inferential analysis
.venv/bin/python scripts/infer.py

# Container image and example run
bash docker/build.sh
bash docker/run-example.sh
```

From Windows PowerShell, prefix with:
`wsl -d Ubuntu -- bash -lc "cd ~/projects/page-replacement-study && ..."`

---

## 8. Source-of-truth index

| Need | File |
|---|---|
| Research design, rules, conceptual distinction | `README.md` (especially §2, §4–§6, §10–§12) |
| Approved protocol v2 | `configs/experiment-v2.json` |
| Superseded protocol v1 | `configs/experiment.json` |
| Protocol history, approvals, caveats | `docs/decision-log.md` |
| Raw records (750) | `results/experiment-v2/raw/results.jsonl` |
| Run manifest and hashes | `results/experiment-v2/run_manifest.json` |
| Amendment/approval record | `results/experiment-v2/amendment.json` |
| Traces and generation metadata | `results/experiment-v2/traces/` |
| Descriptive tables | `results/experiment-v2/processed/descriptive_stats.csv`, `descriptive_summary.json` |
| Model specification | `results/experiment-v2/processed/inferential/model_spec.json` |
| Model summaries and fixed effects | `.../inferential/model_summary.txt`, `fixed_effects.csv`, `interaction_terms.csv` |
| Pairwise results and effect sizes | `.../inferential/pairwise_algorithms.csv`, `pairwise_by_condition.csv`, `paired_effect_sizes.csv` |
| Diagnostics | `.../inferential/diagnostics.json` |
| Timing model | `.../inferential/timing_model_summary.txt`, `timing_pairwise.csv` |
| Simulator source | `src/fifo.c`, `src/lru.c`, `src/clock.c`, `src/common.c`, `src/simulator.c` |
| Correctness tests | `tests/run_tests.py` |
