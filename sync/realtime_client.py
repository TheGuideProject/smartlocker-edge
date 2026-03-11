"""
Real-time WebSocket client for SmartLocker edge.

Maintains a persistent WebSocket connection to the cloud for bidirectional
real-time sync. Falls back to HTTP polling when disconnected.

Uses the `websockets` library's synchronous client (compatible with threading).
If `websockets` is not installed, the client gracefully disables itself.
"""

import json
import time
import logging
import threading
from typing import Optional, Callable, Dict, Any, List

logger = logging.getLogger("smartlocker.realtime")

# Graceful import — disable if library not available
try:
    from websockets.sync.client import connect as ws_connect
    from websockets.exceptions import ConnectionClosed, InvalidStatusCode
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("[RealtimeClient] websockets library not installed. "
                   "Install with: pip install websockets>=12.0")


class RealtimeClient:
    """
    WebSocket client with auto-reconnect for SmartLocker edge devices.

    Usage:
        client = RealtimeClient(cloud_url, api_key, device_id)
        client.on_command = my_command_handler
        client.on_ack = my_ack_handler
        client.start()

        # Send data (returns True if sent, False if not connected)
        client.send_events([...])
        client.send_heartbeat({...})

        client.stop()
    """

    def __init__(self, cloud_url: str, api_key: str, device_id: str):
        from config import settings

        self._ws_url = self._build_ws_url(cloud_url, api_key, device_id)
        self._device_id = device_id
        self._ws = None
        self._connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Config
        self._reconnect_delay = getattr(settings, 'WS_RECONNECT_INITIAL_S', 2)
        self._reconnect_initial = getattr(settings, 'WS_RECONNECT_INITIAL_S', 2)
        self._reconnect_max = getattr(settings, 'WS_RECONNECT_MAX_S', 120)
        self._ping_interval = getattr(settings, 'WS_PING_INTERVAL_S', 25)

        # Callbacks
        self.on_command: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_ack: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None

    @staticmethod
    def _build_ws_url(cloud_url: str, api_key: str, device_id: str) -> str:
        """Convert https://... to wss://... and add WS path + auth."""
        base = cloud_url.rstrip("/")
        base = base.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/api/devices/{device_id}/ws?api_key={api_key}"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self):
        """Start the WebSocket connection thread."""
        if not HAS_WEBSOCKETS:
            logger.warning("[RealtimeClient] Cannot start — websockets library not installed")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._connection_loop,
            name="RealtimeClient",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"[RealtimeClient] Started for device {self._device_id}")

    def stop(self):
        """Stop the WebSocket connection."""
        self._running = False
        self._connected = False
        # The connection loop will exit on its own
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("[RealtimeClient] Stopped")

    def _connection_loop(self):
        """Main loop: connect -> process messages -> reconnect on failure."""
        while self._running:
            try:
                logger.info(f"[RealtimeClient] Connecting to cloud WebSocket...")
                ws = ws_connect(
                    self._ws_url,
                    ping_interval=self._ping_interval,
                    ping_timeout=10,
                    close_timeout=5,
                    additional_headers={},
                )

                with ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnect_delay = self._reconnect_initial
                    logger.info("[RealtimeClient] Connected!")

                    if self.on_connect:
                        try:
                            self.on_connect()
                        except Exception as e:
                            logger.error(f"on_connect callback error: {e}")

                    # Message receive loop
                    while self._running:
                        try:
                            msg_str = ws.recv(timeout=1.0)
                            if msg_str:
                                msg = json.loads(msg_str)
                                self._handle_message(msg)
                        except TimeoutError:
                            continue  # No message, keep looping
                        except ConnectionClosed:
                            logger.info("[RealtimeClient] Connection closed by server")
                            break

            except Exception as e:
                if self._running:
                    logger.warning(f"[RealtimeClient] Connection error: {e}")
            finally:
                was_connected = self._connected
                self._connected = False
                self._ws = None
                if was_connected and self.on_disconnect:
                    try:
                        self.on_disconnect()
                    except Exception:
                        pass

            # Reconnect with exponential backoff
            if self._running:
                logger.info(f"[RealtimeClient] Reconnecting in {self._reconnect_delay}s...")
                # Sleep in small chunks so we can stop quickly
                sleep_end = time.time() + self._reconnect_delay
                while self._running and time.time() < sleep_end:
                    time.sleep(0.5)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._reconnect_max,
                )

    def _handle_message(self, msg: dict):
        """Process an incoming message from the cloud."""
        msg_type = msg.get("type", "")

        if msg_type == "command":
            logger.info(f"[RealtimeClient] Received command: {msg.get('command_type')}")
            if self.on_command:
                try:
                    self.on_command(msg)
                except Exception as e:
                    logger.error(f"on_command callback error: {e}")
            # Auto-ack
            self.send_json({
                "type": "ack",
                "command_id": msg.get("command_id", ""),
            })

        elif msg_type in ("ack", "ack_mixing"):
            if self.on_ack:
                try:
                    self.on_ack(msg)
                except Exception as e:
                    logger.error(f"on_ack callback error: {e}")

        else:
            logger.debug(f"[RealtimeClient] Unknown message type: {msg_type}")

    def send_json(self, data: dict) -> bool:
        """Send a JSON message over WebSocket. Returns False if not connected."""
        if not self._connected or not self._ws:
            return False
        try:
            with self._lock:
                self._ws.send(json.dumps(data))
            return True
        except Exception as e:
            logger.warning(f"[RealtimeClient] Send error: {e}")
            self._connected = False
            return False

    # ---- Convenience methods for each data type ----

    def send_events(self, events: List[dict]) -> bool:
        """Send a batch of events via WebSocket."""
        if not events:
            return True
        return self.send_json({"type": "event_batch", "events": events})

    def send_heartbeat(self, data: dict) -> bool:
        """Send heartbeat data via WebSocket."""
        return self.send_json({"type": "heartbeat", "data": data})

    def send_mixing_sessions(self, sessions: List[dict]) -> bool:
        """Send mixing sessions via WebSocket."""
        if not sessions:
            return True
        return self.send_json({"type": "mixing_sessions", "sessions": sessions})

    def send_inventory_snapshot(self, slots: List[dict]) -> bool:
        """Send inventory snapshot via WebSocket."""
        if not slots:
            return True
        return self.send_json({"type": "inventory_snapshot", "slots": slots})

    def send_health_logs(self, logs: List[dict]) -> bool:
        """Send health logs via WebSocket."""
        if not logs:
            return True
        return self.send_json({"type": "health_logs", "logs": logs})
