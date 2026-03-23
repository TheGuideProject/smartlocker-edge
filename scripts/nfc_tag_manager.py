#!/usr/bin/env python3
"""
NFC Tag Manager - Write and Read product data on NTAG215 tags via RC522.

Data format stored on tag:
  PPG_CODE/BATCH/PRODUCT_NAME/COLOR
  Example: 616826/80008800/SIGMAPRIME-200/YELLOWGREEN

NTAG215 memory: 504 bytes user data (pages 4-129, 4 bytes per page).

Usage:
  python3 scripts/nfc_tag_manager.py write
  python3 scripts/nfc_tag_manager.py read
  python3 scripts/nfc_tag_manager.py loop   (continuous reading)
"""

import sys
import time

# ---------- NTAG215 low-level operations via RC522 ----------

NTAG_READ_CMD = 0x30   # Read 4 pages (16 bytes)
NTAG_WRITE_CMD = 0xA2  # Write 1 page (4 bytes)
USER_PAGE_START = 4     # First user-writable page
USER_PAGE_END = 129     # Last user-writable page
MAX_USER_BYTES = (USER_PAGE_END - USER_PAGE_START + 1) * 4  # 504 bytes


def init_reader():
    """Initialize RC522 and return the low-level MFRC522 reader."""
    try:
        from mfrc522 import SimpleMFRC522
        simple = SimpleMFRC522()
        return simple.READER
    except Exception as e:
        print(f"  ERRORE inizializzazione RC522: {e}")
        sys.exit(1)


def wait_for_tag(reader):
    """Wait for a tag and return its UID. Blocks until found."""
    while True:
        (status, _) = reader.MFRC522_Request(reader.PICC_REQIDL)
        if status == reader.MI_OK:
            (status, uid) = reader.MFRC522_Anticoll()
            if status == reader.MI_OK:
                # Select the tag (required before read/write)
                reader.MFRC522_SelectTag(uid)
                tag_id = ":".join(f"{b:02X}" for b in uid if b != 0)
                return uid, tag_id
        time.sleep(0.1)


def ntag_read_page(reader, page):
    """Read a single NTAG215 page (returns 4 bytes or None)."""
    # NTAG READ command returns 16 bytes (4 pages starting from `page`)
    buf = [NTAG_READ_CMD, page]
    (status, data, _) = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, buf)
    if status == reader.MI_OK and data and len(data) >= 4:
        return data[:4]
    return None


def ntag_write_page(reader, page, data_4bytes):
    """Write 4 bytes to a single NTAG215 page."""
    if len(data_4bytes) != 4:
        raise ValueError("Ogni pagina NTAG = 4 bytes esatti")
    buf = [NTAG_WRITE_CMD, page] + list(data_4bytes)
    (status, _, _) = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, buf)
    return status == reader.MI_OK


def read_tag_data(reader):
    """Read all user data from NTAG215 tag. Returns decoded string."""
    raw = bytearray()
    for page in range(USER_PAGE_START, USER_PAGE_END + 1):
        data = ntag_read_page(reader, page)
        if data is None:
            break
        raw.extend(data)
        # Stop at null terminator
        if 0x00 in data:
            break

    # Decode and strip padding
    try:
        text = raw.split(b'\x00')[0].decode('utf-8')
        return text
    except Exception:
        return ""


def write_tag_data(reader, text):
    """Write text data to NTAG215 tag (null-terminated)."""
    data = text.encode('utf-8') + b'\x00'

    if len(data) > MAX_USER_BYTES:
        print(f"  ERRORE: testo troppo lungo ({len(data)} bytes, max {MAX_USER_BYTES})")
        return False

    # Pad to multiple of 4
    while len(data) % 4 != 0:
        data += b'\x00'

    # Write page by page
    pages_needed = len(data) // 4
    for i in range(pages_needed):
        page = USER_PAGE_START + i
        chunk = data[i * 4:(i + 1) * 4]
        ok = ntag_write_page(reader, page, chunk)
        if not ok:
            print(f"  ERRORE scrittura pagina {page}")
            return False
        sys.stdout.write(f"\r  Scrittura: {i + 1}/{pages_needed} pagine")
        sys.stdout.flush()

    print(f"\n  Scritti {len(text)} caratteri su {pages_needed} pagine")
    return True


def parse_product_data(text):
    """Parse PPG_CODE/BATCH/PRODUCT_NAME/COLOR format."""
    parts = text.split('/')
    if len(parts) >= 4:
        return {
            'ppg_code': parts[0],
            'batch': parts[1],
            'product_name': parts[2],
            'color': parts[3],
        }
    return None


def format_product_data(ppg_code, batch, product_name, color):
    """Format product data as PPG_CODE/BATCH/PRODUCT_NAME/COLOR."""
    return f"{ppg_code}/{batch}/{product_name}/{color}"


# ---------- Commands ----------

def cmd_write(reader):
    """Interactive write: ask for product data and write to tag."""
    print("\n== SCRIVI TAG PRODOTTO ==\n")

    ppg_code = input("  PPG Code (es. 616826): ").strip()
    batch = input("  Batch Number (es. 80008800): ").strip()
    product_name = input("  Nome Prodotto (es. SIGMAPRIME-200): ").strip().upper()
    color = input("  Colore (es. YELLOWGREEN): ").strip().upper()

    if not all([ppg_code, batch, product_name, color]):
        print("  ERRORE: tutti i campi sono obbligatori")
        return

    tag_data = format_product_data(ppg_code, batch, product_name, color)
    print(f"\n  Dati da scrivere: {tag_data}")
    print(f"  Lunghezza: {len(tag_data)} byte (max {MAX_USER_BYTES})\n")
    print("  Avvicina il tag al lettore...")

    uid, tag_id = wait_for_tag(reader)
    print(f"  Tag trovato: {tag_id}")

    ok = write_tag_data(reader, tag_data)
    if ok:
        print(f"\n  ✅ TAG SCRITTO CON SUCCESSO!")
        print(f"     UID:     {tag_id}")
        print(f"     Dati:    {tag_data}")
    else:
        print(f"\n  ❌ ERRORE SCRITTURA")


def cmd_read(reader):
    """Read and display product data from tag."""
    print("\n== LEGGI TAG PRODOTTO ==\n")
    print("  Avvicina il tag al lettore...")

    uid, tag_id = wait_for_tag(reader)
    print(f"  Tag trovato: {tag_id}")

    text = read_tag_data(reader)

    if not text:
        print(f"  Tag vuoto (nessun dato prodotto)")
        return

    print(f"\n  Dati raw: {text}")

    product = parse_product_data(text)
    if product:
        print(f"\n  ┌─────────────────────────────────┐")
        print(f"  │  PPG Code:  {product['ppg_code']:<20}│")
        print(f"  │  Batch:     {product['batch']:<20}│")
        print(f"  │  Prodotto:  {product['product_name']:<20}│")
        print(f"  │  Colore:    {product['color']:<20}│")
        print(f"  └─────────────────────────────────┘")
    else:
        print(f"  ⚠ Formato non riconosciuto (atteso: CODE/BATCH/NOME/COLORE)")


def cmd_loop(reader):
    """Continuous reading loop."""
    print("\n== LETTURA CONTINUA ==")
    print("  Avvicina i tag uno alla volta... (Ctrl+C per fermare)\n")

    last_tag = None
    while True:
        (status, _) = reader.MFRC522_Request(reader.PICC_REQIDL)
        if status == reader.MI_OK:
            (status, uid) = reader.MFRC522_Anticoll()
            if status == reader.MI_OK:
                tag_id = ":".join(f"{b:02X}" for b in uid if b != 0)

                if tag_id != last_tag:
                    reader.MFRC522_SelectTag(uid)
                    text = read_tag_data(reader)
                    product = parse_product_data(text) if text else None

                    if product:
                        print(f"  🏷  {tag_id}  →  {product['ppg_code']} | {product['product_name']} | {product['color']} | Batch: {product['batch']}")
                    elif text:
                        print(f"  🏷  {tag_id}  →  {text}")
                    else:
                        print(f"  🏷  {tag_id}  →  (vuoto)")

                    last_tag = tag_id
        else:
            last_tag = None  # Reset when tag removed

        time.sleep(0.2)


# ---------- Main ----------

if __name__ == "__main__":
    print("=" * 50)
    print("  SmartLocker NFC Tag Manager")
    print("=" * 50)

    reader = init_reader()

    if len(sys.argv) < 2:
        print("\nUso:")
        print("  python3 scripts/nfc_tag_manager.py write  - Scrivi dati prodotto")
        print("  python3 scripts/nfc_tag_manager.py read   - Leggi tag")
        print("  python3 scripts/nfc_tag_manager.py loop   - Lettura continua")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    try:
        if cmd == "write":
            cmd_write(reader)
        elif cmd == "read":
            cmd_read(reader)
        elif cmd == "loop":
            cmd_loop(reader)
        else:
            print(f"  Comando sconosciuto: {cmd}")
    except KeyboardInterrupt:
        print("\n\nFermato.")
    finally:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("Done!")
