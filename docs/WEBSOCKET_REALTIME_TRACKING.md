# Real-Time Bus Tracking via WebSocket

## Overview

This document describes the real-time bus location tracking system using Django Channels and WebSocket technology.

## Architecture

### Components

1. **GPS Data Ingestion** (`kiosks/models.py`)
   - Kiosks send GPS pings via REST API
   - Saved to `BusLocation` model

2. **Signal Handler** (`realtime/signals.py`)
   - Django signal triggered on new `BusLocation` creation
   - Publishes event to Redis Pub/Sub channel

3. **WebSocket Consumer** (`realtime/consumers.py`)
   - Listens to Redis Pub/Sub channel
   - Pushes updates to connected clients (school dashboard, parent app)

4. **Frontend Client** (`templates/school_dashboard/dashboard.html`)
   - Connects via WebSocket
   - Receives real-time updates
   - Updates map markers instantly

### Data Flow

```
Kiosk GPS → REST API → BusLocation (DB) → Django Signal
                                              ↓
                                         Redis Pub/Sub
                                              ↓
                                    WebSocket Consumer
                                              ↓
                            School Dashboard / Parent App (Browser)
```

## API Reference

### WebSocket Endpoint

**URL:** `ws://domain.com/ws/bus-tracking/`
**Protocol:** WebSocket
**Authentication:** Required (session-based)

### Message Format

**Server → Client (Location Update)**

```json
{
  "type": "location_update",
  "data": {
    "bus_id": "uuid-string",
    "license_plate": "WB01AB1234",
    "latitude": 22.5726,
    "longitude": 88.3639,
    "speed": 45.5,
    "heading": 90.0,
    "status": "on_route",
    "timestamp": "2025-01-15T10:30:45.123Z"
  }
}
```

## Configuration

### Django Settings

```python
# settings.py

# Enable Channels
INSTALLED_APPS = [
    ...
    'channels',
    'realtime',
]

# ASGI Application
ASGI_APPLICATION = 'bus_kiosk_backend.asgi.application'

# Channel Layer (Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')],
        },
    },
}
```

### Docker Deployment

**docker-compose.prod.yml:**

```yaml
services:
  web:
    command: daphne -b 0.0.0.0 -p 8000 bus_kiosk_backend.asgi:application
    # ASGI server (Daphne) handles both HTTP and WebSocket
```

## Frontend Integration

### JavaScript Client

```javascript
// Connect to WebSocket
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/ws/bus-tracking/`;
const socket = new WebSocket(wsUrl);

// Handle connection
socket.onopen = function(e) {
    console.log('[WebSocket] Connected');
};

// Receive location updates
socket.onmessage = function(event) {
    const message = JSON.parse(event.data);

    if (message.type === 'location_update') {
        updateBusMarker(message.data);
    }
};

// Handle disconnection
socket.onclose = function(event) {
    console.log('[WebSocket] Disconnected, reconnecting...');
    setTimeout(connectWebSocket, 5000);  // Reconnect after 5s
};

// Handle errors
socket.onerror = function(error) {
    console.error('[WebSocket] Error:', error);
};
```

## Performance Characteristics

### Latency

- **GPS → WebSocket Client:** < 500ms (typical)
- **Breakdown:**
  - GPS save: 10-50ms
  - Signal processing: 5-10ms
  - Redis Pub/Sub: 1-5ms
  - WebSocket push: 1-10ms
  - Network latency: 50-200ms

### Scalability

- **Concurrent WebSocket Connections:** 1000+ per Daphne worker
- **Redis Pub/Sub Throughput:** 100,000+ messages/second
- **Recommended Setup:**
  - 100 buses: 1 Daphne worker
  - 1000 buses: 2-3 Daphne workers (behind Nginx load balancer)

### Resource Usage

- **Memory:** ~50MB per Daphne worker (baseline)
- **CPU:** Minimal (event-driven, no polling)
- **Network:** ~1KB per location update

## Advantages Over Polling

| Aspect | WebSocket (Current) | Polling (Old) |
|--------|-------------------|---------------|
| **Latency** | < 500ms | 5-30 seconds |
| **Server Load** | Minimal (event-driven) | High (constant requests) |
| **Client Load** | Minimal (push-based) | High (constant polling) |
| **Network Traffic** | Low (only changes) | High (full dataset every poll) |
| **Battery (Mobile)** | Efficient | Drains battery |
| **Scalability** | Excellent | Poor |

**Example:**
- 100 buses, 20 admins, 30s polling: **4000 requests/min**
- 100 buses, 20 admins, WebSocket: **100 events/min** (40× reduction)

## Testing

### Run WebSocket Tests

```bash
# All WebSocket tests
pytest tests/integration/test_websocket_realtime.py -v

# Specific test
pytest tests/integration/test_websocket_realtime.py::TestBusTrackingWebSocket::test_websocket_connection_authenticated -v

# Signal tests
pytest tests/unit/test_realtime_signals.py -v
```

### Manual Testing

```bash
# Install wscat (WebSocket client)
npm install -g wscat

# Connect to WebSocket (requires authentication)
wscat -c ws://localhost:8000/ws/bus-tracking/
```

## Troubleshooting

### WebSocket Connection Fails

**Symptom:** Browser console shows WebSocket connection error

**Causes:**
1. Daphne not running (check `docker-compose ps`)
2. Redis not accessible (check `REDIS_URL` env var)
3. CORS/ALLOWED_HOSTS misconfiguration

**Solution:**
```bash
# Check Daphne logs
docker logs bus_kiosk_web

# Test Redis connection
docker exec -it bus_kiosk_redis redis-cli ping

# Verify ALLOWED_HOSTS includes domain
```

### No Real-Time Updates

**Symptom:** Initial map loads but no live updates

**Causes:**
1. Signal handler not registered
2. Channel layer misconfigured
3. WebSocket not connected

**Solution:**
```bash
# Verify signal is registered
python manage.py shell
>>> from django.db.models.signals import post_save
>>> from kiosks.models import BusLocation
>>> post_save.has_listeners(BusLocation)  # Should be True

# Test channel layer
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> channel_layer is not None  # Should be True
```

### Memory Leaks

**Symptom:** Daphne memory usage grows over time

**Causes:**
1. WebSocket connections not cleaned up
2. Markers not removed from map

**Solution:**
```javascript
// Frontend: Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (busSocket) {
        busSocket.close();
    }
});
```

## Future Enhancements

### Planned Features

1. **Client-Side Filtering**
   - Subscribe to specific buses/routes only
   - Reduce unnecessary updates

2. **Message Compression**
   - Use WebSocket message compression
   - Reduce bandwidth usage

3. **Presence Detection**
   - Track which admins are viewing dashboard
   - Show "viewing now" count

4. **Replay Buffer**
   - Keep last 10 minutes of updates in Redis
   - New connections receive recent history

## References

- [Django Channels Documentation](https://channels.readthedocs.io/)
- [channels-redis](https://github.com/django/channels_redis)
- [Daphne ASGI Server](https://github.com/django/daphne)
- [WebSocket Protocol RFC](https://datatracker.ietf.org/doc/html/rfc6455)
