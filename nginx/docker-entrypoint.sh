#!/bin/sh
set -e

# Wait for upstream services to be resolvable before starting nginx
# This prevents nginx from failing to start due to DNS resolution issues

echo "Waiting for upstream services to be available..."

# Maximum wait time in seconds
MAX_WAIT=60
WAIT_INTERVAL=2
elapsed=0

# Function to check if a hostname is resolvable
check_host() {
    host=$1
    if getent hosts "$host" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Wait for each upstream service
for service in fastfoodordering-ui session-manager dozzle; do
    echo "Checking $service..."
    while ! check_host "$service"; do
        if [ $elapsed -ge $MAX_WAIT ]; then
            echo "WARNING: $service not resolvable after ${MAX_WAIT}s, starting nginx anyway..."
            break
        fi
        echo "  $service not yet available, waiting..."
        sleep $WAIT_INTERVAL
        elapsed=$((elapsed + WAIT_INTERVAL))
    done
    if check_host "$service"; then
        echo "  ✓ $service is resolvable"
    fi
done

echo "Starting nginx..."

# Execute the original nginx entrypoint
exec /docker-entrypoint.sh "$@"
