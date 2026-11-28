"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - PYDANTIC DATA SCHEMAS
=============================================================================
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class PredictRequest(BaseModel):
    """
    Input payload for POST /predict and POST /scan
    """
    scan_id: str = Field(..., example="SCAN_000025", description="Unique identifier for the scan")
    timestamp: Optional[int] = Field(None, example=1795591379778, description="Unix timestamp in ms")
    wavelength: List[float] = Field(..., description="Array of 18 AS7265x wavelengths in nm")
    intensity: List[float] = Field(..., description="Array of 18 calibrated intensity values")
    model_version: Optional[str] = Field(None, description="Optional model version override ('v2' or 'v3')")

    @field_validator("wavelength")
    @classmethod
    def check_wavelength_count(cls, v):
        if len(v) != 18:
            raise ValueError(f"Expected exactly 18 wavelength values, got {len(v)}")
        return v

    @field_validator("intensity")
    @classmethod
    def check_intensity_count(cls, v):
        if len(v) != 18:
            raise ValueError(f"Expected exactly 18 intensity values, got {len(v)}")
        return v


class PredictResponse(BaseModel):
    """
    Output payload for POST /predict
    """
    scan_id: str
    timestamp: Optional[int] = None
    wavelength: List[float]
    intensity: List[float]
    fabric: str
    confidence: float
    probabilities: Dict[str, float]
    model: str = "fabric_svm_pipeline_v2"
    status: str = "predicted"


class ModelInfoResponse(BaseModel):
    """
    Output payload for GET /model-info
    """
    model: str = "SVM"
    version: str = "v3"
    active_version: str = "v3"
    available_versions: List[str] = ["v2", "v3"]
    models_summary: Optional[Dict[str, Any]] = None
    classes: List[str]
    wavelengths: Optional[List[str]] = None
    preprocessing: Optional[List[str]] = None
    test_accuracy: float
    cv_accuracy: float
    cv_std: Optional[float] = None
    model_loaded: bool = True
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """
    Output payload for GET /health
    """
    status: str
    model_loaded: bool
    firebase_connected: bool
    service: str = "Fabric Identification ML Backend"
