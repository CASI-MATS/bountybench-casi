#!/usr/bin/env python3
"""
Parallel BountyBench Runner
============================
Runs multiple BountyBench workflow jobs in parallel on a single machine,
with full isolation of Docker resources, git state, and filesystem.

Each job gets its own:
  - Deep-copy of the repo (git/filesystem isolation)
  - Docker network (no DNS/hostname collisions between jobs)
  - COMPOSE_PROJECT_NAME (no docker-compose container name collisions)
  - Prefixed container_name: entries in docker-compose files
  - Separate log collection back to the original repo

Usage:
    python run_parallel.py config.yaml
    python run_parallel.py config.yaml --max-parallel 4
    python run_parallel.py config.yaml --workdir /tmp/bb_runs
    python run_parallel.py config.yaml --keep-clones

Config YAML format (same as run_experiments.py):
    workflow_type: exploit_workflow
    trials_per_config: 1
    tasks:
      - task_dir: bountytasks/lunary
        bounty_number: "0"
    models:
      - name: anthropic/claude-3-5-sonnet-20241022
    phase_iterations: 1
"""

import argparse
import asyncio
import itertools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"

# Directories to skip when cloning (saves disk and time).
# The runner falls back to sys.executable if clone's venv is missing.
CLONE_SKIP_DIRS = {"venv", ".venv", "node_modules", "__pycache__", ".mypy_cache"}


def _log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def _ensure_list(val: Any) -> list:
    return val if isinstance(val, list) else [val]


def _load_config(path: str) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Job generation (mirrors run_experiments.py logic)
# ---------------------------------------------------------------------------

def generate_jobs(config: Dict) -> List[Dict]:
    """Generate job descriptors from the YAML config."""
    workflow_type = config["workflow_type"]
    trials = config.get("trials_per_config", 1)
    tasks = config.get("tasks", [])
    models = config.get("models", [])
    phase_iterations_list = _ensure_list(config.get("phase_iterations", [1]))
    vuln_types = _ensure_list(config.get("vulnerability_type", []))
    mock_model = config.get("use_mock_model", False)

    params = [tasks, models, phase_iterations_list]
    if vuln_types and workflow_type.startswith("detect_"):
        params.append(vuln_types)

    jobs: List[Dict] = []
    for combo in itertools.product(*params):
        task, model, iters = combo[:3]
        vuln = combo[3] if len(combo) > 3 else None
        for _trial in range(trials):
            jobs.append({
                "workflow_type": workflow_type,
                "task_dir": task["task_dir"],
                "bounty_number": str(task["bounty_number"]),
                "model": model["name"],
                "use_mock_model": mock_model,
                "phase_iterations": iters,
                "vulnerability_type": vuln,
            })
    return jobs


# ---------------------------------------------------------------------------
# Port-conflict grouping
# ---------------------------------------------------------------------------

def _get_ports_for_task(task_dir: str) -> List[int]:
    """Try to import the project's port utility; fall back to empty list."""
    try:
        sys.path.insert(0, os.getcwd())
        from utils.get_task_ports import get_ports_for_directory
        return get_ports_for_directory(task_dir)
    except Exception:
        return []


def group_jobs_by_port_conflict(jobs: List[Dict]) -> List[List[Dict]]:
    """
    Group jobs into parallel-safe lists.

    Since each job's docker-compose host ports are remapped to 0 (Docker
    auto-assigns free ports), there are no port collisions even for the
    same task_dir+bounty.  Every job gets its own group and can run fully
    in parallel.
    """
    # Each job is its own group — full parallelism
    return [[job] for job in jobs]


# ---------------------------------------------------------------------------
# Clone management
# ---------------------------------------------------------------------------

def create_clone(source_repo: Path, workdir: Path, job_id: str) -> Path:
    """
    Create a deep copy of the BountyBench repo for an isolated run.
    Skips venv/node_modules/__pycache__ to save disk.
    """
    clone_dir = workdir / f"bb_job_{job_id}"
    _log(f"[{job_id}] Cloning repo -> {clone_dir}")

    def _ignore(directory: str, contents: list) -> list:
        """Skip large/unnecessary directories."""
        ignored = []
        for item in contents:
            if item in CLONE_SKIP_DIRS:
                ignored.append(item)
        return ignored

    if IS_WINDOWS:
        # robocopy is much faster on Windows; /MIR mirrors, /MT for threads
        xd_args = []
        for skip in CLONE_SKIP_DIRS:
            xd_args.extend([skip])
        subprocess.run(
            ["robocopy", str(source_repo), str(clone_dir), "/MIR",
             "/NFL", "/NDL", "/NJH", "/NJS", "/MT:8",
             "/XD"] + xd_args,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # robocopy excludes .git too broadly; copy root .git separately
        src_git = source_repo / ".git"
        dst_git = clone_dir / ".git"
        if src_git.is_dir() and not dst_git.exists():
            shutil.copytree(src_git, dst_git, symlinks=True)
    else:
        shutil.copytree(source_repo, clone_dir, symlinks=True, ignore=_ignore)

    _log(f"[{job_id}] Clone ready ({_dir_size_mb(clone_dir):.0f} MB)")
    return clone_dir


def _dir_size_mb(path: Path) -> float:
    """Estimate directory size in MB (best-effort)."""
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024 * 1024)
    except Exception:
        return 0.0


def cleanup_clone(clone_dir: Path) -> None:
    """Remove a cloned directory tree."""
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["cmd", "/c", "rmdir", "/s", "/q", str(clone_dir)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            shutil.rmtree(clone_dir, ignore_errors=True)
    except Exception as e:
        _log(f"Warning: failed to clean up {clone_dir}: {e}", "WARN")


# ---------------------------------------------------------------------------
# Per-job isolation: patch clone files
# ---------------------------------------------------------------------------

NETWORK_LITERAL = "shared_net"


def patch_clone_for_isolation(clone_dir: Path, job_id: str) -> str:
    """
    Patch all hardcoded Docker resource names and unsafe git operations
    in the clone so this job's containers/networks/volumes don't collide
    with any other job, and git operations stay within the clone.

    Returns the per-job network name.
    """
    job_network = f"bb_net_{job_id}"
    compose_prefix = f"bb_{job_id}"

    # --- 1. Replace "shared_net" with per-job network in all Python files ---
    _patch_shared_net_in_python(clone_dir, job_network)

    # --- 2. Patch docker-compose files in bountytasks ---
    #   a) Replace/add external network references to use job_network
    #   b) Prefix any container_name: values to avoid collisions
    _patch_docker_compose_files(clone_dir, job_network, compose_prefix)

    # --- 3. Fix git_utils.py: hardcoded chown on ~/bountybench/bountytasks ---
    #   Every _run_git_command() call does:
    #     subprocess.run(["sudo", "chown", "-r", "ubuntu", "~/bountybench/bountytasks"])
    #   This is a hardcoded absolute path that:
    #     a) Races with all other parallel jobs doing chown on the same tree
    #     b) Is irrelevant inside our clone (wrong path entirely)
    #     c) May fail with "sudo: not found" or permission errors on EC2
    #   Fix: remove the chown line entirely from the clone's git_utils.py
    _patch_git_utils(clone_dir)

    return job_network


def _patch_git_utils(clone_dir: Path) -> None:
    """
    Fix dangerous/racy git operations in the clone:

    1. Remove the hardcoded `sudo chown -r ubuntu ~/bountybench/bountytasks`
       from _run_git_command() — it runs on every git command and hits a
       shared path outside the clone.

    2. Remove `use_sudo=True` from git_checkout/git_clean calls — sudo git
       can change file ownership and break parallel jobs sharing the Docker
       daemon. The clone is owned by the current user anyway.
    """
    git_utils = clone_dir / "utils" / "git_utils.py"
    if not git_utils.exists():
        return

    try:
        content = git_utils.read_text(encoding="utf-8")
        original = content

        # Remove the chown line (may have varying whitespace)
        content = re.sub(
            r'^\s*subprocess\.run\(\["sudo",\s*"chown",\s*"-r",\s*"ubuntu",\s*"~/bountybench/bountytasks"\]\)\s*\n',
            '',
            content,
            flags=re.MULTILINE,
        )

        # Replace use_sudo=True with use_sudo=False in function calls
        # This prevents `sudo git clean` from changing file ownership
        content = content.replace("use_sudo=True", "use_sudo=False")

        if content != original:
            git_utils.write_text(content, encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        pass


def _patch_shared_net_in_python(clone_dir: Path, job_network: str) -> None:
    """
    Replace all occurrences of the literal string "shared_net" in Python files.
    This covers:
      - workflows/utils.py        (network creation)
      - resources/kali_env_resource.py  (network= param)
      - agents/*/agent.py         (network= param)
    """
    # Only scan directories that contain the hardcoded references
    scan_dirs = ["workflows", "resources", "agents", "tests"]

    for scan_dir in scan_dirs:
        base = clone_dir / scan_dir
        if not base.exists():
            continue
        for py_file in base.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                if NETWORK_LITERAL not in content:
                    continue
                # Replace both quoted forms: "shared_net" and 'shared_net'
                new_content = content.replace(
                    f'"{NETWORK_LITERAL}"', f'"{job_network}"'
                ).replace(
                    f"'{NETWORK_LITERAL}'", f"'{job_network}'"
                )
                if new_content != content:
                    py_file.write_text(new_content, encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                pass


def _patch_docker_compose_files(
    clone_dir: Path, job_network: str, compose_prefix: str
) -> None:
    """
    Walk all docker-compose.yml files in the clone and:
      1. Replace any 'shared_net' network references with job_network
      2. Prefix any `container_name:` values with compose_prefix to avoid
         collisions (COMPOSE_PROJECT_NAME doesn't help if container_name is set)
    """
    for dc_path in clone_dir.rglob("docker-compose.yml"):
        _patch_one_compose_file(dc_path, job_network, compose_prefix)
    for dc_path in clone_dir.rglob("docker-compose.yaml"):
        _patch_one_compose_file(dc_path, job_network, compose_prefix)


def _patch_one_compose_file(
    dc_path: Path, job_network: str, compose_prefix: str
) -> None:
    """Patch a single docker-compose file."""
    try:
        content = dc_path.read_text(encoding="utf-8")
        original = content

        # Replace shared_net references
        content = content.replace(NETWORK_LITERAL, job_network)

        # Prefix container_name values.
        # Matches lines like:  container_name: some-name
        # or:                  container_name: "some-name"
        def _prefix_container_name(m: re.Match) -> str:
            indent = m.group(1)
            name = m.group(2).strip().strip("'\"")
            return f'{indent}container_name: {compose_prefix}-{name}'

        content = re.sub(
            r'^(\s*)container_name:\s*(.+)$',
            _prefix_container_name,
            content,
            flags=re.MULTILINE,
        )

        # Remap host ports to 0 (Docker auto-assigns a free port).
        # This prevents port collisions when running multiple jobs for the
        # same task in parallel.  The container port stays the same, and
        # container-to-container traffic uses Docker DNS — not host ports.
        # Matches:  - "8080:80"  or  - 8080:80  or  - "8080:80/tcp"
        content = re.sub(
            r'^(\s*)-\s*(["\']?)(\d+):(\d+(?:/\w+)?)\2\s*$',
            lambda m: f'{m.group(1)}- {m.group(2)}0:{m.group(4)}{m.group(2)}',
            content,
            flags=re.MULTILINE,
        )

        if content != original:
            dc_path.write_text(content, encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        pass


# ---------------------------------------------------------------------------
# Docker network lifecycle
# ---------------------------------------------------------------------------

def create_job_network(network_name: str) -> None:
    """Create a Docker network for this job."""
    subprocess.run(
        ["docker", "network", "create", network_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def destroy_job_network(network_name: str) -> None:
    """Remove the per-job Docker network (best-effort)."""
    subprocess.run(
        ["docker", "network", "rm", network_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Targeted container cleanup (NOT global prune)
# ---------------------------------------------------------------------------

def cleanup_job_containers(compose_prefix: str) -> None:
    """
    Remove only Docker containers belonging to this job's compose project.
    Uses label filtering — docker-compose labels containers with the project name.
    """
    try:
        # List containers with this compose project label (running or stopped)
        result = subprocess.run(
            [
                "docker", "ps", "-a", "-q",
                "--filter", f"label=com.docker.compose.project={compose_prefix}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        container_ids = result.stdout.strip().split()
        if container_ids:
            subprocess.run(
                ["docker", "rm", "-f"] + container_ids,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60,
            )
    except Exception:
        pass


def cleanup_kali_containers_by_network(network_name: str) -> None:
    """
    Remove any containers still connected to this job's network.
    Catches Kali containers that aren't managed by docker-compose.
    """
    try:
        # Find containers on this network
        result = subprocess.run(
            [
                "docker", "network", "inspect", network_name,
                "--format", "{{range .Containers}}{{.Name}} {{end}}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        names = result.stdout.strip().split()
        for name in names:
            if name:
                subprocess.run(
                    ["docker", "rm", "-f", name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=30,
                )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Log collection
# ---------------------------------------------------------------------------

def _collect_logs(clone_dir: Path, logs_base: Path, job_id: str) -> None:
    """
    Collect logs from a job's clone into shared parallel_logs subdirectories.

    BountyBench produces logs in several places (all relative to cwd):
      - logs/          JSON workflow result logs
      - full_logs/     Verbose archived text logs

    Files are copied into shared folders with job_id prefixes to avoid
    name collisions:
      parallel_logs/logs/{job_id}__{original_filename}
      parallel_logs/full_logs/{job_id}__{original_filename}
    """
    for dir_name in ["logs", "full_logs"]:
        src = clone_dir / dir_name
        if not src.exists() or not src.is_dir():
            continue
        dst_dir = logs_base / dir_name
        dst_dir.mkdir(parents=True, exist_ok=True)
        try:
            for src_file in src.rglob("*"):
                if not src_file.is_file():
                    continue
                # Preserve subdirectory structure relative to src, prefixed with job_id
                rel = src_file.relative_to(src)
                dst_file = dst_dir / f"{job_id}__{rel}"
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
        except Exception as e:
            _log(f"[{job_id}] Warning: failed to copy {dir_name}/: {e}", "WARN")


# ---------------------------------------------------------------------------
# Build the CLI command
# ---------------------------------------------------------------------------

def build_command(job: Dict, clone_dir: Path) -> List[str]:
    """Build the `python -m workflows.runner ...` command for a job."""
    # Try clone's venv first, fall back to current interpreter
    if IS_WINDOWS:
        venv_python = clone_dir / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = clone_dir / "venv" / "bin" / "python"

    python = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [
        python,
        "-m", "workflows.runner",
        "--workflow-type", job["workflow_type"],
        "--task_dir", job["task_dir"],
        "--bounty_number", job["bounty_number"],
        "--phase_iterations", str(job["phase_iterations"]),
    ]

    # Model or mock (mutually exclusive)
    if job.get("use_mock_model"):
        cmd.append("--use_mock_model")
    else:
        cmd.extend(["--model", job["model"]])

    if job.get("vulnerability_type") and job["workflow_type"].startswith("detect_"):
        cmd.extend(["--vulnerability_type", job["vulnerability_type"]])

    return cmd


# ---------------------------------------------------------------------------
# Run a single job
# ---------------------------------------------------------------------------

async def run_job(
    job: Dict,
    job_id: str,
    source_repo: Path,
    workdir: Path,
    keep_clones: bool,
    semaphore: asyncio.Semaphore,
) -> Dict:
    """
    Run one BountyBench workflow job in a fully isolated clone.
    """
    result = {
        "job_id": job_id,
        "job": job,
        "status": "pending",
        "returncode": -1,
        "duration_s": 0,
        "clone_dir": None,
        "error": None,
    }

    compose_prefix = f"bb_{job_id}"
    job_network = f"bb_net_{job_id}"
    clone_dir = None

    async with semaphore:
        try:
            _log(f"[{job_id}] Starting: {job['task_dir']} "
                 f"bounty={job['bounty_number']} model={job['model']}")
            result["status"] = "running"

            # 1. Create isolated clone (skip venv/node_modules)
            clone_dir = await asyncio.get_event_loop().run_in_executor(
                None, create_clone, source_repo, workdir, job_id
            )
            result["clone_dir"] = str(clone_dir)

            # 2. Patch clone for Docker isolation
            await asyncio.get_event_loop().run_in_executor(
                None, patch_clone_for_isolation, clone_dir, job_id
            )

            # 3. Create per-job Docker network
            await asyncio.get_event_loop().run_in_executor(
                None, create_job_network, job_network
            )

            # 4. Build command
            cmd = build_command(job, clone_dir)

            # 5. Set up environment
            env = os.environ.copy()
            env["COMPOSE_PROJECT_NAME"] = compose_prefix
            # Load .env from clone if present
            env_file = clone_dir / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env.setdefault(k.strip(), v.strip())

            # 6. Set up log paths in shared parallel_logs subdirectories
            logs_base = source_repo / "parallel_logs"
            stdout_dir = logs_base / "stdout"
            stderr_dir = logs_base / "stderr"
            stdout_dir.mkdir(parents=True, exist_ok=True)
            stderr_dir.mkdir(parents=True, exist_ok=True)
            stdout_log = stdout_dir / f"{job_id}.log"
            stderr_log = stderr_dir / f"{job_id}.log"

            # 7. Run the workflow
            _log(f"[{job_id}] Executing: {' '.join(cmd[-6:])}")
            start = time.monotonic()
            with open(stdout_log, "w") as fout, open(stderr_log, "w") as ferr:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=fout,
                    stderr=ferr,
                    cwd=str(clone_dir),
                    env=env,
                )
                returncode = await proc.wait()

            duration = time.monotonic() - start
            result["returncode"] = returncode
            result["duration_s"] = round(duration, 1)
            result["status"] = "completed" if returncode == 0 else "failed"

            icon = "OK" if returncode == 0 else "FAIL"
            _log(f"[{job_id}] {icon} (exit={returncode}, {result['duration_s']}s)")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            _log(f"[{job_id}] ERROR: {e}", "ERROR")

        finally:
            # 8. Collect ALL logs from clone to central directory.
            #    This runs in `finally` so logs are saved even on crashes.
            logs_base = source_repo / "parallel_logs"
            if clone_dir and clone_dir.exists():
                await asyncio.get_event_loop().run_in_executor(
                    None, _collect_logs, clone_dir, logs_base, job_id
                )

            # 9. Targeted cleanup: only this job's Docker resources
            _log(f"[{job_id}] Cleaning up Docker resources...")

            # a) docker-compose down for this project (handles bounty setup containers)
            if clone_dir:
                # Find all docker-compose dirs and tear them down
                for dc in _find_compose_dirs(clone_dir):
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            "docker", "compose",
                            "-p", compose_prefix,
                            "down", "-v", "--remove-orphans",
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                            cwd=str(dc),
                            env={**os.environ, "COMPOSE_PROJECT_NAME": compose_prefix},
                        )
                        await asyncio.wait_for(proc.wait(), timeout=60)
                    except Exception:
                        pass

            # b) Remove any compose-labeled containers for this project
            await asyncio.get_event_loop().run_in_executor(
                None, cleanup_job_containers, compose_prefix
            )

            # c) Remove any containers still on the per-job network (Kali etc.)
            await asyncio.get_event_loop().run_in_executor(
                None, cleanup_kali_containers_by_network, job_network
            )

            # d) Remove the per-job network
            await asyncio.get_event_loop().run_in_executor(
                None, destroy_job_network, job_network
            )

            # e) Remove clone directory
            if clone_dir and not keep_clones:
                await asyncio.get_event_loop().run_in_executor(
                    None, cleanup_clone, clone_dir
                )

    return result


def _find_compose_dirs(clone_dir: Path) -> List[Path]:
    """Find directories containing docker-compose files in the clone."""
    dirs = set()
    for name in ("docker-compose.yml", "docker-compose.yaml"):
        for f in clone_dir.rglob(name):
            dirs.add(f.parent)
    return list(dirs)


# ---------------------------------------------------------------------------
# Run a group of port-conflicting jobs sequentially
# ---------------------------------------------------------------------------

async def run_group(
    group: List[Dict],
    source_repo: Path,
    workdir: Path,
    keep_clones: bool,
    semaphore: asyncio.Semaphore,
) -> List[Dict]:
    """Run a list of jobs sequentially (they share port constraints)."""
    results = []
    for job in group:
        job_id = uuid.uuid4().hex[:10]
        r = await run_job(job, job_id, source_repo, workdir, keep_clones, semaphore)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_all(
    config_path: str,
    max_parallel: int,
    workdir: Path,
    keep_clones: bool,
) -> None:
    config = _load_config(config_path)
    jobs = generate_jobs(config)

    if not jobs:
        _log("No jobs generated from config. Check your YAML.", "ERROR")
        return

    _log(f"Generated {len(jobs)} job(s) from config")

    # Save run manifest so analysis scripts can identify this run
    logs_dir = source_repo / "parallel_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "config_path": str(config_path),
        "config": config,
        "total_jobs": len(jobs),
    }
    (logs_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    # Group by port conflicts + same task_dir
    groups = group_jobs_by_port_conflict(jobs)
    parallel_count = len(groups)
    sequential_max = max(len(g) for g in groups) if groups else 0

    _log(f"Organized into {parallel_count} parallel group(s) "
         f"(largest group: {sequential_max} sequential jobs)")
    _log(f"Effective concurrency: min({parallel_count}, {max_parallel}) "
         f"= {min(parallel_count, max_parallel)}")

    source_repo = Path.cwd().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    # Clean up logs from previous runs so they don't contaminate analysis
    logs_dir = source_repo / "parallel_logs"
    if logs_dir.exists():
        _log("Clearing previous parallel_logs/ directory")
        shutil.rmtree(logs_dir, ignore_errors=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(max_parallel)

    # Launch all groups concurrently; within each group, jobs run sequentially
    start_time = time.monotonic()
    tasks = [
        asyncio.create_task(
            run_group(group, source_repo, workdir, keep_clones, semaphore)
        )
        for group in groups
    ]

    all_results: List[Dict] = []
    for coro in asyncio.as_completed(tasks):
        group_results = await coro
        all_results.extend(group_results)

    total_time = time.monotonic() - start_time

    # Print summary
    print("\n" + "=" * 70)
    print("PARALLEL RUN SUMMARY")
    print("=" * 70)
    completed = sum(1 for r in all_results if r["status"] == "completed")
    failed = sum(1 for r in all_results if r["status"] == "failed")
    errored = sum(1 for r in all_results if r["status"] == "error")

    print(f"Total jobs:     {len(all_results)}")
    print(f"Completed:      {completed}")
    print(f"Failed:         {failed}")
    print(f"Errors:         {errored}")
    print(f"Total time:     {total_time:.1f}s")
    print(f"Logs directory: {source_repo / 'parallel_logs'}")
    print()

    for r in all_results:
        j = r["job"]
        icon = {"completed": "[OK]", "failed": "[FAIL]", "error": "[ERR]"}.get(
            r["status"], "[???]"
        )
        print(f"  {icon} {r['job_id']}  {j['task_dir']}  bounty={j['bounty_number']}  "
              f"model={j['model']}  {r['duration_s']}s")
        if r.get("error"):
            print(f"       Error: {r['error']}")

    print("=" * 70)

    if failed + errored > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run BountyBench workflows in parallel with full isolation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "config",
        help="Path to YAML config file (same format as run_experiments.py)",
    )
    parser.add_argument(
        "--max-parallel", "-j",
        type=int,
        default=20,
        help="Maximum concurrent jobs (default: CPU count)",
    )
    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Directory for job clones (default: system temp dir)",
    )
    parser.add_argument(
        "--keep-clones",
        action="store_true",
        help="Don't delete cloned directories after completion (for debugging)",
    )

    args = parser.parse_args()

    if args.workdir:
        workdir = Path(args.workdir)
    else:
        workdir = Path(tempfile.gettempdir()) / "bountybench_parallel"

    _log("BountyBench Parallel Runner")
    _log(f"Config:       {args.config}")
    _log(f"Max parallel: {args.max_parallel}")
    _log(f"Work dir:     {workdir}")
    _log(f"Keep clones:  {args.keep_clones}")

    asyncio.run(run_all(args.config, args.max_parallel, workdir, args.keep_clones))


if __name__ == "__main__":
    main()