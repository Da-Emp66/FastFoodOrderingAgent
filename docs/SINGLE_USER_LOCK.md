# Single User Per Instance Lock

## ⚠️ DEPRECATED - FEATURE REMOVED

**Note: The single-user lock feature has been removed from the codebase.**

This document is kept for historical reference only. The system now supports **multiple concurrent users** per instance without any locking mechanism.

---

## Previous Overview (No Longer Applicable)

~~Each instance of the FastFoodOrderingAgent enforced a **single active user** at a time to prevent resource conflicts and ensure optimal performance.~~

The single-user lock has been removed to allow better scalability and concurrent access.

## How It Works

### Automatic Locking
- When a user sends a request to `/{user}/sessions/chat`, they automatically acquire the instance lock
- The lock is tied to their username
- The lock refreshes on every request (timeout resets)

### Lock Timeout
- **Default timeout**: 1 hour of inactivity
- After 1 hour with no requests, the lock automatically releases
- The next user can then acquire the lock

### Blocked Access
If a second user tries to access a locked instance, they receive:
```json
{
  "response": "This instance is currently in use by another user. Please try again later or use a different instance.",
  "session_id": null
}
```

## API Endpoints

### Check Instance Status
```bash
GET /instance/status
```

**Response:**
```json
{
  "locked": true,
  "active_user": "john@example.com",
  "last_activity": 1699632000.123
}
```

### Manually Release Lock
```bash
POST /{user}/release
```

**Success Response:**
```json
{
  "message": "Instance lock released successfully"
}
```

**Error Response (wrong user):**
```json
{
  "error": "You don't have the lock",
  "locked_by": "other_user@example.com"
}
```

## Usage Examples

### Check if Instance is Available
```bash
curl https://your-domain.com/instance/status
```

### Release Lock When Done
```bash
curl -X POST https://your-domain.com/john@example.com/release
```

### Using with Frontend
```typescript
// Check status before starting
const status = await fetch('/instance/status').then(r => r.json());
if (status.locked && status.active_user !== currentUser) {
  alert('Instance is in use. Please wait.');
}

// Release when user logs out or closes app
window.addEventListener('beforeunload', () => {
  fetch(`/${currentUser}/release`, { method: 'POST' });
});
```

## Multi-Instance Setup

To serve multiple users simultaneously, run multiple instances:

```bash
# Instance 1 - ports 443, 8000
./manage-instances.sh start-1

# Instance 2 - ports 444, 8001
./manage-instances.sh start-2
```

Each instance maintains its own lock independently.

## Implementation Details

- **Lock storage**: In-memory (lost on restart)
- **Scope**: Per instance (not shared across instances)
- **Thread-safety**: Single worker mode (uvicorn workers=1)

## Limitations

- Lock is **not persisted** - restarting the service releases all locks
- Does **not work** with multiple uvicorn workers (set `workers=1`)
- No distributed lock for multi-replica deployments

For production deployments requiring high availability, consider implementing Redis-based distributed locking.
