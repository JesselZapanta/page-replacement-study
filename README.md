# Research Project Brief: FIFO, LRU, and Clock Page Replacement under Containerized Workloads

> **Document purpose:** This README is the project handoff for an AI
> coding agent or developer. It explains the research question,
> experimental design, implementation boundaries, repository structure,
> and rules for making changes.
>
> **Research status:** Implementation complete. The approved v2 protocol (an
> amendment of the original protocol, 2026-11-26) was executed on 2026-11-26;
> the v1 run is retained but superseded. No experimental findings are claimed
> in this document. All result tables must be populated only with measurements
> from actual runs.

## 1. Research identity

### Working title

**An Experimental Evaluation of FIFO, LRU, and Clock Page Replacement
Algorithms under Memory-Constrained Containerized Workloads**

### Research area

Operating systems, memory management, algorithm evaluation,
containerized experimentation, and performance measurement.

### Core idea

Implement three classic page-replacement algorithms---First-In,
First-Out (FIFO), Least Recently Used (LRU), and Clock---as user-space
simulators written in C or C++. Generate reproducible memory-reference
traces and run the same traces through each algorithm under controlled
logical page-frame capacities. Use Docker containers as a repeatable
execution environment and, where appropriate, impose container memory
limits to observe and document the execution environment.

The algorithms are evaluated by their **simulated page-replacement
behavior**, not by changing or selecting the Linux kernel's actual
page-replacement policy.

## 2. Important conceptual distinction

This distinction must be preserved in the code, documentation, analysis,
and any paper draft.

-   **Simulated page faults:** A fault recorded by the user-space
    simulator when a referenced page is not present in its configured
    logical frame set. This is the primary outcome for comparing FIFO,
    LRU, and Clock.
-   **Logical page frames:** The number of page slots configured inside
    the simulator (for example, 3, 5, 8, 10, or 15). This is the direct
    capacity factor controlling the simulated algorithms.
-   **Docker memory limit:** A resource limit applied to the container
    (for example, through Docker's memory option). It constrains the
    container's real memory usage. It does not automatically translate
    into a specific number of simulated page frames.
-   **Linux minor/major page faults:** Operating-system counters
    relating to the real process and its memory activity. They are not
    the same as simulator-recorded page faults.
-   **Container memory events and usage:** Docker/cgroup measurements of
    actual container resource use. These are environmental measurements,
    not simulated page-fault counts.

Do not state or imply that Docker lets this project choose FIFO, LRU, or
Clock as the Linux kernel's page-replacement algorithm. The project
simulates those policies in user space.

## 3. Research problem and objectives

### General objective

To experimentally compare FIFO, LRU, and Clock page-replacement
algorithms under controlled memory-reference workloads and logical
page-frame capacities, using a containerized environment for repeatable
execution.

### Specific objectives

1.  Implement correct user-space versions of FIFO, LRU, and Clock.
2.  Generate deterministic memory-reference traces representing
    different access patterns.
3.  Run all algorithms against identical traces and frame-capacity
    conditions.
4.  Measure simulated page faults and page-fault rate.
5.  Measure algorithm execution time and, where consistently measurable,
    replacement-decision overhead and throughput.
6.  Record relevant Docker/container resource information without
    confusing it with simulated paging results.
7.  Analyze differences by algorithm, workload type, and logical frame
    capacity.

### Research questions to operationalize

-   How do FIFO, LRU, and Clock compare in simulated page-fault count
    and page-fault rate across the selected workloads?
-   Does the relative performance of the algorithms vary with logical
    page-frame capacity?
-   How do workload access patterns affect the observed differences?
-   What execution-time and resource-use differences are observed when
    the simulators run in the selected container environment?

The final wording of research questions and hypotheses should be
confirmed with the research adviser and aligned with the final approved
protocol.

## 4. Experimental design

Use a **quantitative, controlled comparative experiment**.

### Algorithms

-   FIFO: evict the page that has been resident the longest.
-   LRU: evict the page whose most recent access is farthest in the
    past.
-   Clock: use a circular frame scan and reference bits to select a
    victim according to the Clock policy.

Each algorithm must receive the exact same input trace and logical frame
count for a matched experimental condition.

### Workload types

Initial workload categories:

1.  **Sequential:** references progress through a sequence of page
    identifiers.
2.  **Random:** references are selected using a documented pseudorandom
    generator and fixed seed.
3.  **Looping:** references repeatedly access a working set that may be
    larger than, equal to, or smaller than the frame capacity.
4.  **Mixed:** a documented combination of access patterns.

The generator must document how each pattern is created. Do not label a
trace "random," "looping," or "mixed" without recording its generation
rules and parameters.

### Initial experimental factors

  -----------------------------------------------------------------------
  Factor                              Initial planned values
  ----------------------------------- -----------------------------------
  Algorithm                           FIFO, LRU, Clock

  Workload                            Sequential, Random, Looping, Mixed

  Logical frame capacity              3, 5, 8, 10, 15 frames

  Trace length                        Initially 100,000 references;
                                      confirm through pilot testing

  Repetitions                         Initially at least 10 per
                                      condition, subject to final
                                      protocol

  Trace generation                    Deterministic, with recorded seeds
                                      and parameters
  -----------------------------------------------------------------------

These values were approved on 2026-11-26 and then amended as v2 the same day
(§12, `configs/experiment-v2.json`). The v2 pilot confirmed the settings now
produce meaningful variation; the earlier saturation and the amendment are
recorded in `docs/decision-log.md`. Any subsequent change must be documented
in the experiment configuration and research log.

### Fair-comparison rules

-   Use identical traces for all three algorithms within each matched
    condition.
-   Use fixed and recorded random seeds.
-   Do not generate a separate, easier trace for one algorithm.
-   Keep the trace length and logical frame count consistent across
    matched runs.
-   Record algorithm, workload, frame count, trace ID, seed, repetition,
    software version, and run configuration.
-   Rotate or randomize algorithm run order where practical to reduce
    order-related bias.
-   Keep trace generation and file I/O outside the algorithm timing
    interval unless the protocol explicitly defines otherwise.
-   Run correctness tests before collecting performance data.
-   Do not discard inconvenient results without a documented,
    pre-defined reason.

## 5. Outcome measures

### Primary outcome

**Simulated page-fault rate**

`page_fault_rate_percent = (simulated_page_faults / total_references) * 100`

Also record the raw simulated page-fault count.

### Secondary outcomes

-   Total algorithm execution time.
-   Replacement-decision overhead, if the timing method can isolate it
    consistently.
-   Throughput, such as references processed per second.
-   Container CPU and memory usage, where collected using a documented
    method.
-   Linux process minor/major page-fault counters, if included, clearly
    labeled as OS-level observations rather than simulated faults.

### Measurement requirements

-   Define precisely when timing starts and stops.
-   Exclude trace generation and file reading from algorithm timing
    unless intentionally measured as a separate metric.
-   Use the same timing method for every algorithm.
-   Record units (nanoseconds, microseconds, milliseconds, seconds,
    bytes, MiB, etc.).
-   Preserve raw run-level data; do not store only averages.
-   Report missing or failed runs and explain how they are handled.

## 6. Statistical analysis plan

The final analysis method should be reviewed with the research adviser
or statistician after pilot data are available.

Because algorithms are run against matched traces, preserve the
paired/repeated structure. Do not treat every measurement as independent
or pool all observations into a simple one-way ANOVA without checking
whether that model matches the design.

Potential analysis components:

-   Descriptive statistics: mean and standard deviation; median and
    interquartile range where useful.
-   A repeated-measures or mixed-effects approach with algorithm,
    workload, frame capacity, and relevant interactions, if supported by
    the final design and data.
-   Corrected post-hoc pairwise comparisons (for example, Holm
    adjustment) where appropriate.
-   Effect sizes, confidence intervals, and p-values.
-   Diagnostic checks for model assumptions and distributional issues.

Do not select a statistical test solely because it is familiar. The
final model must reflect the actual experimental unit, repeated trace
structure, and number of observations.

## 7. Technical architecture and implementation requirements

### Suggested repository layout

``` text
page-replacement-study/
├── README.md
├── src/
│   ├── fifo.c
│   ├── lru.c
│   └── clock.c
├── include/
│   └── (shared headers, if needed)
├── traces/
│   ├── generated/
│   └── (trace metadata or documentation)
├── results/
│   ├── raw/
│   └── processed/
├── scripts/
│   ├── (trace generation and analysis scripts)
│   └── (experiment orchestration scripts)
├── docker/
│   └── Dockerfile
├── tests/
│   └── (known-answer and correctness tests)
├── configs/
│   └── (versioned experiment configurations)
└── docs/
    └── (protocol, decisions, and run notes)
```

This is a suggested structure. Keep the project simple and avoid adding
unnecessary frameworks or dependencies.

### Simulator behavior

Each simulator should:

1.  Accept or read a memory-reference trace.
2.  Accept a positive logical frame capacity.
3.  Process references in their original order.
4.  Track hits and simulated page faults.
5.  Apply the specified replacement policy on a miss when all frames are
    occupied.
6.  Emit a machine-readable result record.
7.  Return a non-zero exit status for invalid input or execution errors.

At minimum, ensure:

`hits + simulated_page_faults = total_references`

Document page identifier format, input format, empty-trace behavior,
invalid frame-count behavior, and duplicate-page handling.

### Correctness testing

Create small hand-checkable traces with known expected behavior. Test:

-   Empty trace.
-   One unique page repeated.
-   More unique pages than available frames.
-   Repeated accesses that distinguish FIFO from LRU.
-   Clock reference-bit behavior.
-   Frame capacity of one.
-   Invalid or malformed input.
-   The invariant that hits plus faults equals references.

Use the same test traces for each algorithm where applicable. Do not
start the main experiment until correctness tests pass.

## 8. Docker and environment

The current development setup is:

-   Windows 11 host.
-   WSL2.
-   Ubuntu 26.04.1 LTS under WSL2.
-   GCC/G++ and Python 3 installed in Ubuntu.
-   Git installed in Ubuntu.
-   Visual Studio Code installed on Windows and connected to Ubuntu
    using the WSL extension.
-   Docker Desktop installed on Windows with WSL2 integration enabled.

Docker has been tested successfully using:

``` bash
docker run hello-world
docker ps
```

The Docker CLI is available from Ubuntu and runs without `sudo` for the
configured user.

### Container experiment principles

-   Build and run the simulator in a documented Docker image.
-   Record the Docker image tag or digest, build instructions, and
    relevant software versions.
-   Use Docker memory limits only as actual container resource
    constraints.
-   Do not convert a Docker memory limit into a frame count unless a
    separately justified and explicitly documented model is developed.
-   Run identical simulator inputs under comparable container settings.
-   Record the configured memory limit and observed resource use for
    each run.
-   Ensure the memory limit is sufficient for the simulator and trace
    input; avoid accidental out-of-memory termination.
-   Keep logical frame capacity as an explicit simulator input.

Example command pattern (adjust the image name and executable after
implementation):

``` bash
docker run --rm \
  --memory=512m \
  -v "$PWD:/work" \
  -w /work \
  page-replacement-study:latest \
  ./simulator --algorithm fifo --frames 5 --trace traces/generated/example.trace
```

This is illustrative. The final command-line interface and image name
must match the actual implementation.

## 9. Reproducibility and data management

Every experimental run should be reproducible from saved inputs and
configuration.

Record at least:

-   Unique run ID.
-   Date/time and machine/environment details.
-   Git commit hash or source version.
-   Docker image tag or digest.
-   Algorithm.
-   Workload type.
-   Trace filename and trace hash.
-   Trace length.
-   Random seed and generator parameters.
-   Logical frame capacity.
-   Repetition number.
-   Docker memory limit and other container settings.
-   Simulated hits and page faults.
-   Simulated page-fault rate.
-   Timing values and units.
-   Container/OS resource measurements, if collected.
-   Run status and error details.

Preserve raw output separately from processed summaries. Never silently
overwrite raw experimental results. Use version control for source code,
configuration, and documentation; avoid committing large generated
traces or result files unless the repository policy specifically
requires them.

## 10. Interpretation boundaries and limitations

The study evaluates implementations of classic page-replacement policies
in a user-space simulation. It does not modify the Linux kernel and does
not establish which policy the host Linux kernel or Docker uses
internally.

Synthetic traces are controlled inputs and may not represent every real
application workload. The simulator does not automatically model all
operating-system memory-management mechanisms, such as page tables, TLB
behavior, swapping, kernel reclaim, file-backed page cache, or storage
I/O. Claims must remain within the measured scope.

Do not claim that an algorithm is universally best. Interpret findings
by workload, frame capacity, and measured outcome.

## 11. Instructions for the AI coding agent

When working in this repository, follow these instructions:

1.  **Read this README first** before changing code or proposing
    architecture.
2.  Preserve the research distinction between simulated page faults,
    Linux page faults, and Docker/cgroup memory events.
3.  Implement FIFO, LRU, and Clock as user-space algorithms. Do not
    attempt to modify the Linux kernel's page-replacement policy.
4.  Keep the three implementations comparable and feed them identical
    traces for matched conditions.
5.  Prefer simple, readable C code (or C++ only if the project decision
    explicitly changes). Avoid unnecessary libraries and abstractions.
6.  Do not invent experimental results, benchmark values, citations, or
    research findings.
7.  Do not label untested code as verified. State what was run and what
    remains untested.
8.  Add correctness tests before performance benchmarking.
9.  Keep raw data, processed data, and source code separate.
10. Make experiment parameters configurable and record them with every
    run.
11. Do not change the approved research design, title, metrics, workload
    definitions, or statistical plan without explaining the reason and
    flagging the change for researcher/adviser approval.
12. If a requirement is ambiguous, ask the researcher rather than
    silently making a consequential assumption.
13. When making changes, update this README or the relevant
    documentation if commands, interfaces, or experiment procedures
    change.
14. Avoid collecting unrelated system information or personal data.
    Collect only information needed for reproducibility and research.

### Expected agent workflow

1.  Inspect the repository and this README.
2.  Report the current state of files and identify missing components.
3.  Propose a small implementation plan.
4.  Implement one component at a time.
5.  Compile with warnings enabled and fix warnings.
6.  Add and run correctness tests.
7.  Demonstrate a small example run with clearly labeled sample/test
    data.
8.  Only then help build the experiment runner and data collection
    workflow.
9.  Never present test/demo output as actual research findings.

## 12. Decisions (confirmed)

Baseline values were confirmed by the researcher on 2026-11-26 and used for
the v1 run. They were amended the same day by `configs/experiment-v2.json`,
which is the **current approved protocol** used for the reported run: added
the `locality` workload and reduced spans/loop sizes; all other values below
are unchanged. See `docs/decision-log.md`. The final inferential statistical
model remains a separate approval item.

-   Final trace length: 100,000 references.
-   Final number of repetitions: 10.
-   Exact workload-generation rules and parameters.
-   Docker memory limit: fixed environmental setting, not an experimental factor.
-   Container settings: memory `512m`, `cpus=1`.
-   OS-level minor/major page-fault counters and cgroup metrics: not included.
-   Final statistical model: still pending adviser/statistician approval; outputs remain descriptive.
-   Final command-line interface and output schema: approved as implemented.

Decisions are recorded in `docs/decision-log.md`.

## 13. Current project status

### Environment setup

-   [x] WSL2 installed.
-   [x] Ubuntu 26.04.1 LTS installed and initialized.
-   [x] GCC/G++ toolchain installed.
-   [x] Python 3 installed (reported version: 3.14.4).
-   [x] Git installed (reported version: 2.53.0).
-   [x] VS Code installed on Windows.
-   [x] VS Code WSL connection working.
-   [x] Docker Desktop installed and integrated with Ubuntu.
-   [x] `docker run hello-world` succeeded.
-   [x] `docker ps` succeeded.

### Research implementation

-   [x] Confirm final experimental protocol (approved by researcher 2026-11-26).
-   [x] Create source and test directories.
-   [x] Implement FIFO simulator.
-   [x] Implement LRU simulator.
-   [x] Implement Clock simulator.
-   [x] Create hand-checked correctness tests.
-   [x] Implement reproducible trace generator.
-   [x] Define result schema and raw-data format (approved; see `docs/decision-log.md`).
-   [x] Create Dockerfile and experiment runner (image build and container run verified; see `docs/decision-log.md`).
-   [ ] Conduct pilot experiment.
-   [ ] Finalize statistical analysis plan.
-   [x] Run full experiment and analyze actual results (`results/proposed-full-experiment/`, v1; `results/experiment-v2/`, current).
-   [x] Amend saturated workload parameters and re-run (v2 approved 2026-11-26).

## 14. Implementation quick reference (as built)

Run these from the repository root in Ubuntu/WSL. OpenCode reaches this
directory as a WSL UNC path from Windows, so Linux commands must be routed
through `wsl -d Ubuntu -- bash -lc "..."`.

``` bash
make                       # build build/simulator with -Wall -Wextra -Wpedantic
make test                  # build + known-answer correctness tests

# One simulator run
build/simulator --algorithm fifo --frames 5 \
  --trace results/demo/traces/sequential_rep1.trace

# Generate one deterministic trace
python3 scripts/generate_trace.py --workload random --length 100000 --seed 7 \
  --output traces/generated/random_s7.trace

# Current approved experiment (v2), then descriptive summary
python3 scripts/run_experiment.py --config configs/experiment-v2.json
python3 scripts/analyze.py --input results/experiment-v2/raw/results.jsonl \
  --output-dir results/experiment-v2/processed

# Demo (sample data only)
python3 scripts/run_experiment.py --config configs/demo.json
python3 scripts/analyze.py --input results/demo/raw/results.jsonl \
  --output-dir results/demo/processed

# Inferential analysis (approved mixed-effects model; uses a local venv)
python3 -m venv .venv
.venv/bin/python -m pip install numpy pandas scipy statsmodels
.venv/bin/python scripts/infer.py

# Container image: records digest and in-image toolchain versions
bash docker/build.sh
bash docker/run-example.sh
```

-   `configs/experiment-v2.json` is the **current approved** protocol; `configs/experiment.json` is the superseded v1; `configs/demo.json` is a small sample-data config.
-   Raw run records go to `results/<label>/raw/results.jsonl`, the run manifest to `results/<label>/run_manifest.json`, traces plus generation metadata to `results/<label>/traces/`, and descriptive summaries to `results/<label>/processed/`.
-   Invalid input exits non-zero: 2 bad arguments, 3 bad input, 4 simulation error, 5 output error.
-   The image entrypoint is `/src/build/simulator`, so the Docker command omits the leading `./simulator` shown in the illustrative §8 example.
-   `scripts/infer.py` needs its statistical packages in `.venv/`; all other scripts run on system `python3`. Its specification and approval are in `results/experiment-v2/processed/inferential/model_spec.json`; outputs (pairwise contrasts, effect sizes, diagnostics) are in the same directory.
-   `docs/manuscript-source.md` consolidates the verified design, results and statistics for manuscript drafting.
-   `docs/decision-log.md` records approvals and remaining items. `results/demo/` is sample/test data, never a research finding.

------------------------------------------------------------------------

**Core rule:** This repository is an experimental research project, not
merely an algorithm demo. Correctness, fair comparison, reproducibility,
transparent measurement, and honest reporting take priority over adding
features.
