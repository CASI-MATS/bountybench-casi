#!/usr/bin/env bash
#
# Reset bountytasks submodules to clean state.
# Run on EC2 when git errors occur (e.g. "unable to write new index file", index.lock).
# Workflows modify task dirs; this restores them for the next run.
#
set -e
cd "$(dirname "$0")"
echo "Resetting bountytasks (removing locks, checking out main, cleaning)..."
cd bountytasks
# Reset each submodule: remove index.lock, checkout main, clean
git submodule foreach --recursive 'rm -f .git/index.lock 2>/dev/null; git checkout main 2>/dev/null || git checkout master 2>/dev/null; git clean -fdx 2>/dev/null; true'
cd ..
echo "Done. You can run workflows again."
