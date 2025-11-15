#!/bin/bash

# Auto-pull script for FastFoodOrderingAgent
# This script pulls the latest changes from the GitHub repository

# Set the repository directory
REPO_DIR="/home/fastfoodorderingagent/FastFoodOrderingAgent"
LOG_FILE="$REPO_DIR/logs/auto-pull.log"

# Create logs directory if it doesn't exist
mkdir -p "$REPO_DIR/logs"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Change to repository directory
cd "$REPO_DIR" || {
    log_message "ERROR: Failed to change to repository directory"
    exit 1
}

log_message "Starting auto-pull process..."

# Fetch the latest changes
log_message "Fetching from origin..."
git fetch origin 2>&1 | tee -a "$LOG_FILE"

# Check if there are any changes
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$(git branch --show-current))

if [ "$LOCAL" = "$REMOTE" ]; then
    log_message "Already up to date. No changes to pull."
else
    log_message "Changes detected. Pulling updates..."
    
    # Stash any local changes (optional - remove if you don't want this)
    # git stash save "Auto-stash before pull at $(date)" 2>&1 | tee -a "$LOG_FILE"
    
    # Pull the latest changes
    git pull origin $(git branch --show-current) 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        log_message "Successfully pulled latest changes"
        
        # Optional: Restart services after pull (uncomment if needed)
        log_message "Restarting Docker services..."
        docker compose down && docker compose up -d 2>&1 | tee -a "$LOG_FILE"
    else
        log_message "ERROR: Failed to pull changes"
        exit 1
    fi
fi

log_message "Auto-pull process completed"
