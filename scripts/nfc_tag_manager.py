#!/usr/bin/env python3
"""
NFC Tag Manager - Write and Read product data on NTAG215 tags via RC522.

Data format stored on tag:
  PPG_CODE/BATCH/PRODUCT_NAME/COLOR
  Example: 616826/80008800/SIGMAPRIME-200/YELLOWGREEN

NTAG215 memory: 504 bytes user data (pages 4-129, 4 bytes per page).
Each read returns 16 bytes (4 pages at once).

Usage:
  python3 scripts/nfc_tag_manager.py write
  python3 scripts/nfc_tag_manager.py read
  python3 scripts/nfc_tag_manager.py loop   (continuous reading)
"""

import sys
import time

USER_PAGE_START = 4
USER_PAGE_END = 129
MAX_USER_BYTES = (USER_PAGE_END - USER_PAGE_START + 1) * 4  # 504 bytes


def init_reader():
    """Initialize RC522 and return the low-level MFRC522 reader."""
    try:
        from mfrc522 import SimpleMFRC522
        simple = SimpleMFRC522()
        return simple, simple.READER
    except Exception as e:
        print(f"  ERRORE inizializzazione RC522: {e}")
        sys.exit(1)


def wait_for_tag(rdr):
    """Wait for a tag, select it, return UID. Blocks until found."""
    while True:
        (status, _) = rdr.MFRC522_Request(rdr.PICC_REQIDL)
        if status == rdr.MI_OK:
            (status, uid) = rdr.MFRC522_Anticoll()
            if status == rdr.MI_OK:
                rdr.MFRC522_SelectTag(uid)
                rdr.MFRC522_StopCrypto1()
                tag_id = ":".join(f"{b:02X}" for b in uid if b != 0)
                return uid, tag_id
        time.sleep(0.1)


def ntag_read_page(rdr, page):
    """
    Read 16 bytes (4 pages) starting from `page` on NTAG215.
    Uses manual CRC calculation + disabled RX CRC.
    """
    # Disable CRC on RX
    rdr.Write_MFRC522(0x13, 0x00)

    # Calculate CRC_A for the READ command
    data_to_send = [0x30, page]
    rdr.Write_MFRC522(0x01, 0x00)  # Idle
    rdr.Write_MFRC522(0x05, 0x04)  # DivIrqReg clear
    rdr.Write_MFRC522(0x0A, 0x80)  # Flush FIFO
    for b in data_to_send:
        rdr.Write_MFRC522(0x09, b)  # Write to FIFO
    rdr.Write_MFRC522(0x01, 0x03)  # CalcCRC command

    time.sleep(0.05)

    crc_lo = rdr.Read_MFRC522(0x22)
    crc_hi = rdr.Read_MFRC522(0x21)

    buf = [0x30, page, crc_lo, crc_hi]
    (status, recv, bits) = rdr.MFRC522_ToCard(rdr.PCD_TRANSCEIVE, buf)

    if status == rdr.MI_OK and recv and len(recv) >= 16:
        return recv[:16]
    return None


def ntag_write_page(rdr, page, data_4bytes):
    """Write 4 bytes to a single NTAG215 page."""
    if len(data_4bytes) != 4:
        raise ValueError("Ogni pagina NTAG = 4 bytes esatti")

    # Disable CRC on RX
    rdr.Write_MFRC522(0x13, 0x00)

    # Calculate CRC_A for WRITE command
    data_to_send = [0xA2, page] + list(data_4bytes)
    rdr.Write_MFRC522(0x01, 0x00)
    rdr.Write_MFRC522(0x05, 0x04)
    rdr.Write_MFRC522(0x0A, 0x80)
    for b in data_to_send:
        rdr.Write_MFRC522(0x09, b)
    rdr.Write_MFRC522(0x01, 0x03)

    time.sleep(0.05)

    crc_lo = rdr.Read_MFRC522(0x22)
    crc_hi = rdr.Read_MFRC522(0x21)

    buf = [0xA2, page] + list(data_4bytes) + [crc_lo, crc_hi]
    (status, recv, bits) = rdr.MFRC522_ToCard(rdr.PCD_TRANSCEIVE, buf)
    return status == 0 or (recv and len(recv) > 0)  # NTAG ACK = 4 bits


def read_tag_text(rdr):
    """Read raw text from NTAG215 user pages. Returns decoded string."""
    raw = bytearray()

    # Read 4 pages at a time (16 bytes per read)
    for page in range(USER_PAGE_START, USER_PAGE_START + 32, 4):
        data = ntag_read_page(rdr, page)
        if data is None:
            break
        raw.extend(data)
        # Stop if null terminator found
        if 0x00 in data:
            break

    # Decode — skip any NDEF header bytes, find our data after "en"
    try:
        text = raw.decode('latin-1')
        # Look for our format: PPG_CODE/BATCH/NAME/COLOR
        # NDEF text record has prefix bytes + "en" language code
        # Find first digit or slash pattern
        for i, ch in enumerate(text):
            # Find start of our data (first alphanumeric after NDEF header)
            remaining = text[i:]
            if '/' in remaining:
                parts = remaining.split('\x00')[0]  # Until null
                # Validate it looks like our format
                segments = parts.split('/')
                if len(segments) >= 4 and len(segments[0]) > 0:
                    return parts
        # Fallback: strip non-printable and try
        clean = ''.join(c for c in text if c.isprintable())
        if '/' in clean:
            for i in range(len(clean)):
                remaining = clean[i:]
                segments = remaining.split('/')
                if len(segments) >= 4:
                    return remaining.split('\x00')[0]
    except Exception:
        pass

    return ""


def write_tag_text(rdr, text):
    """Write plain text to NTAG215 pages (no NDEF, raw UTF-8 + null terminator)."""
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
        ok = ntag_write_page(rdr, page, chunk)
        if not ok:
            print(f"\n  ERRORE scrittura pagina {page}")
            return False
        sys.stdout.write(f"\r  Scrittura: {i + 1}/{pages_needed} pagine")
        sys.stdout.flush()
        time.sleep(0.02)

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
    """Format product data string."""
    return f"{ppg_code}/{batch}/{product_name}/{color}"


# ---------- Commands ----------

def cmd_write(rdr):
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

    uid, tag_id = wait_for_tag(rdr)
    print(f"  Tag trovato: {tag_id}")

    ok = write_tag_text(rdr, tag_data)
    if ok:
        print(f"\n  TAG SCRITTO CON SUCCESSO")
        print(f"     UID:     {tag_id}")
        print(f"     Dati:    {tag_data}")
    else:
        print(f"\n  ERRORE SCRITTURA")


def cmd_read(rdr):
    """Read and display product data from tag."""
    print("\n== LEGGI TAG PRODOTTO ==\n")
    print("  Avvicina il tag al lettore...")

    uid, tag_id = wait_for_tag(rdr)
    print(f"  Tag trovato: {tag_id}")

    text = read_tag_text(rdr)

    if not text:
        print(f"  Tag vuoto (nessun dato prodotto)")
        return

    print(f"\n  Dati raw: {text}")

    product = parse_product_data(text)
    if product:
        print(f"\n  +-----------------------------------+")
        print(f"  |  PPG Code:  {product['ppg_code']:<22}|")
        print(f"  |  Batch:     {product['batch']:<22}|")
        print(f"  |  Prodotto:  {product['product_name']:<22}|")
        print(f"  |  Colore:    {product['color']:<22}|")
        print(f"  +-----------------------------------+")
    else:
        print(f"  Formato non riconosciuto (atteso: CODE/BATCH/NOME/COLORE)")


def cmd_loop(rdr):
    """Continuous reading loop."""
    print("\n== LETTURA CONTINUA ==")
    print("  Avvicina i tag uno alla volta... (Ctrl+C per fermare)\n")

    last_tag = None
    while True:
        (status, _) = rdr.MFRC522_Request(rdr.PICC_REQIDL)
        if status == rdr.MI_OK:
            (status, uid) = rdr.MFRC522_Anticoll()
            if status == rdr.MI_OK:
                tag_id = ":".join(f"{b:02X}" for b in uid if b != 0)

                if tag_id != last_tag:
                    rdr.MFRC522_SelectTag(uid)
                    rdr.MFRC522_StopCrypto1()
                    text = read_tag_text(rdr)
                    product = parse_product_data(text) if text else None

                    if product:
                        print(f"  {tag_id}  ->  {product['ppg_code']} | {product['product_name']} | {product['color']} | Batch: {product['batch']}")
                    elif text:
                        print(f"  {tag_id}  ->  {text}")
                    else:
                        print(f"  {tag_id}  ->  (vuoto)")

                    last_tag = tag_id
        else:
            last_tag = None

        time.sleep(0.2)


# ---------- Main ----------

if __name__ == "__main__":
    print("=" * 50)
    print("  SmartLocker NFC Tag Manager")
    print("=" * 50)

    simple, rdr = init_reader()

    if len(sys.argv) < 2:
        print("\nUso:")
        print("  python3 scripts/nfc_tag_manager.py write  - Scrivi dati prodotto")
        print("  python3 scripts/nfc_tag_manager.py read   - Leggi tag")
        print("  python3 scripts/nfc_tag_manager.py loop   - Lettura continua")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    try:
        if cmd == "write":
            cmd_write(rdr)
        elif cmd == "read":
            cmd_read(rdr)
        elif cmd == "loop":
            cmd_loop(rdr)
        else:
            print(f"  Comando sconosciuto: {cmd}")
    except KeyboardInterrupt:
        print("\n\nFermato.")
    finally:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("Done!")
