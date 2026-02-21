#!/bin/bash
# Run on EC2 to free disk space. Run with: bash tools/ec2_disk_cleanup.sh
# Optionally run with sudo for system caches (script will prompt where needed).

set -e

echo "=== Disk usage before ==="
df -h /

echo ""
echo "=== 1. Docker: remove all unused images, containers, build cache ==="
docker system prune -a -f
docker builder prune -a -f

echo ""
echo "=== 2. Docker: remove dangling and unused volumes ==="
docker volume prune -f

echo ""
echo "=== 3. APT cache ==="
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*
sudo apt-get update  # recreate lists so apt still works

echo ""
echo "=== 4. Journal logs (keep last 2 days) ==="
sudo journalctl --vacuum-time=2d

echo ""
echo "=== 5. Pip cache ==="
rm -rf ~/.cache/pip

echo ""
echo "=== 6. Find large dirs under current directory (top 20) ==="
du -h --max-depth=2 . 2>/dev/null | sort -hr | head -20

echo ""
echo "=== 7. System large dirs (optional: run with sudo) ==="
echo "  /var/log: $(sudo du -sh /var/log 2>/dev/null)"
echo "  /tmp: $(du -sh /tmp 2>/dev/null)"
sudo find /var/log -type f -name '*.log' -mtime +7 -delete 2>/dev/null || true
sudo find /var/log -type f -name '*.gz' -delete 2>/dev/null || true

echo ""
echo "=== 8. Old kernels (Ubuntu; frees 100MB–1GB) ==="
# List installed kernels; keep current and one previous
# dpkg -l | grep 'linux-image-.*-generic'
echo "  To remove old kernels (manual): sudo apt-get purge linux-image-*-generic (except current)"
echo "  Or: sudo apt-get autoremove --purge"

echo ""
echo "=== Disk usage after ==="
df -h /

echo ""
echo "Done. If still low, check: docker images (remove unneeded), du -sh ~/*, and move logs off-instance."
