#!/bin/bash

ORIGINAL_PWD=$PWD
CURRENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a temorary virtual environment
uv venv

if [ "$1" = "--legacy-python-script" ]; then
    # Install necessary dependencies and download the model
    uv pip install pyyaml python-box llama-cpp-python huggingface-hub
    uv run $CURRENT_SCRIPT_DIR/internal/download-llamacpp-gguf.py
else
    uv pip install huggingface-hub[cli]

    if ! [ -x "$(command -v yq)" ]; then
        sudo wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq &&\
        sudo chmod +x /usr/local/bin/yq
    fi

    CONFIGURATION_FILE=$CURRENT_SCRIPT_DIR/../configuration.yaml
    MODEL_REPOSITORY=$(yq '.MODEL_PATH' $CONFIGURATION_FILE)
    MMPROJ_REPOSITORY=$(yq '.VISION_HANDLER_PATH' $CONFIGURATION_FILE)
    MODEL_FILE=$(yq '.MODEL_ARGS.filename' $CONFIGURATION_FILE)
    MMPROJ_FILE=$(yq '.VISION_ARGS.filename' $CONFIGURATION_FILE)
    MODEL_LOCAL_DIR=$(yq '.MODEL_ARGS.local_dir' $CONFIGURATION_FILE)
    MMPROJ_LOCAL_DIR=$(yq '.VISION_ARGS.local_dir' $CONFIGURATION_FILE)

    if [ ! -f "$MODEL_LOCAL_DIR/$MODEL_FILE" ]; then
        echo "uv run hf download $MODEL_REPOSITORY $MODEL_FILE --local-dir $MODEL_LOCAL_DIR"
        uv run hf download $MODEL_REPOSITORY $MODEL_FILE --local-dir $MODEL_LOCAL_DIR
    else
        echo "Skipping download of $MODEL_REPOSITORY/$MODEL_FILE to $MODEL_LOCAL_DIR/$MODEL_FILE as a file called $MODEL_LOCAL_DIR/$MODEL_FILE already exists."
    fi
    
    if [ ! -f "$MMPROJ_LOCAL_DIR/$MMPROJ_FILE" ]; then
        echo "uv run hf download $MMPROJ_REPOSITORY $MMPROJ_FILE --local-dir $MMPROJ_LOCAL_DIR"
        uv run hf download $MMPROJ_REPOSITORY $MMPROJ_FILE --local-dir $MMPROJ_LOCAL_DIR
    else
        echo "Skipping download of $MMPROJ_REPOSITORY/$MMPROJ_FILE to $MMPROJ_LOCAL_DIR/$MMPROJ_FILE as a file called $MMPROJ_LOCAL_DIR/$MMPROJ_FILE already exists."
    fi
fi

# Remove the temporary virtual environment
# rm -rf .venv

cd $ORIGINAL_PWD
