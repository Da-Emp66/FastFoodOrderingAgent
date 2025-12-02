# Scaling Guide - Managing Multiple Instances

## Overview

The FastFoodOrderingAgent now supports **dynamic scaling** by simply adding configuration files. No code changes required!

## Quick Start

### Add a New Instance

```bash
# Create instance 3
./create-instance.sh 3

# Start it
./manage-instances.sh start-3
```

That's it! The system automatically detects and manages the new instance.

### Manage All Instances

```bash
# List all configured instances
./manage-instances.sh list

# Start all instances
./manage-instances.sh start-all

# Stop all instances
./manage-instances.sh stop-all

# Restart all instances
./manage-instances.sh restart-all

# Check status
./manage-instances.sh status
```

## How It Works

### Auto-Detection
The `manage-instances.sh` script automatically discovers instances by scanning for `.env.instance*` files:

```bash
# Automatically managed:
.env.instance1  → Instance 1
.env.instance2  → Instance 2
.env.instance3  → Instance 3
.env.instance10 → Instance 10
```

### Port Auto-Assignment
The `create-instance.sh` script automatically calculates non-conflicting ports:

| Instance | HTTPS | HTTP | Session | LLM  | UI   | Dozzle |
|----------|-------|------|---------|------|------|--------|
| 1        | 443   | 80   | 5000    | 8000 | 3001 | 10000  |
| 2        | 444   | 81   | 5001    | 8001 | 3002 | 10001  |
| 3        | 445   | 82   | 5002    | 8002 | 3003 | 10002  |
| N        | 442+N | 79+N | 4999+N  | 7999+N | 3000+N | 9999+N |

## Commands Reference

### Individual Instance Commands

```bash
# Start specific instance
./manage-instances.sh start-1
./manage-instances.sh start-2
./manage-instances.sh start-3

# Stop specific instance
./manage-instances.sh stop-1

# Restart specific instance
./manage-instances.sh restart-1
```

### Bulk Commands

```bash
# Start all configured instances
./manage-instances.sh start-all

# Stop all configured instances
./manage-instances.sh stop-all

# Restart all configured instances
./manage-instances.sh restart-all

# Show status of all instances
./manage-instances.sh status

# List configured instances
./manage-instances.sh list
```

## Creating Custom Instances

### Method 1: Use the Script (Recommended)

```bash
./create-instance.sh 5
```

This creates `.env.instance5` with auto-calculated ports.

### Method 2: Manual Creation

```bash
# Copy an existing config
cp .env.instance1 .env.instance5

# Edit the file
nano .env.instance5
```

Change these values:
```bash
INSTANCE_ID=5
DOCKER_NETWORK_NAME=fast-food-5
HTTP_PORT=84      # Must be unique
HTTPS_PORT=447    # Must be unique
ADMIN_PORT=8447   # Must be unique
LLM_PORT=8004     # Must be unique
SESSION_PORT=5004 # Must be unique
DOZZLE_PORT=10004 # Must be unique
UI_PORT=3005      # Must be unique
```

## Per-Instance Configuration

Each instance can be customized independently:

```bash
# .env.instance1
LLM_DEVICE_TYPE=gpu  # Use GPU

# .env.instance2
LLM_DEVICE_TYPE=cpu  # Use CPU only

# .env.instance3
LLM_DEVICE_TYPE=gpu
MODEL=minicpm-v-2_6  # Different model
```

## Scaling Patterns

### Small Team (2-5 users)
```bash
./create-instance.sh 1
./create-instance.sh 2
./create-instance.sh 3
./manage-instances.sh start-all
```

**Resources**: ~3-6 GB RAM, 2-4 CPU cores per instance

### Medium Team (5-10 users)
```bash
for i in {1..10}; do
  ./create-instance.sh $i
done
./manage-instances.sh start-all
```

**Resources**: ~30-60 GB RAM, 20-40 CPU cores total

### Load Balancing
For production use with many users, add an nginx load balancer:

```nginx
upstream instances {
    server localhost:35000;  # Instance 1
    server localhost:5001;  # Instance 2
    server localhost:5002;  # Instance 3
    # Add more as needed
}

server {
    location / {
        proxy_pass http://instances;
    }
}
```

## Resource Management

### Check Resource Usage

```bash
# All instances
docker stats

# Specific instance
docker stats --filter "label=com.docker.compose.project=fastfood-instance-1"
```

### Stop Unused Instances

```bash
# Stop just instance 3
./manage-instances.sh stop-3

# Or stop all and start only what you need
./manage-instances.sh stop-all
./manage-instances.sh start-1
./manage-instances.sh start-2
```

## Monitoring

### Check Instance Health

```bash
# Quick status check
./manage-instances.sh status

# Detailed check for instance 1
curl http://localhost:35000/instance/status

# Check logs
docker logs session-manager-1
docker logs session-manager-2
```

### Access Dozzle (Log Viewer)

Each instance has its own Dozzle:
- Instance 1: http://localhost:40000
- Instance 2: http://localhost:10001
- Instance 3: http://localhost:10002

## Troubleshooting

### Port Conflicts

If you get "port already allocated" errors:

```bash
# Find what's using the port
sudo lsof -i :5002

# Stop the conflicting instance
./manage-instances.sh stop-2

# Or change the port in .env.instance2
nano .env.instance2
```

### Instance Won't Start

```bash
# Check logs
docker logs session-manager-3 --tail 100

# Rebuild the instance
docker compose -p fastfood-instance-3 --env-file .env.instance3 up -d --build

# Or use the script
./manage-instances.sh restart-3
```

### Clean Start

```bash
# Stop everything
./manage-instances.sh stop-all

# Remove all networks and volumes
docker network prune -f
docker volume prune -f

# Start fresh
./manage-instances.sh start-all
```

## Best Practices

1. **Multiple users per instance** - Instances now support concurrent users
2. **Start with 2-3 instances** - Add more as needed based on load
3. **Monitor resources** - Use `docker stats` to watch CPU/RAM
4. **Use GPU instances for heavy workloads** - Set `LLM_DEVICE_TYPE=gpu`
5. **Regular backups** - Backup `.env.instance*` files

## Cost Optimization

### Development
```bash
# Run just one instance
./manage-instances.sh stop-all
./manage-instances.sh start-1
```

### Production
```bash
# Auto-start on boot
crontab -e
# Add: @reboot /path/to/manage-instances.sh start-all
```

### Scaling Down
```bash
# Stop high-numbered instances first
./manage-instances.sh stop-10
./manage-instances.sh stop-9
./manage-instances.sh stop-8
```

## Limits

- **Maximum instances**: Limited by available ports and resources
- **Port range**: 65535 total ports available
- **Practical limit**: ~50-100 instances per machine (resource dependent)
- **Concurrent users**: Multiple users can access each instance simultaneously

## Migration from Old System

If you have the old hardcoded setup:

```bash
# The new system is backward compatible
# Your .env.instance1 and .env.instance2 files work as-is
./manage-instances.sh list  # Should show instances 1 and 2
```

No migration needed!
