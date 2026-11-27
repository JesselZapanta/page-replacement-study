#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-page-replacement-study:latest}"

docker build -f docker/Dockerfile -t "$IMAGE" .
echo "--- image ---"
docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}' 2>/dev/null \
  || echo "no registry digest (locally built image): record the image ID instead"
docker image inspect "$IMAGE" --format 'ID={{.Id}} Created={{.Created}}'
echo "--- toolchain inside image ---"
docker run --rm --entrypoint bash "$IMAGE" -lc 'gcc --version | head -1; python3 --version'
