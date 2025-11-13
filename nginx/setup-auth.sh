#!/bin/bash

# Script to set up authentication for Nginx
# This creates password files for basic authentication

NGINX_DIR="$(dirname "$0")"

echo "Setting up Nginx authentication..."

# Install apache2-utils if not already installed
if ! command -v htpasswd &> /dev/null; then
    echo "Installing apache2-utils..."
    sudo apt-get update && sudo apt-get install -y apache2-utils
fi

# Create password for regular users (session manager, logs)
echo "=== Regular User Authentication ==="
read -p "Enter username for backend services access: " username
sudo htpasswd -c -B "$NGINX_DIR/.htpasswd" "$username"

echo ""
echo "=== Admin Authentication (for admin panel) ==="
read -p "Enter admin username: " admin_username
sudo htpasswd -c -B "$NGINX_DIR/.htpasswd-admin" "$admin_username"

# Set proper permissions
sudo chmod 644 "$NGINX_DIR/.htpasswd"
sudo chmod 644 "$NGINX_DIR/.htpasswd-admin"

echo ""
echo "Authentication files created successfully!"
echo "Files created:"
echo "  - $NGINX_DIR/.htpasswd (for /api/session and /logs)"
echo "  - $NGINX_DIR/.htpasswd-admin (for admin panel)"
echo ""
echo "Now restart nginx to apply changes:"
echo "  docker compose restart nginx-proxy"
