SmartLocker Nano Firmware v1.2 - Setup Guide
=============================================

HARDWARE WIRING
  Arduino Nano Pin -> Component
  --------------------------------
  D2  -> HX711 Shelf DT (data)
  D3  -> HX711 Shelf SCK (clock)
  D4  -> HX711 Mix DT (data)
  D5  -> HX711 Mix SCK (clock)
  D6  -> Bar graph segment 0 (green) via 220ohm
  D7  -> Bar graph segment 1 (green) via 220ohm
  D8  -> Bar graph segment 2 (green) via 220ohm
  D9  -> Bar graph segment 3 (yellow) via 220ohm
  D10 -> Bar graph segment 4 (yellow) via 220ohm
  D11 -> Bar graph segment 5 (yellow) via 220ohm
  D12 -> Bar graph segment 6 (red) via 220ohm
  D13 -> Bar graph segment 7 (red) via 220ohm
  A0  -> Piezo buzzer
  A1  -> (free)
  A2  -> Shelf LED slot 0 (red) via resistor
  A3  -> Shelf LED slot 1 (red) via resistor
  A4  -> Shelf LED slot 2 (red) via resistor
  A5  -> Shelf LED slot 3 (red) via resistor
  5V  -> HX711 VCC (both, joined)
  GND -> HX711 GND (both, joined) + bar common + LEDs GND + buzzer GND

FLASH FROM RPi (after git pull)
  Option A: arduino-cli (compile + flash)
    sudo apt install avrdude
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
    ./scripts/flash_arduino.sh

  Option B: pre-compiled .hex
    1. On Windows: Arduino IDE -> Sketch -> Export Compiled Binary
    2. Copy the .hex file to firmware/smartlocker_nano/smartlocker_nano.hex
    3. On RPi: ./scripts/flash_arduino.sh

TESTING (Serial Monitor 115200 baud)
  {"cmd":"ping"}              -> {"status":"ok","fw":"1.2"}
  {"cmd":"status"}            -> HX711 + LED + buzzer status
  {"cmd":"read","ch":"shelf"} -> weight reading
  {"cmd":"bar","pct":50}      -> bar graph 50%
  {"cmd":"slot","idx":0,"on":1}  -> shelf LED 0 on
  {"cmd":"buzz","pattern":"confirm"}  -> beep!
  {"cmd":"buzz","freq":1000,"dur":500} -> custom tone
  {"cmd":"led_off"}           -> everything off
