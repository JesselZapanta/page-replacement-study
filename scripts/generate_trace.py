#!/usr/bin/env python3
"""Deterministic memory-reference trace generator.

Generation rules (version 2.0), all reproducible from seed + parameters:
  sequential : page = (start_page + i) % span
  random     : page = random.Random(seed).randrange(span), one draw per reference
  looping    : page = (start_page + (i % loop_size)) % span
  mixed      : split into segments of `segment_length`; for each segment choose
               sequential/random/looping with the same seeded RNG, using the
               segment's global offset for the looping rule.
  locality   : with probability `hot_prob` draw from a hot set of
               `hot_set_size` pages (starting at start_page), otherwise draw
               uniformly from `span`; both decisions use the seeded RNG.

Blank lines and #-comments are ignored by the simulator; none are emitted here.
"""

import argparse
import hashlib
import json
import platform
import random
import sys
from pathlib import Path

from common import utc_now

GENERATOR_VERSION = "2.0"

WORKLOADS = ("sequential", "random", "looping", "mixed", "locality")


def generate(workload, length, seed, params=None):
    """Return a list of `length` non-negative page ids. See module docstring."""
    if workload not in WORKLOADS:
        raise ValueError(f"unknown workload: {workload}")
    if length < 0:
        raise ValueError("length must be non-negative")

    params = dict(params or {})
    start = int(params.get("start_page", 0))
    span = int(params.get("span", max(1, length)))
    if start < 0 or span < 1:
        raise ValueError("start_page must be >= 0 and span must be >= 1")

    rng = random.Random(seed)

    if workload == "sequential":
        return [(start + i) % span for i in range(length)]

    if workload == "random":
        return [rng.randrange(span) for _ in range(length)]

    if workload == "looping":
        loop_size = int(params.get("loop_size", max(1, span // 10)))
        if loop_size < 1:
            raise ValueError("loop_size must be >= 1")
        return [(start + (i % loop_size)) % span for i in range(length)]

    if workload == "locality":
        hot_size = int(params.get("hot_set_size", 4))
        hot_prob = float(params.get("hot_prob", 0.8))
        if hot_size < 1 or not 0.0 <= hot_prob <= 1.0:
            raise ValueError("hot_set_size must be >= 1 and hot_prob in [0, 1]")
        hot_size = min(hot_size, span)
        refs = []
        for _ in range(length):
            upper = hot_size if rng.random() < hot_prob else span
            refs.append((start + rng.randrange(upper)) % span)
        return refs

    segment = int(params.get("segment_length", max(1, length // 10)))
    loop_size = int(params.get("loop_size", max(1, span // 10)))
    if segment < 1 or loop_size < 1:
        raise ValueError("segment_length and loop_size must be >= 1")

    refs = []
    for offset in range(0, length, segment):
        pattern = rng.choice(("sequential", "random", "looping"))
        seg_len = min(segment, length - offset)
        if pattern == "sequential":
            refs.extend((start + offset + j) % span for j in range(seg_len))
        elif pattern == "random":
            refs.extend(rng.randrange(span) for _ in range(seg_len))
        else:
            refs.extend((start + (offset + j) % loop_size) % span
                        for j in range(seg_len))
    return refs


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_trace(path, refs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for ref in refs:
            handle.write(f"{ref}\n")


def make_metadata(path, workload, length, seed, params):
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "generator_version": GENERATOR_VERSION,
        "python_version": platform.python_version(),
        "workload": workload,
        "length": length,
        "seed": seed,
        "parameters": dict(params or {}),
        "trace_path": str(path),
        "trace_sha256": sha256_file(path),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", required=True, choices=WORKLOADS)
    parser.add_argument("--length", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metadata", type=Path,
                        help="metadata path (default: <output>.metadata.json)")
    parser.add_argument("--start-page", type=int, default=0)
    parser.add_argument("--span", type=int, default=None,
                        help="page id space size (default: max(1, length))")
    parser.add_argument("--loop-size", type=int, default=None)
    parser.add_argument("--segment-length", type=int, default=None)
    parser.add_argument("--hot-set-size", type=int, default=None)
    parser.add_argument("--hot-prob", type=float, default=None)
    args = parser.parse_args()

    params = {"start_page": args.start_page}
    if args.span is not None:
        params["span"] = args.span
    if args.loop_size is not None:
        params["loop_size"] = args.loop_size
    if args.segment_length is not None:
        params["segment_length"] = args.segment_length
    if args.hot_set_size is not None:
        params["hot_set_size"] = args.hot_set_size
    if args.hot_prob is not None:
        params["hot_prob"] = args.hot_prob

    try:
        refs = generate(args.workload, args.length, args.seed, params)
    except ValueError as exc:
        parser.error(str(exc))

    metadata_path = args.metadata or Path(f"{args.output}.metadata.json")
    write_trace(args.output, refs)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(make_metadata(args.output, args.workload, args.length,
                                 args.seed, params), indent=2) + "\n",
        encoding="utf-8")
    print(f"wrote {args.output} ({len(refs)} references, "
          f"sha256={sha256_file(args.output)[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
