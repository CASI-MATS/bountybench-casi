#!/usr/bin/env bash
#
# Reset bountytasks submodules to clean state.
# Run on EC2 when git errors occur (e.g. "unable to write new index file", index.lock).
# Workflows modify task dirs; this restores them for the next run.
#
set -e
cd "$(dirname "$0")"
echo "Resetting bountytasks (ownership, locks, index, checkout main, clean)..."
# Fix ownership so all git ops work as current user (undo any root-owned files from past sudo)
if command -v sudo >/dev/null 2>&1; then
  sudo chown -R "$USER:$USER" bountytasks 2>/dev/null || true
fi
cd bountytasks
# Remove lock and corrupted index in each submodule, then checkout main and clean
git submodule foreach --recursive 'rm -f .git/index.lock 2>/dev/null; rm -f .git/index 2>/dev/null; git checkout main 2>/dev/null || git checkout master 2>/dev/null; git clean -fdx 2>/dev/null; true'
cd ..
echo "Done. You can run workflows again."
