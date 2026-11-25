/*
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - ESP32 SENSOR FIRMWARE (PURE HARDWARE REAL-TIME)
 * ============================================================================
 * Architecture: ESP32 -> Firebase Realtime DB & USB Serial -> Dashboard / ML
 * 
 * Mode: 100% PURE REAL-TIME HARDWARE SENSOR ACQUISITION (No simulation)
 * 
 * Hardware Setup:
 *   - ESP32 Dev Module
 *   - Spectroscopy Sensor: AS7265x Triad 18-Channel Spectrometer (I2C)
 *     Wiring:
 *       VCC -> 3.3V
 *       GND -> GND
 *       SDA -> D4  (ESP32 GPIO 4)
 *       SCL -> TX2 (ESP32 GPIO 17)
 * ============================================================================
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <vector>
#include <Wire.h>
#include "SparkFun_AS7265X.h"  // Install "SparkFun AS7265X" in Arduino Library Manager

// ============================================================================
// I2C PIN CONFIGURATION (SDA = D4, SCL = TX2)
// ============================================================================
const int I2C_SDA_PIN = 4;   // Pin marked D4  (GPIO 4)
const int I2C_SCL_PIN = 17;  // Pin marked TX2 (GPIO 17 / U2TXD)

// Sensor instance
AS7265X sensor;

// ============================================================================
// NETWORK & CLOUD CONFIGURATION
// ============================================================================
// Enter your local Wi-Fi credentials:
const char* WIFI_SSID     = "Hwjunction";
const char* WIFI_PASSWORD = "forged@forge";

// Firebase Realtime Database Host (without https:// prefix and without trailing slash)
// Example: "your-project-default-rtdb.firebaseio.com"
const char* FIREBASE_HOST = "fabric-identification-da466-default-rtdb.asia-southeast1.firebasedatabase.app";

// Optional Database Secret or Auth Token (leave "" for open development rules)
const char* FIREBASE_AUTH = "";

// Real-Time Scan Frequency in milliseconds (2000ms = 2 seconds for continuous live scans)
const unsigned long SCAN_INTERVAL_MS = 2000;

// Device Heartbeat Interval (milliseconds)
const unsigned long HEARTBEAT_INTERVAL_MS = 8000;

// ============================================================================
// STATE & NTP
// ============================================================================
unsigned long lastScanTime = 0;
unsigned long lastHeartbeatTime = 0;
unsigned long scanCounter = 0;
bool sensorInitialized = false;

const char* NTP_SERVER = "pool.ntp.org";
const long  GMT_OFFSET_SEC = 0;
const int   DAYLIGHT_OFFSET_SEC = 0;

// ============================================================================
// SENSOR DRIVER (AS7265X 18-CHANNEL SPECTROMETER)
// ============================================================================

bool initializeSensor() {
    Serial.printf("[SENSOR] Initializing hardware AS7265x spectrometer on I2C (SDA=D4/GPIO %d, SCL=TX2/GPIO %d)...\n", I2C_SDA_PIN, I2C_SCL_PIN);
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

    if (!sensor.begin()) {
        Serial.println("[SENSOR ERROR] AS7265x sensor NOT DETECTED!");
        Serial.printf("[SENSOR ERROR] Please check wiring: 3.3V -> VCC, GND -> GND, D4 -> SDA (pin %d), TX2 -> SCL (pin %d).\n", I2C_SDA_PIN, I2C_SCL_PIN);
        sensorInitialized = false;
        return false;
    }

    // Configure sensor illumination and integration
    // Disable blinking indicator LED on sensor
    sensor.disableIndicator();
    
    // Set sensor gain: 0=1x, 1=3.7x, 2=16x, 3=64x (16x default recommended for fabric NIR)
    sensor.setGain(2);

    // Set integration cycles: value * 2.8ms (default 49 = ~137ms per measurement)
    sensor.setIntegrationCycles(49);

    Serial.println("[SENSOR OK] AS7265x 18-channel Spectroscopy Sensor initialized successfully.");
    sensorInitialized = true;
    return true;
}

/**
 * Acquire real optical spectrum across 18 calibrated bands (410nm to 940nm)
 */
bool readSpectrum(std::vector<float>& wavelengths, std::vector<float>& intensities) {
    wavelengths.clear();
    intensities.clear();

    if (!sensorInitialized) {
        // Attempt re-init if previously disconnected
        if (!initializeSensor()) {
            return false;
        }
    }

    // Take real-time measurement with built-in illumination bulb for consistent reflection
    sensor.takeMeasurementsWithBulb();

    // 18 calibrated spectral channels from UV/VIS through NIR
    const float wlChannels[18] = {
        410.0f, 435.0f, 460.0f, 485.0f, 510.0f, 535.0f,
        560.0f, 585.0f, 610.0f, 645.0f, 680.0f, 705.0f,
        730.0f, 760.0f, 810.0f, 860.0f, 900.0f, 940.0f
    };

    // Read real calibrated float intensities from hardware
    const float rawValues[18] = {
        sensor.getCalibratedA(), sensor.getCalibratedB(), sensor.getCalibratedC(),
        sensor.getCalibratedD(), sensor.getCalibratedE(), sensor.getCalibratedF(),
        sensor.getCalibratedG(), sensor.getCalibratedH(), sensor.getCalibratedI(),
        sensor.getCalibratedJ(), sensor.getCalibratedK(), sensor.getCalibratedL(),
        sensor.getCalibratedR(), sensor.getCalibratedS(), sensor.getCalibratedT(),
        sensor.getCalibratedU(), sensor.getCalibratedV(), sensor.getCalibratedW()
    };

    for (int i = 0; i < 18; i++) {
        wavelengths.push_back(wlChannels[i]);
        intensities.push_back(rawValues[i]);
    }

    return true;
}

// ============================================================================
// TIMESTAMPS & WI-FI / FIREBASE
// ============================================================================

unsigned long long getEpochMillis() {
    time_t now;
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo, 100)) {
        return 1700000000000ULL + millis();
    }
    time(&now);
    return ((unsigned long long)now) * 1000ULL + (millis() % 1000);
}

String generateScanId(unsigned long idNum) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "SCAN_%06lu", idNum);
    return String(buffer);
}

void connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;
    if (String(WIFI_SSID) == "YOUR_WIFI_SSID") {
        Serial.println("[WIFI] Credentials not configured. Streaming over USB Serial (115200 baud).");
        return;
    }

    Serial.printf("[WIFI] Connecting to SSID: %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 15) {
        delay(400);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI OK] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
    } else {
        Serial.println("\n[WIFI] Could not connect. Continuing in USB Serial streaming mode.");
    }
}

bool sendFirebaseData(const String& path, const String& jsonPayload) {
    if (WiFi.status() != WL_CONNECTED || String(FIREBASE_HOST).startsWith("YOUR_PROJECT")) {
        return false;
    }

    WiFiClientSecure client;
    client.setInsecure();

    // Sanitize host: ensure no duplicate https:// or trailing slashes
    String cleanHost = String(FIREBASE_HOST);
    cleanHost.replace("https://", "");
    cleanHost.replace("http://", "");
    while (cleanHost.endsWith("/")) cleanHost.remove(cleanHost.length() - 1);

    HTTPClient http;
    String url = "https://" + cleanHost + path + ".json";
    if (strlen(FIREBASE_AUTH) > 0) {
        url += "?auth=" + String(FIREBASE_AUTH);
    }

    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");

    int code = http.PUT(jsonPayload);
    bool success = (code >= 200 && code < 300);

    if (code == 401) {
        Serial.printf("[FIREBASE 401 PERMISSION DENIED] Check Realtime Database rules in Firebase Console: change to .read: true, .write: true\n");
    } else if (!success) {
        Serial.printf("[FIREBASE HTTP ERROR] Code %d for %s\n", code, url.c_str());
    }

    http.end();
    return success;
}

void sendDeviceHeartbeat() {
    unsigned long long nowMs = getEpochMillis();
    char buffer[256];
    snprintf(buffer, sizeof(buffer),
        "{\"connected\":true,\"last_seen\":%llu,\"sensor_status\":\"%s\",\"sensor_model\":\"AS7265x_Triad\"}",
        nowMs,
        sensorInitialized ? "online" : "offline"
    );
    sendFirebaseData("/device/esp32", String(buffer));
}

// ============================================================================
// MAIN SETUP & REAL-TIME ACQUISITION LOOP
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n========================================================");
    Serial.println("   FABRIC IDENTIFICATION SYSTEM - REAL-TIME HARDWARE   ");
    Serial.println("========================================================");

    // Initialize physical spectroscopy sensor
    if (!initializeSensor()) {
        Serial.println("[WARNING] System started, but sensor was not found. Please attach AS7265x sensor.");
    }

    // Connect to Wi-Fi if credentials are provided
    connectWiFi();

    // Send initial device status
    sendDeviceHeartbeat();
}

void loop() {
    // Keep Wi-Fi connection alive if configured
    if (WiFi.status() != WL_CONNECTED && String(WIFI_SSID) != "YOUR_WIFI_SSID") {
        connectWiFi();
    }

    unsigned long currentMillis = millis();

    // Send heartbeat
    if (currentMillis - lastHeartbeatTime >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatTime = currentMillis;
        sendDeviceHeartbeat();
    }

    // Real-Time Acquisition & Broadcast
    if (currentMillis - lastScanTime >= SCAN_INTERVAL_MS) {
        lastScanTime = currentMillis;

        std::vector<float> wavelengths;
        std::vector<float> intensities;

        if (readSpectrum(wavelengths, intensities)) {
            scanCounter++;
            String scanId = generateScanId(scanCounter);
            unsigned long long timestamp = getEpochMillis();

            // Construct payload with real measurements
            String payload = "{";
            payload += "\"scan_id\":\"" + scanId + "\",";
            payload += "\"timestamp\":" + String(timestamp) + ",";
            
            payload += "\"wavelength\":[";
            for (size_t i = 0; i < wavelengths.size(); i++) {
                payload += String(wavelengths[i], 1);
                if (i + 1 < wavelengths.size()) payload += ",";
            }
            payload += "],";

            payload += "\"intensity\":[";
            for (size_t i = 0; i < intensities.size(); i++) {
                payload += String(intensities[i], 2);
                if (i + 1 < intensities.size()) payload += ",";
            }
            payload += "],";

            payload += "\"status\":\"raw\",";
            payload += "\"prediction\":{\"fabric\":null,\"confidence\":null,\"model_version\":null}";
            payload += "}";

            // 1. Broadcast over USB Serial (for direct desktop / Python bridge real-time ingestion)
            Serial.print("[REALTIME_SCAN] ");
            Serial.println(payload);

            // 2. Broadcast to Firebase Realtime Database
            if (WiFi.status() == WL_CONNECTED) {
                bool ok = sendFirebaseData("/fabric_scans/" + scanId, payload);
                if (ok) {
                    Serial.printf("[FIREBASE OK] Real-time scan %s pushed\n", scanId.c_str());
                }
            }
        } else {
            Serial.printf("[SENSOR WAITING] Waiting for sensor connection on I2C (SDA=D4/GPIO %d, SCL=TX2/GPIO %d)...\n", I2C_SDA_PIN, I2C_SCL_PIN);
        }
    }

    delay(20);
}
