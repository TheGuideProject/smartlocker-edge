/*
 * SmartLocker Nano Firmware v1.2
 * ==============================
 * Arduino Nano as bridge for:
 *   - 2x HX711 load cell amplifiers (shelf + mixing scale)
 *   - 1x KYX-B10BGYR LED bar graph (8 segments used)
 *   - 4x Red indicator LEDs (panel mount, one per shelf slot)
 *   - 1x Piezo buzzer (confirmation beeps, warnings)
 *
 * Pin allocation:
 *   D0,D1  = Serial USB (reserved)
 *   D2,D3  = HX711 Shelf (DT, SCK)
 *   D4,D5  = HX711 Mix (DT, SCK)
 *   D6-D13 = Bar graph segments 0-7 (through 220ohm resistors)
 *   A0     = Piezo buzzer
 *   A1     = (free for future use)
 *   A2-A5  = Shelf slot LEDs (through resistors)
 *
 * Serial protocol (115200 baud, JSON lines):
 *
 *   RPi -> Arduino:
 *     {"cmd":"ping"}
 *     {"cmd":"read","ch":"shelf"}
 *     {"cmd":"read","ch":"mix"}
 *     {"cmd":"tare","ch":"shelf"}
 *     {"cmd":"tare","ch":"mix"}
 *     {"cmd":"tare","ch":"all"}
 *     {"cmd":"bar","pct":75}
 *     {"cmd":"bar","seg":6}
 *     {"cmd":"bar_off"}
 *     {"cmd":"slot","idx":0,"on":1}
 *     {"cmd":"slot_all","on":0}
 *     {"cmd":"led_off"}
 *     {"cmd":"buzz","pattern":"confirm"}
 *     {"cmd":"buzz","freq":1000,"dur":200}
 *     {"cmd":"buzz_off"}
 *     {"cmd":"cal","ch":"shelf","scale":9.81}
 *     {"cmd":"status"}
 *
 *   Arduino -> RPi:
 *     {"status":"ok","fw":"1.2"}
 *     {"ch":"shelf","g":1234.5,"raw":8388607,"stable":true}
 *     {"ok":"bar","seg":6}
 *     {"ok":"buzz","pattern":"confirm"}
 *     {"err":"unknown command"}
 *
 * Libraries required:
 *   - HX711 by Bogdan Necula
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

// LED bar graph (8 segments used of KYX-B10BGYR)
const int BAR_PINS[8] = {6, 7, 8, 9, 10, 11, 12, 13};
#define NUM_BAR_SEGS 8

// Buzzer
#define BUZZER_PIN A0

// Shelf indicator LEDs
const int SLOT_PINS[4] = {A2, A3, A4, A5};
#define NUM_SLOTS 4

// ============================================================
// HX711 CONFIGURATION
// ============================================================
#define SAMPLES_NORMAL    5
#define SAMPLES_TARE      15
#define STABILITY_WINDOW  3
#define STABILITY_THRESH  15.0

// ============================================================
// GLOBALS
// ============================================================
HX711 scaleShelf;
HX711 scaleMix;

float shelfScale  = 9.81;
float mixScale    = 20.69;
long  shelfOffset = 0;
long  mixOffset   = 0;

float shelfHistory[STABILITY_WINDOW];
float mixHistory[STABILITY_WINDOW];
int   shelfHistIdx = 0;
int   mixHistIdx   = 0;
bool  shelfStable  = false;
bool  mixStable    = false;

char serialBuf[128];
int  serialPos = 0;

int barSegments = 0;

bool hx711_initialized = false;

// Buzzer async state
unsigned long buzzEndTime = 0;
bool buzzing = false;

// ============================================================
// BUZZER PATTERNS
// ============================================================
void buzzConfirm() {
    tone(BUZZER_PIN, 1800, 80);
    delay(100);
    tone(BUZZER_PIN, 2400, 80);
}

void buzzWarning() {
    tone(BUZZER_PIN, 1200, 150);
    delay(200);
    tone(BUZZER_PIN, 1200, 150);
}

void buzzError() {
    tone(BUZZER_PIN, 400, 500);
}

void buzzTick() {
    tone(BUZZER_PIN, 2000, 30);
}

void buzzTarget() {
    for (int f = 1000; f <= 2500; f += 300) {
        tone(BUZZER_PIN, f, 50);
        delay(60);
    }
}

void buzzAlarm() {
    for (int i = 0; i < 5; i++) {
        tone(BUZZER_PIN, 3000, 100);
        delay(150);
        tone(BUZZER_PIN, 2000, 100);
        delay(150);
    }
}

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println(F("{\"boot\":\"starting\"}"));

    // Bar graph pins
    for (int i = 0; i < NUM_BAR_SEGS; i++) {
        pinMode(BAR_PINS[i], OUTPUT);
        digitalWrite(BAR_PINS[i], LOW);
    }

    // Buzzer pin
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);

    // Shelf LED pins
    for (int i = 0; i < NUM_SLOTS; i++) {
        pinMode(SLOT_PINS[i], OUTPUT);
        digitalWrite(SLOT_PINS[i], LOW);
    }

    // Startup animation
    for (int i = 0; i < NUM_BAR_SEGS; i++) {
        digitalWrite(BAR_PINS[i], HIGH);
        delay(40);
    }
    buzzConfirm();
    delay(150);
    for (int i = NUM_BAR_SEGS - 1; i >= 0; i--) {
        digitalWrite(BAR_PINS[i], LOW);
        delay(40);
    }

    // Init stability history
    for (int i = 0; i < STABILITY_WINDOW; i++) {
        shelfHistory[i] = 0;
        mixHistory[i] = 0;
    }

    Serial.println(F("{\"boot\":\"ready\"}"));
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
    // Stop buzzer when duration elapsed
    if (buzzing && millis() >= buzzEndTime) {
        noTone(BUZZER_PIN);
        buzzing = false;
    }

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
// HX711 LAZY INIT
// ============================================================
void initHX711() {
    if (hx711_initialized) return;
    Serial.println(F("{\"info\":\"hx711_init_start\"}"));

    scaleShelf.begin(SHELF_DT, SHELF_SCK);
    scaleMix.begin(MIX_DT, MIX_SCK);

    if (scaleShelf.wait_ready_timeout(2000)) {
        shelfOffset = scaleShelf.read_average(SAMPLES_TARE);
        Serial.println(F("{\"info\":\"shelf_tared\"}"));
    }
    if (scaleMix.wait_ready_timeout(2000)) {
        mixOffset = scaleMix.read_average(SAMPLES_TARE);
        Serial.println(F("{\"info\":\"mix_tared\"}"));
    }

    hx711_initialized = true;
    Serial.println(F("{\"info\":\"hx711_init_done\"}"));
}

// ============================================================
// COMMAND PROCESSOR
// ============================================================
void processCommand(const char* json) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, json);

    if (err) {
        Serial.println(F("{\"err\":\"json_parse\"}"));
        return;
    }

    const char* cmd = doc["cmd"] | "";

    // ---- PING ----
    if (strcmp(cmd, "ping") == 0) {
        Serial.println(F("{\"status\":\"ok\",\"fw\":\"1.2\"}"));
    }

    // ---- INIT HX711 ----
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
            Serial.println(F("{\"err\":\"unknown channel\"}"));
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
            Serial.println(F("{\"err\":\"tare_failed\"}"));
        }
    }

    // ---- BAR GRAPH ----
    else if (strcmp(cmd, "bar") == 0) {
        int seg = -1;
        if (doc.containsKey("pct")) {
            int pct = doc["pct"] | 0;
            if (pct < 0) pct = 0;
            if (pct > 100) pct = 100;
            seg = (pct * NUM_BAR_SEGS + 50) / 100;
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
            Serial.println(F("{\"err\":\"bar_range\"}"));
        }
    }

    // ---- BAR OFF ----
    else if (strcmp(cmd, "bar_off") == 0) {
        setBar(0);
        Serial.println(F("{\"ok\":\"bar_off\"}"));
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
            Serial.println(F("{\"err\":\"slot_idx\"}"));
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

    // ---- BUZZER (named pattern) ----
    else if (strcmp(cmd, "buzz") == 0) {
        if (doc.containsKey("pattern")) {
            const char* pat = doc["pattern"] | "";
            if (strcmp(pat, "confirm") == 0)       buzzConfirm();
            else if (strcmp(pat, "warning") == 0)  buzzWarning();
            else if (strcmp(pat, "error") == 0)    buzzError();
            else if (strcmp(pat, "tick") == 0)      buzzTick();
            else if (strcmp(pat, "target") == 0)    buzzTarget();
            else if (strcmp(pat, "alarm") == 0)     buzzAlarm();
            else {
                Serial.println(F("{\"err\":\"unknown pattern\"}"));
                return;
            }
            char resp[48];
            snprintf(resp, sizeof(resp), "{\"ok\":\"buzz\",\"pattern\":\"%s\"}", pat);
            Serial.println(resp);
        }
        else if (doc.containsKey("freq")) {
            int freq = doc["freq"] | 1000;
            int dur = doc["dur"] | 200;
            tone(BUZZER_PIN, freq, dur);
            buzzing = true;
            buzzEndTime = millis() + dur;
            Serial.println(F("{\"ok\":\"buzz\"}"));
        }
        else {
            Serial.println(F("{\"err\":\"buzz_args\"}"));
        }
    }

    // ---- BUZZER OFF ----
    else if (strcmp(cmd, "buzz_off") == 0) {
        noTone(BUZZER_PIN);
        buzzing = false;
        Serial.println(F("{\"ok\":\"buzz_off\"}"));
    }

    // ---- EVERYTHING OFF ----
    else if (strcmp(cmd, "led_off") == 0) {
        setBar(0);
        for (int i = 0; i < NUM_SLOTS; i++) {
            digitalWrite(SLOT_PINS[i], LOW);
        }
        noTone(BUZZER_PIN);
        buzzing = false;
        Serial.println(F("{\"ok\":\"led_off\"}"));
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
            Serial.println(F("{\"err\":\"invalid scale\"}"));
        }
    }

    // ---- STATUS ----
    else if (strcmp(cmd, "status") == 0) {
        bool shelf_ok = hx711_initialized ? scaleShelf.is_ready() : false;
        bool mix_ok = hx711_initialized ? scaleMix.is_ready() : false;
        char resp[96];
        snprintf(resp, sizeof(resp),
            "{\"status\":\"ok\",\"shelf_ok\":%s,\"mix_ok\":%s,\"bar\":%d,\"slots\":%d,\"buzz\":true,\"fw\":\"1.2\"}",
            shelf_ok ? "true" : "false",
            mix_ok ? "true" : "false",
            NUM_BAR_SEGS, NUM_SLOTS);
        Serial.println(resp);
    }

    // ---- UNKNOWN ----
    else {
        Serial.println(F("{\"err\":\"unknown command\"}"));
    }
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
// READ HX711 AND SEND JSON
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

    long raw = scale->read_average(SAMPLES_NORMAL);
    float grams = (float)(calOffset - raw) / calScale;
    if (grams < 0) grams = 0;

    history[*histIdx] = grams;
    *histIdx = (*histIdx + 1) % STABILITY_WINDOW;

    float minVal = history[0], maxVal = history[0];
    for (int i = 1; i < STABILITY_WINDOW; i++) {
        if (history[i] < minVal) minVal = history[i];
        if (history[i] > maxVal) maxVal = history[i];
    }
    *stable = (maxVal - minVal) < STABILITY_THRESH;

    char gramsStr[16];
    dtostrf(grams, 1, 1, gramsStr);

    char resp[96];
    snprintf(resp, sizeof(resp),
        "{\"ch\":\"%s\",\"g\":%s,\"raw\":%ld,\"stable\":%s}",
        chName, gramsStr, raw, *stable ? "true" : "false");
    Serial.println(resp);
}
