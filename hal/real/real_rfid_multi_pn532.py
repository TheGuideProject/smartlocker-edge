"""
Multi-Reader RFID Driver - N × PN532 NFC Readers via USB Serial

Manages multiple PN532 modules, each on its own USB serial port (CH340/CP210x).
Each reader maps 1:1 to a shelf slot (reader_id = "shelf1_slot1", etc.).

Hardware setup:
  - USB hub → N × PN532 V2/V3 modules with CH340 USB-UART bridges
  - Plus 1 Arduino Nano for weight (identified first, port excluded)

Scaling:
  - Demo: 4 readers (sequential poll, ~200ms per cycle)
  - Production: 40-50 readers (threaded parallel poll, ~100ms per cycle)

Required: pip install pyserial adafruit-circuitpython-pn532
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False
    logger.warning("[MultiPN532] pyserial not installed")

try:
    from adafruit_pn532.uart import PN532_UART
    HAS_ADAFRUIT = True
except ImportError:
    HAS_ADAFRUIT = False
    PN532_UART = None
    logger.warning("[MultiPN532] adafruit-circuitpython-pn532 not installed")


USER_PAGE_START = 4
USER_PAGE_END = 129
PRODUCT_SEPARATOR = "|"

# Parallel polling threshold: use thread pool above this many readers
PARALLEL_THRESHOLD = 6


@dataclass
class ReaderInstance:
    """One physical PN532 reader."""
    port: str
    reader_id: str
    ser: Optional["serial.Serial"] = None
    pn532: Optional["PN532_UART"] = None
    healthy: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_error_time: float = 0.0
    last_reconnect_attempt: float = 0.0
    reconnect_backoff_s: float = 5.0
    # Tag data cache for this reader
    tag_cache: Dict[str, dict] = field(default_factory=dict)


class RealRFIDMultiPN532USB(RFIDDriverInterface):
    """Multi-reader PN532 NFC driver via USB serial.

    Manages N PN532 modules simultaneously. Each module is on its own
    USB serial port via a USB hub. Reader IDs are assigned either:
      1. From explicit config: RFID_READER_MAP = [{"port":..., "reader_id":...}, ...]
      2. Auto-detected: all CH340/CP210x ports (excluding Arduino) get
         sequential reader_ids: shelf1_slot1, shelf1_slot2, ...

    Thread-safety: Each reader has its own lock. Multiple readers can
    be polled in parallel (for 40+ reader setups).
    """

    def __init__(
        self,
        reader_configs: Optional[List[dict]] = None,
        skip_ports: Optional[Set[str]] = None,
        poll_timeout: float = 0.05,
    ):
        """
        Args:
            reader_configs: List of {"port": "/dev/ttyUSBx", "reader_id": "shelf1_slotN"}.
                           If None/empty, auto-detects all available PN532 ports.
            skip_ports: Set of serial ports to skip (e.g., Arduino port).
            poll_timeout: Timeout in seconds for read_passive_target per reader.
        """
        self._reader_configs = reader_configs or []
        self._skip_ports: Set[str] = set(skip_ports or set())
        self._poll_timeout = poll_timeout

        self._readers: Dict[str, ReaderInstance] = {}  # reader_id → ReaderInstance
        self._initialized = False
        self._global_lock = threading.Lock()

        # Thread pool for parallel polling (created on init if needed)
        self._executor: Optional[ThreadPoolExecutor] = None

    # ----------------------------------------------------------
    # Port Detection
    # ----------------------------------------------------------

    def _find_all_pn532_ports(self) -> List[str]:
        """Find all USB serial ports that could be PN532 modules.

        Excludes ports in self._skip_ports (Arduino, etc.).
        Returns sorted list of port paths.
        """
        if not HAS_SERIAL:
            return []

        found = []
        try:
            for p in serial.tools.list_ports.comports():
                if p.device in self._skip_ports:
                    continue
                desc = (p.description or "").lower()
                vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else ""

                is_usb_serial = any(k in desc for k in [
                    "ch340", "ch341", "cp210", "usb-serial", "usb serial",
                ])
                is_known_vid = vid_pid in ("1A86:7523", "10C4:EA60")

                if is_usb_serial or is_known_vid:
                    found.append(p.device)
        except Exception as e:
            logger.warning(f"[MultiPN532] Port scan error: {e}")

        # Also check /dev/ttyUSBx that might not appear in comports
        if not found:
            import os
            for i in range(10):
                path = f"/dev/ttyUSB{i}"
                if os.path.exists(path) and path not in self._skip_ports:
                    found.append(path)

        found.sort()
        return found

    # ----------------------------------------------------------
    # Reader Connection Management
    # ----------------------------------------------------------

    def _connect_reader(self, port: str, reader_id: str) -> Optional[ReaderInstance]:
        """Open serial port and initialize one PN532 reader."""
        reader = ReaderInstance(port=port, reader_id=reader_id)

        try:
            reader.ser = serial.Serial(port, 115200, timeout=1)
            # CH340 stabilization
            time.sleep(1.5)
            reader.ser.reset_input_buffer()
            reader.ser.reset_output_buffer()

            reader.pn532 = PN532_UART(reader.ser, debug=False)

            # Verify connection
            ic, ver, rev, support = reader.pn532.firmware_version
            logger.info(
                f"[MultiPN532] Reader '{reader_id}' on {port}: "
                f"PN532 fw v{ver}.{rev}"
            )

            reader.pn532.SAM_configuration()
            reader.healthy = True
            return reader

        except Exception as e:
            logger.warning(f"[MultiPN532] Failed to init reader on {port}: {e}")
            if reader.ser:
                try:
                    reader.ser.close()
                except Exception:
                    pass
            return None

    def _disconnect_reader(self, reader: ReaderInstance):
        """Close one reader's serial connection."""
        reader.pn532 = None
        reader.healthy = False
        if reader.ser:
            try:
                reader.ser.close()
            except Exception:
                pass
            reader.ser = None

    def _try_reconnect_reader(self, reader: ReaderInstance):
        """Attempt to reconnect a failed reader."""
        now = time.time()
        if now - reader.last_reconnect_attempt < reader.reconnect_backoff_s:
            return
        reader.last_reconnect_attempt = now

        logger.info(f"[MultiPN532] Reconnecting '{reader.reader_id}' on {reader.port}...")
        self._disconnect_reader(reader)

        new_reader = self._connect_reader(reader.port, reader.reader_id)
        if new_reader:
            reader.ser = new_reader.ser
            reader.pn532 = new_reader.pn532
            reader.healthy = True
            logger.info(f"[MultiPN532] Reconnected '{reader.reader_id}'")
        else:
            reader.healthy = False

    # ----------------------------------------------------------
    # Tag Read/Write Operations
    # ----------------------------------------------------------

    def _read_product_data(self, pn532) -> Optional[str]:
        """Read product data string from NTAG215 user pages."""
        if not pn532:
            return None

        try:
            data = bytearray()
            for page in range(USER_PAGE_START, min(USER_PAGE_END, USER_PAGE_START + 20)):
                page_data = pn532.ntag2xx_read_block(page)
                if not page_data:
                    break
                null_idx = page_data.find(b"\x00")
                if null_idx >= 0:
                    data.extend(page_data[:null_idx])
                    break
                data.extend(page_data)

            if data:
                text = data.decode("ascii", errors="ignore").strip()
                if text and PRODUCT_SEPARATOR in text:
                    return text
        except Exception as e:
            logger.debug(f"[MultiPN532] Read product data error: {e}")

        return None

    def _poll_one_reader(self, reader: ReaderInstance) -> List[TagReading]:
        """Poll a single reader for tags. Thread-safe."""
        if not reader.healthy or not reader.pn532:
            self._try_reconnect_reader(reader)
            return []

        with reader.lock:
            try:
                uid = reader.pn532.read_passive_target(timeout=self._poll_timeout)
                if uid is None:
                    return []

                tag_id = ":".join(f"{b:02X}" for b in uid)

                # Check tag data cache
                cached = reader.tag_cache.get(tag_id)
                if cached:
                    product_data = cached["product_data"]
                    parsed = cached["parsed"]
                else:
                    product_data = self._read_product_data(reader.pn532)
                    parsed = {}
                    if product_data:
                        parts = product_data.split(PRODUCT_SEPARATOR)
                        if len(parts) >= 4:
                            parsed = {
                                "ppg_code": parts[0],
                                "batch_number": parts[1],
                                "product_name": parts[2],
                                "color": parts[3],
                            }
                    reader.tag_cache[tag_id] = {
                        "product_data": product_data,
                        "parsed": parsed,
                        "time": time.time(),
                    }
                    logger.info(
                        f"[MultiPN532] Reader '{reader.reader_id}' tag {tag_id}: "
                        f"{product_data or 'no data'}"
                    )

                return [TagReading(
                    tag_id=tag_id,
                    reader_id=reader.reader_id,
                    signal_strength=90,
                    timestamp=time.time(),
                    product_data=product_data,
                    ppg_code=parsed.get("ppg_code"),
                    batch_number=parsed.get("batch_number"),
                    product_name=parsed.get("product_name"),
                    color=parsed.get("color"),
                )]

            except Exception as e:
                now = time.time()
                if now - reader.last_error_time > 30:
                    logger.error(
                        f"[MultiPN532] Reader '{reader.reader_id}' poll error: {e}"
                    )
                    reader.last_error_time = now

                err_str = str(e).lower()
                if ("i/o error" in err_str or "input/output" in err_str
                        or "errno 5" in err_str):
                    logger.warning(
                        f"[MultiPN532] Reader '{reader.reader_id}' USB I/O error"
                    )
                    self._try_reconnect_reader(reader)
                elif reader.ser and not reader.ser.is_open:
                    self._try_reconnect_reader(reader)
                return []

    # ----------------------------------------------------------
    # HAL Interface Implementation
    # ----------------------------------------------------------

    def initialize(self) -> bool:
        """Initialize all PN532 readers."""
        if not HAS_SERIAL or not HAS_ADAFRUIT:
            logger.warning("[MultiPN532] Missing dependencies")
            return False

        # Build reader configs (auto-detect if not explicitly set)
        if not self._reader_configs:
            ports = self._find_all_pn532_ports()
            if not ports:
                logger.warning("[MultiPN532] No PN532 USB ports found")
                return False
            self._reader_configs = [
                {"port": p, "reader_id": f"shelf1_slot{i + 1}"}
                for i, p in enumerate(ports)
            ]
            logger.info(
                f"[MultiPN532] Auto-detected {len(ports)} ports: "
                f"{[c['port'] for c in self._reader_configs]}"
            )

        # Initialize each reader (sequential — serial init can't overlap)
        success = 0
        for cfg in self._reader_configs:
            port = cfg["port"]
            reader_id = cfg["reader_id"]

            if port in self._skip_ports:
                logger.info(f"[MultiPN532] Skipping {port} (claimed by other device)")
                continue

            # Try up to 2 times per reader
            for attempt in range(1, 3):
                reader = self._connect_reader(port, reader_id)
                if reader:
                    self._readers[reader_id] = reader
                    success += 1
                    break
                logger.warning(
                    f"[MultiPN532] Init '{reader_id}' on {port} "
                    f"attempt {attempt}/2 failed"
                )
                time.sleep(1)

        # Create thread pool for parallel polling if many readers
        if len(self._readers) > PARALLEL_THRESHOLD:
            # Cap at 16 workers (OS thread limit consideration)
            workers = min(len(self._readers), 16)
            self._executor = ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="rfid-poll"
            )
            logger.info(
                f"[MultiPN532] Parallel polling enabled: "
                f"{workers} threads for {len(self._readers)} readers"
            )

        self._initialized = success > 0
        logger.info(
            f"[MultiPN532] Initialized {success}/{len(self._reader_configs)} readers"
        )
        return self._initialized

    def poll_tags(self) -> List[TagReading]:
        """Poll ALL readers and return combined tag list."""
        if not self._initialized:
            return []

        readers = list(self._readers.values())

        if self._executor and len(readers) > PARALLEL_THRESHOLD:
            # Parallel poll for many readers
            return self._poll_parallel(readers)
        else:
            # Sequential poll for few readers
            return self._poll_sequential(readers)

    def _poll_sequential(self, readers: List[ReaderInstance]) -> List[TagReading]:
        """Poll readers one by one (fast enough for ≤6 readers)."""
        results = []
        for reader in readers:
            results.extend(self._poll_one_reader(reader))
        return results

    def _poll_parallel(self, readers: List[ReaderInstance]) -> List[TagReading]:
        """Poll readers in parallel using thread pool (for 7+ readers)."""
        results = []
        futures = {
            self._executor.submit(self._poll_one_reader, r): r
            for r in readers
        }
        for future in as_completed(futures, timeout=2.0):
            try:
                tags = future.result()
                results.extend(tags)
            except Exception as e:
                reader = futures[future]
                logger.warning(
                    f"[MultiPN532] Parallel poll error for "
                    f"'{reader.reader_id}': {e}"
                )
        return results

    def get_reader_ids(self) -> List[str]:
        """Return list of all configured reader IDs."""
        return list(self._readers.keys())

    def write_product_data(self, product_string: str,
                           reader_id: Optional[str] = None) -> bool:
        """Write product data to NFC tag.

        If reader_id is specified, write via that reader.
        Otherwise, try all readers and write to the first one with a tag present.
        """
        if not self._initialized:
            return False

        # Specific reader requested
        if reader_id and reader_id in self._readers:
            return self._write_on_reader(self._readers[reader_id], product_string)

        # Try all readers — find one with a tag present
        for reader in self._readers.values():
            if not reader.healthy or not reader.pn532:
                continue
            with reader.lock:
                try:
                    uid = reader.pn532.read_passive_target(timeout=0.1)
                    if uid is not None:
                        logger.info(
                            f"[MultiPN532] Writing via reader '{reader.reader_id}'"
                        )
                        return self._write_on_reader_unlocked(reader, product_string)
                except Exception:
                    continue

        logger.warning("[MultiPN532] No reader has a tag present for writing")
        return False

    def _write_on_reader(self, reader: ReaderInstance, data_str: str) -> bool:
        """Write to a tag on a specific reader (acquires lock)."""
        with reader.lock:
            return self._write_on_reader_unlocked(reader, data_str)

    def _write_on_reader_unlocked(self, reader: ReaderInstance, data_str: str) -> bool:
        """Write to tag — caller must hold reader.lock."""
        if not reader.pn532:
            return False

        try:
            # Ensure tag is present
            uid = reader.pn532.read_passive_target(timeout=0.1)
            if uid is None:
                logger.warning(
                    f"[MultiPN532] No tag on '{reader.reader_id}' for write"
                )
                return False

            data = data_str.encode("ascii")
            page = USER_PAGE_START
            for i in range(0, len(data), 4):
                chunk = data[i:i + 4]
                if len(chunk) < 4:
                    chunk = chunk + b"\x00" * (4 - len(chunk))
                reader.pn532.ntag2xx_write_block(page, chunk)
                page += 1

            # Null terminator
            reader.pn532.ntag2xx_write_block(page, b"\x00\x00\x00\x00")

            # Clear this reader's tag cache
            reader.tag_cache.clear()

            tag_id = ":".join(f"{b:02X}" for b in uid)
            logger.info(
                f"[MultiPN532] Wrote {len(data)} bytes on '{reader.reader_id}' "
                f"tag {tag_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"[MultiPN532] Write failed on '{reader.reader_id}': {e}"
            )
            return False

    def is_healthy(self) -> bool:
        """True if at least one reader is operational."""
        return self._initialized and any(
            r.healthy for r in self._readers.values()
        )

    def get_healthy_count(self) -> tuple:
        """Return (healthy_count, total_count) for status display."""
        total = len(self._readers)
        healthy = sum(1 for r in self._readers.values() if r.healthy)
        return healthy, total

    def get_mapping(self) -> list:
        """Return current port → reader_id mapping for persistence."""
        return [
            {"port": r.port, "reader_id": rid}
            for rid, r in self._readers.items()
        ]

    def apply_saved_mapping(self, saved_map: List[dict]) -> int:
        """Apply a saved port→reader_id mapping after auto-detection.

        After auto-detect assigns sequential IDs (shelf1_slot1, slot2, ...),
        this rearranges readers so each port maps to the reader_id the user
        configured via the reorder UI.

        Args:
            saved_map: List of {"port": "/dev/ttyUSBx", "reader_id": "shelf1_slotN"}

        Returns:
            Number of readers successfully remapped.
        """
        if not saved_map or not self._readers:
            return 0

        # Build port→desired_reader_id from saved config
        port_to_desired = {m["port"]: m["reader_id"] for m in saved_map}

        # Index current readers by port
        by_port: Dict[str, ReaderInstance] = {}
        for reader in self._readers.values():
            by_port[reader.port] = reader

        # Rebuild _readers dict with saved IDs
        new_readers: Dict[str, ReaderInstance] = {}
        used_ids: set = set()
        remapped = 0

        # First pass: assign saved reader_ids to known ports
        for port, reader in by_port.items():
            desired_id = port_to_desired.get(port)
            if desired_id:
                reader.reader_id = desired_id
                new_readers[desired_id] = reader
                used_ids.add(desired_id)
                remapped += 1

        # Second pass: assign IDs to new/unknown ports (not in saved map)
        slot_num = 1
        for port, reader in by_port.items():
            if port not in port_to_desired:
                while f"shelf1_slot{slot_num}" in used_ids:
                    slot_num += 1
                new_id = f"shelf1_slot{slot_num}"
                reader.reader_id = new_id
                new_readers[new_id] = reader
                used_ids.add(new_id)
                slot_num += 1

        self._readers = new_readers

        # Clear all tag caches (reader_ids changed)
        for r in self._readers.values():
            r.tag_cache.clear()

        logger.info(
            f"[MultiPN532] Applied saved mapping: {remapped}/{len(self._readers)} remapped"
        )
        return remapped

    def swap_readers(self, id1: str, id2: str) -> bool:
        """Swap the logical reader_ids of two physical readers.

        After swap, the reader that was shelf1_slot1 becomes shelf1_slot2
        and vice-versa. The physical PN532 modules stay on their ports.
        """
        if id1 not in self._readers or id2 not in self._readers:
            return False
        r1, r2 = self._readers[id1], self._readers[id2]
        # Swap reader_ids
        r1.reader_id, r2.reader_id = id2, id1
        # Swap dict entries
        self._readers[id1] = r2
        self._readers[id2] = r1
        # Clear caches so tags get re-read with correct reader_id
        r1.tag_cache.clear()
        r2.tag_cache.clear()
        logger.info(f"[MultiPN532] Swapped {id1} <-> {id2}")
        return True

    def shutdown(self) -> None:
        """Close all readers and release resources."""
        for reader in self._readers.values():
            self._disconnect_reader(reader)
        self._readers.clear()
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        self._initialized = False
        logger.info("[MultiPN532] All readers shut down")
