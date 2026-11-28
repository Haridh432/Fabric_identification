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
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] pyserial is required. Install it using: pip install pyserial")
    sys.exit(1)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
FIREBASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://fabric-identification-da466-default-rtdb.asia-southeast1.firebasedatabase.app"
).rstrip("/")


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
    """Send live 18-channel scan to FastAPI (/predict) and preserve raw + prediction in Firebase."""
    scan_id = scan.get("scan_id", "SCAN_LIVE")
    timestamp_ms = scan.get("timestamp", int(time.time() * 1000))
    wavelengths = scan.get("wavelength", [])
    intensities = scan.get("intensity", [])

    peak_wl = wavelengths[intensities.index(max(intensities))] if intensities else None
    max_int = round(max(intensities), 2) if intensities else 0.0

    print(f"\n[LIVE HARDWARE] >>> Captured {scan_id} ({len(wavelengths)} bands | Peak: {int(peak_wl) if peak_wl else '--'} nm | Max: {max_int})")

    prediction_data = None

    # 1. Forward to FastAPI /predict for live SVM V2 classification
    try:
        resp = requests.post(f"{BACKEND_URL}/predict", json={
            "scan_id": scan_id,
            "timestamp": timestamp_ms,
            "wavelength": wavelengths,
            "intensity": intensities
        }, timeout=3)

        if resp.ok:
            pred = resp.json()
            conf_pct = round(pred["confidence"] * 100, 1)
            print(f"[SVM V2 PREDICTION] \033[92m{pred['fabric']}\033[0m | Confidence: \033[96m{conf_pct}%\033[0m")
            prediction_data = {
                "fabric": pred["fabric"],
                "confidence": pred["confidence"],
                "probabilities": pred["probabilities"],
                "model": pred["model"],
                "status": "predicted"
            }
        else:
            print(f"[ML WARNING] Status {resp.status_code}: {resp.text}")
            # Fall back to /scan so raw data still reaches dashboard
            requests.post(f"{BACKEND_URL}/scan", json={
                "scan_id": scan_id,
                "timestamp": timestamp_ms,
                "wavelength": wavelengths,
                "intensity": intensities
            }, timeout=3)
    except Exception as e:
        print(f"[BACKEND OFFLINE] Could not reach {BACKEND_URL}: {e}")

    # 2. Push raw spectrum + prediction sub-node to Firebase under /fabric_scans/{scan_id}
    if FIREBASE_URL:
        try:
            readable_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            readable_spectrum = {
                f"{int(wl) if float(wl).is_integer() else wl}nm": round(float(val), 2)
                for wl, val in zip(wavelengths, intensities)
            }

            fb_payload = {
                "scan_id": scan_id,
                "peak_wavelength": f"{int(peak_wl)} nm" if peak_wl is not None else "--",
                "max_intensity": max_int,
                "time": readable_time,
                "status": "predicted" if prediction_data else "collected",
                "spectrum": readable_spectrum
            }
            if prediction_data:
                fb_payload["prediction"] = prediction_data

            fb_url = f"{FIREBASE_URL}/fabric_scans/{scan_id}.json"
            requests.put(fb_url, json=fb_payload, timeout=3)
            print(f"[FIREBASE OK] Saved {scan_id} to Firebase.")
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
