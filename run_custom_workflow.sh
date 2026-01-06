#!/usr/bin/env bash
set -e

python -m workflows.runner \
  --workflow-type patch_workflow \
  --task_dir bountytasks/kedro \
  --bounty_number 0 \
  --model openrouter/anthropic/claude-sonnet-4.5 \
  --phase_iterations 100