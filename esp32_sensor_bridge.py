"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - REAL-TIME HARDWARE SENSOR BRIDGE
=============================================================================
Connects the physical ESP32 to the ML Backend and Firebase in real-time.
Reads live optical spectra from the ESP32 over USB Serial COM port (115200 baud).

Workflow:
  Physical ESP32 + Spectroscopy Sensor (AS7265x)
         │
         ▼ (USB Serial / COM Port)
  esp32_sensor_bridge.py
         │
         ├──► Forward to FastAPI ML Backend (/predict) -> Real-Time SVM Result
         └──► Forward to Firebase Realtime Database (/fabric_scans) -> Web Dashboard
=============================================================================
"""

import os
import sys
import time
import json
import requests
import argparse
from typing import Dict, Any

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] pyserial is required. Install it using: pip install pyserial")
    sys.exit(1)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
FIREBASE_URL = os.getenv("https://fabric-identification-da466-default-rtdb.asia-southeast1.firebasedatabase.app/", "").rstrip("/")


def auto_detect_esp32_port():
    """Detect available USB serial COM ports."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "ch340" in desc or "cp210" in desc or "uart" in desc or "usb-serial" in desc or "esp32" in desc:
            return p.device
    if len(ports) > 0:
        return ports[0].device
    return None


def forward_real_scan(scan: Dict[str, Any]):
    """Send live scan to ML backend and Firebase."""
    scan_id = scan.get("scan_id", "SCAN_LIVE")
    wavelengths = scan.get("wavelength", [])
    intensities = scan.get("intensity", [])

    print(f"\n[LIVE HARDWARE] >>> Captured {scan_id} ({len(wavelengths)} optical bands)")

    # 1. Forward to Python ML Backend for immediate SVM classification
    try:
        resp = requests.post(f"{BACKEND_URL}/predict", json={
            "scan_id": scan_id,
            "wavelength": wavelengths,
            "intensity": intensities
        }, timeout=3)

        if resp.ok:
            pred = resp.json()
            fabric = pred["fabric"]
            conf = pred["confidence"]
            print(f"[LIVE PREDICTION] \033[92m{fabric}\033[0m | Confidence: \033[96m{conf}%\033[0m | Model: {pred['model_version']}")
            scan["prediction"] = pred
            scan["status"] = "processed"
        else:
            print(f"[ML BACKEND WARNING] Status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[ML BACKEND OFFLINE] Could not reach {BACKEND_URL}: {e}")

    # 2. Push to Firebase Realtime Database
    if FIREBASE_URL:
        try:
            fb_url = f"{FIREBASE_URL}/fabric_scans/{scan_id}.json"
            requests.put(fb_url, json=scan, timeout=3)
            print(f"[FIREBASE OK] Pushed {scan_id} to {fb_url}")
        except Exception as e:
            print(f"[FIREBASE ERROR] Failed to push to Firebase: {e}")


def send_heartbeat(status: str = "online"):
    try:
        requests.post(f"{BACKEND_URL}/device/heartbeat", json={
            "connected": True,
            "sensor_status": status,
            "source": "usb_serial"
        }, timeout=2)
    except Exception:
        pass


def run_hardware_bridge(port: str, baud: int = 115200):
    print("=================================================================")
    print("   FABRIC IDENTIFICATION SYSTEM - LIVE HARDWARE SERIAL BRIDGE    ")
    print("=================================================================")
    print(f"Connecting to ESP32 on port: {port} at {baud} baud...")
    print(f"Target ML Backend:          {BACKEND_URL}")
    print(f"Target Firebase URL:         {FIREBASE_URL or 'Direct Local Mode (Firebase not required)'}")
    print("Waiting for physical sensor scans from ESP32... Press Ctrl+C to exit.\n")

    try:
        ser = serial.Serial(port, baud, timeout=1.5)
        time.sleep(2.0)  # Wait for ESP32 serial reset
        send_heartbeat("online")
        print("[BRIDGE OK] Connected to ESP32! Dashboard status set to Connected.")
    except Exception as e:
        print(f"[SERIAL ERROR] Could not open port {port}: {e}")
        return
    except Exception as e:
        print(f"[SERIAL ERROR] Could not open port {port}: {e}")
        return

    while True:
        try:
            raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not raw_line:
                continue

            if raw_line.startswith("[REALTIME_SCAN]"):
                json_str = raw_line.replace("[REALTIME_SCAN]", "").strip()
                try:
                    scan_data = json.loads(json_str)
                    forward_real_scan(scan_data)
                except json.JSONDecodeError as err:
                    print(f"[JSON ERROR] Could not parse ESP32 serial output: {err}")
            else:
                # Print status messages from ESP32 firmware
                print(f"[ESP32 LOG] {raw_line}")

        except KeyboardInterrupt:
            print("\n[BRIDGE] Stopped by user.")
            break
        except Exception as e:
            print(f"[SERIAL EXCEPTION] {e}")
            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Hardware ESP32 Serial Bridge")
    parser.add_argument("--port", type=str, help="ESP32 COM Port (e.g. COM7 or COM8)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate (default: 115200)")
    args = parser.parse_args()

    target_port = args.port or auto_detect_esp32_port()
    if not target_port:
        print("[ERROR] No COM port specified and no ESP32 detected automatically.")
        print("Please specify your port with: python esp32_sensor_bridge.py --port COM8")
        sys.exit(1)

    run_hardware_bridge(target_port, args.baud)
