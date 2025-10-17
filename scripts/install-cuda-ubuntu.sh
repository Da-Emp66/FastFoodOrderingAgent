#!/bin/bash

# Declare context
CURRENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$CURRENT_SCRIPT_DIR/.." && pwd)"

# Update environment - handle spaces in path properly
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
    echo "Loaded .env file. CUDA_VERSION: $CUDA_VERSION"
else
    echo "Warning: .env file not found at $PROJECT_ROOT/.env"
    echo "Setting default CUDA_VERSION=12.4"
    CUDA_VERSION="12.4"
fi

install_cuda () {
    
    # Visit https://developer.nvidia.com/cuda-downloads for more information

    if [ ! -d "/usr/local/cuda-$CUDA_VERSION" ]; then
        
        CUDA_VERSION_WITH_DASHES=$(echo $CUDA_VERSION | sed 's/\./-/g')
        
        # Detect Ubuntu version
        UBUNTU_VERSION=$(lsb_release -rs | tr -d '.')
        
        # Check if we're in WSL or native Ubuntu
        if grep -qi microsoft /proc/version; then
            # WSL environment
            echo "Detected WSL environment"
            REPO_NAME="wsl-ubuntu"
            PIN_URL="https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin"
            PIN_FILE="cuda-wsl-ubuntu.pin"
            DEB_NAME="cuda-repo-wsl-ubuntu-$CUDA_VERSION_WITH_DASHES-local_$CUDA_VERSION.1-1_amd64.deb"
            REPO_PATH="/var/cuda-repo-wsl-ubuntu-$CUDA_VERSION_WITH_DASHES-local"
        else
            # Native Ubuntu environment
            echo "Detected native Ubuntu $UBUNTU_VERSION environment"
            REPO_NAME="ubuntu$UBUNTU_VERSION"
            PIN_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu$UBUNTU_VERSION/x86_64/cuda-ubuntu$UBUNTU_VERSION.pin"
            PIN_FILE="cuda-ubuntu$UBUNTU_VERSION.pin"
            DEB_NAME="cuda-repo-ubuntu$UBUNTU_VERSION-$CUDA_VERSION_WITH_DASHES-local_$CUDA_VERSION.1-1_amd64.deb"
            REPO_PATH="/var/cuda-repo-ubuntu$UBUNTU_VERSION-$CUDA_VERSION_WITH_DASHES-local"
        fi

        # Download and install CUDA repository
        wget $PIN_URL
        sudo mv $PIN_FILE /etc/apt/preferences.d/cuda-repository-pin-600
        wget https://developer.download.nvidia.com/compute/cuda/$CUDA_VERSION.1/local_installers/$DEB_NAME
        sudo dpkg -i $DEB_NAME
        sudo cp $REPO_PATH/cuda-*-keyring.gpg /usr/share/keyrings/
        sudo apt-get update
        sudo apt-get -y install cuda-toolkit-$CUDA_VERSION_WITH_DASHES

    fi

}

# Install the desired cuda version if it is not installed
install_cuda
