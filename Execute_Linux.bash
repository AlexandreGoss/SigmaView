#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/gui/SigmaView_tools_gui.py"
ENV_NAME="sigma_env_linux"

if command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base)"
else
    echo "Error: conda not found. Please install Miniconda or Anaconda."
    exit 1
fi

if [ ! -d "$CONDA_BASE" ]; then
    echo "Error: Anaconda directory not found at $CONDA_BASE"
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script $SCRIPT_PATH not found"
    exit 1
fi

source "$CONDA_BASE/etc/profile.d/conda.sh"
if ! conda activate "$ENV_NAME"; then
    echo "Error: Could not activate environment $ENV_NAME"
    exit 1
fi

python "$SCRIPT_PATH"
conda deactivate
