"""
Database Layer

SQLite connection management and schema initialization.
WAL mode for crash safety. All data stored locally for offline operation.
"""

import sqlite3
import json
import logging
import os
from typing import Optional, List, Dict, Any

from config import settings
from core.event_types import Event

logger = logging.getLogger("smartlocker")


class Database:
    """
    SQLite database manager.

    Handles:
    - Connection setup with WAL mode
    - Schema initialization
    - Event log persistence
    - Sync queue management
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Open database connection and initialize schema."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row  # Dict-like row access

        # Enable WAL mode for crash safety
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        # Initialize schema
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                self._conn.executescript(f.read())
            logger.info(f"Database initialized: {self.db_path}")
        else:
            logger.warning(f"Schema file not found: {schema_path}")

        # Migration: add 'synced' column to mixing_session if missing
        try:
            self._conn.execute("ALTER TABLE mixing_session ADD COLUMN synced INTEGER DEFAULT 0")
        except Exception:
            pass  # Column already exists

        # Create sensor health log table (added for offline health logging)
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS sensor_health_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                value TEXT,
                synced INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self._conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_health_log_synced '
            'ON sensor_health_log(synced)'
        )
        self._conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_health_log_sensor '
            'ON sensor_health_log(sensor)'
        )

        # Create vessel_stock table (cloud-synced vessel inventory)
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS vessel_stock (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                product_type TEXT DEFAULT 'base_paint',
                current_liters REAL DEFAULT 0.0,
                initial_liters REAL DEFAULT 0.0,
                density_g_per_ml REAL DEFAULT 1.0,
                colors_json TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration: add colors_json column to product if missing
        try:
            self._conn.execute("ALTER TABLE product ADD COLUMN colors_json TEXT DEFAULT '[]'")
        except Exception:
            pass  # Column already exists

        # Migration: add sync_retries column to event_log for retry tracking
        try:
            self._conn.execute("ALTER TABLE event_log ADD COLUMN sync_retries INTEGER DEFAULT 0")
        except Exception:
            pass  # Column already exists

        # Migration: add sync_retries to mixing_session
        try:
            self._conn.execute("ALTER TABLE mixing_session ADD COLUMN sync_retries INTEGER DEFAULT 0")
        except Exception:
            pass  # Column already exists

        self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # ============================================================
    # EVENT LOG
    # ============================================================

    def save_event(self, event: Event) -> None:
        """Save an event to the local event log (append-only)."""
        self.conn.execute(
            """INSERT OR IGNORE INTO event_log
               (event_id, sequence_num, event_type, timestamp, device_id,
                shelf_id, slot_id, tag_id, session_id, user_name,
                data_json, confirmation, synced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.sequence_num,
                event.event_type.value,
                event.timestamp,
                event.device_id,
                event.shelf_id,
                event.slot_id,
                event.tag_id,
                event.session_id,
                event.user_name,
                json.dumps(event.data),
                event.confirmation,
                0,  # Not synced yet
            ),
        )
        self.conn.commit()

    def get_unsynced_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get events that haven't been synced to cloud yet.

        Skips events that have exceeded MAX_SYNC_RETRIES (they get force-marked).
        """
        cursor = self.conn.execute(
            """SELECT * FROM event_log
               WHERE synced = 0
               ORDER BY sequence_num ASC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_events_synced(self, event_ids: List[str]) -> None:
        """Mark events as synced after successful cloud upload."""
        if not event_ids:
            return
        placeholders = ",".join("?" * len(event_ids))
        self.conn.execute(
            f"UPDATE event_log SET synced = 1 WHERE event_id IN ({placeholders})",
            event_ids,
        )
        self.conn.commit()

    def increment_event_retries(self, event_ids: List[str]) -> None:
        """Increment sync_retries counter for failed events."""
        if not event_ids:
            return
        placeholders = ",".join("?" * len(event_ids))
        self.conn.execute(
            f"UPDATE event_log SET sync_retries = COALESCE(sync_retries, 0) + 1 WHERE event_id IN ({placeholders})",
            event_ids,
        )
        self.conn.commit()

    def get_stuck_events(self, max_retries: int = 5) -> List[str]:
        """Get event IDs that have exceeded max retry count."""
        cursor = self.conn.execute(
            """SELECT event_id FROM event_log
               WHERE synced = 0 AND COALESCE(sync_retries, 0) >= ?""",
            (max_retries,),
        )
        return [row[0] for row in cursor.fetchall()]

    def force_mark_stuck_synced(self, max_retries: int = 5) -> int:
        """Force-mark stuck events as synced to unblock the queue.

        Returns count of events force-marked.
        """
        cursor = self.conn.execute(
            """UPDATE event_log SET synced = 1
               WHERE synced = 0 AND COALESCE(sync_retries, 0) >= ?""",
            (max_retries,),
        )
        count = cursor.rowcount
        if count > 0:
            self.conn.commit()
            logger.warning(f"Force-marked {count} stuck events as synced (>{max_retries} retries)")
        return count

    def get_event_count(self, synced: Optional[bool] = None) -> int:
        """Count events in the log."""
        if synced is None:
            cursor = self.conn.execute("SELECT COUNT(*) FROM event_log")
        else:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM event_log WHERE synced = ?",
                (1 if synced else 0,),
            )
        return cursor.fetchone()[0]

    # ============================================================
    # SYNC QUEUE
    # ============================================================

    def enqueue_for_sync(self, event: Event) -> None:
        """Add an event to the sync queue."""
        self.conn.execute(
            """INSERT INTO sync_queue (event_id, payload_json, created_at, status)
               VALUES (?, ?, ?, 'pending')""",
            (event.event_id, json.dumps(event.to_dict()), event.timestamp),
        )
        self.conn.commit()

    def get_pending_sync(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending items from sync queue."""
        cursor = self.conn.execute(
            """SELECT * FROM sync_queue
               WHERE status = 'pending'
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_sync_acked(self, event_ids: List[str]) -> None:
        """Mark sync queue items as acknowledged by server."""
        placeholders = ",".join("?" * len(event_ids))
        self.conn.execute(
            f"UPDATE sync_queue SET status = 'acked' WHERE event_id IN ({placeholders})",
            event_ids,
        )
        self.mark_events_synced(event_ids)

    # ============================================================
    # SENSOR HEALTH LOG (offline health logging)
    # ============================================================

    def log_sensor_health(self, sensor: str, status: str,
                          message: str = '', value: str = '') -> None:
        """Log a sensor health snapshot (called every 5 min by SyncEngine)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO sensor_health_log
               (timestamp, sensor, status, message, value, synced)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (now, sensor, status, message, value),
        )
        self.conn.commit()

    def get_pending_health_logs(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get unsynced health logs for batch upload to cloud."""
        cursor = self.conn.execute(
            """SELECT id, timestamp, sensor, status, message, value
               FROM sensor_health_log
               WHERE synced = 0
               ORDER BY id ASC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_health_logs_synced(self, log_ids: List[int]) -> None:
        """Mark health logs as synced after successful upload."""
        if not log_ids:
            return
        placeholders = ",".join("?" * len(log_ids))
        self.conn.execute(
            f"UPDATE sensor_health_log SET synced = 1 WHERE id IN ({placeholders})",
            log_ids,
        )
        self.conn.commit()

    def cleanup_old_health_logs(self, days: int = 30) -> None:
        """Delete synced health logs older than X days to save RPi storage."""
        self.conn.execute(
            """DELETE FROM sensor_health_log
               WHERE synced = 1
               AND created_at < datetime('now', '-' || ? || ' days')""",
            (days,),
        )
        self.conn.commit()

    # ============================================================
    # PRODUCT CATALOG
    # ============================================================

    def get_products(self) -> List[Dict[str, Any]]:
        """Get all products from local catalog."""
        cursor = self.conn.execute("SELECT * FROM product")
        return [dict(row) for row in cursor.fetchall()]

    def get_recipes(self) -> List[Dict[str, Any]]:
        """Get all mixing recipes."""
        cursor = self.conn.execute("SELECT * FROM mixing_recipe")
        return [dict(row) for row in cursor.fetchall()]

    def upsert_product(self, product: Dict[str, Any]) -> None:
        """Insert or update a product in the local catalog."""
        colors = product.get("colors_json", [])
        if isinstance(colors, str):
            colors_str = colors
        else:
            colors_str = json.dumps(colors) if colors else "[]"
        self.conn.execute(
            """INSERT OR REPLACE INTO product
               (product_id, ppg_code, name, product_type, density_g_per_ml,
                pot_life_minutes, hazard_class, can_sizes_ml, can_tare_weight_g,
                colors_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                product["product_id"],
                product.get("ppg_code", ""),
                product["name"],
                product["product_type"],
                product.get("density_g_per_ml", 1.0),
                product.get("pot_life_minutes"),
                product.get("hazard_class", ""),
                json.dumps(product.get("can_sizes_ml", [])),
                json.dumps(product.get("can_tare_weight_g", {})),
                colors_str,
            ),
        )
        self.conn.commit()

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a single product by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM product WHERE product_id = ?", (product_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_product_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a product by name (case-insensitive partial match)."""
        cursor = self.conn.execute(
            "SELECT * FROM product WHERE UPPER(name) LIKE UPPER(?)",
            (f"%{name}%",),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_product_by_ppg_code(self, ppg_code: str) -> Optional[Dict[str, Any]]:
        """Find a product by PPG code."""
        cursor = self.conn.execute(
            "SELECT * FROM product WHERE UPPER(ppg_code) = UPPER(?)",
            (ppg_code,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ============================================================
    # BARCODE LOOKUP (for barcode scanner inventory)
    # ============================================================

    def get_barcode_product(self, barcode_data: str,
                            ppg_code: str = "") -> Optional[Dict[str, Any]]:
        """Look up a barcode string and return linked product info.

        Tries:
        1. Exact barcode_data match
        2. PPG code match in product_barcode table
        3. PPG code match in product table
        """
        # Strategy 1: exact barcode match
        cursor = self.conn.execute(
            """SELECT b.*, p.name as p_name, p.product_type as p_type,
                      p.density_g_per_ml, p.ppg_code as p_ppg
               FROM product_barcode b
               LEFT JOIN product p ON b.product_id = p.product_id
               WHERE b.barcode_data = ?""",
            (barcode_data,),
        )
        row = cursor.fetchone()

        # Strategy 2: ppg_code match in product_barcode table
        if not row and ppg_code:
            cursor = self.conn.execute(
                """SELECT b.*, p.name as p_name, p.product_type as p_type,
                          p.density_g_per_ml, p.ppg_code as p_ppg
                   FROM product_barcode b
                   LEFT JOIN product p ON b.product_id = p.product_id
                   WHERE UPPER(b.ppg_code) = UPPER(?)
                   LIMIT 1""",
                (ppg_code,),
            )
            row = cursor.fetchone()

        # Strategy 3: ppg_code match in product table only
        if not row and ppg_code:
            cursor = self.conn.execute(
                """SELECT product_id, name as p_name, ppg_code as p_ppg,
                          product_type as p_type, density_g_per_ml
                   FROM product
                   WHERE UPPER(ppg_code) = UPPER(?)""",
                (ppg_code,),
            )
            row = cursor.fetchone()
            if row:
                d = dict(row)
                return {
                    "product_id": d.get("product_id", ""),
                    "product_name": d.get("p_name", ""),
                    "ppg_code": d.get("p_ppg", ppg_code),
                    "product_type": d.get("p_type", ""),
                    "density_g_per_ml": d.get("density_g_per_ml", 1.3),
                    "batch_number": "",
                    "color": "",
                    "match_type": "ppg_product",
                }

        if not row:
            return None

        d = dict(row)
        return {
            "product_id": d.get("product_id", ""),
            "product_name": d.get("p_name") or d.get("product_name", ""),
            "ppg_code": d.get("p_ppg") or d.get("ppg_code", ""),
            "product_type": d.get("p_type") or d.get("product_type", ""),
            "density_g_per_ml": d.get("density_g_per_ml", 1.3),
            "batch_number": d.get("batch_number", ""),
            "color": d.get("color", ""),
            "match_type": "exact",
        }

    def save_barcode(self, barcode_data: str, product_id: str,
                     ppg_code: str, batch_number: str,
                     product_name: str, color: str = "",
                     barcode_type: str = "code128") -> None:
        """Save or update a product barcode mapping."""
        self.conn.execute(
            """INSERT OR REPLACE INTO product_barcode
               (barcode_data, product_id, ppg_code, batch_number,
                product_name, color, barcode_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (barcode_data, product_id, ppg_code, batch_number,
             product_name, color, barcode_type),
        )
        self.conn.commit()

    # ============================================================
    # VESSEL STOCK (cloud-synced vessel inventory)
    # ============================================================

    def upsert_vessel_stock(self, stock: Dict[str, Any]) -> None:
        """Insert or update a vessel stock entry from cloud sync."""
        colors = stock.get("colors_json", [])
        if isinstance(colors, str):
            colors_str = colors
        else:
            colors_str = json.dumps(colors) if colors else "[]"
        self.conn.execute(
            """INSERT OR REPLACE INTO vessel_stock
               (product_id, product_name, product_type,
                current_liters, initial_liters, density_g_per_ml,
                colors_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                stock["product_id"],
                stock["product_name"],
                stock.get("product_type", "base_paint"),
                stock.get("current_liters", 0.0),
                stock.get("initial_liters", 0.0),
                stock.get("density_g_per_ml", 1.0),
                colors_str,
            ),
        )
        self.conn.commit()

    def get_vessel_stock(self) -> List[Dict[str, Any]]:
        """Get all vessel stock entries (from cloud sync + local barcode scans)."""
        cursor = self.conn.execute(
            "SELECT * FROM vessel_stock ORDER BY product_name"
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_vessel_stock_from_barcode(self, product_info: dict,
                                          action: str,
                                          weight_g: float = 0.0) -> None:
        """Update vessel_stock when a barcode scan adds/removes a product.

        Args:
            product_info: dict with product_id, product_name, ppg_code, etc.
            action: 'load' or 'unload'
            weight_g: weight in grams (absolute value of change)
        """
        product_id = product_info.get("product_id") or product_info.get("ppg_code", "")
        product_name = product_info.get("product_name", "Unknown")
        product_type = product_info.get("product_type", "base_paint")
        density = float(product_info.get("density_g_per_ml", 1.3))

        # Convert weight (grams) to liters: g / (density_g_ml * 1000)
        liters_change = abs(weight_g) / (density * 1000) if density > 0 else 0.0

        # Check if product already exists in vessel_stock
        cursor = self.conn.execute(
            "SELECT product_id, current_liters FROM vessel_stock WHERE product_id = ?",
            (product_id,),
        )
        row = cursor.fetchone()

        if row:
            current = float(row[1] or 0)
            if action == "load":
                new_liters = current + liters_change
            else:
                new_liters = max(0, current - liters_change)
            self.conn.execute(
                """UPDATE vessel_stock
                   SET current_liters = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE product_id = ?""",
                (new_liters, product_id),
            )
        else:
            # New product — insert it
            initial = liters_change if action == "load" else 0.0
            self.conn.execute(
                """INSERT INTO vessel_stock
                   (product_id, product_name, product_type,
                    current_liters, initial_liters, density_g_per_ml,
                    colors_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, '[]', CURRENT_TIMESTAMP)""",
                (product_id, product_name, product_type,
                 initial, initial, density),
            )

        self.conn.commit()
        logger.info(
            f"Vessel stock updated: {action} {product_name} "
            f"weight={weight_g:.0f}g liters_change={liters_change:.2f}L"
        )

    def clear_vessel_stock(self) -> None:
        """Clear vessel stock table before full refresh."""
        self.conn.execute("DELETE FROM vessel_stock")
        self.conn.commit()

    # ============================================================
    # MIXING RECIPES
    # ============================================================

    def upsert_recipe(self, recipe: Dict[str, Any]) -> None:
        """Insert or update a mixing recipe."""
        self.conn.execute(
            """INSERT OR REPLACE INTO mixing_recipe
               (recipe_id, name, base_product_id, hardener_product_id,
                ratio_base, ratio_hardener, tolerance_pct,
                thinner_pct_brush, thinner_pct_roller, thinner_pct_spray,
                recommended_thinner_id, pot_life_minutes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                recipe["recipe_id"],
                recipe["name"],
                recipe["base_product_id"],
                recipe["hardener_product_id"],
                recipe["ratio_base"],
                recipe["ratio_hardener"],
                recipe.get("tolerance_pct", 5.0),
                recipe.get("thinner_pct_brush", 5.0),
                recipe.get("thinner_pct_roller", 5.0),
                recipe.get("thinner_pct_spray", 10.0),
                recipe.get("recommended_thinner_id"),
                recipe.get("pot_life_minutes", 480),
            ),
        )
        self.conn.commit()

    # ============================================================
    # RFID TAG → PRODUCT MAPPING
    # ============================================================

    def upsert_rfid_tag(self, tag_uid: str, product_id: str,
                        can_size_ml: int = None,
                        batch_number: str = None) -> None:
        """Map an RFID tag to a product, with optional batch/lot number."""
        self.conn.execute(
            """INSERT OR REPLACE INTO rfid_tag
               (tag_uid, product_id, can_size_ml, batch_number)
               VALUES (?, ?, ?, ?)""",
            (tag_uid, product_id, can_size_ml, batch_number),
        )
        self.conn.commit()

    def get_product_for_tag(self, tag_uid: str) -> Optional[Dict[str, Any]]:
        """Look up the product associated with an RFID tag."""
        cursor = self.conn.execute(
            """SELECT p.* FROM product p
               JOIN rfid_tag t ON t.product_id = p.product_id
               WHERE t.tag_uid = ?""",
            (tag_uid,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_rfid_tag_info(self, tag_uid: str) -> Optional[Dict[str, Any]]:
        """Look up RFID tag details including product info, lot number, can size."""
        cursor = self.conn.execute(
            """SELECT t.tag_uid, t.product_id, t.batch_number, t.can_size_ml,
                      t.weight_full_g, t.weight_current_g,
                      p.name as product_name, p.product_type, p.ppg_code
               FROM rfid_tag t
               LEFT JOIN product p ON t.product_id = p.product_id
               WHERE t.tag_uid = ?""",
            (tag_uid,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ============================================================
    # SLOT STATE (inventory tracking)
    # ============================================================

    def update_slot_state(self, slot_id: str, status: str,
                          current_tag_id: Optional[str] = None,
                          current_product_id: Optional[str] = None,
                          weight_when_placed_g: float = 0.0,
                          weight_current_g: float = 0.0) -> None:
        """Update or insert current state for a shelf slot."""
        self.conn.execute(
            """INSERT OR REPLACE INTO slot_state
               (slot_id, status, current_tag_id, current_product_id,
                weight_when_placed_g, weight_current_g, last_change_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (slot_id, status, current_tag_id, current_product_id,
             weight_when_placed_g, weight_current_g),
        )
        self.conn.commit()

    def get_inventory_snapshot(self) -> List[Dict[str, Any]]:
        """Get current state of all slots for cloud sync / reconciliation."""
        cursor = self.conn.execute('''
            SELECT s.slot_id, s.status, s.current_tag_id, s.current_product_id,
                   s.weight_when_placed_g, s.weight_current_g, s.last_change_at,
                   p.name as product_name, p.product_type,
                   t.batch_number, t.can_size_ml
            FROM slot_state s
            LEFT JOIN product p ON s.current_product_id = p.product_id
            LEFT JOIN rfid_tag t ON s.current_tag_id = t.tag_uid
        ''')
        return [dict(row) for row in cursor.fetchall()]

    # ============================================================
    # MAINTENANCE CHART (stored as JSON in config table)
    # ============================================================

    def save_maintenance_chart(self, chart_data: dict) -> None:
        """Save maintenance chart data for offline access."""
        self.conn.execute(
            """INSERT OR REPLACE INTO config (key, value, updated_at)
               VALUES ('maintenance_chart', ?, CURRENT_TIMESTAMP)""",
            (json.dumps(chart_data),),
        )
        self.conn.commit()
        logger.info("Maintenance chart saved to local DB")

    def get_maintenance_chart(self) -> Optional[dict]:
        """Get the locally cached maintenance chart."""
        cursor = self.conn.execute(
            "SELECT value FROM config WHERE key = 'maintenance_chart'"
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    # ============================================================
    # ADMIN CONFIG
    # ============================================================

    def save_admin_config(self, config_dict: dict) -> None:
        """Save admin settings as JSON in config table (key='admin_settings')."""
        self.conn.execute(
            """INSERT OR REPLACE INTO config (key, value, updated_at)
               VALUES ('admin_settings', ?, CURRENT_TIMESTAMP)""",
            (json.dumps(config_dict),),
        )
        self.conn.commit()
        logger.info("Admin config saved to DB")

    def get_admin_config(self) -> dict:
        """Load admin settings from config table. Returns {} if none."""
        cursor = self.conn.execute(
            "SELECT value FROM config WHERE key = 'admin_settings'"
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def get_admin_password_hash(self) -> Optional[str]:
        """Get stored admin password hash."""
        cursor = self.conn.execute(
            "SELECT value FROM config WHERE key = 'admin_password_hash'"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def set_admin_password_hash(self, hash_str: str) -> None:
        """Store new admin password hash."""
        self.conn.execute(
            """INSERT OR REPLACE INTO config (key, value, updated_at)
               VALUES ('admin_password_hash', ?, CURRENT_TIMESTAMP)""",
            (hash_str,),
        )
        self.conn.commit()
        logger.info("Admin password hash updated")

    def get_admin_password_change_date(self) -> Optional[str]:
        """Get the timestamp of the last admin password change."""
        cursor = self.conn.execute(
            "SELECT updated_at FROM config WHERE key = 'admin_password_hash'"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    # ============================================================
    # RECIPE LOOKUP BY PRODUCT NAME
    # ============================================================

    def find_recipe_by_product_name(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Find a mixing recipe that uses a product with the given name as base."""
        product = self.get_product_by_name(product_name)
        if not product:
            return None
        cursor = self.conn.execute(
            "SELECT * FROM mixing_recipe WHERE base_product_id = ?",
            (product["product_id"],),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ============================================================
    # ALARM LOG (v1.0.6)
    # ============================================================

    def save_alarm(self, alarm_dict: Dict[str, Any]) -> None:
        """Save a new alarm to the alarm log."""
        self.conn.execute(
            """INSERT OR IGNORE INTO alarm_log
               (alarm_id, error_code, error_title, severity, category,
                details, source, status, raised_at, support_requested, synced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                alarm_dict["alarm_id"],
                alarm_dict["error_code"],
                alarm_dict["error_title"],
                alarm_dict["severity"],
                alarm_dict["category"],
                alarm_dict.get("details", ""),
                alarm_dict.get("source", ""),
                alarm_dict.get("status", "active"),
                alarm_dict["raised_at"],
                1 if alarm_dict.get("support_requested") else 0,
            ),
        )
        self.conn.commit()

    def update_alarm(self, alarm_id: str, updates: Dict[str, Any]) -> None:
        """Update alarm fields."""
        allowed = {
            "status", "acknowledged_at", "resolved_at",
            "support_requested", "support_requested_at", "synced",
        }
        sets = []
        vals = []
        for key, val in updates.items():
            if key in allowed:
                sets.append(f"{key} = ?")
                vals.append(1 if isinstance(val, bool) and val else val)
        if not sets:
            return
        vals.append(alarm_id)
        self.conn.execute(
            f"UPDATE alarm_log SET {', '.join(sets)} WHERE alarm_id = ?",
            vals,
        )
        self.conn.commit()

    def get_active_alarms(self) -> List[Dict[str, Any]]:
        """Get all active (unresolved) alarms."""
        cursor = self.conn.execute(
            """SELECT * FROM alarm_log
               WHERE status IN ('active', 'acknowledged')
               ORDER BY raised_at DESC"""
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_alarm_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alarm history (all statuses)."""
        cursor = self.conn.execute(
            """SELECT * FROM alarm_log
               ORDER BY raised_at DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_alarms(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alarms not yet synced to cloud."""
        cursor = self.conn.execute(
            """SELECT * FROM alarm_log
               WHERE synced = 0
               ORDER BY raised_at ASC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_alarms_synced(self, alarm_ids: List[str]) -> None:
        """Mark alarms as synced to cloud."""
        if not alarm_ids:
            return
        placeholders = ",".join("?" * len(alarm_ids))
        self.conn.execute(
            f"UPDATE alarm_log SET synced = 1 WHERE alarm_id IN ({placeholders})",
            alarm_ids,
        )
        self.conn.commit()

    # ============================================================
    # MIXING SESSION PERSISTENCE
    # ============================================================

    def save_mixing_session(self, session, status: str = "completed") -> None:
        """Save (INSERT OR REPLACE) a mixing session to the database."""
        self.conn.execute(
            """INSERT OR REPLACE INTO mixing_session
               (session_id, recipe_id, job_id, user_name,
                started_at, completed_at,
                base_product_id, base_tag_id,
                base_weight_target_g, base_weight_actual_g,
                hardener_product_id, hardener_tag_id,
                hardener_weight_target_g, hardener_weight_actual_g,
                thinner_product_id, thinner_weight_g,
                ratio_achieved, ratio_in_spec,
                override_reason, application_method,
                pot_life_started_at, pot_life_expires_at,
                status, confirmation, synced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                session.session_id,
                session.recipe_id,
                session.job_id or "",
                session.user_name,
                session.started_at,
                session.completed_at,
                session.base_product_id,
                session.base_tag_id,
                session.base_weight_target_g,
                session.base_weight_actual_g,
                session.hardener_product_id,
                session.hardener_tag_id,
                session.hardener_weight_target_g,
                session.hardener_weight_actual_g,
                session.thinner_product_id,
                session.thinner_weight_g,
                session.ratio_achieved,
                1 if session.ratio_in_spec else 0,
                session.override_reason,
                session.application_method.value if hasattr(session.application_method, 'value') else str(session.application_method),
                session.pot_life_started_at,
                session.pot_life_expires_at,
                status,
                session.confirmation.value if hasattr(session.confirmation, 'value') else str(session.confirmation),
            ),
        )
        self.conn.commit()

    def get_mixing_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent mixing sessions."""
        cursor = self.conn.execute(
            """SELECT * FROM mixing_session
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_mixing_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get mixing sessions not yet synced to cloud."""
        cursor = self.conn.execute(
            """SELECT * FROM mixing_session
               WHERE synced = 0
               ORDER BY started_at ASC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_mixing_sessions_synced(self, session_ids: List[str]) -> None:
        """Mark mixing sessions as synced to cloud."""
        if not session_ids:
            return
        placeholders = ",".join("?" * len(session_ids))
        self.conn.execute(
            f"UPDATE mixing_session SET synced = 1 WHERE session_id IN ({placeholders})",
            session_ids,
        )
        self.conn.commit()

    # ============================================================
    # CONFIG HELPERS
    # ============================================================

    def save_config(self, key: str, value: str) -> None:
        """Save a key-value config pair."""
        self.conn.execute(
            """INSERT OR REPLACE INTO config (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (key, value),
        )
        self.conn.commit()

    def get_config(self, key: str) -> Optional[str]:
        """Get a config value by key."""
        cursor = self.conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
