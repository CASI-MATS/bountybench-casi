#!/usr/bin/env bash
set -e

sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type patch_workflow \
  --task_dir bountytasks/kedro \
  --bounty_number 0 \
  --model openrouter/anthropic/claude-sonnet-4.5 \
  --phase_iterations 100

sudo chown -R "$USER":"$USER" bountytasks
git -C bountytasks submodule foreach --recursive git clean -fdx