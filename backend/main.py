"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - FASTAPI ML BACKEND
=============================================================================
Main API application:
  - GET  /health          : Service and model health status
  - POST /predict         : Predict fabric from wavelength & intensity
  - GET  /model-info      : Model metadata, classes, and training specs
  - GET  /listener/status : Firebase background listener status
  - POST /listener/start  : Start Firebase background listener
  - POST /listener/stop   : Stop Firebase background listener
=============================================================================
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from schemas import PredictRequest, PredictResponse, ModelInfoResponse, HealthResponse
from ml_service import ml_service
from firebase_service import firebase_sync_service
import time
from typing import Dict, Any, Optional

# Real-time state store for latest scan and device health
latest_scan_record: Optional[Dict[str, Any]] = None
device_status_record: Dict[str, Any] = {
    "connected": False,
    "sensor_status": "offline",
    "last_seen": None,
    "source": "none"
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Firebase sync worker if database URL is configured
    print("[FastAPI] Starting Fabric Identification System Backend...")
    if firebase_sync_service.database_url:
        firebase_sync_service.start_listener()
    yield
    # Shutdown
    print("[FastAPI] Shutting down...")
    firebase_sync_service.stop_listener()


app = FastAPI(
    title="Fabric Identification System ML API",
    description="Spectroscopy-based material classification using Support Vector Machines (SVM)",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for web dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
def root():
    return {
        "title": "Fabric Identification System API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "model_loaded": ml_service.is_ready
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """
    Check operational status of ML backend and model readiness.
    """
    return HealthResponse(
        status="healthy" if ml_service.is_ready else "degraded",
        model_loaded=ml_service.is_ready,
        firebase_connected=firebase_sync_service.is_connected,
        service="Fabric Identification ML Backend"
    )


@app.post("/predict", response_model=PredictResponse, tags=["Inference"])
def predict_fabric(request: PredictRequest):
    """
    Perform SVM fabric prediction on incoming NIR spectral data.
    Input requires:
      - scan_id
      - wavelength array (e.g. [900, 920, 940, ...])
      - intensity array (matching length)
    """
    global latest_scan_record, device_status_record

    result = ml_service.predict(
        scan_id=request.scan_id,
        wavelengths=request.wavelength,
        intensities=request.intensity
    )

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    # Store latest real-time scan so dashboard receives it immediately
    latest_scan_record = {
        "scan_id": result["scan_id"],
        "timestamp": int(time.time() * 1000),
        "wavelength": request.wavelength,
        "intensity": request.intensity,
        "status": "processed",
        "prediction": {
            "fabric": result["fabric"],
            "confidence": result["confidence"],
            "model_version": result["model_version"]
        }
    }

    # Mark ESP32 and sensor as actively connected
    device_status_record = {
        "connected": True,
        "sensor_status": "online",
        "last_seen": int(time.time() * 1000),
        "source": "live_hardware"
    }

    return PredictResponse(
        scan_id=result["scan_id"],
        fabric=result["fabric"],
        confidence=result["confidence"],
        model_version=result["model_version"]
    )


@app.get("/latest-scan", tags=["Real-Time Stream"])
def get_latest_scan():
    """
    Retrieve the most recent real-time spectrum and ML prediction.
    """
    if latest_scan_record is None:
        return {"status": "waiting", "message": "No scan received yet"}
    return latest_scan_record


@app.get("/device-status", tags=["Real-Time Stream"])
def get_device_status():
    """
    Check current connection and sensor status of ESP32.
    """
    # If no scan seen in last 12 seconds, mark ESP32 as offline
    now_ms = int(time.time() * 1000)
    if device_status_record["last_seen"] and (now_ms - device_status_record["last_seen"] > 12000):
        device_status_record["connected"] = False
        device_status_record["sensor_status"] = "offline"

    return device_status_record


@app.post("/device/heartbeat", tags=["Real-Time Stream"])
def post_device_heartbeat(data: Dict[str, Any]):
    """
    Allow ESP32 or serial bridge to report heartbeat directly.
    """
    global device_status_record
    device_status_record = {
        "connected": data.get("connected", True),
        "sensor_status": data.get("sensor_status", "online"),
        "last_seen": int(time.time() * 1000),
        "source": data.get("source", "esp32")
    }
    return {"status": "ok"}


@app.get("/model-info", response_model=ModelInfoResponse, tags=["Metadata"])
def get_model_info():
    """
    Retrieve model metadata, class labels, and evaluation metrics.
    """
    meta = ml_service.get_metadata()
    return ModelInfoResponse(
        model=meta.get("model", "SVM"),
        version=meta.get("version", "svm_v1"),
        classes=meta.get("classes", ["Cotton", "Nylon", "Polyester", "Silk"]),
        accuracy=meta.get("accuracy", 0.0),
        wavelength_range=meta.get("wavelength_range"),
        num_wavelengths=meta.get("num_wavelengths"),
        kernel=meta.get("kernel"),
        data_leakage_prevented=meta.get("data_leakage_prevented", True),
        split_strategy=meta.get("split_strategy")
    )


@app.get("/listener/status", tags=["Firebase Sync"])
def get_listener_status():
    """
    Get status of background Firebase sync worker.
    """
    return {
        "running": firebase_sync_service.is_running,
        "firebase_url": firebase_sync_service.database_url or "not_configured",
        "connected": firebase_sync_service.is_connected,
        "processed_scans_count": len(firebase_sync_service.processed_scans)
    }


@app.post("/listener/start", tags=["Firebase Sync"])
def start_listener():
    """
    Manually start the Firebase background listener.
    """
    firebase_sync_service.start_listener()
    return {"status": "started", "running": firebase_sync_service.is_running}


@app.post("/listener/stop", tags=["Firebase Sync"])
def stop_listener():
    """
    Manually stop the Firebase background listener.
    """
    firebase_sync_service.stop_listener()
    return {"status": "stopped", "running": firebase_sync_service.is_running}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", 8000))
    print(f"[FastAPI] Starting server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
