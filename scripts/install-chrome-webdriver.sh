#!/bin/bash

# Fetch the latest download for Google Chrome in Linux
wget -nc https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Install Google Chrome for Linux
sudo apt update -y
sudo apt install ./google-chrome-stable_current_amd64.deb
