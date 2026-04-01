SmartLocker Nano Firmware - Setup Guide
=======================================

HARDWARE WIRING
  Arduino Nano Pin -> Component
  --------------------------------
  D2  -> HX711 Shelf DT (data)
  D3  -> HX711 Shelf SCK (clock)
  D4  -> HX711 Mix DT (data)
  D5  -> HX711 Mix SCK (clock)
  D6  -> WS2812B DIN (data in)
  5V  -> HX711 VCC (both)
  GND -> HX711 GND (both) + WS2812B GND

  WS2812B POWER: Use external 5V supply for LEDs (NOT Arduino 5V).
  Connect GND of external supply to Arduino GND (common ground).

  LED CHAIN ORDER:
    LED 0-3  = Shelf slot indicators (under cans)
    LED 4-11 = Balance bar (weight progress during mixing)
  Total: 12 LEDs default (adjust NUM_SLOT_LEDS / NUM_BAR_LEDS in .ino)

REQUIRED ARDUINO LIBRARIES (install via Library Manager)
  1. HX711 by Bogdan Necula (or Rob Tillaart)
  2. Adafruit NeoPixel
  3. ArduinoJson v7

UPLOAD STEPS
  1. Open smartlocker_nano/smartlocker_nano.ino in Arduino IDE
  2. Board: Arduino Nano
  3. Processor: ATmega328P (Old Bootloader) -- try both if upload fails
  4. Port: COMx (Windows) or /dev/ttyUSBx (Linux)
  5. Upload

RPi CONFIGURATION
  In smartlocker-edge/config/settings.py change:
    WEIGHT_MODE = "arduino_serial"    # was "hx711_direct"
    DRIVER_LED = "real"               # was "fake"

  The serial port auto-detects (looks for CH340/FTDI), but you can
  also set WEIGHT_SERIAL_PORT = "/dev/ttyUSB0" explicitly.

TESTING
  After upload, open Serial Monitor at 115200 baud and type:
    {"cmd":"ping"}           -> should reply {"status":"ok","fw":"1.0"}
    {"cmd":"status"}         -> shows HX711 + LED status
    {"cmd":"read","ch":"shelf"} -> shelf weight reading
    {"cmd":"read","ch":"mix"}   -> mixing scale reading
    {"cmd":"tare","ch":"all"}   -> zero both scales
    {"cmd":"led","idx":0,"r":0,"g":255,"b":0}  -> LED 0 green
    {"cmd":"led_bar","pct":50,"r":255,"g":200,"b":0}  -> bar 50% yellow
    {"cmd":"led_off"}        -> all LEDs off
