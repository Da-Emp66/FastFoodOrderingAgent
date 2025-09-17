#!/bin/bash

ORIGINAL_PWD=$PWD
CURRENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a temorary virtual environment
uv venv

# Install necessary dependencies and download the model
uv pip install pyyaml python-box llama-cpp-python huggingface-hub

# This line didn't work for me, so I replaced it with the python command after the following commented out line
#uv run $CURRENT_SCRIPT_DIR/internal/download-llamacpp-gguf.py

uv pip install llama-cpp-python --find-links https://github.com/jllllll/llama-cpp-python-cuBLAS-wheels/releases/expanded_assets/textgen-webui || {
    echo "Prebuilt wheels not available, installing from source..."
    # Set environment variables to help with OpenMP linking
    export CMAKE_ARGS="-DGGML_OPENMP=ON"
    export FORCE_CMAKE=1
    # Add system library paths to help find libgomp
    export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
    export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LIBRARY_PATH"
    uv pip install llama-cpp-python
}
uv run "$CURRENT_SCRIPT_DIR/internal/download-llamacpp-gguf.py"



# Remove the temporary virtual environment
rm -rf .venv

cd $ORIGINAL_PWD
