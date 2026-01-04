#!/bin/bash

# Configuration
PYTHON_SCRIPT="log_analysis.py"
INPUT_DIR="./analysis_in"
OUTPUT_DIR="./analysis_out"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Log Analysis Automation ===${NC}"

# 1. Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 could not be found.${NC}"
    exit 1
fi

# 2. Check for the Python script file
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}Error: '$PYTHON_SCRIPT' not found.${NC}"
    echo "Please ensure you have saved the python code from the previous step"
    echo "as '$PYTHON_SCRIPT' in this directory."
    exit 1
fi

# 3. Setup Directories
if [ ! -d "$INPUT_DIR" ]; then
    echo -e "${YELLOW}Creating input directory: $INPUT_DIR${NC}"
    mkdir -p "$INPUT_DIR"
fi

if [ ! -d "$OUTPUT_DIR" ]; then
    echo -e "${YELLOW}Creating output directory: $OUTPUT_DIR${NC}"
    mkdir -p "$OUTPUT_DIR"
fi

# 4. Check for JSON input files
FILE_COUNT=$(find "$INPUT_DIR" -maxdepth 1 -name "*.json" 2>/dev/null | wc -l)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}Warning: No JSON log files found in $INPUT_DIR${NC}"
    echo "Please copy your log files into the '$INPUT_DIR' folder and run this script again."
    
    exit 0
fi

# 5. Run the Analysis
echo -e "Found ${GREEN}$FILE_COUNT${NC} log files. Running analysis..."
echo "---------------------------------------------------"

python3 "$PYTHON_SCRIPT"

EXIT_CODE=$?

echo "---------------------------------------------------"

# 6. Final Status
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Success! Analysis complete.${NC}"
    echo -e "Results stored in: ${GREEN}$OUTPUT_DIR${NC}"
    
    echo -e "\nGenerated Summaries:"
    ls -1 "$OUTPUT_DIR"
else
    echo -e "${RED}Analysis failed with error code $EXIT_CODE.${NC}"
fi