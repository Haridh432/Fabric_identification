"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - FASTAPI ML BACKEND (SVM V2)
=============================================================================
"""

import os
import sys
import time
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from schemas import PredictRequest, PredictResponse, ModelInfoResponse, HealthResponse
from ml_service import ml_service
from firebase_service import firebase_sync_service

# Real-time in-memory state (capped to prevent unbounded memory growth)
latest_scan_record: Optional[Dict[str, Any]] = None
recent_scans_feed: List[Dict[str, Any]] = []
recent_predictions: List[Dict[str, Any]] = []
device_status_record: Dict[str, Any] = {
    "connected": False,
    "sensor_status": "offline",
    "last_seen": None,
    "source": "none"
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[FastAPI] Starting Fabric Identification System Backend (SVM V2)...")
    if firebase_sync_service.database_url:
        firebase_sync_service.start_listener()
    yield
    print("[FastAPI] Shutting down...")
    firebase_sync_service.stop_listener()


app = FastAPI(
    title="Fabric Identification System ML API",
    description="Real-time AS7265x spectroscopy classification using SVM V2",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _record_scan_and_prediction(
    scan_id: str,
    timestamp_ms: int,
    wavelength: List[float],
    intensity: List[float],
    pred_result: Optional[Dict[str, Any]] = None,
    pred_error: Optional[str] = None
):
    """Update latest_scan_record, live feed (max 30), and recent predictions (max 10)."""
    global latest_scan_record, device_status_record

    peak_wl = wavelength[intensity.index(max(intensity))] if intensity else None
    max_int = round(max(intensity), 2) if intensity else None

    record: Dict[str, Any] = {
        "scan_id": scan_id,
        "timestamp": timestamp_ms,
        "wavelength": wavelength,
        "intensity": intensity,
        "peak_wavelength": peak_wl,
        "max_intensity": max_int,
        "status": "predicted" if pred_result else "collected"
    }

    if pred_result:
        record["fabric"] = pred_result["fabric"]
        record["confidence"] = pred_result["confidence"]
        record["probabilities"] = pred_result["probabilities"]
        record["model"] = pred_result["model"]
        record["prediction"] = {
            "fabric": pred_result["fabric"],
            "confidence": pred_result["confidence"],
            "probabilities": pred_result["probabilities"],
            "model": pred_result["model"],
            "status": "predicted"
        }

        recent_predictions.insert(0, {
            "scan_id": scan_id,
            "timestamp": timestamp_ms,
            "fabric": pred_result["fabric"],
            "confidence": pred_result["confidence"],
            "model": pred_result["model"]
        })
        if len(recent_predictions) > 10:
            recent_predictions.pop()
    else:
        record["prediction_error"] = pred_error or "ML prediction unavailable"

    latest_scan_record = record

    recent_scans_feed.insert(0, {
        "scan_id": scan_id,
        "timestamp": timestamp_ms,
        "peak_wavelength": peak_wl,
        "max_intensity": max_int,
        "fabric": pred_result["fabric"] if pred_result else None,
        "confidence": pred_result["confidence"] if pred_result else None,
        "status": record["status"]
    })
    if len(recent_scans_feed) > 30:
        recent_scans_feed.pop()

    device_status_record = {
        "connected": True,
        "sensor_status": "online",
        "last_seen": timestamp_ms,
        "source": "live_hardware"
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "title": "Fabric Identification System API",
        "version": "2.0.0",
        "model_loaded": ml_service.is_ready
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    return HealthResponse(
        status="healthy" if ml_service.is_ready else "degraded",
        model_loaded=ml_service.is_ready,
        firebase_connected=firebase_sync_service.is_connected,
        service="Fabric Identification ML Backend"
    )


@app.post("/predict", response_model=PredictResponse, tags=["Inference"])
def predict_fabric(request: PredictRequest):
    """
    Validate 18-channel spectrum, apply SNV, and run SVM (V2 or V3) prediction.
    """
    ts = request.timestamp or int(time.time() * 1000)
    try:
        result = ml_service.predict_fabric(
            scan_id=request.scan_id,
            wavelengths=request.wavelength,
            intensities=request.intensity,
            timestamp=ts,
            version=request.model_version
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction error: {e}")

    _record_scan_and_prediction(
        scan_id=request.scan_id,
        timestamp_ms=ts,
        wavelength=request.wavelength,
        intensity=request.intensity,
        pred_result=result
    )

    return PredictResponse(**result)


@app.post("/scan", tags=["Real-Time Stream"])
def ingest_scan(request: PredictRequest):
    """
    Ingest a new 18-channel scan and automatically run live SVM V2 prediction
    if available (never fails raw ingestion if ML is temporarily unavailable).
    """
    ts = request.timestamp or int(time.time() * 1000)
    pred_result = None
    pred_error = None

    try:
        pred_result = ml_service.predict_fabric(
            scan_id=request.scan_id,
            wavelengths=request.wavelength,
            intensities=request.intensity,
            timestamp=ts
        )
    except Exception as e:
        pred_error = str(e)

    _record_scan_and_prediction(
        scan_id=request.scan_id,
        timestamp_ms=ts,
        wavelength=request.wavelength,
        intensity=request.intensity,
        pred_result=pred_result,
        pred_error=pred_error
    )

    return latest_scan_record


@app.get("/latest-scan", tags=["Real-Time Stream"])
def get_latest_scan():
    """Retrieve the latest scan, live prediction, and recent 10 predictions."""
    if latest_scan_record is None:
        return {
            "status": "waiting",
            "message": "No scan received yet",
            "recent_predictions": recent_predictions
        }
    return {
        **latest_scan_record,
        "recent_predictions": recent_predictions
    }


@app.get("/live-feed", tags=["Real-Time Stream"])
def get_live_feed():
    return {"items": recent_scans_feed}


@app.get("/recent-predictions", tags=["Inference"])
def get_recent_predictions():
    return {"items": recent_predictions}


@app.get("/device-status", tags=["Real-Time Stream"])
def get_device_status():
    now_ms = int(time.time() * 1000)
    if device_status_record["last_seen"] and (now_ms - device_status_record["last_seen"] > 12000):
        device_status_record["connected"] = False
        device_status_record["sensor_status"] = "offline"
    return device_status_record


@app.post("/device/heartbeat", tags=["Real-Time Stream"])
def post_device_heartbeat(data: Dict[str, Any]):
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
    meta = ml_service.get_model_info()
    return ModelInfoResponse(
        model=meta.get("model", "SVM Combined"),
        version=meta.get("version", "v2+v3"),
        active_version=meta.get("active_version", "v2+v3"),
        available_versions=meta.get("available_versions", []),
        models_summary=meta.get("models_summary"),
        classes=meta.get("classes", ["Cotton", "Linen", "Nylon", "Polyester", "Silk"]),
        wavelengths=meta.get("wavelengths"),
        preprocessing=meta.get("preprocessing", ["SNV", "StandardScaler"]),
        test_accuracy=meta.get("test_accuracy", 0.0),
        cv_accuracy=meta.get("cv_accuracy", 0.0),
        cv_std=meta.get("cv_std"),
        model_loaded=meta.get("model_loaded", False),
        error=meta.get("error")
    )


@app.get("/listener/status", tags=["Firebase Sync"])
def get_listener_status():
    return {
        "running": firebase_sync_service.is_running,
        "firebase_url": firebase_sync_service.database_url or "not_configured",
        "connected": firebase_sync_service.is_connected,
        "processed_scans_count": len(firebase_sync_service.processed_scans)
    }


@app.post("/listener/start", tags=["Firebase Sync"])
def start_listener():
    firebase_sync_service.start_listener()
    return {"status": "started", "running": firebase_sync_service.is_running}


@app.post("/listener/stop", tags=["Firebase Sync"])
def stop_listener():
    firebase_sync_service.stop_listener()
    return {"status": "stopped", "running": firebase_sync_service.is_running}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)
