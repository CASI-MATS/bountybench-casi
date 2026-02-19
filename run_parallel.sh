#!/usr/bin/env bash
#
# Run BountyBench tasks in parallel.
# Execute on EC2 after SSH: ./run_parallel.sh

set -e

# Configs

RUNS_PER_TASK=5
PHASE_ITERATIONS=100
BOUNTY_NUMBER=0

# TESTING: Test with both strong and weak model pairs

MODEL="openrouter/mistralai/mistral-small-3.2-24b-instruct"
# MODEL="openrouter/qwen/qwen3-coder-flash" or coder-next
# MODEL="openrouter/minimax/minimax-m2.5"
# MODEL="openrouter/deepseek/deepseek-v3.2" 
# MODEL="openrouter/moonshotai/kimi-k2-thinking"
PARALLEL_JOBS=10
BBENCH_TASKS=("kedro" "yaml" "zipp" "curl" "vllm" "astropy" "gluon-cv" "llama_index" "parse-url" "setuptools") # ("undici" "vllm" "yaml" "zipp")

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

# Cap PARALLEL_JOBS to num_tasks. Each task has one git repo and Docker setup;
# two jobs on the same task (e.g. kedro exploit + kedro patch) would conflict.
NUM_TASKS=${#BBENCH_TASKS[@]}
if [[ "$PARALLEL_JOBS" -gt "$NUM_TASKS" ]]; then
    echo "Capping PARALLEL_JOBS from $PARALLEL_JOBS to $NUM_TASKS (one job per task max to avoid git/Docker conflicts)"
    PARALLEL_JOBS=$NUM_TASKS
fi

echo "=============================================="
echo "BountyBench Parallel Run"
echo "  Runs per task: $RUNS_PER_TASK"
echo "  Phase iterations (msg max): $PHASE_ITERATIONS"
echo "  Model: $MODEL"
echo "  Tasks: ${BBENCH_TASKS[*]}"
echo "  Workflows: ${WORKFLOWS[*]}"
echo "  Parallel jobs: $PARALLEL_JOBS (max $NUM_TASKS per task)"
echo "  Log dir: $LOG_DIR"
echo "=============================================="

# Build job list: run -> workflow -> task. Ensures each parallel batch has
# at most one job per task (e.g. kedro, yaml, zipp, curl), avoiding git/Docker conflicts.
JOBS_FILE="${LOG_DIR}/.jobs_$$.txt"
: > "$JOBS_FILE"
for ((run=1; run<=RUNS_PER_TASK; run++)); do
    for workflow in "${WORKFLOWS[@]}"; do
        for task in "${BBENCH_TASKS[@]}"; do
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