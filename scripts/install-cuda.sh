#!/bin/bash

# Declare context
CURRENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Update environment
source $CURRENT_SCRIPT_DIR/../../.env

install_cuda () {
    
    # Visit https://developer.nvidia.com/cuda-downloads for more information

    if [ ! -d "/usr/local/cuda-$CUDA_VERSION" ]; then
        
        CUDA_VERSION_WITH_DASHES=$(echo $CUDA_VERSION | sed 's/\./-/g')

        wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin
        sudo mv cuda-wsl-ubuntu.pin /etc/apt/preferences.d/cuda-repository-pin-600
        wget https://developer.download.nvidia.com/compute/cuda/$CUDA_VERSION.1/local_installers/cuda-repo-wsl-ubuntu-$CUDA_VERSION_WITH_DASHES-local_$CUDA_VERSION.1-1_amd64.deb
        sudo dpkg -i cuda-repo-wsl-ubuntu-$CUDA_VERSION_WITH_DASHES-local_$CUDA_VERSION.1-1_amd64.deb
        sudo cp /var/cuda-repo-wsl-ubuntu-$CUDA_VERSION_WITH_DASHES-local/cuda-*-keyring.gpg /usr/share/keyrings/
        sudo apt-get update
        sudo apt-get -y install cuda-toolkit-$CUDA_VERSION_WITH_DASHES

    fi

}

# Install the desired cuda version if it is not installed
install_cuda
