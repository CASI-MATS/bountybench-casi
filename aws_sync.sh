#!/usr/bin/env bash
# Usage: ./aws_sync.sh [push|pull|both]
# push = local → EC2
# pull = EC2 → local (logs from task runs and any remote edits)
# both = push then pull (default)

# Source the .env file
source .env

EC2_HOST=$EC2_HOST  # e.g. "ubuntu@compute-instance-id.compute.amazonaws.com"
EC2_KEY=$EC2_KEY  # e.g. "~/<key-name>.pem"
REMOTE_DIR="~/bountybench-casi"
LOCAL_DIR=$LOCAL_DIR  # e.g. "/home/<username>/bountybench-casi"

# Exclude bountytasks entirely - workflows modify task dirs (git checkouts, tmp, build artifacts).
# Keep bountytasks only on EC2 (from clone); sync code, scripts, and logs only.
RSYNC_EXCLUDES="--exclude venv --exclude .git --exclude bountytasks --exclude logs --exclude logs_parallel"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude __pycache__ --exclude frontend --exclude node_modules"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude wip_tests --exclude tests --exclude analytics"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude full_logs --exclude error_logs"

ssh_cmd="ssh -i $EC2_KEY"
mode="${1:-both}"

push_sync() {
  echo ">>> Pushing local → EC2..."
  rsync -avz --progress -e "$ssh_cmd" $RSYNC_EXCLUDES \
    "$LOCAL_DIR/" "$EC2_HOST:$REMOTE_DIR/"
}

pull_sync() {
  echo ">>> Pulling EC2 → local (logs + full tree)..."
  rsync -avz --progress -e "$ssh_cmd" --exclude venv --exclude .git --exclude bountytasks/ \
    "$EC2_HOST:$REMOTE_DIR/" "$LOCAL_DIR/"
}

case "$mode" in
  push)  push_sync ;;
  pull)  pull_sync ;;
  both)  push_sync; pull_sync ;;
  *)    echo "Usage: $0 [push|pull|both]"; exit 1 ;;
esac

echo "Done."