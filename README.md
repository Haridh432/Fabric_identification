# 🧵 Fabric Identification System
### Real-Time Spectroscopy-Based Material Classification using ESP32, Firebase & Support Vector Machines (SVM)

[![ESP32](https://img.shields.io/badge/Hardware-ESP32%20Dev%20Module-blue.svg)](https://www.espressif.com/)
[![Sensor](https://img.shields.io/badge/Sensor-AS7265x%20Triad%20Spectrometer-orange.svg)](https://www.sparkfun.com/products/15050)
[![Python](https://img.shields.io/badge/Python-3.10%2B%20%7C%20FastAPI%20%7C%20Scikit--Learn-green.svg)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-Firebase%20Realtime%20DB-yellow.svg)](https://firebase.google.com/)

---

## 🌟 Overview

The **Fabric Identification System** identifies fabric materials (such as **Cotton**, **Nylon**, **Polyester**, and **Silk**) in real-time by analyzing their Near-Infrared (NIR) optical signatures.

Every fabric absorbs and reflects light at different wavelengths based on its molecular structure (cellulose, ester bonds, amide links). An **AS7265x Triad 18-Channel Spectrometer** connected to an **ESP32** captures these optical bands and transmits them to a **Support Vector Machine (SVM)** machine learning model, which classifies the fabric and displays the result live on an interactive web dashboard.

---

## 🏗 System Architecture

```text
                     FABRIC SAMPLE
                           │
                           ▼
                 Spectroscopy Sensor
              (AS7265x Triad 18-Channel)
                           │
                           ▼
                         ESP32
                           │
             ┌─────────────┴─────────────┐
             │ (Wi-Fi HTTPS)             │ (USB Serial)
             ▼                           ▼
      Firebase Database          esp32_sensor_bridge
             │                           │
             └─────────────┬─────────────┘
                           ▼
                  Python ML Backend
               (FastAPI + SVM Classifier)
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       Real-Time Graph             ML Result Card
    - Wavelength (410 - 940 nm)   - Fabric: Cotton
    - Intensity Values            - Confidence: 96.4%
    - Live Inspection Table       - Model Version: svm_v1
```

---

## 🔌 Hardware Wiring Diagram

Connect your **AS7265x Triad Spectrometer** to the **ESP32** using standard I2C jumper wires:

```text
ESP32 Dev Module         AS7265x Triad Spectrometer
┌────────────────┐       ┌────────────────┐
│            3V3 ├───────┤ VCC (3.3V)     │
│            GND ├───────┤ GND            │
│       D4 (IO4) ├───────┤ SDA            │
│      TX2 (IO17)├───────┤ SCL            │
└────────────────┘       └────────────────┘
```

| Sensor Pin | ESP32 Board Pin | GPIO Pin Number | Description |
|:---|:---|:---|:---|
| **VCC** | **3V3** | — | 3.3V Power Supply |
| **GND** | **GND** | — | Common Ground |
| **SDA** | **D4** | **GPIO 4** | I2C Data Line |
| **SCL** | **TX2** | **GPIO 17** *(U2TXD)* | I2C Clock Line |

---

## 🚀 Quick Start Guide (For Teammates — Sample Collection)

### 1. Requirements
- Windows 10/11
- **Python 3.10+** installed (with *"Add Python to PATH"* checked)
- ESP32 + AS7265x sensor (already flashed — just plug into USB!)

### 2. First-Time Run (1-Click Auto Setup)
Simply double-click:
👉 **`run_realtime.bat`**

On the first run, it automatically creates `.venv`, installs all dependencies, and opens **`http://127.0.0.1:3000`** in your browser.

### 3. How to Collect & Export Samples
1. Place the fabric sample flat against the AS7265x sensor.
2. In the dashboard (**Capture & Labeling**):
   - Select the **Fabric Class Label** (e.g., `Cotton`, `Silk`, `Linen`, `Nylon`, `Polyester`, or `+ Add Class`).
   - Check **Physical Fabric Sample ID** (e.g., `SAMPLE_COTTON_01`). *Use a new number (`_02`, `_03`) for each different physical cloth piece!*
3. Click **▶ Start Capture** and wait for 5–10 scans to appear in **Samples Collected List**.
4. Click **⏹ Stop Capture**.
5. Click **📥 Export CSV (Wide / ML)** to download the CSV file and share it with your team.

---

## 📡 Two Ways to Use the Hardware

### Mode A: USB Cable (Easiest — Plug & Play)
1. Plug the ESP32 into your computer with a USB cable.
2. Double-click `run_realtime.bat`.
3. The launcher automatically detects the ESP32 COM port and streams data to the dashboard in real time!

### Mode B: Wi-Fi & Firebase (Untethered / Wireless)
1. In `esp32/fabric_sensor/fabric_sensor.ino`, enter your Wi-Fi credentials:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_Name";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   const char* FIREBASE_HOST = "your-project-id-default-rtdb.asia-southeast1.firebasedatabase.app";
   ```
2. In the **Firebase Console** $\rightarrow$ **Realtime Database** $\rightarrow$ **Rules**, set:
   ```json
   {
     "rules": {
       ".read": true,
       ".write": true
     }
   }
   ```
3. Upload the code to the ESP32. It will now transmit live scans over Wi-Fi anywhere within network range!

---

## 📊 Web Dashboard Features

Open **`http://127.0.0.1:3000`** in any browser:

- **Live Spectrum Curve**: Interactive Chart.js graph plotting spectral intensity across wavelengths with peak wavelength calculation.
- **Fabric Result Card**: Large, high-visibility display showing the predicted fabric class, confidence meter (0–100%), and scan ID.
- **System Health Status Bar**:
  - `ESP32` ● Connected / Offline
  - `Sensor` ● Online / Offline
  - `Firebase` ● Connected / Not Configured
  - `ML Backend` ● Connected / Offline
- **Dataset Capture & Labeling**:
  - Select fabric class (Cotton, Nylon, Polyester, Silk, or `+ Add Class` for custom fabrics).
  - Enter `Physical_Sample_ID` (prevents data leakage).
  - Click **Start Capture** $\rightarrow$ **Download CSV (Wide / ML)** to export custom training data.
- **Raw Sensor Data Table**: Real-time tabular view of all 18 channels with search filter.

---

## 🧠 Machine Learning & Data Leakage Prevention

### The Leakage Problem
When scanning fabrics, taking multiple replicate scans of the same piece of cloth and randomly splitting them across training and test sets produces an **artificially high 99%+ accuracy** that fails on new fabrics.

### The Solution
The system groups scans by `Physical_Sample_ID` (e.g. `SAMPLE_COTTON_01`) and applies `GroupShuffleSplit`. Replicate scans of the same physical piece are kept strictly together in either Train or Test, ensuring unbiased real-world accuracy.

### Re-training the Model
```bash
# Generate benchmark NIR dataset:
.venv\Scripts\python ml/dataset/generate_sample_dataset.py

# Train SVM pipeline with hyperparameter grid search:
.venv\Scripts\python ml/train.py

# Evaluate test metrics and confusion matrix:
.venv\Scripts\python ml/evaluate.py
```

Saved artifacts in `ml/models/`:
- `fabric_svm.pkl` — Trained Support Vector Machine classifier
- `scaler.pkl` — Standard Normal Variate (SNV) + StandardScaler
- `wavelengths.json` — Reference wavelength grid
- `class_names.json` — Supported fabric classes
- `model_metadata.json` — Hyperparameters and performance stats

---

## 📁 Project Structure

```text
Fabric_identification/
├── esp32/
│   └── fabric_sensor/
│       └── fabric_sensor.ino          # ESP32 firmware (AS7265x driver on D4/TX2)
├── dashboard/
│   ├── index.html                     # Responsive dark-slate web dashboard
│   ├── css/style.css                  # UI styling & status pills
│   └── js/
│       ├── firebase.js                # Firebase Realtime DB client wrapper
│       ├── chart.js                   # Chart.js spectral curve visualizer
│       ├── capture.js                 # Dataset recording & CSV export
│       └── dashboard.js               # Main real-time UI orchestrator
├── ml/
│   ├── dataset/                       # Benchmark NIR spectral datasets
│   ├── models/                        # Saved SVM models & scalers
│   ├── preprocessing/                 # SNV normalization & resampling
│   ├── train.py                       # Leakage-free training script
│   ├── predict.py                     # Standalone inference engine
│   └── evaluate.py                    # Accuracy & confusion matrix report
├── backend/
│   ├── main.py                        # FastAPI real-time REST API
│   ├── ml_service.py                  # Singleton inference service
│   ├── firebase_service.py            # Firebase sync & auto-prediction worker
│   └── schemas.py                     # Pydantic request/response schemas
├── esp32_sensor_bridge.py             # USB Serial COM port bridge
├── run_realtime.py                    # Master launcher script
├── run_realtime.bat                   # 1-Click Windows batch runner
└── README.md
```

---

## 🛠 Troubleshooting

| Issue | Cause | Solution |
|:---|:---|:---|
| **Sensor Offline** | Wiring loose or wrong pins | Verify SDA is on **D4** (GPIO 4) and SCL is on **TX2** (GPIO 17) with 3.3V power |
| **Firebase "Rules Locked (401)"** | Firebase security rules locked | In Firebase Console $\rightarrow$ Realtime Database $\rightarrow$ Rules, set `.read: true, .write: true` |
| **ML Backend Offline** | FastAPI server stopped | Run `uvicorn backend.main:app --host 127.0.0.1 --port 8000` |
| **COM Port Access Denied** | Port open in Arduino Serial Monitor | Close the Serial Monitor in Arduino IDE before starting the bridge |

---

## 📄 License
This project is licensed under the MIT License.
