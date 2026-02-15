#!/usr/bin/env bash
# Usage: ./aws_sync.sh [push|pull|both]
# push = local → EC2
# pull = EC2 → local (logs from task runs and any remote edits)
# both = push then pull (default)

EC2_HOST="ubuntu@ec2-3-22-233-10.us-east-2.compute.amazonaws.com"
EC2_KEY="~/arav-1.pem"
REMOTE_DIR="~/bountybench-casi"
LOCAL_DIR="/home/aravs/bountybench-casi"

RSYNC_EXCLUDES="--exclude venv --exclude .git --exclude bountytasks/.git"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude __pycache__ --exclude frontend --exclude node_modules"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude wip_tests --exclude tests --exclude analytics"

ssh_cmd="ssh -i $EC2_KEY"
mode="${1:-both}"

push_sync() {
  echo ">>> Pushing local → EC2..."
  rsync -avz --progress -e "$ssh_cmd" $RSYNC_EXCLUDES \
    "$LOCAL_DIR/" "$EC2_HOST:$REMOTE_DIR/"
}

pull_sync() {
  echo ">>> Pulling EC2 → local (logs + full tree)..."
  rsync -avz --progress -e "$ssh_cmd" \
    "$EC2_HOST:$REMOTE_DIR/" "$LOCAL_DIR/"
}

case "$mode" in
  push)  push_sync ;;
  pull)  pull_sync ;;
  both)  push_sync; pull_sync ;;
  *)    echo "Usage: $0 [push|pull|both]"; exit 1 ;;
esac

echo "Done."