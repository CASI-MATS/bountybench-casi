#!/usr/bin/env bash
set -e

python -m workflows.runner \
  --workflow-type detect_workflow \
  --task_dir bountytasks/kedro \
  --bounty_number 0 \
  --model casiv2/openai/gpt-4o-mini \
  --phase_iterations 3