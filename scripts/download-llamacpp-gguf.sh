#!/bin/bash

ORIGINAL_PWD=$PWD
CURRENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a temorary virtual environment
uv venv

# Install necessary dependencies and download the model
uv pip install pyyaml python-box llama-cpp-python huggingface-hub
uv run $CURRENT_SCRIPT_DIR/internal/download-llamacpp-gguf.py

# Remove the temporary virtual environment
rm -rf .venv

cd $ORIGINAL_PWD
