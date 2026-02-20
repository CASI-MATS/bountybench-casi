# run_task.sh  (new file, same directory)
#!/usr/bin/env bash
set -e
SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIRECTORY}/venv/bin/activate"

workflow="$1"
task="$2"
run_index="$3"

# Inherit these from environment or hardcode defaults
BOUNTY_NUMBER="${BOUNTY_NUMBER:-0}"
PHASE_ITERATIONS="${PHASE_ITERATIONS:-100}"
MODEL="${MODEL:-openrouter/mistralai/mistral-small-3.2-24b-instruct}"
LOG_DIR="${LOG_DIR:-${SCRIPT_DIRECTORY}/logs_parallel}"

log_file="${LOG_DIR}/${task}/${task}_${workflow}_${run_index}.log"
mkdir -p "${LOG_DIR}/${task}"
echo "[$(date +%Y-%m-%d\ %H:%M:%S)] Running ${task} with ${workflow} run ${run_index} -> $log_file"

"${SCRIPT_DIRECTORY}/venv/bin/python" -m workflows.runner \
    --workflow-type "$workflow" \
    --task_dir "bountytasks/${task}" \
    --bounty_number "$BOUNTY_NUMBER" \
    --model "$MODEL" \
    --phase_iterations "$PHASE_ITERATIONS" \
    --logging_level INFO \
    > "$log_file" 2>&1 || true

echo "[$(date -Iseconds)] Finished $workflow $task run $run_index"