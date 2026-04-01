/*
 * SmartLocker Nano Firmware v1.0
 * ==============================
 * Arduino Nano as bridge for:
 *   - 2x HX711 load cell amplifiers (shelf + mixing scale)
 *   - WS2812B addressable LEDs (slot indicators + balance bar)
 *
 * Serial protocol (115200 baud, JSON lines):
 *
 *   RPi -> Arduino (commands):
 *     {"cmd":"ping"}
 *     {"cmd":"read","ch":"shelf"}
 *     {"cmd":"read","ch":"mix"}
 *     {"cmd":"tare","ch":"shelf"}
 *     {"cmd":"tare","ch":"mix"}
 *     {"cmd":"tare","ch":"all"}
 *     {"cmd":"led","idx":0,"r":0,"g":255,"b":0}        // single LED
 *     {"cmd":"led_range","from":0,"to":4,"r":255,"g":0,"b":0}  // range
 *     {"cmd":"led_off"}                                  // all off
 *     {"cmd":"led_bar","pct":75,"r":0,"g":255,"b":0}   // balance bar fill %
 *     {"cmd":"cal","ch":"shelf","scale":9.81}           // set calibration
 *     {"cmd":"status"}                                   // health check
 *
 *   Arduino -> RPi (responses):
 *     {"status":"ok","fw":"1.0"}                         // ping response
 *     {"ch":"shelf","g":1234.5,"raw":8388607,"stable":true}
 *     {"ch":"mix","g":567.8,"raw":4194303,"stable":false}
 *     {"ok":"tare","ch":"shelf"}
 *     {"ok":"led"}
 *     {"ok":"cal","ch":"shelf","scale":9.81}
 *     {"err":"unknown command"}
 *     {"status":"ok","shelf_ok":true,"mix_ok":true,"leds":16}
 *
 * Hardware wiring:
 *   HX711 Shelf:  DT=D2, SCK=D3
 *   HX711 Mix:    DT=D4, SCK=D5
 *   WS2812B:      DIN=D6
 *
 * Libraries required (install via Arduino IDE Library Manager):
 *   - HX711 by Bogdan Necula (or Rob Tillaart)
 *   - Adafruit NeoPixel
 *   - ArduinoJson v6 by Benoit Blanchon (6.x works, 7.x also works)
 */

#include <HX711.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

// ============================================================
// PIN DEFINITIONS
// ============================================================
#define SHELF_DT   2
#define SHELF_SCK  3
#define MIX_DT     4
#define MIX_SCK    5
#define LED_PIN    6

// ============================================================
// LED CONFIGURATION
// ============================================================
// Total LEDs = slot LEDs + balance bar LEDs
// Adjust these for your physical setup
#define NUM_SLOT_LEDS    4    // 1 per shelf slot (under cans)
#define NUM_BAR_LEDS     8    // balance indicator bar
#define NUM_LEDS_TOTAL   (NUM_SLOT_LEDS + NUM_BAR_LEDS)

// Balance bar starts after slot LEDs in the chain
#define BAR_START_IDX    NUM_SLOT_LEDS

// ============================================================
// HX711 CONFIGURATION
// ============================================================
#define SAMPLES_NORMAL    5     // readings to average for normal read
#define SAMPLES_TARE      15    // readings to average for tare
#define STABILITY_WINDOW  3     // consecutive reads within threshold = stable
#define STABILITY_THRESH  15.0  // grams — stable if spread < this

// ============================================================
// GLOBALS
// ============================================================
HX711 scaleShelf;
HX711 scaleMix;
Adafruit_NeoPixel leds(NUM_LEDS_TOTAL, LED_PIN, NEO_GRB + NEO_KHZ800);

// Calibration (defaults — overridden by "cal" command or tare)
float shelfScale  = 9.81;
float mixScale    = 20.69;
long  shelfOffset = 0;
long  mixOffset   = 0;

// Stability tracking
float shelfHistory[STABILITY_WINDOW];
float mixHistory[STABILITY_WINDOW];
int   shelfHistIdx = 0;
int   mixHistIdx   = 0;
bool  shelfStable  = false;
bool  mixStable    = false;

// Serial buffer
char serialBuf[256];
int  serialPos = 0;

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    while (!Serial) { ; }  // Wait for serial (Nano: instant)

    // Initialize HX711 channels
    scaleShelf.begin(SHELF_DT, SHELF_SCK);
    scaleMix.begin(MIX_DT, MIX_SCK);

    // Set gain to 128 (channel A) — default
    scaleShelf.set_gain(128);
    scaleMix.set_gain(128);

    // Auto-tare on startup
    if (scaleShelf.is_ready()) {
        shelfOffset = scaleShelf.read_average(SAMPLES_TARE);
    }
    if (scaleMix.is_ready()) {
        mixOffset = scaleMix.read_average(SAMPLES_TARE);
    }

    // Initialize LED strip
    leds.begin();
    leds.setBrightness(50);  // 0-255, start conservative
    leds.clear();
    leds.show();

    // Startup animation: quick green sweep
    for (int i = 0; i < NUM_LEDS_TOTAL; i++) {
        leds.setPixelColor(i, leds.Color(0, 80, 0));
        leds.show();
        delay(50);
    }
    delay(200);
    leds.clear();
    leds.show();

    // Init stability history
    for (int i = 0; i < STABILITY_WINDOW; i++) {
        shelfHistory[i] = 0;
        mixHistory[i] = 0;
    }
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
    // Read serial commands (non-blocking)
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (serialPos > 0) {
                serialBuf[serialPos] = '\0';
                processCommand(serialBuf);
                serialPos = 0;
            }
        } else if (serialPos < (int)sizeof(serialBuf) - 1) {
            serialBuf[serialPos++] = c;
        }
    }
}

// ============================================================
// COMMAND PROCESSOR
// ============================================================
void processCommand(const char* json) {
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, json);

    if (err) {
        Serial.println("{\"err\":\"json_parse\"}");
        return;
    }

    const char* cmd = doc["cmd"] | "";

    // ---- PING ----
    if (strcmp(cmd, "ping") == 0) {
        Serial.println("{\"status\":\"ok\",\"fw\":\"1.0\"}");
    }

    // ---- READ WEIGHT ----
    else if (strcmp(cmd, "read") == 0) {
        const char* ch = doc["ch"] | "";
        if (strcmp(ch, "shelf") == 0 || strcmp(ch, "shelf1") == 0) {
            readAndSend(&scaleShelf, "shelf", shelfScale, shelfOffset,
                        shelfHistory, &shelfHistIdx, &shelfStable);
        }
        else if (strcmp(ch, "mix") == 0 || strcmp(ch, "mixing_scale") == 0) {
            readAndSend(&scaleMix, "mix", mixScale, mixOffset,
                        mixHistory, &mixHistIdx, &mixStable);
        }
        else {
            Serial.println("{\"err\":\"unknown channel\"}");
        }
    }

    // ---- TARE ----
    else if (strcmp(cmd, "tare") == 0) {
        const char* ch = doc["ch"] | "";
        bool ok = false;
        if (strcmp(ch, "shelf") == 0 || strcmp(ch, "shelf1") == 0 || strcmp(ch, "all") == 0) {
            if (scaleShelf.is_ready()) {
                shelfOffset = scaleShelf.read_average(SAMPLES_TARE);
                ok = true;
            }
        }
        if (strcmp(ch, "mix") == 0 || strcmp(ch, "mixing_scale") == 0 || strcmp(ch, "all") == 0) {
            if (scaleMix.is_ready()) {
                mixOffset = scaleMix.read_average(SAMPLES_TARE);
                ok = true;
            }
        }
        if (ok) {
            // Build response
            char resp[64];
            snprintf(resp, sizeof(resp), "{\"ok\":\"tare\",\"ch\":\"%s\"}", ch);
            Serial.println(resp);
        } else {
            Serial.println("{\"err\":\"tare_failed\"}");
        }
    }

    // ---- SINGLE LED ----
    else if (strcmp(cmd, "led") == 0) {
        int idx = doc["idx"] | -1;
        int r = doc["r"] | 0;
        int g = doc["g"] | 0;
        int b = doc["b"] | 0;
        if (idx >= 0 && idx < NUM_LEDS_TOTAL) {
            leds.setPixelColor(idx, leds.Color(r, g, b));
            leds.show();
            Serial.println("{\"ok\":\"led\"}");
        } else {
            Serial.println("{\"err\":\"led_idx\"}");
        }
    }

    // ---- LED RANGE ----
    else if (strcmp(cmd, "led_range") == 0) {
        int from = doc["from"] | 0;
        int to = doc["to"] | 0;
        int r = doc["r"] | 0;
        int g = doc["g"] | 0;
        int b = doc["b"] | 0;
        if (from >= 0 && to <= NUM_LEDS_TOTAL && from <= to) {
            for (int i = from; i < to; i++) {
                leds.setPixelColor(i, leds.Color(r, g, b));
            }
            leds.show();
            Serial.println("{\"ok\":\"led_range\"}");
        } else {
            Serial.println("{\"err\":\"led_range\"}");
        }
    }

    // ---- LED ALL OFF ----
    else if (strcmp(cmd, "led_off") == 0) {
        leds.clear();
        leds.show();
        Serial.println("{\"ok\":\"led_off\"}");
    }

    // ---- BALANCE BAR (fill percentage) ----
    else if (strcmp(cmd, "led_bar") == 0) {
        int pct = doc["pct"] | 0;
        int r = doc["r"] | 0;
        int g = doc["g"] | 0;
        int b = doc["b"] | 0;

        // Fill balance bar LEDs based on percentage
        int fillCount = (pct * NUM_BAR_LEDS + 50) / 100;  // round
        if (fillCount > NUM_BAR_LEDS) fillCount = NUM_BAR_LEDS;
        if (fillCount < 0) fillCount = 0;

        for (int i = 0; i < NUM_BAR_LEDS; i++) {
            int ledIdx = BAR_START_IDX + i;
            if (i < fillCount) {
                leds.setPixelColor(ledIdx, leds.Color(r, g, b));
            } else {
                leds.setPixelColor(ledIdx, 0);
            }
        }
        leds.show();
        Serial.println("{\"ok\":\"led_bar\"}");
    }

    // ---- SET CALIBRATION ----
    else if (strcmp(cmd, "cal") == 0) {
        const char* ch = doc["ch"] | "";
        float scale = doc["scale"] | 0.0f;
        if (scale > 0.001) {
            if (strcmp(ch, "shelf") == 0 || strcmp(ch, "shelf1") == 0) {
                shelfScale = scale;
            } else if (strcmp(ch, "mix") == 0 || strcmp(ch, "mixing_scale") == 0) {
                mixScale = scale;
            }
            char resp[80];
            snprintf(resp, sizeof(resp), "{\"ok\":\"cal\",\"ch\":\"%s\",\"scale\":%.4f}", ch, (double)scale);
            Serial.println(resp);
        } else {
            Serial.println("{\"err\":\"invalid scale\"}");
        }
    }

    // ---- STATUS ----
    else if (strcmp(cmd, "status") == 0) {
        bool shelf_ok = scaleShelf.is_ready();
        bool mix_ok = scaleMix.is_ready();
        char resp[128];
        snprintf(resp, sizeof(resp),
            "{\"status\":\"ok\",\"shelf_ok\":%s,\"mix_ok\":%s,\"leds\":%d,\"fw\":\"1.0\"}",
            shelf_ok ? "true" : "false",
            mix_ok ? "true" : "false",
            NUM_LEDS_TOTAL);
        Serial.println(resp);
    }

    // ---- LED BRIGHTNESS ----
    else if (strcmp(cmd, "led_bright") == 0) {
        int val = doc["val"] | -1;
        if (val >= 0 && val <= 255) {
            leds.setBrightness(val);
            leds.show();
            Serial.println("{\"ok\":\"led_bright\"}");
        } else {
            Serial.println("{\"err\":\"brightness 0-255\"}");
        }
    }

    // ---- UNKNOWN ----
    else {
        Serial.println("{\"err\":\"unknown command\"}");
    }
}

// ============================================================
// READ HX711 AND SEND JSON RESPONSE
// ============================================================
void readAndSend(HX711* scale, const char* chName,
                 float calScale, long calOffset,
                 float* history, int* histIdx, bool* stable) {

    if (!scale->is_ready()) {
        char resp[64];
        snprintf(resp, sizeof(resp), "{\"ch\":\"%s\",\"err\":\"not_ready\"}", chName);
        Serial.println(resp);
        return;
    }

    // Read averaged raw value
    long raw = scale->read_average(SAMPLES_NORMAL);

    // Convert to grams (inverted: heavier = lower raw value)
    float grams = (float)(calOffset - raw) / calScale;
    if (grams < 0) grams = 0;

    // Update stability tracking
    history[*histIdx] = grams;
    *histIdx = (*histIdx + 1) % STABILITY_WINDOW;

    float minVal = history[0], maxVal = history[0];
    for (int i = 1; i < STABILITY_WINDOW; i++) {
        if (history[i] < minVal) minVal = history[i];
        if (history[i] > maxVal) maxVal = history[i];
    }
    *stable = (maxVal - minVal) < STABILITY_THRESH;

    // Send JSON response
    // Using dtostrf for float formatting on AVR
    char gramsStr[16];
    dtostrf(grams, 1, 1, gramsStr);

    char resp[128];
    snprintf(resp, sizeof(resp),
        "{\"ch\":\"%s\",\"g\":%s,\"raw\":%ld,\"stable\":%s}",
        chName, gramsStr, raw, *stable ? "true" : "false");
    Serial.println(resp);
}
