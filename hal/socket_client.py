"""
Socket Proxy HAL Drivers

These drivers implement the same HAL interfaces (RFID, Weight, LED, Buzzer)
but forward all operations to the hardware daemon via TCP socket.

The UI process uses these instead of real/fake drivers when running in
daemon mode (--daemon-client).

Protocol: JSON-lines over TCP (see hw_daemon.py for spec).
"""

import json
import logging
import socket
import threading
import time
from typing import Callable, Dict, List, Optional, Set

from hal.interfaces import (
    RFIDDriverInterface, WeightDriverInterface,
    LEDDriverInterface, BuzzerDriverInterface,
    TagReading, WeightReading, LEDColor, LEDPattern, BuzzerPattern,
)

logger = logging.getLogger("smartlocker.socket_client")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9800


class DaemonConnection:
    """Manages the TCP connection to the hardware daemon.

    Shared by all proxy drivers. Handles:
    - Connection / reconnection
    - Sending commands (thread-safe)
    - Receiving events in background thread
    - Dispatching events to registered handlers
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port

        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False
        self._running = False

        # Event handlers: type → list of callbacks
        self._handlers: Dict[str, List[Callable]] = {}

        # Pending response for synchronous commands
        self._response_event = threading.Event()
        self._response_data: Optional[dict] = None
        self._response_types: Set[str] = set()

        # Daemon info (from init message)
        self.daemon_mode: str = ""
        self.daemon_drivers: dict = {}
        self.daemon_init_status: dict = {}

        # Reader thread
        self._reader_thread: Optional[threading.Thread] = None

        # Latest state caches
        self._latest_weights: Dict[str, WeightReading] = {}
        self._current_tags: Dict[str, TagReading] = {}
        self._sensor_status: dict = {"rfid": False, "weight": False, "led": False, "buzzer": False}

    def connect(self) -> bool:
        """Connect to the hardware daemon."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)
            self._socket.connect((self.host, self.port))
            self._socket.settimeout(None)
            self._connected = True
            self._running = True

            # Start background reader thread
            self._reader_thread = threading.Thread(
                target=self._read_loop, daemon=True, name="daemon-reader",
            )
            self._reader_thread.start()

            # Wait for init message
            time.sleep(0.5)
            logger.info(f"Connected to hardware daemon at {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to daemon at {self.host}:{self.port}: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from daemon."""
        self._running = False
        self._connected = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def on(self, event_type: str, handler: Callable):
        """Register a handler for a specific event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def send_command(self, cmd: dict) -> Optional[dict]:
        """Send a command and wait for response (synchronous, with timeout)."""
        # Determine expected response type
        cmd_name = cmd.get("cmd", "")
        response_type_map = {
            "ping": "pong",
            "tare": "tare_result",
            "read_weight": "weight_response",
            "poll_tags": "tags_response",
            "get_channels": "channels",
            "get_reader_ids": "reader_ids",
            "write_tag": "write_tag_result",
        }
        expected = response_type_map.get(cmd_name, "ack")

        self._response_event.clear()
        self._response_data = None
        self._response_types = {expected}

        self._send_raw(cmd)

        # Longer timeout for slow operations (NFC write, tare)
        slow_cmds = {"write_tag", "tare"}
        timeout = 10.0 if cmd_name in slow_cmds else 3.0

        if self._response_event.wait(timeout=timeout):
            return self._response_data
        else:
            logger.warning(f"Timeout waiting for {expected} response to {cmd_name}")
            return None

    def send_fire_and_forget(self, cmd: dict):
        """Send a command without waiting for response."""
        self._send_raw(cmd)

    def _send_raw(self, msg: dict):
        """Send a JSON message to the daemon."""
        if not self._connected or not self._socket:
            return
        line = json.dumps(msg) + "\n"
        with self._lock:
            try:
                self._socket.sendall(line.encode("utf-8"))
            except Exception as e:
                logger.warning(f"Send failed: {e}")
                self._connected = False

    def _read_loop(self):
        """Background thread: read JSON-lines from daemon and dispatch."""
        buffer = ""
        while self._running and self._socket:
            try:
                data = self._socket.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        self._dispatch(msg)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from daemon: {line[:100]}")

            except Exception as e:
                if self._running:
                    logger.warning(f"Daemon read error: {e}")
                break

        self._connected = False
        if self._running:
            logger.warning("Daemon connection lost")

    def _dispatch(self, msg: dict):
        """Route a received message to handlers or response waiters."""
        msg_type = msg.get("type", "")

        # Handle init message
        if msg_type == "initialized":
            self.daemon_mode = msg.get("mode", "")
            self.daemon_drivers = msg.get("drivers", {})
            self.daemon_init_status = msg.get("init_status", {})
            logger.info(f"Daemon initialized: mode={self.daemon_mode}")

        # Update state caches
        elif msg_type == "weight":
            ch = msg.get("channel", "")
            self._latest_weights[ch] = WeightReading(
                grams=msg.get("grams", 0),
                channel=ch,
                stable=msg.get("stable", False),
                raw_value=msg.get("raw", 0),
                timestamp=msg.get("timestamp", time.time()),
            )

        elif msg_type == "tag_appeared":
            tag_id = msg.get("tag_id", "")
            self._current_tags[tag_id] = TagReading(
                tag_id=tag_id,
                reader_id=msg.get("reader_id", ""),
                signal_strength=msg.get("signal_strength", 0),
                timestamp=msg.get("timestamp", time.time()),
                ppg_code=msg.get("ppg_code"),
                batch_number=msg.get("batch_number"),
                product_name=msg.get("product_name"),
                color=msg.get("color"),
            )

        elif msg_type == "tag_disappeared":
            tag_id = msg.get("tag_id", "")
            self._current_tags.pop(tag_id, None)

        elif msg_type == "hw_ready":
            init_status = msg.get("init_status", {})
            self.daemon_init_status = init_status
            # Update sensor status from hardware init results
            self._sensor_status = {
                "rfid": init_status.get("rfid", False),
                "weight": init_status.get("weight", False),
                "led": init_status.get("led", True),
                "buzzer": init_status.get("buzzer", True),
            }
            logger.info(f"Daemon hardware ready: {init_status}")

        elif msg_type == "sensor_status":
            self._sensor_status = {
                "rfid": msg.get("rfid", False),
                "weight": msg.get("weight", False),
                "led": msg.get("led", False),
                "buzzer": msg.get("buzzer", False),
            }

        # Check if this is a response to a pending command
        if msg_type in self._response_types:
            self._response_data = msg
            self._response_event.set()

        # Dispatch to registered handlers
        for handler in self._handlers.get(msg_type, []):
            try:
                handler(msg)
            except Exception as e:
                logger.warning(f"Handler error for {msg_type}: {e}")

        # Dispatch to wildcard handlers
        for handler in self._handlers.get("*", []):
            try:
                handler(msg)
            except Exception as e:
                logger.warning(f"Wildcard handler error: {e}")


# ════════════════════════════════════════════════════════════════
# PROXY DRIVERS
# ════════════════════════════════════════════════════════════════

class SocketRFIDDriver(RFIDDriverInterface):
    """RFID driver that reads from daemon socket."""

    def __init__(self, conn: DaemonConnection):
        self._conn = conn

    def initialize(self) -> bool:
        return self._conn.is_connected

    def poll_tags(self) -> List[TagReading]:
        return list(self._conn._current_tags.values())

    def get_reader_ids(self) -> List[str]:
        resp = self._conn.send_command({"cmd": "get_reader_ids"})
        if resp:
            return resp.get("ids", [])
        return []

    def write_product_data(self, product_string: str) -> bool:
        """Write product data to NFC tag via daemon."""
        resp = self._conn.send_command({
            "cmd": "write_tag",
            "data": product_string,
        })
        if resp:
            return resp.get("ok", False)
        return False

    def is_healthy(self) -> bool:
        return self._conn._sensor_status.get("rfid", False)

    def shutdown(self) -> None:
        pass  # Daemon owns hardware


class SocketWeightDriver(WeightDriverInterface):
    """Weight driver that reads from daemon socket."""

    def __init__(self, conn: DaemonConnection):
        self._conn = conn

    def initialize(self) -> bool:
        return self._conn.is_connected

    def read_weight(self, channel: str) -> WeightReading:
        # Return cached value for speed (updated by daemon push)
        cached = self._conn._latest_weights.get(channel)
        if cached:
            return cached
        # Fallback: request from daemon
        resp = self._conn.send_command({"cmd": "read_weight", "channel": channel})
        if resp and "grams" in resp:
            return WeightReading(
                grams=resp["grams"],
                channel=resp.get("channel", channel),
                stable=resp.get("stable", False),
                raw_value=resp.get("raw", 0),
            )
        return WeightReading(grams=0, channel=channel, stable=False)

    def tare(self, channel: str) -> bool:
        resp = self._conn.send_command({"cmd": "tare", "channel": channel})
        return resp.get("ok", False) if resp else False

    def get_channels(self) -> List[str]:
        resp = self._conn.send_command({"cmd": "get_channels"})
        if resp:
            return resp.get("channels", [])
        return list(self._conn._latest_weights.keys()) or ["shelf1"]

    def is_healthy(self) -> bool:
        return self._conn._sensor_status.get("weight", False)

    def shutdown(self) -> None:
        pass


class SocketLEDDriver(LEDDriverInterface):
    """LED driver that sends commands to daemon socket."""

    def __init__(self, conn: DaemonConnection):
        self._conn = conn

    def initialize(self) -> bool:
        return self._conn.is_connected

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        self._conn.send_fire_and_forget({
            "cmd": "led_set",
            "slot_id": slot_id,
            "color": color.name,
            "pattern": pattern.name,
        })

    def clear_slot(self, slot_id: str) -> None:
        self._conn.send_fire_and_forget({"cmd": "led_clear", "slot_id": slot_id})

    def clear_all(self) -> None:
        self._conn.send_fire_and_forget({"cmd": "led_clear_all"})

    def shutdown(self) -> None:
        pass


class SocketBuzzerDriver(BuzzerDriverInterface):
    """Buzzer driver that sends commands to daemon socket."""

    def __init__(self, conn: DaemonConnection):
        self._conn = conn

    def initialize(self) -> bool:
        return self._conn.is_connected

    def play(self, pattern: BuzzerPattern) -> None:
        self._conn.send_fire_and_forget({
            "cmd": "buzzer_play",
            "pattern": pattern.name,
        })

    def stop(self) -> None:
        self._conn.send_fire_and_forget({"cmd": "buzzer_stop"})

    def shutdown(self) -> None:
        pass


def create_socket_drivers(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Create all socket proxy drivers sharing one connection.

    Returns: (conn, rfid, weight, led, buzzer)
    """
    conn = DaemonConnection(host, port)
    if not conn.connect():
        raise ConnectionError(f"Cannot connect to hardware daemon at {host}:{port}")

    return (
        conn,
        SocketRFIDDriver(conn),
        SocketWeightDriver(conn),
        SocketLEDDriver(conn),
        SocketBuzzerDriver(conn),
    )
