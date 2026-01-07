#!/usr/bin/env bash
set -e

# ===============================
# Model: openrouter/openai/gpt-4.1-mini
# ===============================

sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type detect_workflow \
  --task_dir bountytasks/kedro \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type exploit_workflow \
  --task_dir bountytasks/kedro \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type patch_workflow \
  --task_dir bountytasks/kedro \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type detect_workflow \
  --task_dir bountytasks/langchain \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type exploit_workflow \
  --task_dir bountytasks/langchain \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type patch_workflow \
  --task_dir bountytasks/langchain \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type detect_workflow \
  --task_dir bountytasks/setuptools \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type exploit_workflow \
  --task_dir bountytasks/setuptools \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100


sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \
  --workflow-type patch_workflow \
  --task_dir bountytasks/setuptools \
  --bounty_number 0 \
  --model openrouter/openai/gpt-4.1-mini \
  --phase_iterations 100

sudo chown -R "$USER":"$USER" bountytasks
git -C bountytasks submodule foreach --recursive git clean -fdx
