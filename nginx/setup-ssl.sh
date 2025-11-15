#!/bin/bash

# Script to set up Let's Encrypt SSL certificates
# Note: This requires a domain name. For IP-only access, use the self-signed cert

DOMAIN="${1:-67.8.48.44}"
EMAIL="${2:-your-email@example.com}"

echo "Setting up Let's Encrypt for: $DOMAIN"
echo "Email: $EMAIL"
echo ""

if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "WARNING: Let's Encrypt does not issue certificates for IP addresses."
    echo "You have two options:"
    echo "1. Use a domain name (recommended): Set up a domain and point it to $DOMAIN"
    echo "2. Use self-signed certificates (already configured)"
    echo ""
    echo "For now, the nginx container will use self-signed certificates."
    echo "To use a domain later, update nginx.conf with your domain and run:"
    echo "  docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d yourdomain.com"
    exit 0
fi

# Install certbot if using a domain
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

if [ $? -eq 0 ]; then
    echo "SSL certificate obtained successfully!"
    echo "Restarting nginx..."
    docker compose restart nginx
else
    echo "Failed to obtain SSL certificate"
    echo "Make sure:"
    echo "1. Your domain points to this server"
    echo "2. Port 80 is accessible"
    echo "3. Nginx is running"
fi
