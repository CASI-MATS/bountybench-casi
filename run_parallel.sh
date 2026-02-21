#!/usr/bin/env bash
#
# Run BountyBench tasks in parallel.
# Execute on EC2 after SSH: ./run_parallel.sh

set -e
# PIDs of background task processes (used by trap to kill only our jobs, avoiding kill 0 which can segfault)
pids=()
trap 'echo "Interrupted, stopping jobs..."; for p in "${pids[@]}"; do kill -TERM "$p" 2>/dev/null || true; done; exit 130' INT TERM

# Configs

RUNS_PER_TASK=2
PHASE_ITERATIONS=30
BOUNTY_NUMBER=0

# TESTING: Test with both strong and weak model pairs

MODEL="openrouter/mistralai/mistral-small-3.2-24b-instruct"
# MODEL="openrouter/qwen/qwen3-coder-flash" or coder-next
# MODEL="openrouter/minimax/minimax-m2.5"
# MODEL="openrouter/deepseek/deepseek-v3.2" 
# MODEL="openrouter/moonshotai/kimi-k2-thinking"
PARALLEL_JOBS=2
BBENCH_TASKS=("kedro" "yaml" "zipp" "curl") # "vllm" "astropy" "gluon-cv" "llama_index" "parse-url" "setuptools" ("undici" "vllm" "yaml" "zipp")

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

# Build job list: run -> workflow -> task.
# JOBS_FILE="${LOG_DIR}/.jobs_$$.txt"
# : > "$JOBS_FILE"
# for ((run=1; run<=RUNS_PER_TASK; run++)); do
#     for workflow in "${WORKFLOWS[@]}"; do
#         for task in "${BBENCH_TASKS[@]}"; do
#             echo "$workflow $task $run" >> "$JOBS_FILE"
#         done
#     done
# done
# TOTAL_JOBS=$(wc -l < "$JOBS_FILE")

TOTAL_JOBS=$((RUNS_PER_TASK * ${#WORKFLOWS[@]} * NUM_TASKS))
echo "=============================================="
echo "BountyBench Parallel Run"
echo "  Total jobs: $TOTAL_JOBS (${NUM_TASKS} tasks x ${#WORKFLOWS[@]} workflows x $RUNS_PER_TASK runs)"
echo "  Runs per task: $RUNS_PER_TASK"
echo "  Phase iterations (msg max): $PHASE_ITERATIONS"
echo "  Model: $MODEL"
echo "  Tasks: ${BBENCH_TASKS[*]}"
echo "  Workflows: ${WORKFLOWS[*]}"
echo "  Parallel jobs: $PARALLEL_JOBS (max $NUM_TASKS per task)"
echo "  Log dir: $LOG_DIR"
echo "=============================================="

run_all_for_task() {
    local task="$1"
    for ((run=1; run<=RUNS_PER_TASK; run++)); do
        for workflow in "${WORKFLOWS[@]}"; do
            run_single_task "$workflow" "$task" "$run"
        done
    done
}

# Run each task in its own background subshell
for task in "${BBENCH_TASKS[@]}"; do
    run_all_for_task "$task" &
    pids+=($!)
    echo "Started task $task (PID $!)"
done

# Wait for all tasks to finish
for pid in "${pids[@]}"; do
    wait "$pid"
done

echo "[$(date -Iseconds)] All runs complete."

# PARALLEL_SHELL=bash and "bash -c 'run_single_task \"\$@\"'" ensure the exported
# function is available (parallel may use sh; sem runs the command in a subprocess).
# --line-buffer: print each line as soon as it is ready (no waiting for job to finish).
# --tag: prefix each line with the job (workflow task run) so you see which job produced it.
# Remove: export -f run_single_task (no longer needed)

# if command -v parallel &>/dev/null && [[ "$PARALLEL_JOBS" -gt 1 ]]; then
#     echo "Using GNU parallel with $PARALLEL_JOBS jobs..."
#     export BOUNTY_NUMBER PHASE_ITERATIONS MODEL LOG_DIR SCRIPT_DIRECTORY
#     # Temporarily test with sleeps instead of real tasks
#     parallel -j "$PARALLEL_JOBS" --colsep ' ' -a "$JOBS_FILE" \
#     "sem --id {2} -j 1 bash -c 'echo START {1} {2} {3} at $(date +%H:%M:%S); sleep 5; echo END {2} {3} at $(date +%H:%M:%S)'"
#     # parallel -j "$PARALLEL_JOBS" \
#     #     --colsep ' ' \
#     #     -a "$JOBS_FILE" \
#     #     --line-buffer --tag \
#     #     "sem --id {2} -j 1 ${SCRIPT_DIRECTORY}/run_task.sh {1} {2} {3}"
# else
#     echo "Running sequentially..."
#     while read -r wf task run; do
#         "${SCRIPT_DIRECTORY}/run_task.sh" "$wf" "$task" "$run"
#     done < "$JOBS_FILE"
# fi
# 
# rm -f "$JOBS_FILE"
# echo "[$(date -Iseconds)] All runs complete."