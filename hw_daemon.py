"""
SmartLocker Hardware Daemon

Standalone process that owns all HAL drivers (RFID, Weight, LED, Buzzer)
and exposes them via a local TCP socket using JSON-lines protocol.

The UI process connects as a client and receives sensor events / sends commands.

Usage:
    python hw_daemon.py                # Start daemon (auto-detect drivers)
    python hw_daemon.py --test         # Force fake drivers
    python hw_daemon.py --port 9800    # Custom port (default: 9800)

Protocol (JSON-lines over TCP, one JSON object per line):

  Daemon → Client (events):
    {"type":"tag_appeared","tag_id":"04:A2:...","reader_id":"shelf1_slot1","product_data":{...}}
    {"type":"tag_disappeared","tag_id":"04:A2:..."}
    {"type":"weight","channel":"shelf1","grams":1234.5,"stable":true,"raw":8388607}
    {"type":"sensor_status","rfid":true,"weight":true,"led":true,"buzzer":true}
    {"type":"initialized","mode":"live","drivers":{...}}
    {"type":"pong","ts":1234567890.0}

  Client → Daemon (commands):
    {"cmd":"led_set","slot_id":"shelf1_slot1","color":"green","pattern":"solid"}
    {"cmd":"led_clear","slot_id":"shelf1_slot1"}
    {"cmd":"led_clear_all"}
    {"cmd":"buzzer_play","pattern":"confirm"}
    {"cmd":"buzzer_stop"}
    {"cmd":"tare","channel":"mixing_scale"}
    {"cmd":"read_weight","channel":"shelf1"}
    {"cmd":"poll_tags"}
    {"cmd":"ping"}
    {"cmd":"shutdown"}
"""

import asyncio
import json
import logging
import signal
import sys
import time
from typing import Dict, List, Optional, Set

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HW-DAEMON] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hw_daemon")

# Default socket port
DEFAULT_PORT = 9800


# ════════════════════════════════════════════════════════════════
# DRIVER INITIALIZATION (same logic as main.py)
# ════════════════════════════════════════════════════════════════

def init_drivers(force_mode: Optional[str] = None):
    """Initialize HAL drivers. Returns (rfid, weight, led, buzzer, driver_status, mode)."""
    from config.settings import (
        MODE, DRIVER_RFID, DRIVER_WEIGHT, DRIVER_LED, DRIVER_BUZZER,
    )

    cfg_mode = force_mode or MODE
    if cfg_mode == "test":
        drv_rfid = drv_weight = drv_led = drv_buzzer = "fake"
    elif cfg_mode == "live":
        drv_rfid = drv_weight = drv_led = drv_buzzer = "real"
    else:
        drv_rfid = DRIVER_RFID
        drv_weight = DRIVER_WEIGHT
        drv_led = DRIVER_LED
        drv_buzzer = DRIVER_BUZZER

    # Weight FIRST (Arduino must claim serial port before RFID)
    if drv_weight == "real":
        from config.settings import WEIGHT_MODE
        if WEIGHT_MODE == "hx711_direct":
            from hal.real.real_weight_hx711 import RealWeightDriverHX711
            weight = RealWeightDriverHX711()
        else:
            from hal.real.real_weight import RealWeightDriver
            weight = RealWeightDriver()
    else:
        from hal.fake.fake_weight import FakeWeightDriver
        weight = FakeWeightDriver(channels=["shelf1", "mixing_scale"])

    # RFID
    if drv_rfid == "real":
        from config.settings import RFID_MODULE, RFID_USB_PORT
        if RFID_MODULE == "pn532_usb":
            from hal.real.real_rfid_pn532_usb import RealRFIDDriverPN532USB
            rfid = RealRFIDDriverPN532USB(port=RFID_USB_PORT)
        elif RFID_MODULE == "rc522":
            from hal.real.real_rfid_rc522 import RealRFIDDriverRC522
            rfid = RealRFIDDriverRC522()
        else:
            from hal.real.real_rfid import RealRFIDDriver
            rfid = RealRFIDDriver()
    else:
        from hal.fake.fake_rfid import FakeRFIDDriver
        rfid = FakeRFIDDriver()

    # LED
    if drv_led == "real":
        from config.settings import WEIGHT_MODE
        if WEIGHT_MODE == "arduino_serial":
            from hal.real.real_led_arduino import RealLEDDriverArduino
            led = RealLEDDriverArduino()
            led.set_weight_driver(weight)
        else:
            from hal.real.real_led import RealLEDDriver
            led = RealLEDDriver()
    else:
        from hal.fake.fake_led import FakeLEDDriver
        led = FakeLEDDriver()

    # Buzzer
    if drv_buzzer == "real":
        from config.settings import WEIGHT_MODE as _bwm
        if _bwm == "arduino_serial":
            from hal.real.real_buzzer_arduino import RealBuzzerDriverArduino
            buzzer = RealBuzzerDriverArduino()
            buzzer.set_weight_driver(weight)
        else:
            from hal.real.real_buzzer import RealBuzzerDriver
            buzzer = RealBuzzerDriver()
    else:
        from hal.fake.fake_buzzer import FakeBuzzerDriver
        buzzer = FakeBuzzerDriver()

    driver_status = {
        "rfid": drv_rfid, "weight": drv_weight,
        "led": drv_led, "buzzer": drv_buzzer,
    }

    drivers = [drv_rfid, drv_weight, drv_led, drv_buzzer]
    if all(d == "real" for d in drivers):
        mode = "live"
    elif any(d == "real" for d in drivers):
        mode = "hybrid"
    else:
        mode = "test"

    return rfid, weight, led, buzzer, driver_status, mode


# ════════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS
# ════════════════════════════════════════════════════════════════

def tag_reading_to_dict(reading) -> dict:
    """Convert TagReading to JSON-serializable dict."""
    return {
        "tag_id": reading.tag_id,
        "reader_id": reading.reader_id,
        "signal_strength": reading.signal_strength,
        "timestamp": reading.timestamp,
        "ppg_code": reading.ppg_code,
        "batch_number": reading.batch_number,
        "product_name": reading.product_name,
        "color": reading.color,
    }


def weight_reading_to_dict(reading) -> dict:
    """Convert WeightReading to JSON-serializable dict."""
    return {
        "channel": reading.channel,
        "grams": reading.grams,
        "stable": reading.stable,
        "raw": reading.raw_value,
        "timestamp": reading.timestamp,
    }


# ════════════════════════════════════════════════════════════════
# HARDWARE DAEMON SERVER
# ════════════════════════════════════════════════════════════════

class HardwareDaemon:
    """Async TCP server owning all hardware drivers."""

    def __init__(self, rfid, weight, led, buzzer, driver_status: dict, mode: str,
                 port: int = DEFAULT_PORT):
        self.rfid = rfid
        self.weight = weight
        self.led = led
        self.buzzer = buzzer
        self.driver_status = driver_status
        self.mode = mode
        self.port = port

        # Connected clients
        self._clients: Dict[str, asyncio.StreamWriter] = {}
        self._client_id = 0

        # Sensor state tracking
        self._previous_tags: Set[str] = set()
        self._rfid_healthy = True
        self._running = False
        self._hw_ready = False  # True after hardware init completes

        # Polling intervals (seconds)
        self._rfid_poll_s = 2.0
        self._weight_poll_s = 0.2
        self._status_poll_s = 5.0

    async def start(self):
        """Start the daemon: open TCP server first, then init hardware."""
        self._running = True

        # Start TCP server FIRST so clients can connect while hardware inits
        server = await asyncio.start_server(
            self._handle_client, "127.0.0.1", self.port,
        )
        addr = server.sockets[0].getsockname()
        logger.info(f"Hardware daemon listening on {addr[0]}:{addr[1]}")

        # Set a preliminary init message (hardware still initializing)
        self._init_msg = json.dumps({
            "type": "initialized",
            "mode": self.mode,
            "drivers": self.driver_status,
            "init_status": {"rfid": False, "weight": False, "led": False, "buzzer": False},
            "hw_ready": False,
        })

        # Initialize hardware in a thread (serial init can block 10+ seconds)
        logger.info("Initializing hardware drivers (background)...")
        loop = asyncio.get_running_loop()
        status = await loop.run_in_executor(None, self._init_hardware_sync)
        logger.info(f"Driver init: {status}")

        # Update init message with actual hardware status
        self._init_msg = json.dumps({
            "type": "initialized",
            "mode": self.mode,
            "drivers": self.driver_status,
            "init_status": status,
            "hw_ready": True,
        })

        self._hw_ready = True

        # Broadcast hw_ready to already-connected clients
        await self._broadcast({"type": "hw_ready", "init_status": status})

        # Start polling tasks
        rfid_task = asyncio.create_task(self._poll_rfid_loop())
        weight_task = asyncio.create_task(self._poll_weight_loop())
        status_task = asyncio.create_task(self._poll_status_loop())

        try:
            async with server:
                await server.serve_forever()
        finally:
            self._running = False
            rfid_task.cancel()
            weight_task.cancel()
            status_task.cancel()
            self._shutdown_hardware()

    def _init_hardware_sync(self) -> dict:
        """Initialize all hardware drivers (runs in thread pool).

        Order matters: Weight FIRST so Arduino claims its serial port,
        then RFID can skip it and find the PN532 on the remaining port.
        """
        weight_ok = self.weight.initialize()
        rfid_ok = self.rfid.initialize()
        led_ok = self.led.initialize()
        buzzer_ok = self.buzzer.initialize()

        if led_ok:
            try:
                self.led.clear_all()
            except Exception:
                pass

        return {
            "rfid": rfid_ok, "weight": weight_ok,
            "led": led_ok, "buzzer": buzzer_ok,
        }

    def _shutdown_hardware(self):
        """Clean shutdown of all drivers."""
        logger.info("Shutting down hardware...")
        try:
            self.led.clear_all()
        except Exception:
            pass
        for drv in (self.rfid, self.weight, self.led, self.buzzer):
            try:
                drv.shutdown()
            except Exception:
                pass
        logger.info("Hardware shutdown complete")

    # ── Client Connection Handling ──

    async def _handle_client(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter):
        """Handle a single client connection."""
        self._client_id += 1
        cid = f"client-{self._client_id}"
        peer = writer.get_extra_info("peername")
        logger.info(f"Client connected: {cid} from {peer}")

        self._clients[cid] = writer

        # Send init message
        await self._send(writer, self._init_msg)

        try:
            while self._running:
                data = await asyncio.wait_for(reader.readline(), timeout=30.0)
                if not data:
                    break  # Client disconnected
                line = data.decode("utf-8").strip()
                if not line:
                    continue
                await self._handle_command(cid, writer, line)
        except asyncio.TimeoutError:
            # Send keepalive ping on timeout
            try:
                await self._send_json(writer, {"type": "ping", "ts": time.time()})
            except Exception:
                pass
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.warning(f"Client {cid} error: {e}")
        finally:
            self._clients.pop(cid, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"Client disconnected: {cid}")

    async def _handle_command(self, cid: str, writer: asyncio.StreamWriter, line: str):
        """Process a command from a client."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            await self._send_json(writer, {"type": "error", "msg": "invalid JSON"})
            return

        cmd = msg.get("cmd", "")

        if cmd == "ping":
            await self._send_json(writer, {"type": "pong", "ts": time.time()})

        elif not self._hw_ready:
            # Hardware still initializing — reject commands gracefully
            await self._send_json(writer, {
                "type": "error", "msg": "hardware still initializing",
                "cmd": cmd,
            })

        elif cmd == "led_set":
            from hal.interfaces import LEDColor, LEDPattern
            slot_id = msg.get("slot_id", "")
            color_name = msg.get("color", "off").upper()
            pattern_name = msg.get("pattern", "solid").upper()
            color = LEDColor[color_name] if color_name in LEDColor.__members__ else LEDColor.OFF
            pattern = LEDPattern[pattern_name] if pattern_name in LEDPattern.__members__ else LEDPattern.SOLID
            self.led.set_slot(slot_id, color, pattern)
            await self._send_json(writer, {"type": "ack", "cmd": "led_set"})

        elif cmd == "led_clear":
            self.led.clear_slot(msg.get("slot_id", ""))
            await self._send_json(writer, {"type": "ack", "cmd": "led_clear"})

        elif cmd == "led_clear_all":
            self.led.clear_all()
            await self._send_json(writer, {"type": "ack", "cmd": "led_clear_all"})

        elif cmd == "buzzer_play":
            from hal.interfaces import BuzzerPattern
            pat_name = msg.get("pattern", "").upper()
            if pat_name in BuzzerPattern.__members__:
                self.buzzer.play(BuzzerPattern[pat_name])
            await self._send_json(writer, {"type": "ack", "cmd": "buzzer_play"})

        elif cmd == "buzzer_stop":
            self.buzzer.stop()
            await self._send_json(writer, {"type": "ack", "cmd": "buzzer_stop"})

        elif cmd == "tare":
            channel = msg.get("channel", "")
            loop = asyncio.get_running_loop()
            ok = await loop.run_in_executor(None, self.weight.tare, channel)
            await self._send_json(writer, {"type": "tare_result", "channel": channel, "ok": ok})

        elif cmd == "read_weight":
            channel = msg.get("channel", "")
            loop = asyncio.get_running_loop()
            try:
                reading = await loop.run_in_executor(
                    None, self.weight.read_weight, channel
                )
                await self._send_json(writer, {
                    "type": "weight_response",
                    **weight_reading_to_dict(reading),
                })
            except Exception as e:
                await self._send_json(writer, {
                    "type": "weight_response", "channel": channel,
                    "grams": 0, "stable": False, "error": str(e),
                })

        elif cmd == "poll_tags":
            loop = asyncio.get_running_loop()
            try:
                readings = await loop.run_in_executor(
                    None, self.rfid.poll_tags
                )
                await self._send_json(writer, {
                    "type": "tags_response",
                    "tags": [tag_reading_to_dict(r) for r in readings],
                })
            except Exception as e:
                await self._send_json(writer, {
                    "type": "tags_response", "tags": [], "error": str(e),
                })

        elif cmd == "get_channels":
            loop = asyncio.get_running_loop()
            channels = await loop.run_in_executor(
                None, self.weight.get_channels
            )
            await self._send_json(writer, {"type": "channels", "channels": channels})

        elif cmd == "get_reader_ids":
            loop = asyncio.get_running_loop()
            ids = await loop.run_in_executor(
                None, self.rfid.get_reader_ids
            )
            await self._send_json(writer, {"type": "reader_ids", "ids": ids})

        elif cmd == "shutdown":
            logger.info(f"Shutdown requested by {cid}")
            await self._send_json(writer, {"type": "ack", "cmd": "shutdown"})
            # Graceful shutdown
            asyncio.get_event_loop().call_soon(asyncio.get_event_loop().stop)

        else:
            await self._send_json(writer, {"type": "error", "msg": f"unknown cmd: {cmd}"})

    # ── Polling Loops ──
    # All hardware calls are blocking (serial I/O) so they MUST run
    # in a thread pool via run_in_executor to avoid freezing the
    # asyncio event loop (which handles TCP client communication).

    def _sync_rfid_poll(self):
        """Blocking RFID poll (runs in thread pool)."""
        healthy = self.rfid.is_healthy()
        readings = self.rfid.poll_tags() if healthy else []
        return healthy, readings

    def _sync_weight_read(self, channel: str):
        """Blocking weight read (runs in thread pool)."""
        return self.weight.read_weight(channel)

    def _sync_weight_channels(self):
        """Blocking get_channels (runs in thread pool)."""
        return self.weight.get_channels()

    def _sync_status_check(self):
        """Blocking health check (runs in thread pool)."""
        return self.weight.is_healthy()

    async def _poll_rfid_loop(self):
        """Poll RFID tags and broadcast changes."""
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                healthy, readings = await loop.run_in_executor(
                    None, self._sync_rfid_poll
                )
                self._rfid_healthy = healthy

                if healthy:
                    current_ids = {r.tag_id for r in readings}

                    # Detect new tags
                    for r in readings:
                        if r.tag_id not in self._previous_tags:
                            await self._broadcast({
                                "type": "tag_appeared",
                                **tag_reading_to_dict(r),
                            })

                    # Detect removed tags
                    for tag_id in self._previous_tags - current_ids:
                        await self._broadcast({
                            "type": "tag_disappeared",
                            "tag_id": tag_id,
                        })

                    self._previous_tags = current_ids
                else:
                    if self._previous_tags:
                        for tag_id in self._previous_tags:
                            await self._broadcast({
                                "type": "tag_disappeared",
                                "tag_id": tag_id,
                                "reason": "rfid_unhealthy",
                            })
                        self._previous_tags = set()

            except Exception as e:
                logger.warning(f"RFID poll error: {e}")

            await asyncio.sleep(self._rfid_poll_s)

    async def _poll_weight_loop(self):
        """Poll weight sensors and broadcast readings."""
        loop = asyncio.get_running_loop()
        try:
            channels = await loop.run_in_executor(
                None, self._sync_weight_channels
            )
        except Exception:
            channels = ["shelf1"]

        while self._running:
            for ch in channels:
                try:
                    reading = await loop.run_in_executor(
                        None, self._sync_weight_read, ch
                    )
                    await self._broadcast({
                        "type": "weight",
                        **weight_reading_to_dict(reading),
                    })
                except Exception:
                    pass

            await asyncio.sleep(self._weight_poll_s)

    async def _poll_status_loop(self):
        """Broadcast sensor health status periodically."""
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                weight_ok = await loop.run_in_executor(
                    None, self._sync_status_check
                )
            except Exception:
                weight_ok = False
            status = {
                "type": "sensor_status",
                "rfid": self._rfid_healthy,
                "weight": weight_ok,
                "led": True,
                "buzzer": True,
                "ts": time.time(),
            }
            await self._broadcast(status)
            await asyncio.sleep(self._status_poll_s)

    # ── Broadcast & Send Helpers ──

    async def _broadcast(self, msg: dict):
        """Send a message to all connected clients."""
        line = json.dumps(msg) + "\n"
        dead = []
        for cid, writer in self._clients.items():
            try:
                await self._send(writer, line)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self._clients.pop(cid, None)

    async def _send_json(self, writer: asyncio.StreamWriter, msg: dict):
        """Send a JSON message to a single client."""
        await self._send(writer, json.dumps(msg) + "\n")

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, line: str):
        """Send a raw line to a client."""
        writer.write(line.encode("utf-8") if isinstance(line, str) else line)
        await writer.drain()


# ════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════

def main():
    port = DEFAULT_PORT
    force_mode = None

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--test":
            force_mode = "test"
        elif arg == "--live":
            force_mode = "live"
        elif arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    print("=" * 60)
    print("  SMARTLOCKER HARDWARE DAEMON")
    print(f"  Port: {port}")
    print("=" * 60)

    rfid, weight, led, buzzer, driver_status, mode = init_drivers(force_mode)
    print(f"  Mode: {mode.upper()}")
    print(f"  Drivers: {driver_status}")

    daemon = HardwareDaemon(rfid, weight, led, buzzer, driver_status, mode, port)

    # Handle Ctrl+C gracefully
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def sig_handler():
        logger.info("Signal received, stopping...")
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, sig_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: sig_handler())

    try:
        loop.run_until_complete(daemon.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("\nHardware daemon stopped.")


if __name__ == "__main__":
    main()
