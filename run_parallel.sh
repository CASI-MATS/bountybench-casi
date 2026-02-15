#!/usr/bin/env bash
#
# Run BountyBench tasks in parallel.
# Execute on EC2 after SSH: ./run_parallel.sh

set -e

# Configs

RUNS_PER_TASK=100
PHASE_ITERATIONS=100
BOUNTY_NUMBER=0

# TESTING: Test with both strong and weak model pairs

MODEL="openrouter/mistralai/mistral-small-3.1-24b-instruct"
MODEL="openrouter/deepseek/deepseek-v3.2" 
PARALLEL_JOBS=2

BBENCH_TASKS=("tables" "tests" "undici" "vllm" "yaml" "zipp")

WORKFLOWS=("exploit_workflow" "patch_workflow")

# Script

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" # Switch to script directory for execution
cd "$SCRIPT_DIRECTORY"
LOG_DIR="${SCRIPT_DIRECTORY}/logs_parallel"
mkdir -p "$LOG_DIR"

# Ensure BountyBench virtual environment is activated

if [[ -z "$VIRTUAL_ENV" ]]; then
    if [[ -f "venv/bin/activate" ]]; then
        source "venv/bin/activate"
    else
        echo "Error: BountyBench virtual environment not found (activate or from bountybench-casi with venv)"
        exit 1
    fi
fi

run_single_task() {
    local workflow="$1"
    local task="$2"
    local run_index="$3"
    local log_file="${LOG_DIR}/${task}/${task}_${workflow}_${run_index}.log"
    mkdir -p "${LOG_DIR}/${task}"
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] Running ${task} with ${workflow} for run ${run_index} -> $log_file"

    "${SCRIPT_DIRECTORY}/venv/bin/python" -m workflows.runner \
        --workflow-type "$workflow" \
        --task_dir "bountytasks/${task}" \
        --bounty_number "$BOUNTY_NUMBER" \
        --model "$MODEL" \
        --phase_iterations "$PHASE_ITERATIONS" \
        --logging_level INFO \
        $USE_HELM \
        > "$log_file" 2>&1 || true
    echo "[$(date -Iseconds)] Finished $workflow $task run $run_index (exit: $?)"
}

export -f run_single_task
export SCRIPT_DIRECTORY RUNS_PER_TASK PHASE_ITERATIONS BOUNTY_NUMBER MODEL PARALLEL_JOBS LOG_DIR

echo "=============================================="
echo "BountyBench Parallel Run"
echo "  Runs per task: $RUNS_PER_TASK"
echo "  Phase iterations (msg max): $PHASE_ITERATIONS"
echo "  Model: $MODEL"
echo "  Tasks: ${BBENCH_TASKS[*]}"
echo "  Workflows: ${WORKFLOWS[*]}"
echo "  Parallel jobs: $PARALLEL_JOBS"
echo "  Log dir: $LOG_DIR"
echo "=============================================="

# Iterate through all task-workflow-run_idx combinations to build the job list
JOBS_FILE="${LOG_DIR}/.jobs_$$.txt"
: > "$JOBS_FILE"
for task in "${BBENCH_TASKS[@]}"; do
    for workflow in "${WORKFLOWS[@]}"; do
        for ((run=1; run<=RUNS_PER_TASK; run++)); do
            echo "$workflow $task $run" >> "$JOBS_FILE"
        done
    done
done

if command -v parallel &>/dev/null && [[ "$PARALLEL_JOBS" -gt 1 ]]; then
    echo "Using GNU parallel with $PARALLEL_JOBS jobs..."
    parallel -j "$PARALLEL_JOBS" --colsep ' ' -a "$JOBS_FILE" run_single_task {1} {2} {3}
else
    echo "Running sequentially..."
    while read -r wf task run; do
        run_single_task "$wf" "$task" "$run"
    done < "$JOBS_FILE"
fi

rm -f "$JOBS_FILE"
echo "[$(date -Iseconds)] All runs complete."