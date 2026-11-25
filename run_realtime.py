"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - ALL-IN-ONE REAL-TIME LAUNCHER
=============================================================================
One single command to launch everything:
  1. Checks and loads the SVM model
  2. Starts the Python ML Backend (http://127.0.0.1:8000)
  3. Starts the Web Dashboard (http://127.0.0.1:3000)
  4. Auto-detects ESP32 USB COM port & starts the hardware sensor bridge
     (if plugged in via USB)
  5. Opens the Dashboard in your browser automatically
=============================================================================
"""

import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Locate Python in .venv
if sys.platform == "win32":
    PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
else:
    PYTHON_EXE = PROJECT_ROOT / ".venv" / "bin" / "python"

if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)


def check_and_prepare_model():
    model_path = PROJECT_ROOT / "ml" / "models" / "fabric_svm.pkl"
    if not model_path.exists():
        print("[SETUP] Trained SVM model not found. Training model now...")
        train_script = PROJECT_ROOT / "ml" / "train.py"
        res = subprocess.run([str(PYTHON_EXE), str(train_script)], cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            print("[SETUP ERROR] Failed to train SVM model.")
            sys.exit(1)
        print("[SETUP OK] SVM model trained and saved successfully.\n")
    else:
        print("[SETUP OK] Trained SVM model verified in ml/models/.\n")


def auto_detect_esp32_port():
    """Find plugged-in ESP32 USB COM port."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            desc = (p.description or "").lower()
            if any(k in desc for k in ["ch340", "cp210", "uart", "usb-serial", "esp32"]):
                return p.device
        if len(ports) > 0:
            return ports[0].device
    except Exception:
        pass
    return None


def main():
    print("=================================================================")
    print("   FABRIC IDENTIFICATION SYSTEM - ALL-IN-ONE REAL-TIME LAUNCHER   ")
    print("=================================================================")

    check_and_prepare_model()

    # 1. Start FastAPI ML Backend
    print("[1/4] Starting Python ML Backend on http://127.0.0.1:8000 ...")
    backend_cmd = [
        str(PYTHON_EXE), "-m", "uvicorn", 
        "backend.main:app", 
        "--host", "127.0.0.1", 
        "--port", "8000",
        "--log-level", "warning"
    ]
    backend_proc = subprocess.Popen(backend_cmd, cwd=str(PROJECT_ROOT))

    # 2. Start Web Dashboard HTTP Server
    print("[2/4] Starting Dashboard Server on http://127.0.0.1:3000 ...")
    dashboard_dir = PROJECT_ROOT / "dashboard"
    frontend_cmd = [
        str(PYTHON_EXE), "-m", "http.server", "3000",
        "--directory", str(dashboard_dir)
    ]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(PROJECT_ROOT), 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3. Auto-detect and start ESP32 Sensor Bridge (if connected via USB)
    bridge_proc = None
    esp_port = auto_detect_esp32_port()
    if esp_port:
        print(f"[3/4] Auto-detected ESP32 on USB port: {esp_port}! Starting bridge...")
        bridge_cmd = [str(PYTHON_EXE), "esp32_sensor_bridge.py", "--port", esp_port]
        bridge_proc = subprocess.Popen(bridge_cmd, cwd=str(PROJECT_ROOT))
    else:
        print("[3/4] No ESP32 USB port detected. Running in Wi-Fi / Firebase mode.")

    time.sleep(1.5)

    # 4. Open Browser
    dashboard_url = "http://127.0.0.1:3000"
    print(f"[4/4] Opening Dashboard in browser: {dashboard_url} ...")
    webbrowser.open(dashboard_url)

    print("\n" + "=" * 65)
    print("  🚀 ALL SERVICES RUNNING AUTOMATICALLY!")
    print("=" * 65)
    print(f"  ● Web Dashboard:       http://127.0.0.1:3000")
    print(f"  ● ML Backend API:      http://127.0.0.1:8000")
    if esp_port:
        print(f"  ● ESP32 Hardware:      Connected on {esp_port} (Auto-Bridged)")
    else:
        print(f"  ● ESP32 Hardware:      Wi-Fi / Firebase Mode (No USB cable needed)")
    print("=" * 65)
    print("  To stop all services, simply press Ctrl+C in this window.\n")

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("[ERROR] ML Backend stopped unexpectedly.")
                break
            if frontend_proc.poll() is not None:
                print("[ERROR] Dashboard server stopped unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopping all services...")
    finally:
        if bridge_proc and bridge_proc.poll() is None:
            bridge_proc.terminate()
        if backend_proc.poll() is None:
            backend_proc.terminate()
        if frontend_proc.poll() is None:
            frontend_proc.terminate()
        print("[SHUTDOWN] All background services stopped cleanly. Goodbye!")


if __name__ == "__main__":
    main()
