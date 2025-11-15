#!/bin/bash

# Quick security setup for FastFoodOrderingAgent
# Run this script to apply all security configurations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  FastFoodOrderingAgent - Security Setup                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Authentication
echo "Step 1: Setting up authentication..."
echo "─────────────────────────────────────────────────────────────"
cd "$PROJECT_DIR"
./nginx/setup-auth.sh

echo ""
echo "Step 2: Firewall configuration..."
echo "─────────────────────────────────────────────────────────────"
echo "Setting up firewall requires sudo access."
read -p "Configure firewall now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo "$PROJECT_DIR/scripts/setup-firewall.sh"
else
    echo "Skipping firewall setup. Run manually later with:"
    echo "  sudo $PROJECT_DIR/scripts/setup-firewall.sh"
fi

echo ""
echo "Step 3: Rebuilding Docker containers..."
echo "─────────────────────────────────────────────────────────────"
cd "$PROJECT_DIR"

# Stop existing containers
echo "Stopping existing containers..."
docker compose down

# Build with new configuration
echo "Building containers with nginx..."
docker compose build

# Start services
echo "Starting all services..."
docker compose up -d

echo ""
echo "Step 4: Verifying setup..."
echo "─────────────────────────────────────────────────────────────"
sleep 3
docker compose ps

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Setup Complete!                                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Your application is now secured with:"
echo "  ✓ HTTPS/TLS encryption (self-signed certificate)"
echo "  ✓ Password protection on backend services"
echo "  ✓ Reverse proxy (Nginx)"
echo "  ✓ Firewall rules (if configured)"
echo ""
echo "Access your application at:"
echo "  • Main UI:        https://67.8.48.44"
echo "  • Logs (Dozzle):  https://67.8.48.44/logs (requires auth)"
echo "  • API:            https://67.8.48.44/api/session (requires auth)"
echo ""
echo "Note: Your browser will show a security warning for the"
echo "      self-signed certificate. This is normal for testing."
echo ""
echo "To use a trusted SSL certificate:"
echo "  1. Get a domain name"
echo "  2. Point it to your server IP (67.8.48.44)"
echo "  3. Run: ./nginx/setup-ssl.sh yourdomain.com your@email.com"
echo ""
echo "See SECURITY.md for complete documentation."
