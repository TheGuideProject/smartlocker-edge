# SmartLocker Edge — Changelog

## [4.2.0] — 2026-04-02
### LED System
- Rewrote LED driver with software blink thread (SOLID, BLINK_SLOW 1Hz, BLINK_FAST 2.5Hz)
- LED OFF when product on shelf, RED SOLID when removed, RED BLINK during mixing guidance
- Fixed LED freeze on rapid button presses
- Thread-safe slot config with immediate OFF on clear

### Tag Writer
- Color dropdown populated from cloud product catalog (synced colors)
- Reader/slot selector — choose which reader to scan
- Pause RFID polling during tag writes (no more freezing)
- 8s write timeout

### Shelf Map
- Reorder mode: swap reader-to-slot assignments with drag
- Reader swap state fully reset after reorder (no more reverts on Done)
- Reader positions persist across restarts (saved to DB)

### RFID
- Multi-reader PN532 driver (4 readers via USB hub)
- Fixed skip_ports timing bug (used actual Arduino port, not default)
- Cross-slot can move detection (move from s3 to s1 no longer errors)
- Single-reader poll mode for tag writer exclusive access

### Arduino
- OTA auto-flash pipeline (detect .ino change on git pull, compile, flash)
- Remapped slot LED pins: Slot 1 = A2, Slot 2 = A1

### Cloud Sync
- Products and colors sync continuously via heartbeat (every 2 min)
- Remote cloud log sync for device diagnostics
- Fixed Device Logs page crash (LockerDevice.name attribute)

---

## [4.1.0] — 2026-03-28
### UI Redesign
- Unified icon system + consistent dark theme styling
- All screens optimized for 800x480 4.3" touchscreen
- Sensor health dots update dynamically
- Home screen layout fixed for touch display
- RESUME button + long text truncation fixes

### Hardware Daemon
- TCP daemon separates hardware I/O from UI process
- Background thread polling — UI never freezes
- Daemon guards commands during hardware init
- run_in_executor for all blocking I/O

### RFID Improvements
- NFC tag write via daemon socket
- Daemon passes Arduino port to RFID (no serial conflict)
- Cache NTAG data per tag UID (eliminates UI freeze)

---

## [4.0.0] — 2026-03-26
### Major Architecture
- Migrated from Kivy to PyQt6 (Python 3.13 compatibility)
- Hardware daemon + animated UI
- Desktop launcher for RPi autostart

### Alarm System
- Alarm screen with GPIO LED driver for individual red indicators
- Buzzer mode setting: all / alarms_only / mute

---

## [3.7.0] — 2026-03-24
### Performance
- Hardware polling moved to background thread
- RFID poll throttle to 2s (prevents USB I/O errors)
- PN532 auto-reconnect on USB errors

### Stability
- Arduino firmware RAM optimization (F() macros + smaller buffers)
- Buzzer via Arduino serial (RPi GPIO-free)
- Admin screen with sensor driver toggles

---

## [3.6.0] — 2026-03-23
- Buzzer via Arduino serial bridge
- Flash script for Arduino firmware updates

## [3.5.0] — 2026-03-22
- Arduino Nano firmware for HX711 weight + WS2812B LEDs
- Shelf map barcode slot assignment (RFID backup)
- Admin SAVE & RESTART functionality

## [3.4.0] — 2026-03-21
- Inventory tracking: mixing consumption updates vessel stock
- GPIO auto-restart on sensor failure
- Vessel stock color refresh

## [3.3.0] — 2026-03-20
- Barcode scanner integration (always-on inventory fallback)
- Weight alarm system with buzzer
- Fan control integration
- System Health dashboard + cloud telemetry

## [3.2.0] — 2026-03-19
- Always-on barcode scanner for inventory + mixing fallback
- Product barcode sync from cloud to edge

## [3.1.0] — 2026-03-18
- Calibration wizard for HX711 scales
- Spike filter for weight readings
- Click sounds on button press
- Complete UI redesign (13 screens)

## [3.0.0] — 2026-03-17
- Responsive UI infrastructure
- Dual HX711 support (shelf + mixing scale)
- NFC tag read/write for product data
- RC522 + PN532 RFID driver support
