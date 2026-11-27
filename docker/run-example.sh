#!/usr/bin/env bash
set -euo pipefail

# Demonstration only: the trace and output are sample data, not findings.
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-page-replacement-study:latest}"
MEMORY="${MEMORY:-512m}"
TRACE="${1:-results/demo/traces/sequential_rep1.trace}"
FRAMES="${2:-5}"

docker run --rm \
  --memory="$MEMORY" \
  -v "$PWD:/work" \
  -w /work \
  "$IMAGE" \
  --algorithm fifo --frames "$FRAMES" --trace "$TRACE" \
  --run-id demo-container-example
