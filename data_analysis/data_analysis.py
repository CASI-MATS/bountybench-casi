import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from collections import defaultdict
from typing import List
from scipy import stats
import numpy as np

# =====================
# Configuration (defaults)
# =====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_DIR = os.path.join(SCRIPT_DIR, "..", "logs")
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "analysis_out")
SUMMARY_FILE = "summary.json"

# =====================
# Console colors (Windows-compatible)
# =====================
def _init_colors():
    """Enable ANSI colors on Windows and define color codes."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

    return {
        "GREEN": "\033[0;32m",
        "YELLOW": "\033[1;33m",
        "RED": "\033[0;31m",
        "NC": "\033[0m",
    }

COLORS = _init_colors()
GREEN = COLORS["GREEN"]
YELLOW = COLORS["YELLOW"]
RED = COLORS["RED"]
NC = COLORS["NC"]


# =====================
# Dataclasses
# =====================
@dataclass
class RunRecord:
    bountytask: str
    workflow_type: str
    task_number: int
    model_name: str

    complete: bool
    success: bool

    total_credits_used: float
    total_time_ms: float
    llm_calls: int

    avg_credits_per_llm_call: float
    avg_time_ms_per_llm_call: float


# =====================
# Helpers
# =====================
def get_safe(data, path, default=None):
    try:
        for key in path:
            data = data[key]
        return data
    except (KeyError, TypeError, IndexError):
        return default

def calculate_stats(phase_messages):
    result = {
        "llm_calls": 0,
        "credits": [],
        "latency_ms": [],
    }

    for phase in phase_messages or []:
        for agent_msg in phase.get("agent_messages") or []:
            for action in agent_msg.get("action_messages") or []:
                if action.get("resource_id") == "model":
                    meta = action.get("additional_metadata") or {}
                    result["llm_calls"] += 1
                    result["credits"].append(
                        meta.get("credits_used", 0)
                        or meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
                    )
                    result["latency_ms"].append(
                        meta.get("time_taken_in_ms", 0)
                    )

    return result

def extract_bounty_name(task_dir: str) -> str:
    if not task_dir:
        return "unknown"

    parts = task_dir.replace("\\", "/").split("/")

    if "bountytasks" in parts:
        idx = parts.index("bountytasks")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    # fallback: last directory
    return parts[-1]



def list_output_files(directory: str):
    """Print output files with sizes, similar to ls -lh."""
    try:
        entries = os.listdir(directory)
    except FileNotFoundError:
        return

    for name in sorted(entries):
        full = os.path.join(directory, name)
        if os.path.isfile(full):
            size = os.path.getsize(full)
            if size >= 1_048_576:
                human = f"{size / 1_048_576:.1f}M"
            elif size >= 1024:
                human = f"{size / 1024:.1f}K"
            else:
                human = f"{size}B"
            print(f"  {human:>8s}  {name}")


# =====================
# Per-log processing
# =====================
def parse_log_data(data: dict, filename: str = "") -> RunRecord | None:
    if not isinstance(data, dict):
        return None
    wf_meta = data.get("workflow_metadata", {})
    summary = wf_meta.get("workflow_summary", {})
    task = wf_meta.get("task", {})

    bountytask = extract_bounty_name(task.get("task_dir"))
    workflow_type = wf_meta.get("workflow_name", "unknown").replace("Workflow", "").lower()
    task_number = task.get("bounty_number")
    model_name = get_safe(data, ["resources_used", "model", "config", "model"], "unknown")

    complete = bool(summary.get("complete", False))
    success = bool(summary.get("success", False))

    run_stats = calculate_stats(data.get("phase_messages", []))

    llm_calls = run_stats["llm_calls"]
    total_credits = sum(run_stats["credits"])
    total_time = sum(run_stats["latency_ms"])

    avg_credits = total_credits / llm_calls if llm_calls else 0.0
    avg_time = total_time / llm_calls if llm_calls else 0.0

    return RunRecord(
        bountytask=bountytask,
        workflow_type=workflow_type,
        task_number=task_number,
        model_name=model_name,
        complete=complete,
        success=success,
        total_credits_used=total_credits,
        total_time_ms=total_time,
        llm_calls=llm_calls,
        avg_credits_per_llm_call=avg_credits,
        avg_time_ms_per_llm_call=avg_time,
    )

def clopper_pearson_ci(k, n, confidence=0.95):
    if n == 0:
        return 0.0, 0.0
    ci_low, ci_high = stats.binom.interval(confidence, n, k/n)
    return ci_low/n, ci_high/n

# =====================
# Aggregation
# =====================
def aggregate_runs(runs: List[RunRecord]) -> List[dict]:
    grouped = defaultdict(list)

    for r in runs:
        key = (r.bountytask, r.workflow_type, r.task_number, r.model_name)
        grouped[key].append(r)

    rows = []

    for (bountytask, workflow_type, task_number, model_name), items in grouped.items():
        runs_count = len(items)

        completes = sum(r.complete for r in items)
        successes = sum(r.success for r in items)

        total_credits = sum(r.total_credits_used for r in items)
        total_llm_calls = sum(r.llm_calls for r in items)
        total_time = sum(r.total_time_ms for r in items)

        ci_low, ci_high = clopper_pearson_ci(successes, completes, confidence=0.95)

        rows.append({
            "bountytask": bountytask,
            "workflow_type": workflow_type,
            "task_number": task_number,
            "model_name": model_name,

            "total_runs": runs_count,
            "completes": completes,
            "successes": successes,

            "total_credits_used": total_credits,
            "avg_credits_per_run": total_credits / runs_count if runs_count else 0,
            "avg_credits_per_llm_call": (
                total_credits / total_llm_calls if total_llm_calls else 0
            ),

            "total_llm_calls": total_llm_calls,
            "avg_llm_calls_per_run": total_llm_calls / runs_count if runs_count else 0,

            "total_time_ms": total_time,
            "avg_time_per_run_ms": total_time / runs_count if runs_count else 0,
            "avg_time_per_llm_call_ms": (
                total_time / total_llm_calls if total_llm_calls else 0
            ),
            "measured_success_rate": successes / completes if completes else 0,
            "clopper_pearson_ci": {"low": ci_low, "high": ci_high},
        })

    return rows


# =====================
# Main
# =====================
def parse_args():
    parser = argparse.ArgumentParser(description="Analyze BountyBench log files.")
    parser.add_argument(
        "-i", "--input",
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory containing JSON log files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for analysis results (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)

    print(f"{GREEN}=== Log Analysis Automation ==={NC}")
    print(f"Working directory: {SCRIPT_DIR}")
    print(f"Using Python: {GREEN}{sys.version.split()[0]}{NC}")

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Parse all logs (with dedup by content hash to catch stale logs from previous runs)
    runs: List[RunRecord] = []
    seen_hashes = set()
    dup_count = 0
    total_json = 0

    for root, _, files in os.walk(input_dir):
        for fname in files:
            if fname.endswith(".json"):
                total_json += 1
                rel_path = os.path.relpath(
                    os.path.join(root, fname),
                    input_dir
                )
                path = os.path.join(input_dir, rel_path)
                try:
                    with open(path, "rb") as fb:
                        raw = fb.read()
                    content_hash = hashlib.sha256(raw).hexdigest()
                    if content_hash in seen_hashes:
                        dup_count += 1
                        continue
                    seen_hashes.add(content_hash)
                    data = json.loads(raw)
                except Exception as e:
                    print(f"Failed to read {rel_path}: {e}")
                    continue

                record = parse_log_data(data, rel_path)
                if record and record.model_name != "unknown":
                    runs.append(record)

    if total_json == 0:
        print(f"{YELLOW}No JSON log files found in '{input_dir}'.{NC}")
        print(f"Copy logs into {input_dir} and re-run.")
        return

    if not runs:
        print("No valid logs found.")
        return

    # Aggregate and write summary
    summary = aggregate_runs(runs)

    out_path = os.path.join(output_dir, SUMMARY_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote summary -> {out_path}")
    print("-" * 51)
    print(f"{GREEN}Analysis complete{NC}")
    print(f"Output directory: {GREEN}{output_dir}{NC}")

    # Show generated files
    print("\nGenerated files:")
    list_output_files(output_dir)

    skipped = total_json - len(runs) - dup_count
    print(f"Found {GREEN}{total_json}{NC} JSON files -> {GREEN}{len(runs)}{NC} valid run logs"
          + (f" ({dup_count} duplicates skipped)" if dup_count else "")
          + (f" ({skipped} non-log files ignored)" if skipped else ""))
    print("-" * 51)


if __name__ == "__main__":
    main()
