# Security Setup Guide for FastFoodOrderingAgent

This guide will help you secure your FastFoodOrderingAgent application with HTTPS and authentication.

## Security Features

1. **HTTPS/TLS Encryption** - All traffic encrypted
2. **Authentication** - Backend services protected with passwords
3. **Reverse Proxy** - Nginx handles all external requests
4. **Firewall Rules** - Block direct access to application ports
5. **Rate Limiting** - Prevent abuse and DDoS attacks

## Quick Setup

### 1. Set Up Authentication

Create password files for protecting backend services:

```bash
cd /home/fastfoodorderingagent/FastFoodOrderingAgent
chmod +x nginx/setup-auth.sh
./nginx/setup-auth.sh
```

This will prompt you to create:
- Regular user (for /logs and /api/session access)
- Admin user (for admin panel on port 8443)

### 2. Configure Firewall

Set up UFW firewall to block direct access to application ports:

```bash
sudo chmod +x scripts/setup-firewall.sh
sudo ./scripts/setup-firewall.sh
```

### 3. Build and Start Services

```bash
# Stop existing containers
docker compose down

# Build with new nginx configuration
docker compose build

# Start all services
docker compose up -d
```

### 4. Verify Setup

Check that services are running:

```bash
docker compose ps
```

You should see:
- nginx-proxy
- fastfoodordering-ui
- session-manager
- dozzle
- llama-cpp-server

## Access Your Application

### Public Access (No Authentication Required)
- **Main UI**: `https://67.8.48.44`
  - Self-signed certificate warning is normal (see SSL setup below)

### Protected Access (Authentication Required)
- **Logs (Dozzle)**: `https://67.8.48.44/logs`
- **Session Manager API**: `https://67.8.48.44/api/session`
- **Admin Panel**: `https://67.8.48.44:8443` (optional)

## SSL Certificate Options

### Option 1: Self-Signed Certificate (Current - For Testing)

The nginx container automatically generates a self-signed certificate. Browsers will show a security warning.

**Pros**: Works immediately, no domain required
**Cons**: Browser warnings, not trusted by default

### Option 2: Let's Encrypt (Recommended - Requires Domain)

To use a trusted SSL certificate, you need a domain name:

1. **Get a domain** (e.g., from Namecheap, GoDaddy, etc.)

2. **Point domain to your server**:
   - Create an A record pointing to `67.8.48.44`
   - Example: `fastfood.yourdomain.com` → `67.8.48.44`

3. **Update nginx configuration**:
   ```bash
   # Edit nginx/nginx.conf
   # Replace all instances of '67.8.48.44' with 'fastfood.yourdomain.com'
   nano nginx/nginx.conf
   ```

4. **Obtain SSL certificate**:
   ```bash
   chmod +x nginx/setup-ssl.sh
   ./nginx/setup-ssl.sh fastfood.yourdomain.com your-email@example.com
   ```

5. **Restart nginx**:
   ```bash
   docker compose restart nginx
   ```

### Option 3: Cloudflare Tunnel (Alternative)

Use Cloudflare's free tunnel service for HTTPS without exposing ports:
- No domain purchase required
- Free SSL certificates
- DDoS protection included
- [Setup Guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)

## Security Best Practices

### 1. Change Default Passwords

The authentication setup script creates initial passwords. Change them regularly:

```bash
# Create new password file
docker run --rm -i httpd:alpine htpasswd -c -B -n username > nginx/.htpasswd
```

### 2. Restrict Admin Access by IP

Edit `nginx/nginx.conf` and uncomment/modify the IP restrictions:

```nginx
# In the admin panel server block
allow 192.168.1.0/24;  # Your trusted network
deny all;
```

### 3. Monitor Logs

View nginx access logs for suspicious activity:

```bash
docker compose logs -f nginx

# Or use Dozzle at https://67.8.48.44/logs
```

### 4. Keep Services Updated

Regularly update Docker images:

```bash
docker compose pull
docker compose up -d
```

### 5. Backup Configuration

```bash
# Backup authentication files
cp nginx/.htpasswd nginx/.htpasswd.backup
cp nginx/.htpasswd_admin nginx/.htpasswd_admin.backup

# Backup SSL certificates (if using Let's Encrypt)
docker run --rm -v $(pwd):/backup -v certbot-conf:/certs alpine tar czf /backup/ssl-backup.tar.gz /certs
```

## Troubleshooting

### Can't access the application

1. Check firewall status:
   ```bash
   sudo ufw status
   ```

2. Verify nginx is running:
   ```bash
   docker compose ps nginx
   docker compose logs nginx
   ```

3. Check if ports are listening:
   ```bash
   sudo netstat -tlnp | grep -E '(80|443)'
   ```

### SSL Certificate Errors

1. For self-signed certificates, you can proceed past browser warnings
2. For Let's Encrypt issues, check:
   ```bash
   docker compose logs certbot
   ```

### Authentication Not Working

1. Verify password files exist:
   ```bash
   ls -la nginx/.htpasswd*
   ```

2. Test credentials:
   ```bash
   curl -u username:password https://67.8.48.44/logs
   ```

### Services Can't Communicate

Ensure all services are on the same Docker network:
```bash
docker network inspect fast-food
```

## Additional Security Measures

### 1. Enable Docker Content Trust
```bash
export DOCKER_CONTENT_TRUST=1
```

### 2. Use Docker Secrets (for production)
Move sensitive data to Docker secrets instead of environment variables.

### 3. Implement Rate Limiting on Application Level
Add rate limiting in your application code, not just nginx.

### 4. Set Up Monitoring
- Use Prometheus + Grafana for metrics
- Set up alerts for unusual activity
- Monitor resource usage

### 5. Regular Security Audits
```bash
# Scan for vulnerabilities
docker scan nginx-proxy
docker scan fastfoodordering-ui
```

## Port Summary

| Port  | Service | Access | Description |
|-------|---------|--------|-------------|
| 80    | Nginx   | Public | HTTP (redirects to HTTPS) |
| 443   | Nginx   | Public | HTTPS - Main application |
| 8443  | Nginx   | Restricted | HTTPS - Admin panel (optional) |
| 3000  | UI      | Internal only | Blocked by firewall |
| 8080  | Session | Internal only | Blocked by firewall |
| 8080  | Dozzle  | Internal only | Blocked by firewall |
| 8000  | LLM     | Internal only | Blocked by firewall |

## Support

If you encounter issues, check:
1. Docker logs: `docker compose logs`
2. Nginx logs: `docker compose logs nginx`
3. Firewall: `sudo ufw status verbose`
4. Network: `docker network inspect fast-food`
