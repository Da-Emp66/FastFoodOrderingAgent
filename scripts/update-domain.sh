#!/bin/bash

# Script to update domain name in nginx configuration

CURRENT_DOMAIN="67.8.48.44"
NEW_DOMAIN="${1}"

if [ -z "$NEW_DOMAIN" ]; then
    echo "Usage: $0 <new-domain>"
    echo ""
    echo "Example:"
    echo "  $0 myfastfood.com"
    echo "  $0 app.yourdomain.com"
    echo ""
    echo "This will:"
    echo "  1. Update nginx.conf with your domain name"
    echo "  2. Set up Let's Encrypt SSL certificate"
    echo "  3. Restart nginx"
    exit 1
fi

echo "════════════════════════════════════════════════════════════"
echo "  Updating domain from $CURRENT_DOMAIN to $NEW_DOMAIN"
echo "════════════════════════════════════════════════════════════"
echo ""

# Backup current config
echo "Creating backup of nginx.conf..."
cp nginx/nginx.conf nginx/nginx.conf.backup
echo "✓ Backup saved to nginx/nginx.conf.backup"
echo ""

# Update nginx configuration
echo "Updating nginx.conf..."
sed -i "s/$CURRENT_DOMAIN/$NEW_DOMAIN/g" nginx/nginx.conf
echo "✓ Updated all instances of $CURRENT_DOMAIN to $NEW_DOMAIN"
echo ""

# Restart nginx to apply changes
echo "Restarting nginx..."
docker compose restart nginx
echo "✓ Nginx restarted"
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  Domain Updated Successfully!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Your application is now configured for: https://$NEW_DOMAIN"
echo ""
echo "Next steps:"
echo "  1. Make sure your DNS A record points to 67.8.48.44"
echo "  2. Wait for DNS to propagate (can take 5 minutes to 48 hours)"
echo "  3. Test with: curl -I https://$NEW_DOMAIN"
echo ""
echo "To get a trusted SSL certificate (optional):"
echo "  ./nginx/setup-ssl.sh $NEW_DOMAIN your-email@example.com"
echo ""
echo "Access your application at:"
echo "  • Main UI:        https://$NEW_DOMAIN"
echo "  • Logs (Dozzle):  https://$NEW_DOMAIN/logs"
echo "  • API:            https://$NEW_DOMAIN/api/session"
echo "  • Admin Panel:    https://$NEW_DOMAIN:38443"
