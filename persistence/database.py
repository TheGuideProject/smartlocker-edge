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

        self._conn = sqlite3.connect(self.db_path)
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
        """Get events that haven't been synced to cloud yet."""
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
        placeholders = ",".join("?" * len(event_ids))
        self.conn.execute(
            f"UPDATE event_log SET synced = 1 WHERE event_id IN ({placeholders})",
            event_ids,
        )
        self.conn.commit()

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
        self.conn.execute(
            """INSERT OR REPLACE INTO product
               (product_id, ppg_code, name, product_type, density_g_per_ml,
                pot_life_minutes, hazard_class, can_sizes_ml, can_tare_weight_g)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                        can_size_ml: int = None) -> None:
        """Map an RFID tag to a product."""
        self.conn.execute(
            """INSERT OR REPLACE INTO rfid_tag
               (tag_uid, product_id, can_size_ml)
               VALUES (?, ?, ?)""",
            (tag_uid, product_id, can_size_ml),
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
