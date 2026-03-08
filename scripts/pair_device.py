"""
Device Pairing Script — First Boot Setup

Run this script to pair the SmartLocker device with the cloud backend.
The admin must have generated a 6-digit pairing code in the cloud Admin UI.

Usage:
    python scripts/pair_device.py

What it does:
    1. Asks for the cloud URL (e.g., https://smartlocker-cloud-production.up.railway.app)
    2. Asks for the 6-digit pairing code
    3. Calls POST /api/devices/pair on the cloud
    4. Saves the API key and config locally
    5. Downloads product catalog and recipes
    6. Device is ready to sync!
"""

import sys
import os
import json
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from sync.cloud_client import CloudClient
from persistence.database import Database


def print_banner():
    print()
    print("=" * 60)
    print("    SmartLocker — Device Pairing Setup")
    print("=" * 60)
    print()
    print(f"  Device ID:  {settings.DEVICE_ID}")
    print(f"  Mode:       {settings.MODE.upper()}")
    print()


def print_success(pair_data: dict):
    print()
    print("=" * 60)
    print("    PAIRING SUCCESSFUL!")
    print("=" * 60)
    print()
    print(f"  Vessel:    {pair_data.get('vessel_name', 'N/A')}")
    print(f"  IMO:       {pair_data.get('vessel_imo', 'N/A')}")
    print(f"  Company:   {pair_data.get('company_name', 'N/A')}")
    print(f"  Fleet:     {pair_data.get('fleet_name', 'N/A')}")
    print()

    config = pair_data.get("config", {})
    products = config.get("products", [])
    recipes = config.get("recipes", [])

    print(f"  Products downloaded:  {len(products)}")
    print(f"  Recipes downloaded:   {len(recipes)}")
    print()
    print("  The device will now sync events to the cloud automatically.")
    print("  You can start using the SmartLocker system!")
    print()
    print("=" * 60)
    print()


def save_initial_config(db: Database, pair_data: dict):
    """Save the downloaded products and recipes to local database."""
    config = pair_data.get("config", {})

    # Save products
    for p in config.get("products", []):
        db.upsert_product({
            "product_id": p["id"],
            "ppg_code": p.get("ppg_code", ""),
            "name": p["name"],
            "product_type": p["product_type"],
            "density_g_per_ml": p.get("density_g_per_ml", 1.0),
            "pot_life_minutes": p.get("pot_life_minutes"),
            "hazard_class": p.get("hazard_class", ""),
            "can_sizes_ml": p.get("can_sizes_ml", []),
            "can_tare_weight_g": p.get("can_tare_weight_g", {}),
        })

    # Save recipes
    for r in config.get("recipes", []):
        db.upsert_recipe({
            "recipe_id": r["id"],
            "name": r["name"],
            "base_product_id": r["base_product_id"],
            "hardener_product_id": r["hardener_product_id"],
            "ratio_base": r["ratio_base"],
            "ratio_hardener": r["ratio_hardener"],
            "tolerance_pct": r.get("tolerance_pct", 5.0),
            "thinner_pct_brush": r.get("thinner_pct_brush", 5.0),
            "thinner_pct_roller": r.get("thinner_pct_roller", 5.0),
            "thinner_pct_spray": r.get("thinner_pct_spray", 10.0),
            "recommended_thinner_id": r.get("recommended_thinner_id"),
            "pot_life_minutes": r.get("pot_life_minutes", 480),
        })

    print(f"  Saved {len(config.get('products', []))} products and {len(config.get('recipes', []))} recipes to local DB")


def main():
    print_banner()

    # Check if already paired
    cloud = CloudClient()
    if cloud.is_paired:
        info = cloud.get_pairing_info()
        print(f"  This device is already paired!")
        print(f"  Cloud:   {info.get('cloud_url', 'N/A')}")
        print(f"  Vessel:  {info.get('vessel_name', 'N/A')}")
        print(f"  Company: {info.get('company_name', 'N/A')}")
        print()
        ans = input("  Do you want to re-pair? (y/N): ").strip().lower()
        if ans != "y":
            print("  Keeping current pairing. Bye!")
            return
        cloud.unpair()
        print("  Previous pairing removed.\n")

    # Cloud URL is fixed in settings
    cloud_url = settings.CLOUD_URL
    print(f"  Cloud: {cloud_url}")
    print()

    # Get pairing code
    print("  Enter the 6-digit pairing code from the admin panel")
    print("  (e.g., A3K7M2)")
    print()
    pairing_code = input("  Pairing Code: ").strip().upper()
    if not pairing_code or len(pairing_code) != 6:
        print("  Error: Code must be exactly 6 characters!")
        return

    # Attempt pairing
    print()
    print(f"  Connecting to {cloud_url}...")
    print(f"  Using code: {pairing_code}")
    print()

    success, data = cloud.pair_with_code(cloud_url, pairing_code)

    if success:
        # Initialize database and save config
        db = Database()
        db.connect()
        save_initial_config(db, data)
        db.close()

        print_success(data)
    else:
        print()
        print("  PAIRING FAILED!")
        print(f"  Error: {data.get('detail', 'Unknown error')}")
        print()
        print("  Please check:")
        print("  - Is the cloud URL correct?")
        print("  - Is the pairing code still valid (not expired/used)?")
        print("  - Does the device have internet access?")
        print()


if __name__ == "__main__":
    main()
