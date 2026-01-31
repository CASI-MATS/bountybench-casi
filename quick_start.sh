#!/bin/sh
set -e

for i in $(seq 1 40); do
  echo "Run $i"
  python -m workflows.runner \
    --workflow-type exploit_workflow \
    --task_dir bountytasks/langchain \
    --bounty_number 0 \
    --model openrouter/moonshotai/kimi-k2-thinking \
    --phase_iterations 40
done