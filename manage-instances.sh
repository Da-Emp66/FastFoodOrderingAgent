#!/bin/bash

# Script to manage multiple instances of the Fast Food Ordering Agent

case "$1" in
    start-1)
        echo "Starting Instance 1..."
        docker compose -p fastfood-instance-1 --env-file .env.instance1 up -d
        echo "Instance 1 started!"
        echo "Access at: https://localhost:443"
        echo "LLM API: http://localhost:8000"
        ;;
    start-2)
        echo "Starting Instance 2..."
        docker compose -p fastfood-instance-2 --env-file .env.instance2 up -d
        echo "Instance 2 started!"
        echo "Access at: https://localhost:444"
        echo "LLM API: http://localhost:8001"
        ;;
    start-all)
        echo "Starting all instances..."
        docker compose -p fastfood-instance-1 --env-file .env.instance1 up -d
        docker compose -p fastfood-instance-2 --env-file .env.instance2 up -d
        echo "All instances started!"
        ;;
    stop-1)
        echo "Stopping Instance 1..."
        docker compose -p fastfood-instance-1 --env-file .env.instance1 down
        echo "Instance 1 stopped!"
        ;;
    stop-2)
        echo "Stopping Instance 2..."
        docker compose -p fastfood-instance-2 --env-file .env.instance2 down
        echo "Instance 2 stopped!"
        ;;
    stop-all)
        echo "Stopping all instances..."
        docker compose -p fastfood-instance-1 --env-file .env.instance1 down
        docker compose -p fastfood-instance-2 --env-file .env.instance2 down
        echo "All instances stopped!"
        ;;
    restart-1)
        echo "Restarting Instance 1..."
        docker compose -p fastfood-instance-1 --env-file .env.instance1 down
        docker compose -p fastfood-instance-1 --env-file .env.instance1 up -d
        echo "Instance 1 restarted!"
        ;;
    restart-2)
        echo "Restarting Instance 2..."
        docker compose -p fastfood-instance-2 --env-file .env.instance2 down
        docker compose -p fastfood-instance-2 --env-file .env.instance2 up -d
        echo "Instance 2 restarted!"
        ;;
    restart-all)
        echo "Restarting all instances..."
        docker compose -p fastfood-instance-1 --env-file .env.instance1 down
        docker compose -p fastfood-instance-2 --env-file .env.instance2 down
        docker compose -p fastfood-instance-1 --env-file .env.instance1 up -d
        docker compose -p fastfood-instance-2 --env-file .env.instance2 up -d
        echo "All instances restarted!"
        ;;
    status)
        echo "=== Instance 1 Containers ==="
        docker ps -a | grep -E "(fast-food-1|instance-1|INSTANCE_ID.*1)" || echo "No containers found"
        echo ""
        echo "=== Instance 2 Containers ==="
        docker ps -a | grep -E "(fast-food-2|instance-2|INSTANCE_ID.*2)" || echo "No containers found"
        ;;
    *)
        echo "Usage: $0 {start-1|start-2|start-all|stop-1|stop-2|stop-all|restart-1|restart-2|restart-all|status}"
        echo ""
        echo "Commands:"
        echo "  start-1      - Start Instance 1 (ports 80, 443, 8443, 8000)"
        echo "  start-2      - Start Instance 2 (ports 81, 444, 8444, 8001)"
        echo "  start-all    - Start all instances"
        echo "  stop-1       - Stop Instance 1"
        echo "  stop-2       - Stop Instance 2"
        echo "  stop-all     - Stop all instances"
        echo "  restart-1    - Restart Instance 1"
        echo "  restart-2    - Restart Instance 2"
        echo "  restart-all  - Restart all instances"
        echo "  status       - Show status of all instances"
        exit 1
        ;;
esac

exit 0
