#!/bin/bash

# Script to create a new instance configuration

if [ -z "$1" ]; then
    echo "Usage: $0 <instance_number>"
    echo ""
    echo "Example: $0 3"
    echo "  This will create .env.instance3 with auto-incremented ports"
    exit 1
fi

INSTANCE_NUM=$1
ENV_FILE=".env.instance${INSTANCE_NUM}"

# Check if instance already exists
if [ -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE already exists!"
    echo "Delete it first if you want to recreate it."
    exit 1
fi

# Calculate ports based on instance number
# Base ports: Instance 1 uses 443, 8000, 5000, 10000
# Each instance increments by 1
HTTPS_PORT=$((442 + INSTANCE_NUM))
HTTP_PORT=$((79 + INSTANCE_NUM))
ADMIN_PORT=$((8442 + INSTANCE_NUM))
LLM_PORT=$((7999 + INSTANCE_NUM))
SESSION_PORT=$((4999 + INSTANCE_NUM))
DOZZLE_PORT=$((9999 + INSTANCE_NUM))
UI_PORT=$((3000 + INSTANCE_NUM))

echo "Creating $ENV_FILE with the following configuration:"
echo "  HTTP Port:    $HTTP_PORT"
echo "  HTTPS Port:   $HTTPS_PORT"
echo "  Admin Port:   $ADMIN_PORT"
echo "  LLM Port:     $LLM_PORT"
echo "  Session Port: $SESSION_PORT"
echo "  Dozzle Port:  $DOZZLE_PORT"
echo "  UI Port:      $UI_PORT"
echo ""

cat > "$ENV_FILE" << EOF
# Instance ${INSTANCE_NUM} Configuration
INSTANCE_ID=${INSTANCE_NUM}

# Network
DOCKER_NETWORK_NAME=fast-food-${INSTANCE_NUM}

# Ports (each instance needs unique ports)
HTTP_PORT=${HTTP_PORT}
HTTPS_PORT=${HTTPS_PORT}
ADMIN_PORT=${ADMIN_PORT}
LLM_PORT=${LLM_PORT}
SESSION_PORT=${SESSION_PORT}
DOZZLE_PORT=${DOZZLE_PORT}
UI_PORT=${UI_PORT}

# LLM Configuration (same for all instances, or customize per instance)
LLM_DEVICE_TYPE=cpu
MODEL=minicpm-v-2_6
OPENAI_BASE_URL=http://llama-cpp-server:8080/v1
OPENAI_API_KEY=sk-no-key-required

# Web Agent Configuration
WEB_AGENT_IMAGE=web-agent
WEB_AGENT_TAG=latest

# Optional: Customize system prompt per instance
# SYSTEM_PROMPT="You are Instance ${INSTANCE_NUM}'s assistant..."
EOF

echo "✓ Created $ENV_FILE"
echo ""
echo "Next steps:"
echo "  1. Review and edit $ENV_FILE if needed"
echo "  2. Start the instance: ./manage-instances.sh start-${INSTANCE_NUM}"
echo "  3. Check status: ./manage-instances.sh status"
echo ""
echo "Access points:"
echo "  HTTPS: https://localhost:${HTTPS_PORT}"
echo "  Session Manager API: http://localhost:${SESSION_PORT}"
echo "  LLM API: http://localhost:${LLM_PORT}"
echo "  Dozzle Logs: http://localhost:${DOZZLE_PORT}"

chmod 644 "$ENV_FILE"
