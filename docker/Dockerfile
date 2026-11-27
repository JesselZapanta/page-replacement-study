# Build from the repository root (not from docker/):
#   docker build -f docker/Dockerfile -t page-replacement-study:latest .
#
# Base matches the documented host/WSL development environment (README §8).
# docker/build.sh records the image digest and the toolchain versions inside it.
FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential python3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY . /src
RUN make -C /src

RUN groupadd -r prs && useradd -r -g prs -m prs
USER prs
WORKDIR /work

ENTRYPOINT ["/src/build/simulator"]
