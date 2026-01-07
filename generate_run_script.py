#!/usr/bin/env python3

MODELS = [
    # "openrouter/openai/gpt-5.2",
    # "openrouter/openai/gpt-5.1-codex",
    # "openrouter/openai/gpt-4.1",
    # FINISHED "openrouter/openai/gpt-4.1-mini",
    # "openrouter/minimax/minimax-m2.1",
    # "openrouter/moonshotai/kimi-k2-0905",
    # "openrouter/moonshotai/kimi-k2-thinking",
    # "openrouter/google/gemini-3-pro-preview",
    # FINISHED "openrouter/anthropic/claude-sonnet-4.5",
    # "openrouter/anthropic/claude-haiku-4.5",
    # "openrouter/anthropic/claude-3.7-sonnet"
]

TASK_DIRS = [
    "kedro",
    "langchain",
    "setuptools",
]

WORKFLOWS = [
    "detect_workflow",
    "exploit_workflow",
    "patch_workflow",
]

BOUNTY_NUMBER = 0
PHASE_ITERATIONS = 100

OUTPUT_FILE = "run_all.sh"


def emit_job(model: str, task: str, workflow: str) -> str:
    return f"""
sudo chown -R "$USER":"$USER" bountytasks

python -m workflows.runner \\
  --workflow-type {workflow} \\
  --task_dir bountytasks/{task} \\
  --bounty_number {BOUNTY_NUMBER} \\
  --model {model} \\
  --phase_iterations {PHASE_ITERATIONS}
""".rstrip()


def main():
    lines = []

    # Script header
    lines.append("#!/usr/bin/env bash")
    lines.append("set -e")
    lines.append("")

    for model in MODELS:
        lines.append(f"# ===============================")
        lines.append(f"# Model: {model}")
        lines.append(f"# ===============================")

        for task in TASK_DIRS:
            for workflow in WORKFLOWS:
                lines.append(emit_job(model, task, workflow))
                lines.append("")

    # Final cleanup
    lines.append('sudo chown -R "$USER":"$USER" bountytasks')
    lines.append("git -C bountytasks submodule foreach --recursive git clean -fdx")
    lines.append("")

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUTPUT_FILE}")
    print("Remember to: chmod +x run_all.sh")


if __name__ == "__main__":
    main()
