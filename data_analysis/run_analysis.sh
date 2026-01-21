#!/usr/bin/env bash
set -e

# =====================
# Resolve script location
# =====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =====================
# Configuration
# =====================
PYTHON_SCRIPT="log_analysis.py"
INPUT_DIR="analysis_in"
OUTPUT_DIR="analysis_out"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Log Analysis Automation ===${NC}"
echo "Working directory: $SCRIPT_DIR"

# =====================
# Python detection
# =====================
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo -e "${RED}Error: Python is not installed.${NC}"
    exit 1
fi

echo -e "Using Python: ${GREEN}$($PYTHON --version)${NC}"

# =====================
# Check script existence
# =====================
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}Error: '$PYTHON_SCRIPT' not found.${NC}"
    echo "Expected location: $SCRIPT_DIR/$PYTHON_SCRIPT"
    exit 1
fi

# =====================
# Setup directories
# =====================
mkdir -p "$INPUT_DIR" "$OUTPUT_DIR"

# =====================
# Check for JSON input
# =====================
FILE_COUNT=$(find "$INPUT_DIR" -maxdepth 1 -name "*.json" | wc -l)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No JSON log files found in '$INPUT_DIR'.${NC}"
    echo "➡ Copy logs into $INPUT_DIR and re-run."
    exit 0
fi

# =====================
# Run analysis
# =====================
echo -e "Found ${GREEN}$FILE_COUNT${NC} log files"
echo "---------------------------------------------------"

# Export dirs for future Python extensibility
export INPUT_DIR
export OUTPUT_DIR

$PYTHON "$PYTHON_SCRIPT"

echo "---------------------------------------------------"
echo -e "${GREEN}✔ Analysis complete${NC}"
echo -e "Output directory: ${GREEN}$OUTPUT_DIR${NC}"

# =====================
# Show results
# =====================
echo -e "\nGenerated files:"
ls -lh "$OUTPUT_DIR"

# =====================
# Optional Visidata hint
# =====================
if command -v vd &>/dev/null; then
    echo -e "\n${GREEN}Tip:${NC} Open results with:"
    echo "  vd $OUTPUT_DIR/summary.json"
fi
