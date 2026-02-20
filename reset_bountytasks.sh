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
  sudo chown -R "$USER:$USER" . 2>/dev/null || true
fi
# Remove locks and corrupted index in submodule git dirs (under .git/modules and bountytasks/.git/modules).
# Submodule worktrees have .git as a file, so the real git dir lives here; fixes "index.lock", "packed-refs.lock", "unknown index entry format".
find .git/modules bountytasks/.git/modules -name "index.lock" -type f -delete 2>/dev/null || true
find .git/modules bountytasks/.git/modules -name "packed-refs.lock" -type f -delete 2>/dev/null || true
find .git/modules bountytasks/.git/modules -name "index" -type f -delete 2>/dev/null || true
find bountytasks -name "index.lock" -delete 2>/dev/null || true
cd bountytasks
# Now checkout main and clean in each submodule (git will rebuild index if missing)
git submodule foreach --recursive 'git checkout main 2>/dev/null || git checkout master 2>/dev/null; git clean -fdx 2>/dev/null; true'
cd ..
echo "Done. You can run workflows again."
