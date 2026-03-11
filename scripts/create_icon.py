"""Generate a simple SmartLocker icon (128x128 PNG)."""
try:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Teal rounded rectangle background
    draw.rounded_rectangle([4, 4, 124, 124], radius=20, fill=(0, 209, 186, 255))
    # White "SL" text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except Exception:
        font = ImageFont.load_default()
    draw.text((64, 64), "SL", fill=(255, 255, 255, 255), font=font, anchor="mm")
    img.save("/home/jacopo22295/smartlocker-edge/scripts/smartlocker-icon.png")
    print("Icon created!")
except ImportError:
    # Fallback: create a minimal 1-color PPM and convert
    print("Pillow not installed. Using fallback icon.")
    import struct
    # Simple 16x16 teal square as PNG-like PPM
    with open("/home/jacopo22295/smartlocker-edge/scripts/smartlocker-icon.ppm", "wb") as f:
        f.write(b"P6\n128 128\n255\n")
        for _ in range(128 * 128):
            f.write(struct.pack('BBB', 0, 209, 186))
    print("Fallback icon created (smartlocker-icon.ppm)")
