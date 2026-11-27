#!/usr/bin/env python3
"""Run matched simulator conditions and write raw, reproducible run records.

Each workload/repetition gets one deterministic trace that is shared by all
algorithms and all frame capacities. Raw records are append-only: an existing
results.jsonl is refused unless --force is given.
"""

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from common import utc_now
from generate_trace import generate, make_metadata, sha256_file, write_trace

REPO_ROOT = Path(__file__).resolve().parent.parent


def git_commit():
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else "not-a-git-repo"
    except FileNotFoundError:
        return "git-unavailable"


def git_describe():
    try:
        proc = subprocess.run(["git", "describe", "--tags", "--exact-match", "HEAD"],
                              cwd=REPO_ROOT, capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except FileNotFoundError:
        return None


def docker_digest(image):
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image,
             "--format", "{{index .RepoDigests 0}}"],
            cwd=REPO_ROOT, capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except FileNotFoundError:
        return None


def resolve_simulator(spec):
    path = Path(spec)
    return path if path.is_absolute() else REPO_ROOT / path


def run_command(config, simulator, trace_path, algorithm, frames, run_id):
    exec_cfg = config["execution"]
    rel_trace = str(trace_path.relative_to(REPO_ROOT))
    flags = ["--algorithm", algorithm, "--frames", str(frames),
             "--trace", rel_trace, "--run-id", run_id]
    if exec_cfg.get("mode") == "docker":
        memory = exec_cfg["docker_memory_limit"]
        cpus = exec_cfg["docker_cpus"]
        # The image ENTRYPOINT is already /src/build/simulator, so no binary
        # path is passed after the image name.
        return ["docker", "run", "--rm", f"--memory={memory}", f"--cpus={cpus}",
                "-v", f"{REPO_ROOT}:/work", "-w", "/work",
                exec_cfg["docker_image"], *flags]
    return [str(simulator), *flags]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--simulator", default=None,
                        help="override execution.simulator from the config")
    parser.add_argument("--output-dir", default=None,
                        help="default: results/<config label>")
    parser.add_argument("--force", action="store_true",
                        help="allow writing into an existing result directory")
    parser.add_argument("--use-docker", action="store_true",
                        help="run the simulator inside the configured Docker image")
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if args.use_docker:
        config["execution"]["mode"] = "docker"

    exec_cfg = config["execution"]
    simulator = resolve_simulator(args.simulator or exec_cfg["simulator"])
    if not simulator.is_file():
        parser.error(f"simulator not found: {simulator}")

    label = config["label"]
    output_dir = (Path(args.output_dir).resolve() if args.output_dir
                  else REPO_ROOT / "results" / label)
    raw_dir = output_dir / "raw"
    trace_dir = output_dir / "traces"
    raw_path = raw_dir / "results.jsonl"
    if raw_path.exists() and not args.force:
        parser.error(f"{raw_path} already exists; use --force only if overwriting is intended")

    raw_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    started = utc_now()
    commit_hash = git_commit()
    commit_tag = git_describe()
    image_digest = (docker_digest(exec_cfg["docker_image"])
                    if exec_cfg.get("mode") == "docker" else None)
    algorithms = config["algorithms"]
    frames_list = config["frames"]
    workloads = config["workloads"]
    repetitions = int(config["repetitions"])
    length = int(config["trace_length"])
    base_seed = int(config["base_seed"])
    is_demo = "demo" in label.lower()

    records = []
    failed = []
    total = len(workloads) * repetitions * len(frames_list) * len(algorithms)
    done = 0

    for workload_index, workload in enumerate(workloads):
        params = config["trace_generation"][workload]
        for repetition in range(1, repetitions + 1):
            seed = base_seed + workload_index * 1000 + repetition
            trace_path = trace_dir / f"{workload}_rep{repetition}.trace"
            refs = generate(workload, length, seed, params)
            write_trace(trace_path, refs)
            metadata_path = Path(f"{trace_path}.metadata.json")
            metadata_path.write_text(
                json.dumps(make_metadata(trace_path, workload, length, seed, params),
                           indent=2) + "\n", encoding="utf-8")
            trace_hash = sha256_file(trace_path)

            for frame_index, frames in enumerate(frames_list):
                shift = (workload_index + repetition + frame_index) % len(algorithms)
                ordered_algorithms = algorithms[shift:] + algorithms[:shift]
                for position, algorithm in enumerate(ordered_algorithms, start=1):
                    done += 1
                    run_id = f"{label}-{algorithm}-{workload}-f{frames}-r{repetition}"
                    cmd = run_command(config, simulator, trace_path,
                                      algorithm, frames, run_id)
                    proc = subprocess.run(cmd, cwd=REPO_ROOT,
                                          capture_output=True, text=True)
                    record = {
                        "schema_version": 1,
                        "run_id": run_id,
                        "generated_at_utc": utc_now(),
                        "label": label,
                        "is_demo": is_demo,
                        "execution_mode": exec_cfg.get("mode", "local"),
                        "docker_image": (exec_cfg.get("docker_image")
                                         if exec_cfg.get("mode") == "docker"
                                         else None),
                        "docker_memory_limit": exec_cfg.get("docker_memory_limit"),
                        "docker_image_digest": image_digest,
                        "git_commit": commit_hash,
                        "git_tag": commit_tag,
                        "algorithm": algorithm,
                        "algorithm_order": list(ordered_algorithms),
                        "run_order_position": position,
                        "run_order_rule": "rotate by (workload_index + repetition + frame_index) mod 3",
                        "workload": workload,
                        "frames": frames,
                        "trace_path": str(trace_path.relative_to(REPO_ROOT)),
                        "trace_sha256": trace_hash,
                        "trace_length": len(refs),
                        "seed": seed,
                        "repetition": repetition,
                        "python_version": platform.python_version(),
                    }
                    if proc.returncode == 0:
                        try:
                            record.update(json.loads(proc.stdout))
                        except json.JSONDecodeError as exc:
                            proc.returncode = 99
                            proc.stderr += f"; invalid simulator JSON: {exc}"
                    if proc.returncode != 0:
                        record["status"] = "error"
                        record["exit_code"] = proc.returncode
                        record["error"] = proc.stderr.strip()[:2000]
                        failed.append(run_id)
                    records.append(record)
                    print(f"[{done}/{total}] {run_id}: {record['status']}")

    with open(raw_path, "w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    manifest = {
        "schema_version": 1,
        "label": label,
        "is_demo": is_demo,
        "started_utc": started,
        "finished_utc": utc_now(),
        "config_path": (str(config_path.relative_to(REPO_ROOT))
                        if config_path.is_relative_to(REPO_ROOT) else str(config_path)),
        "config": config,
        "git_commit": commit_hash,
        "git_tag": commit_tag,
        "docker_image_digest": image_digest,
        "run_order_rule": "rotate by (workload_index + repetition + frame_index) mod 3",
        "simulator": str(simulator.relative_to(REPO_ROOT)),
        "planned_runs": total,
        "completed_runs": sum(1 for r in records if r["status"] == "ok"),
        "failed_runs": len(failed),
        "failed_run_ids": failed,
        "raw_records": str(raw_path.relative_to(REPO_ROOT)),
        "note": ("Demo/sample data only; never report as research findings."
                 if is_demo else
                 ("Approved protocol (docs/decision-log.md)."
                  if "approved" in str(config.get("status", "")).lower()
                  else "Configuration values are not yet approved (README section 12).")),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"\nwrote {raw_path} ({len(records)} records, {len(failed)} failures)")
    if is_demo:
        print("DEMO DATA ONLY - do not present these numbers as research findings.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
