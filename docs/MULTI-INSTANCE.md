# Multi-Instance Setup Guide

This application is now configured to run up to **2 simultaneous instances** on the same server.

## Instance Configuration

### Instance 1
- **HTTP**: Port 80
- **HTTPS**: Port 443
- **Admin**: Port 8443
- **LLM API**: Port 8000
- **Dozzle Logs**: Port 10000
- **Network**: fast-food-1

### Instance 2
- **HTTP**: Port 81
- **HTTPS**: Port 444
- **Admin**: Port 8444
- **LLM API**: Port 8001
- **Dozzle Logs**: Port 10001
- **Network**: fast-food-2

## Quick Start

### Using the Management Script (Recommended)

```bash
# Start Instance 1
./manage-instances.sh start-1

# Start Instance 2
./manage-instances.sh start-2

# Start both instances
./manage-instances.sh start-all

# Check status
./manage-instances.sh status

# Stop an instance
./manage-instances.sh stop-1
./manage-instances.sh stop-2

# Restart an instance
./manage-instances.sh restart-1
```

### Manual Docker Compose Commands

```bash
# Start Instance 1
docker-compose --env-file .env.instance1 up -d

# Start Instance 2
docker-compose --env-file .env.instance2 up -d

# Stop Instance 1
docker-compose --env-file .env.instance1 down

# Stop Instance 2
docker-compose --env-file .env.instance2 down
```

## Accessing the Instances

### Instance 1
- Web UI: https://localhost or https://localhost:30443
- LLM API: http://localhost:38000
- Admin Panel: https://localhost:38443
- Logs (Dozzle): Accessible via nginx proxy

### Instance 2
- Web UI: https://localhost:444
- LLM API: http://localhost:8001
- Admin Panel: https://localhost:8444
- Logs (Dozzle): Accessible via nginx proxy

## Resource Usage (A6000 GPU with 48GB VRAM)

Each instance uses approximately:
- **VRAM**: ~10-12GB (with context size 8192)
- **RAM**: ~4GB
- **CPU**: 6 threads

**Total for 2 instances:**
- **VRAM**: ~20-24GB (50% of GPU)
- **RAM**: ~8GB (50% of system RAM)
- **CPU**: All 12 threads will be utilized

## Environment Variables

Each instance has its own `.env.instanceX` file:

- `.env.instance1` - Configuration for Instance 1
- `.env.instance2` - Configuration for Instance 2

You can modify these files to customize ports or other settings.

## Important Notes

1. **Port Conflicts**: Make sure no other services are using the configured ports
2. **GPU Sharing**: Both instances share the same A6000 GPU
3. **Performance**: With 2 instances running, expect some performance degradation under heavy load
4. **Network Names**: Each instance uses a separate Docker network to avoid conflicts
5. **Volumes**: Each instance has separate volumes for SSL certificates and logs

## Firewall Configuration

If using a firewall, you need to allow these ports:

```bash
# Instance 1
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8443/tcp
sudo ufw allow 8000/tcp

# Instance 2
sudo ufw allow 81/tcp
sudo ufw allow 444/tcp
sudo ufw allow 8444/tcp
sudo ufw allow 8001/tcp
```

## Troubleshooting

### Check running containers
```bash
./manage-instances.sh status
# or
docker ps -a
```

### View logs for specific instance
```bash
# Instance 1
docker logs llama-cpp-server-1
docker logs nginx-proxy-1
docker logs session-manager-1

# Instance 2
docker logs llama-cpp-server-2
docker logs nginx-proxy-2
docker logs session-manager-2
```

### Rebuild containers
```bash
docker-compose --env-file .env.instance1 up -d --build
docker-compose --env-file .env.instance2 up -d --build
```
