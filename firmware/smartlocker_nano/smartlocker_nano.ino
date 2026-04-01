/*
 * SmartLocker Nano Firmware v1.1
 * ==============================
 * Arduino Nano as bridge for:
 *   - 2x HX711 load cell amplifiers (shelf + mixing scale)
 *   - 1x KYX-B10BGYR-4 LED bar graph (10 segments: green/yellow/red)
 *   - 4x Red indicator LEDs (panel mount, one per shelf slot)
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
 *     {"cmd":"bar","pct":75}                // fill bar to 75%
 *     {"cmd":"bar","seg":7}                 // light first 7 segments
 *     {"cmd":"bar_off"}                     // bar all off
 *     {"cmd":"slot","idx":0,"on":1}         // shelf LED 0 on
 *     {"cmd":"slot","idx":2,"on":0}         // shelf LED 2 off
 *     {"cmd":"slot_all","on":0}             // all shelf LEDs off
 *     {"cmd":"led_off"}                     // everything off
 *     {"cmd":"cal","ch":"shelf","scale":9.81}
 *     {"cmd":"status"}
 *
 *   Arduino -> RPi (responses):
 *     {"status":"ok","fw":"1.1"}
 *     {"ch":"shelf","g":1234.5,"raw":8388607,"stable":true}
 *     {"ok":"bar","seg":7}
 *     {"ok":"slot","idx":0}
 *     {"err":"unknown command"}
 *
 * Hardware wiring:
 *   HX711 Shelf:  DT=D2, SCK=D3
 *   HX711 Mix:    DT=D4, SCK=D5
 *   Bar graph:    seg0=D6 .. seg7=D13, seg8=A0, seg9=A1
 *                 (each through 220ohm resistor)
 *   Shelf LEDs:   slot0=A2, slot1=A3, slot2=A4, slot3=A5
 *                 (each through appropriate resistor)
 *
 * Bar graph segment colors (KYX-B10BGYR-4):
 *   seg 0-3  = GREEN  (0-40%)
 *   seg 4-6  = YELLOW (40-70%)
 *   seg 7-9  = RED    (70-100%)
 *
 * Libraries required:
 *   - HX711 by Bogdan Necula (or Rob Tillaart)
 *   - ArduinoJson v7 by Benoit Blanchon
 */

#include <HX711.h>
#include <ArduinoJson.h>

// ============================================================
// PIN DEFINITIONS
// ============================================================

// HX711 load cells
#define SHELF_DT   2
#define SHELF_SCK  3
#define MIX_DT     4
#define MIX_SCK    5

// LED bar graph (10 segments) - KYX-B10BGYR-4
// Segment 0 = bottom (green), segment 9 = top (red)
const int BAR_PINS[10] = {6, 7, 8, 9, 10, 11, 12, 13, A0, A1};
#define NUM_BAR_SEGS 10

// Shelf indicator LEDs (red, panel mount)
const int SLOT_PINS[4] = {A2, A3, A4, A5};
#define NUM_SLOTS 4

// ============================================================
// HX711 CONFIGURATION
// ============================================================
#define SAMPLES_NORMAL    5
#define SAMPLES_TARE      15
#define STABILITY_WINDOW  3
#define STABILITY_THRESH  15.0  // grams

// ============================================================
// GLOBALS
// ============================================================
HX711 scaleShelf;
HX711 scaleMix;

// Calibration
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

// Bar graph current state
int barSegments = 0;  // how many segments are lit (0-10)

// HX711 lazy init flag
bool hx711_initialized = false;

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("{\"boot\":\"starting\"}");

    // Initialize bar graph pins
    for (int i = 0; i < NUM_BAR_SEGS; i++) {
        pinMode(BAR_PINS[i], OUTPUT);
        digitalWrite(BAR_PINS[i], LOW);
    }
    Serial.println("{\"boot\":\"bar_ok\"}");

    // Initialize shelf LED pins
    for (int i = 0; i < NUM_SLOTS; i++) {
        pinMode(SLOT_PINS[i], OUTPUT);
        digitalWrite(SLOT_PINS[i], LOW);
    }
    Serial.println("{\"boot\":\"slots_ok\"}");

    // Init stability history
    for (int i = 0; i < STABILITY_WINDOW; i++) {
        shelfHistory[i] = 0;
        mixHistory[i] = 0;
    }

    Serial.println("{\"boot\":\"ready\"}");
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
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
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, json);

    if (err) {
        Serial.println("{\"err\":\"json_parse\"}");
        return;
    }

    const char* cmd = doc["cmd"] | "";

    // ---- PING ----
    if (strcmp(cmd, "ping") == 0) {
        Serial.println("{\"status\":\"ok\",\"fw\":\"1.1\"}");
    }

    // ---- INIT HX711 (manual trigger) ----
    else if (strcmp(cmd, "init_hx") == 0) {
        initHX711();
    }

    // ---- READ WEIGHT ----
    else if (strcmp(cmd, "read") == 0) {
        if (!hx711_initialized) initHX711();
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
        if (!hx711_initialized) initHX711();
        const char* ch = doc["ch"] | "";
        bool ok = false;
        if (strcmp(ch, "shelf") == 0 || strcmp(ch, "shelf1") == 0 || strcmp(ch, "all") == 0) {
            if (scaleShelf.wait_ready_timeout(1000)) {
                shelfOffset = scaleShelf.read_average(SAMPLES_TARE);
                ok = true;
            }
        }
        if (strcmp(ch, "mix") == 0 || strcmp(ch, "mixing_scale") == 0 || strcmp(ch, "all") == 0) {
            if (scaleMix.wait_ready_timeout(1000)) {
                mixOffset = scaleMix.read_average(SAMPLES_TARE);
                ok = true;
            }
        }
        if (ok) {
            char resp[64];
            snprintf(resp, sizeof(resp), "{\"ok\":\"tare\",\"ch\":\"%s\"}", ch);
            Serial.println(resp);
        } else {
            Serial.println("{\"err\":\"tare_failed\"}");
        }
    }

    // ---- BAR GRAPH (percentage or segment count) ----
    else if (strcmp(cmd, "bar") == 0) {
        int seg = -1;

        if (doc.containsKey("pct")) {
            int pct = doc["pct"] | 0;
            if (pct < 0) pct = 0;
            if (pct > 100) pct = 100;
            seg = (pct * NUM_BAR_SEGS + 50) / 100;  // round
        }
        else if (doc.containsKey("seg")) {
            seg = doc["seg"] | 0;
        }

        if (seg >= 0 && seg <= NUM_BAR_SEGS) {
            setBar(seg);
            char resp[48];
            snprintf(resp, sizeof(resp), "{\"ok\":\"bar\",\"seg\":%d}", seg);
            Serial.println(resp);
        } else {
            Serial.println("{\"err\":\"bar_range\"}");
        }
    }

    // ---- BAR OFF ----
    else if (strcmp(cmd, "bar_off") == 0) {
        setBar(0);
        Serial.println("{\"ok\":\"bar_off\"}");
    }

    // ---- SINGLE SHELF LED ----
    else if (strcmp(cmd, "slot") == 0) {
        int idx = doc["idx"] | -1;
        int on = doc["on"] | 0;
        if (idx >= 0 && idx < NUM_SLOTS) {
            digitalWrite(SLOT_PINS[idx], on ? HIGH : LOW);
            char resp[48];
            snprintf(resp, sizeof(resp), "{\"ok\":\"slot\",\"idx\":%d,\"on\":%d}", idx, on);
            Serial.println(resp);
        } else {
            Serial.println("{\"err\":\"slot_idx\"}");
        }
    }

    // ---- ALL SHELF LEDs ----
    else if (strcmp(cmd, "slot_all") == 0) {
        int on = doc["on"] | 0;
        for (int i = 0; i < NUM_SLOTS; i++) {
            digitalWrite(SLOT_PINS[i], on ? HIGH : LOW);
        }
        char resp[48];
        snprintf(resp, sizeof(resp), "{\"ok\":\"slot_all\",\"on\":%d}", on);
        Serial.println(resp);
    }

    // ---- EVERYTHING OFF ----
    else if (strcmp(cmd, "led_off") == 0) {
        setBar(0);
        for (int i = 0; i < NUM_SLOTS; i++) {
            digitalWrite(SLOT_PINS[i], LOW);
        }
        Serial.println("{\"ok\":\"led_off\"}");
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
            "{\"status\":\"ok\",\"shelf_ok\":%s,\"mix_ok\":%s,\"bar\":%d,\"slots\":%d,\"fw\":\"1.1\"}",
            shelf_ok ? "true" : "false",
            mix_ok ? "true" : "false",
            NUM_BAR_SEGS, NUM_SLOTS);
        Serial.println(resp);
    }

    // ---- UNKNOWN ----
    else {
        Serial.println("{\"err\":\"unknown command\"}");
    }
}

// ============================================================
// HX711 LAZY INIT
// ============================================================
void initHX711() {
    if (hx711_initialized) return;

    Serial.println("{\"info\":\"hx711_init_start\"}");

    scaleShelf.begin(SHELF_DT, SHELF_SCK);
    scaleMix.begin(MIX_DT, MIX_SCK);

    // Tare if ready (with timeout)
    if (scaleShelf.wait_ready_timeout(2000)) {
        shelfOffset = scaleShelf.read_average(SAMPLES_TARE);
        Serial.println("{\"info\":\"shelf_tared\"}");
    }
    if (scaleMix.wait_ready_timeout(2000)) {
        mixOffset = scaleMix.read_average(SAMPLES_TARE);
        Serial.println("{\"info\":\"mix_tared\"}");
    }

    hx711_initialized = true;
    Serial.println("{\"info\":\"hx711_init_done\"}");
}

// ============================================================
// BAR GRAPH HELPER
// ============================================================
void setBar(int segments) {
    if (segments < 0) segments = 0;
    if (segments > NUM_BAR_SEGS) segments = NUM_BAR_SEGS;

    barSegments = segments;
    for (int i = 0; i < NUM_BAR_SEGS; i++) {
        digitalWrite(BAR_PINS[i], (i < segments) ? HIGH : LOW);
    }
}

// ============================================================
// READ HX711 AND SEND JSON RESPONSE
// ============================================================
void readAndSend(HX711* scale, const char* chName,
                 float calScale, long calOffset,
                 float* history, int* histIdx, bool* stable) {

    if (!scale->wait_ready_timeout(500)) {
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
    char gramsStr[16];
    dtostrf(grams, 1, 1, gramsStr);

    char resp[128];
    snprintf(resp, sizeof(resp),
        "{\"ch\":\"%s\",\"g\":%s,\"raw\":%ld,\"stable\":%s}",
        chName, gramsStr, raw, *stable ? "true" : "false");
    Serial.println(resp);
}
