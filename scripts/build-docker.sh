#!/bin/bash

# Set up environment variables
source .env

# Build the web-agent
cd python/fastfoodordering
docker compose -f "docker-compose.web-agent.yaml" build
cd ../..

# Build the rest of the project
docker compose build
