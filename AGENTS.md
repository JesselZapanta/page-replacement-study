# AGENTS.md

## Orientation
- Experimental research project, not an algorithm demo. `README.md` is the authoritative design brief — read it (especially §2, §11, §12) before changing code or architecture.
- Current state: simulator, `Makefile`, known-answer tests, trace generator, experiment runner, analyzer, inference script, Docker files and configs exist; README §14 lists exact commands. The current approved protocol is `configs/experiment-v2.json` (v1 superseded); data is in `results/experiment-v2/`, including `processed/inferential/`. `results/proposed-full-experiment/` is the retained v1 run and `results/demo/` is sample data.
- Implement in plain C and keep the three algorithms structurally comparable; no extra libraries or frameworks unless the project decision explicitly changes (README §11).

## Hard constraints
- Keep these distinct in all code, docs, and analysis: simulated page faults and logical frames (simulator), versus Linux minor/major faults and Docker/cgroup memory (environment). Docker memory limits are not frame counts, and nothing here changes the kernel's page-replacement policy (README §2, §8).
- Never fabricate results, benchmarks, citations, or "verified" status. State exactly what was run; test/demo output is never a research finding.
- Correctness tests must pass before any performance benchmarking. Required invariant: `hits + simulated_page_faults == total_references`.
- Matched conditions: same trace, same frame count, recorded seed for FIFO/LRU/Clock. Preserve raw run records separately from processed summaries and log run metadata (algorithm, workload, trace hash, seed, repetition, versions, container settings).
- README §12 protocol values (trace length, repetitions, workload rules, Docker settings, OS-counter policy, CLI/output schema) are approved as recorded in `docs/decision-log.md`. The mixed-effects inferential model was also approved on 2026-11-26 and executed by `scripts/infer.py`. Flag any further change to design, title, metrics, workloads, or statistics for researcher/adviser approval; ask when a consequential requirement is ambiguous rather than assuming.

## Environment and commands
- The repo lives at the WSL UNC path `\\wsl$\Ubuntu\home\jessel_zapanta\projects\page-replacement-study`. The harness shell is Windows PowerShell, so run Linux tools through `wsl -d Ubuntu -- bash -lc "..."`.
- Ubuntu has GCC/G++, Python 3, and Git; Docker Desktop WSL2 integration works and `docker` runs without `sudo`.
- `make` builds `build/simulator` with `-Wall -Wextra -Wpedantic`; `make test` runs the known-answer suite. Fix warnings rather than suppressing them.
- The image `page-replacement-study:latest` now exists (digest in `docs/decision-log.md`); its entrypoint is `/src/build/simulator`, so container commands omit the leading `./simulator` from README §8's illustrative example.
