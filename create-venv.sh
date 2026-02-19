#!/usr/bin/env bash
#
# Set up BountyBench environment on EC2: Docker, Python, venv, dependencies.
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

# Install Docker (required for BountyBench workflows - spins up Kali containers)
if command -v docker &>/dev/null; then
  log_ok "✅ Docker is installed: $(docker --version)"
else
  log_info "Installing Docker..."
  sudo apt update
  sudo apt install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  log_ok "Docker installed. Log out and back in (or run: newgrp docker) for group to apply."
fi

# Install Python 3.11 and venv
log_info "Installing system packages..."
sudo apt install -y software-properties-common
echo -e '\n' | sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential

log_info "Checking for 'tree' command..."
if ! command -v tree &> /dev/null; then
    log_info "⏳ Installing tree utility..."
    sudo apt-get update && sudo apt-get install -y tree || error_exit "Failed to install tree via apt-get"
    log_ok "✅ Successfully installed tree"
else
    log_ok "✅ tree already installed"
fi

# Create virtual environment
cd ~/bountybench-casi
log_info "Removing existing virtual environment (if any)..."
rm -rf venv
log_ok "Creating new virtual environment..."

python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

log_info "📦 Upgrading pip..."
pip install --upgrade pip || error_exit "Failed to upgrade pip."

log_info "📄 Installing requirements from requirements.txt..."
pip install --no-cache-dir -r requirements.txt || error_exit "Failed to install requirements."

# 4. Initialize git submodules
log_info "🔗 Initializing git submodules..."
git submodule update --init || error_exit "Failed to initialize submodules."

# 5. Update submodules to the latest commit from remote repositories
log_info "🔗 Updating submodules to the latest commit..."
git submodule update --remote || error_exit "Failed to update submodules to the latest commit."

cd bountytasks
git submodule update --init
cd ..
log_ok "Submodules initialized and updated."



# Use following command to monitor/increase the size of the nvme0n1p1 partition if needed (i.e. if you increase space in the EC2 instance volume)

# df -h              # List disk usage
# lsblk              # List block devices/partitions
# sudo du -sh /* 2>/dev/null | sort -rh    # List disk usage by directory

# sudo growpart /dev/nvme0n1 1             # Grow the partition to the full size of the device after modifying volume size