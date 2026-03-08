"""
Logging configuration for SmartLocker Edge.

Three log streams:
  1. Application log  - software events, errors, debug info
  2. Event log        - business events (stored in SQLite, not here)
  3. Sensor log       - raw sensor readings for hardware debugging
"""

import logging
import logging.handlers
import os
from config.settings import LOG_LEVEL, LOG_DIR


def setup_logging():
    """Initialize all log handlers. Call once at startup."""
    os.makedirs(LOG_DIR, exist_ok=True)

    # Application logger
    app_logger = logging.getLogger("smartlocker")
    app_logger.setLevel(getattr(logging, LOG_LEVEL))

    app_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
    )
    app_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    app_logger.addHandler(app_handler)

    # Console handler (always show in terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    app_logger.addHandler(console_handler)

    # Sensor logger (separate file, rotates faster)
    sensor_logger = logging.getLogger("smartlocker.sensor")
    sensor_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "sensor.log"),
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
    )
    sensor_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(name)s: %(message)s"
    ))
    sensor_logger.addHandler(sensor_handler)

    return app_logger
