#!/bin/bash

# Security setup script for FastFoodOrderingAgent
# This script configures firewall rules using UFW (Uncomplicated Firewall)

echo "=== FastFoodOrderingAgent Security Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Install UFW if not already installed
if ! command -v ufw &> /dev/null; then
    echo "Installing UFW..."
    apt-get update
    apt-get install -y ufw
fi

echo "Configuring firewall rules..."

# Reset UFW to default settings
ufw --force reset

# Set default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (IMPORTANT: Don't lock yourself out!)
ufw allow 22/tcp comment 'SSH'

# Allow HTTP and HTTPS through Nginx
ufw allow 80/tcp comment 'HTTP - Nginx'
ufw allow 443/tcp comment 'HTTPS - Nginx'

# Optional: Allow admin panel on port 8443 (only if needed)
# ufw allow 8443/tcp comment 'HTTPS Admin Panel'

# Block direct access to application ports
ufw deny 3001/tcp comment 'Block direct UI access'
ufw deny 8080/tcp comment 'Block direct session-manager access'
ufw deny 10000/tcp comment 'Block direct Dozzle access'
ufw deny 8000/tcp comment 'Block direct LLM server access'

# Enable UFW
ufw --force enable

echo ""
echo "Firewall configuration complete!"
echo ""
echo "Active rules:"
ufw status numbered

echo ""
echo "=== Security Summary ==="
echo "✓ SSH (port 22): ALLOWED"
echo "✓ HTTP (port 80): ALLOWED (redirects to HTTPS)"
echo "✓ HTTPS (port 443): ALLOWED"
echo "✗ Direct application ports: BLOCKED"
echo ""
echo "Your application is now accessible only through:"
echo "  - https://67.8.48.44 (main UI)"
echo "  - https://67.8.48.44/logs (Dozzle - requires authentication)"
echo "  - https://67.8.48.44/api/session (Session Manager - requires authentication)"
