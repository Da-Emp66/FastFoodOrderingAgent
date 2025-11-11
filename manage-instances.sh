#!/bin/bash

# Script to dynamically manage multiple instances of the Fast Food Ordering Agent
# Automatically detects instances based on .env.instance* files

# Function to get all instance numbers from .env.instance* files
get_instances() {
    for file in .env.instance*; do
        if [ -f "$file" ]; then
            echo "$file" | sed 's/.env.instance//'
        fi
    done | sort -n
}

# Function to get instance info from env file
get_instance_info() {
    local instance_num=$1
    local env_file=".env.instance${instance_num}"
    
    if [ ! -f "$env_file" ]; then
        echo "Error: $env_file not found"
        return 1
    fi
    
    # Source the env file to get port info
    local https_port=$(grep "^HTTPS_PORT=" "$env_file" | cut -d'=' -f2)
    local session_port=$(grep "^SESSION_PORT=" "$env_file" | cut -d'=' -f2)
    local llm_port=$(grep "^LLM_PORT=" "$env_file" | cut -d'=' -f2)
    
    echo "HTTPS: ${https_port:-N/A}, Session: ${session_port:-N/A}, LLM: ${llm_port:-N/A}"
}

# Function to start a single instance
start_instance() {
    local instance_num=$1
    echo "Starting Instance $instance_num..."
    docker compose -p fastfood-instance-${instance_num} --env-file .env.instance${instance_num} up -d
    echo "Instance $instance_num started! ($(get_instance_info $instance_num))"
}

# Function to stop a single instance
stop_instance() {
    local instance_num=$1
    echo "Stopping Instance $instance_num..."
    docker compose -p fastfood-instance-${instance_num} --env-file .env.instance${instance_num} down
    echo "Instance $instance_num stopped!"
}

# Function to restart a single instance
restart_instance() {
    local instance_num=$1
    echo "Restarting Instance $instance_num..."
    docker compose -p fastfood-instance-${instance_num} --env-file .env.instance${instance_num} down
    docker compose -p fastfood-instance-${instance_num} --env-file .env.instance${instance_num} up -d
    echo "Instance $instance_num restarted! ($(get_instance_info $instance_num))"
}

# Function to show status
show_status() {
    local instances=$(get_instances)
    
    if [ -z "$instances" ]; then
        echo "No instance configuration files found (.env.instance*)"
        return
    fi
    
    echo "=== Configured Instances ==="
    for instance_num in $instances; do
        echo ""
        echo "Instance $instance_num ($(get_instance_info $instance_num))"
        echo "---"
        docker ps -a --filter "label=com.docker.compose.project=fastfood-instance-${instance_num}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -n 10
        if [ ${PIPESTATUS[0]} -ne 0 ] || [ -z "$(docker ps -a --filter "label=com.docker.compose.project=fastfood-instance-${instance_num}" -q)" ]; then
            echo "No containers found"
        fi
    done
}

# Function to list available instances
list_instances() {
    local instances=$(get_instances)
    
    if [ -z "$instances" ]; then
        echo "No instances configured. Create .env.instance1, .env.instance2, etc. to add instances."
        return
    fi
    
    echo "Available instances:"
    for instance_num in $instances; do
        echo "  Instance $instance_num - $(get_instance_info $instance_num)"
    done
}

# Main command handling
case "$1" in
    start-all)
        echo "Starting all instances..."
        instances=$(get_instances)
        if [ -z "$instances" ]; then
            echo "No instances configured!"
            exit 1
        fi
        for instance_num in $instances; do
            start_instance $instance_num
        done
        echo "All instances started!"
        ;;
    stop-all)
        echo "Stopping all instances..."
        instances=$(get_instances)
        if [ -z "$instances" ]; then
            echo "No instances configured!"
            exit 1
        fi
        for instance_num in $instances; do
            stop_instance $instance_num
        done
        echo "All instances stopped!"
        ;;
    restart-all)
        echo "Restarting all instances..."
        instances=$(get_instances)
        if [ -z "$instances" ]; then
            echo "No instances configured!"
            exit 1
        fi
        for instance_num in $instances; do
            restart_instance $instance_num
        done
        echo "All instances restarted!"
        ;;
    start-*)
        instance_num=${1#start-}
        if [ -f ".env.instance${instance_num}" ]; then
            start_instance $instance_num
        else
            echo "Error: .env.instance${instance_num} not found!"
            echo ""
            list_instances
            exit 1
        fi
        ;;
    stop-*)
        instance_num=${1#stop-}
        if [ -f ".env.instance${instance_num}" ]; then
            stop_instance $instance_num
        else
            echo "Error: .env.instance${instance_num} not found!"
            echo ""
            list_instances
            exit 1
        fi
        ;;
    restart-*)
        instance_num=${1#restart-}
        if [ -f ".env.instance${instance_num}" ]; then
            restart_instance $instance_num
        else
            echo "Error: .env.instance${instance_num} not found!"
            echo ""
            list_instances
            exit 1
        fi
        ;;
    status)
        show_status
        ;;
    list)
        list_instances
        ;;
    *)
        echo "Usage: $0 {start-<N>|stop-<N>|restart-<N>|start-all|stop-all|restart-all|status|list}"
        echo ""
        echo "Commands:"
        echo "  start-<N>    - Start instance N (e.g., start-1, start-2, start-3)"
        echo "  stop-<N>     - Stop instance N"
        echo "  restart-<N>  - Restart instance N"
        echo "  start-all    - Start all configured instances"
        echo "  stop-all     - Stop all configured instances"
        echo "  restart-all  - Restart all configured instances"
        echo "  status       - Show status of all instances"
        echo "  list         - List all configured instances"
        echo ""
        echo "To add a new instance:"
        echo "  1. Copy .env.instance1 to .env.instance3 (or any number)"
        echo "  2. Edit the new file to use different ports"
        echo "  3. Run: ./manage-instances.sh start-3"
        echo ""
        list_instances
        exit 1
        ;;
esac

exit 0
