# Manuscript source notes — Simulation-Based Comparison of FIFO, LRU and Clock Page Replacement under Synthetic Workloads (Docker-executed)

> **Purpose.** A single, verified source for drafting the manuscript. It is not
> the paper itself and makes no claim beyond what was actually run. Every
> number below comes from files in this repository, listed in §8.
>
> **Status.** Approved protocol v2.1 (`configs/experiment-v2.1.json`), executed
> 2026-11-27. All 750 runs executed inside Docker with rotated algorithm order.
> Earlier v1/v2 datasets are superseded. Compiled: 2026-11-27.

---

## 1. Research identity, objective and scope

**Working title.** Simulation-Based Comparison of FIFO, LRU and Clock Page
Replacement under Synthetic Workloads (Docker-executed).

**Keywords.** page replacement; FIFO; LRU; Clock; simulation; synthetic traces;
Docker (execution environment only).

**Area.** Operating systems, memory management, algorithm evaluation,
simulation-based experimentation, performance measurement.

**Core idea.** Implement FIFO, LRU and Clock as user-space simulators in C,
generate deterministic memory-reference traces, run identical traces through
each algorithm at controlled logical frame capacities, and compare simulated
page-fault behaviour. Docker supplies the execution environment only; no
container or OS-level paging metrics were collected.

**General objective.** Compare the three algorithms under controlled synthetic
workloads and logical capacities using a repeatable execution environment.

**Research questions.**

1. How do FIFO, LRU and Clock compare in simulated page-fault count and rate
   across the selected workloads?
2. Does relative performance vary with logical frame capacity?
3. How do workload access patterns affect observed differences?
4. What execution-time differences are observed when the simulators are run in
   the documented Docker environment (execution environment only; no container
   or OS paging metrics were collected)?

### 1.1 Conceptual distinction — must be preserved in the paper

| Term | Meaning | Role |
|---|---|---|
| Simulated page fault | Fault recorded by the user-space simulator when a referenced page is absent from its logical frames | **Primary outcome** |
| Logical page frames | Number of frame slots configured inside the simulator (3–15) | Direct capacity factor |
| Docker memory limit | Container resource constraint (512 MiB here), applied to every run in v2.1 | Environment only; **not** a frame count |
| Linux minor/major faults | OS counters for the real process | Not simulated faults |
| Container/cgroup memory events | Docker resource measurements | Environmental observations, not simulated faults |

The study does **not** modify, select or evaluate the Linux kernel's actual
page-replacement policy. Docker provides the execution environment and its
resource limits; it does not choose a paging policy. Do not state or imply
otherwise.

---

## 2. Methods

### 2.1 Algorithms

- **FIFO** — evict the page resident longest; insertion order tracked by a
  monotonic sequence number.
- **LRU** — evict the page whose last access is farthest in the past.
- **Clock** — circular scan with a reference bit; a referenced page gets a
  second chance (bit cleared, hand advanced) before eviction.

Each policy is an independent function in `src/fifo.c`, `src/lru.c`,
`src/clock.c`; shared parsing, state and JSON output are in `src/common.c`.
Invariant enforced and tested:
`hits + simulated_page_faults = total_references`.

### 2.2 Workloads and trace generation

Generator: `scripts/generate_trace.py`, rules version 2.1. All rules use
`random.Random(seed)`, so traces are reproducible from seed + parameters.

| Workload | Generation rule | Parameters |
|---|---|---|
| Sequential | page = (start_page + i) mod span | span = 10 |
| Random | one seeded `randrange(span)` draw per reference | span = 12 |
| Looping | page = (start_page + i mod loop_size) mod span | span = 12, loop_size = 8 |
| Mixed | segments of `segment_length`; pattern chosen per segment by seeded RNG; v2.1 uses a per-segment local index, but this is a **no-op** for the approved parameters (segment offsets are multiples of 2000, span 20 and loop size 8), so mixed traces are byte-identical to v2. Simulator cache state is **not** reset between segments. | span = 20, loop_size = 8, segment_length = 2000 |
| Locality | with probability `hot_prob`, draw from a hot set of `hot_set_size` pages; otherwise draw uniformly from span | span = 40, hot_set_size = 4, hot_prob = 0.8 |

`start_page = 0` for all workloads. Each trace contains 100,000 page IDs, one
per line. Blank lines and `#` comments are ignored by the simulator.

Three workload caveats, stated plainly:

- **Random** is a validity check, not a comparison condition. Under uniform
  i.i.d. references over N pages with F frames, the expected fault rate is about
  `1 − F/N` for every policy. With span N = 12 and F = 3, that is 75%; observed
  rates were 75.002% (FIFO), 74.985% (LRU) and 74.995% (Clock). This confirms
  the simulator behaves as expected; it is not evidence about policy quality.
- **Locality** is i.i.d. with skewed popularity (80% draws from a 4-page hot
  set), with **no temporal phases**. Under this trace model the expected
  ordering is LRU < Clock < FIFO; the observed ordering is the expected result,
  not a surprising finding.
- **Sequential** and **looping** are deterministic. Across the 10 seeded runs
  each has only **one distinct trace hash** (effective n = 1), so they are
  descriptive boundary conditions only. The phrase "10 repetitions" does not
  mean 10 independent replicates for these two workloads.

### 2.3 Experimental design

- Algorithms: FIFO, LRU, Clock (3).
- Workloads: sequential, random, looping, mixed, locality (5).
- Logical frame capacities: 3, 5, 8, 10, 15 (5).
- Seeded runs per condition: 10 (these are independent traces only for the
  stochastic workloads random, mixed and locality; sequential and looping are
  deterministic and yield one distinct trace across all 10 seeds, effective
  n = 1).
- Total runs: 3 × 5 × 5 × 10 = **750 seeded runs**.
- Seed rule: `seed = base_seed + workload_index × 1000 + repetition`, with
  `base_seed = 20261126`, repetitions 1-based.
- One trace per workload × seeded run, shared by all algorithms and all frame
  counts — the matched/paired unit for stochastic workloads.
- **Run order rotated** by `(workload_index + repetition + frame_index) mod 3`
  so timing is not systematically confounded with algorithm order. Three
  distinct orders occurred (249, 249 and 252 runs). Each record stores
  `algorithm_order` and `run_order_position`.

Fair-comparison rules applied: identical traces per condition; fixed recorded
seeds; no algorithm-specific easier trace; identical trace length and frame
count within a condition; algorithm, workload, frames, trace hash, seed,
repetition, versions, container settings, git commit/tag and run order recorded
with every run; correctness tests passed before data collection; no results
dropped.

### 2.4 Outcome measures

**Primary outcome**

```
page_fault_rate_percent = simulated_page_faults / total_references × 100
```

Raw simulated fault counts are preserved.

**Secondary outcome** — algorithm execution time. Timing uses
`CLOCK_MONOTONIC` and wraps only the policy loop; trace reading, generation and
file I/O are excluded. Units are ns; throughput is refs/s. Timing values are
reported in **milliseconds** in this document (1 ms = 1,000,000 ns).

No OS minor/major fault counters and no cgroup metrics were collected
(`os_fault_counters: false`), so no OS-level paging claim is made.

### 2.5 Implementation and environment

- Simulator: C11, compiled with `gcc -Wall -Wextra -Wpedantic` (GCC 15.2.0).
- CLI: `build/simulator --algorithm NAME --frames N --trace FILE [--run-id ID] [--output FILE]`.
- Exit codes: 0 ok; 2 bad arguments; 3 bad input; 4 simulation error; 5 output error.
- Every one of the 750 reported runs executed inside Docker:
  `page-replacement-study:latest`, base `ubuntu:26.04`, digest
  `sha256:0430529978c7517adaee53cb47234fa94c181d7977b7ea7e03339a5f264bab6f`,
  `--memory=512m`, `--cpus=1`. These are fixed environment settings, **not** an
  experimental factor and **not** a frame count. The repo is mounted at
  `/work`; the image entrypoint is `/src/build/simulator`.
- In-image toolchain: GCC 15.2.0, Python 3.14.4. Host: Windows 11, WSL2,
  Ubuntu 26.04.1, Git 2.53.0, Docker Desktop 29.9.3 with WSL2 integration.
- Analysis packages (in `.venv/`): numpy 2.5.5, pandas 3.1.1, scipy 1.18.1,
  statsmodels 0.15.0.
- Code provenance: every v2.1 record carries `git_commit =
  a4f37d6b59dc6a539523231e648c5f94991bdcde` and `git_tag = v2.1.2`, the exact
  state used to generate the data.

### 2.6 Reproducibility and data handling

Each raw JSONL record includes: run ID, UTC timestamp, label, execution mode,
Docker image/tag/digest and memory limit, git commit/tag, algorithm, workload,
frames, trace path, trace SHA-256, trace length, seed, repetition, algorithm
order and position, hits, simulated faults, fault rate, time ns, throughput,
status and Python version. Each trace has a `.metadata.json` with generator
version, seed, parameters and SHA-256.

Raw records are in `results/<label>/raw/`, traces in `results/<label>/traces/`,
summaries in `results/<label>/processed/`. The runner refuses to overwrite an
existing `results.jsonl` unless `--force` is given. Approval records are JSON
files in the result directories.

### 2.7 Correctness testing

`make test` runs 8 known-answer cases × 3 algorithms plus 7 invalid-input
checks: empty trace; one repeated page; more pages than frames; FIFO vs LRU
distinguishing trace; Clock second-chance trace; frame capacity one; duplicate
pages; comments/blanks/mixed IDs; malformed trace; missing file; zero/negative
frames; unknown algorithm; missing argument; unknown argument. All passed.

---

## 3. Protocol history and approvals

1. **v1 (approved 2026-11-26).** `configs/experiment.json`: span = 1000, four
   workloads. Executed locally: 600 runs, 0 failures. Data retained in
   `results/proposed-full-experiment/`, but it saturated near 100% faults and
   is superseded. `git_commit` is `not-a-git-repo` in every record.
2. **Design problem in v1.** Sequential and looping faulted on ~100% of
   references; random 99.7→98.5% and mixed 99.9→99.5% across frames; algorithm
   differences only 0.001–0.003 percentage points. Operational check, not a
   research finding.
3. **v2 (approved 2026-11-26).** Added `locality`, reduced spans. Pilot showed
   variation. Full run: 750 local runs, 0 failures. Also superseded, and also
   carries `git_commit = not-a-git-repo`.
4. **v2.1 (approved 2026-11-27).** `configs/experiment-v2.1.json` and tag
   `v2.1.2`: Docker execution with applied limits, rotated run order, generator
   v2.1 with git provenance in every record and corrected inference. The mixed
   indexing change was a no-op (byte-identical traces to v2). Full run:
   **750 Docker runs, 0 failures**. All records verified
   for invariant, trace SHA-256, unique run IDs, image digest and commit/tag.
5. **Statistical model (approved 2026-11-26; revised 2026-11-27).** The revised
   specification is in §5 and `results/experiment-v2.1/processed/inferential/model_spec.json`.

Because the repository was initialized after the v1 and v2 runs, no commit
identifies the code that produced those datasets. This is recorded as a
retroactive-provenance limitation in `results/experiment-v2.1/amendment.json`;
those runs must not be used as the reported dataset.

OPT (Belady) baseline was deliberately deferred and is not part of this protocol.

---

## 4. Descriptive results (approved v2.1 run)

Mean fault rate (%) with SD in parentheses across 10 seeded runs per cell.
For deterministic sequential/looping workloads these are one trace (effective
n = 1) and the SD reflects seed-independent zero variance, not replication.
Docker execution does not change deterministic fault counts, so fault-rate
values match v2; timing values come from the Docker runs.
Machine-readable table: `results/experiment-v2.1/processed/descriptive_stats.csv`.

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

Sequential and looping are boundary conditions: the working set is either far
larger than or fits inside capacity, so no eviction choice is required and the
algorithms coincide. Their ten repetitions use one identical trace each
(effective n = 1), so they are excluded from inference.

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

#### Mixed-workload artifact at 15 frames (do not use in conclusions)

At 15 frames the mixed table shows FIFO at 27.724% versus LRU 42.596% and
Clock 42.056% — paired differences of **+14.873 pp (LRU − FIFO)** and
**+14.333 pp (Clock − FIFO)**, both statistically significant after Holm
correction (p ≈ 5e−6; 95% CIs [12.48, 17.27] and [12.06, 16.60]). These are
**a trace-construction artifact, not evidence that FIFO is better**.

Reason: the mixed trace hands cache state from one segment to the next; it is
not reset. A cyclic sequential scan over 20 pages with 15 frames faults on
every reference from a cold FIFO start, but when the preceding segment is
random, FIFO's queue order is scrambled relative to the scan order and it
faults only about half the time in the following sequential segment; LRU stays
near 100% faults in those segments. Evidence from `mixed_rep1`: in sequential
segments FIFO faults were 994, 1000, 994, 994, 996, 998, 1000, 997, 997, 997,
998, 997 and 1000 out of 2000 references (about 997 on average), while LRU
faults were 1991, 2000, 1988, 1988, 1988, 1990, 2000, 1992, 1988, 1992, 1992,
1991 and 2000 (about 1992). Clock intermediate. This path dependence, not
policy quality, explains the 15-frame result. The mixed workload should not be
used to rank the algorithms.

### Locality

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 54.255 (0.247) | 51.875 (0.251) | 53.789 (0.240) |
| 5 | 36.901 (0.281) | 28.986 (0.255) | 33.957 (0.278) |
| 8 | 26.064 (0.214) | 17.306 (0.191) | 20.542 (0.213) |
| 10 | 22.206 (0.214) | 15.212 (0.156) | 16.757 (0.191) |
| 15 | 16.253 (0.166) | 12.449 (0.127) | 12.625 (0.131) |

### Execution time, locality workload (mean ms, Docker runs, rotated order)

| Frames | FIFO | LRU | Clock |
|---|---|---|---|
| 3 | 1.847 | 1.934 | 2.218 |
| 5 | 2.840 | 2.477 | 3.202 |
| 8 | 2.670 | 2.785 | 3.628 |
| 10 | 4.173 | 2.859 | 4.160 |
| 15 | 3.329 | 4.201 | 3.340 |

Full timing values and SDs are in `descriptive_stats.csv` and
`descriptive_summary.json`. **Timing is environment-specific and secondary.**
For the same locality condition, the earlier local run measured about 0.86 ms
while the Docker run measures about 1.85 ms — roughly a 2× difference caused by
the execution environment, not by the paging policy. Values above are means;
rotated order reduces but does not eliminate order-related bias. Timing must
not be presented as a measure of policy quality, and comparisons are only
meaningful within the Docker environment.

---

## 5. Inferential analysis

### 5.1 Primary method

The primary inference is a **per-condition paired analysis**. Within each
workload × frame cell, the 10 seeded runs are independent traces **only for
the stochastic workloads** (random, mixed, locality); all three algorithms
process each trace. For each pair, the 10 paired differences are analysed with
a one-sample t-test:

```
d_i   = rate(pair member B, trace i) − rate(pair member A, trace i)
mean  = Σd_i / n            n = 10 independent traces (stochastic workloads only)
sd    = sample SD of d_i
CI95  = mean ± t(0.975, n−1) × sd / √n
dz    = mean / sd
```

- **Holm correction** is applied across **all 42 tested cell × pair
  comparisons** in one family (not within each cell separately).
- **Boundary rule:** cells whose repetitions share a single trace hash have
  effective n = 1 and are not tested. This excludes sequential and looping
  (30 comparisons) plus three zero-variance cells, leaving 33 boundary
  comparisons recorded in `boundary_cells.csv`.
- Per-condition variances are used, so the single-residual-variance assumption
  is not imposed on the primary results.

### 5.2 Model-based supplementary analysis and interaction test

Mixed-effects models are retained only as supplementary estimates:

```
page_fault_rate_percent ~ algorithm * workload * frames + (1 | trace_id)
```

FIFO and sequential are references; frames are categorical. REML fits give the
fixed-effect summary (`fixed_effects.csv`, `model_summary.txt`). The
interaction likelihood-ratio test compares the full model with an additive
model using **ML fits on both** (`reml=False`), because likelihood-ratio tests
of differing fixed effects are invalid under REML.
Result: χ² = 3440.38, df = 64, p ≈ 0 — effects depend strongly on workload and
frame capacity, so per-condition results are the ones to interpret.

### 5.3 Condition-specific paired results — locality workload

Effect sizes and 95% confidence intervals are reported first; p-values are
secondary.

| Frames | LRU − FIFO, pp (95% CI) | Clock − FIFO, pp (95% CI) | Clock − LRU, pp (95% CI) |
|---|---|---|---|
| 3 | −2.380 [−2.436, −2.325] | −0.466 [−0.502, −0.429] | +1.915 [+1.875, +1.954] |
| 5 | −7.915 [−7.970, −7.860] | −2.944 [−2.972, −2.916] | +4.971 [+4.912, +5.029] |
| 8 | −8.759 [−8.806, −8.711] | −5.522 [−5.573, −5.471] | +3.237 [+3.209, +3.264] |
| 10 | −6.994 [−7.039, −6.948] | −5.449 [−5.492, −5.406] | +1.545 [+1.510, +1.580] |
| 15 | −3.805 [−3.848, −3.761] | −3.628 [−3.677, −3.579] | +0.177 [+0.147, +0.206] |

All 15 locality comparisons survive Holm correction across the 42-comparison
family; Holm p-values range from about 1e−18 to 7e−6. The very small p-values
arise because trace-to-trace noise is tiny (SDs around 0.13–0.28 fault-rate
points), not because the effects are large in absolute terms. Standardised
effect sizes (Cohen's dz) are correspondingly large and should be read with
the unstandardised intervals above. Full results are in
`paired_by_condition.csv`; timing results are in
`paired_timing_by_condition.csv`. The expected ordering under this i.i.d.
skewed-popularity trace model is LRU < Clock < FIFO.

### 5.4 Diagnostics

- 750 runs, 50 traces; 42 rate comparisons tested, 33 boundary comparisons
  excluded; 45 timing comparisons tested.
- All four mixed-model fits (REML and ML) converged; the timing model used the
  default optimizer in v2.1.
- Interaction LR (ML): χ² = 3440.38, df = 64, p ≈ 0.
- Residual Shapiro-Wilk: W = 0.567, p ≈ 1.9e−39. The single-variance mixed
  model is a poor fit because rates cluster at 0% and 100%; this is why the
  primary inference uses per-condition variances.
- All raw records passed the fault invariant and trace SHA-256 checks.

---

## 6. Interpretation boundaries and limitations

- The study evaluates user-space simulations; it does not model page tables,
  TLB, swapping, kernel reclaim, file-backed page cache or storage I/O, and it
  does not establish which policy the Linux kernel or Docker uses internally.
- Only synthetic traces were used; they are controlled inputs and may not
  represent real workloads. Scale is small: 3–15 logical frames and page spans
  of 8–40. No OPT (Belady) baseline was included, so distance from optimal
  cannot be reported.
- The primary outcome is a simulated fault count/rate, not Linux minor/major
  faults or Docker/cgroup memory events. No container or OS paging metrics
  were collected; Docker is the execution environment only.
- Do not claim any algorithm is universally best. In the locality workload,
  LRU < Clock < FIFO is the **expected** ordering for an i.i.d. skewed-popularity
  trace, and the observed 7–9 pp advantages at moderate capacities are
  condition-specific, not a general ranking.
- Random is a validity/sanity check (`1 − F/N`), not a comparison. Sequential
  and looping are deterministic boundary conditions with effective n = 1: they
  are descriptive only, are not tested, and no conclusion rests on inference
  from them. The 10 seeded runs are not 10 independent replicates for these
  workloads.
- The mixed workload at 15 frames shows a FIFO advantage caused by segment
  path dependence (documented above). This is a trace-construction artifact;
  no conclusion that FIFO outperforms LRU or Clock may be drawn from it.
- Timing is environment-specific (Docker values are roughly 2× the earlier
  local values), mean-based, secondary, and not fully de-biased by rotation;
  it is not a measure of policy quality.
- The v1 and v2 datasets are superseded and lack a code commit hash; the
  manuscript must use v2.1 numbers only.
- Further robustness analyses or protocol changes (OPT baseline, phased
  locality, reworked mixed segments, working-set-relative frame counts) need
  separate approval and a new labelled run.

---

## 7. Reproduction

```bash
cd ~/projects/page-replacement-study

make                       # build build/simulator with warnings enabled
make test                  # known-answer correctness suite

# One run inside the container
docker run --rm --memory=512m --cpus=1 -v "$PWD:/work" -w /work \
  page-replacement-study:latest \
  --algorithm fifo --frames 5 \
  --trace results/experiment-v2.1/traces/locality_rep1.trace

# Full approved v2.1 experiment (already executed; --force only if intentional)
python3 scripts/run_experiment.py --config configs/experiment-v2.1.json
python3 scripts/analyze.py \
  --input results/experiment-v2.1/raw/results.jsonl \
  --output-dir results/experiment-v2.1/processed

# Approved inferential analysis
.venv/bin/python scripts/infer.py

# Rebuild the image if the simulator source changes
bash docker/build.sh
```

From Windows PowerShell, prefix with:
`wsl -d Ubuntu -- bash -lc "cd ~/projects/page-replacement-study && ..."`

---

## 8. Source-of-truth index

| Need | File |
|---|---|
| Research design, rules, conceptual distinction | `README.md` (especially §2, §4–§6, §10–§12) |
| Approved protocol v2.1 | `configs/experiment-v2.1.json` |
| Superseded protocols | `configs/experiment-v2.json`, `configs/experiment.json` |
| Protocol history, approvals, caveats | `docs/decision-log.md` |
| Raw records (750, Docker, tagged code) | `results/experiment-v2.1/raw/results.jsonl` |
| Run manifest | `results/experiment-v2.1/run_manifest.json` |
| Amendment/approval and provenance | `results/experiment-v2.1/amendment.json` |
| Traces and generation metadata | `results/experiment-v2.1/traces/` |
| Descriptive tables | `results/experiment-v2.1/processed/descriptive_stats.csv`, `descriptive_summary.json` |
| Primary inference | `results/experiment-v2.1/processed/inferential/paired_by_condition.csv`, `paired_timing_by_condition.csv`, `boundary_cells.csv` |
| Model specification and diagnostics | `results/experiment-v2.1/processed/inferential/model_spec.json`, `diagnostics.json` |
| Supplementary model outputs | `results/experiment-v2.1/processed/inferential/model_summary.txt`, `fixed_effects.csv`, `timing_model_summary.txt` |
| Simulator source | `src/fifo.c`, `src/lru.c`, `src/clock.c`, `src/common.c`, `src/simulator.c` |
| Correctness tests | `tests/run_tests.py` |
