#!/usr/bin/env bash
#
# Create a virtual environment for BountyBench.
# Execute on EC2 after SSH: ./create-venv.sh
#

set -e

# Colors for console output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()   { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# Install Python 3.11 and venv
log_info "Installing system packages..."
sudo apt install -y software-properties-common
echo -e '\n' | sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential

# Create virtual environment
cd ~/bountybench-casi
# Note: Script runs in a fresh subshell, so no venv is active. Skip deactivate.
log_info "Removing existing virtual environment (if any)..."
rm -rf venv
log_ok "Creating new virtual environment..."

python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate
log_info "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt
log_ok "Done! Virtual environment ready."

# Use following command to monitor/increase the size of the nvme0n1p1 partition if needed (i.e. if you increase space in the EC2 instance volume)

# df -h              # List disk usage
# lsblk              # List block devices/partitions
# sudo du -sh /* 2>/dev/null | sort -rh    # List disk usage by directory

# sudo growpart /dev/nvme0n1 1             # Grow the partition to the full size of the device after modifying volume size