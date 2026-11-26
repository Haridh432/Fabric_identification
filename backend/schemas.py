"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - PYDANTIC DATA SCHEMAS
=============================================================================
Defines validation schemas for API inputs, outputs, and dataset training.
=============================================================================
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class MatchedSample(BaseModel):
    sample_id: str
    fabric: str
    physical_sample_id: Optional[str] = ""
    similarity: float


class PredictRequest(BaseModel):
    """
    Input payload for POST /predict
    """
    scan_id: str = Field(..., example="SCAN_000001", description="Unique identifier for the scan")
    wavelength: List[float] = Field(..., min_length=2, description="Array of spectral wavelengths in nm")
    intensity: List[float] = Field(..., min_length=2, description="Array of spectral intensities")

    @field_validator("intensity")
    @classmethod
    def check_lengths_match(cls, v, info):
        wavelength = info.data.get("wavelength")
        if wavelength and len(v) != len(wavelength):
            raise ValueError(f"Intensity length ({len(v)}) must match wavelength length ({len(wavelength)})")
        return v


class PredictResponse(BaseModel):
    """
    Output payload for POST /predict
    """
    scan_id: str = Field(..., example="SCAN_000001")
    fabric: str = Field(..., example="Cotton")
    confidence: float = Field(..., example=96.4)
    model_version: str = Field(..., example="svm_v1")
    matched_samples: Optional[List[MatchedSample]] = []
    error: Optional[str] = None


class CollectedSampleItem(BaseModel):
    sample_id: str
    fabric: str
    physical_sample_id: str
    wavelength: List[float]
    intensity: List[float]


class TrainDatasetRequest(BaseModel):
    samples: List[CollectedSampleItem]
    replace_existing: bool = False


class ModelInfoResponse(BaseModel):
    """
    Output payload for GET /model-info
    """
    model: str
    version: str
    classes: List[str]
    accuracy: float
    wavelength_range: Optional[List[float]] = None
    num_wavelengths: Optional[int] = None
    kernel: Optional[str] = None
    data_leakage_prevented: Optional[bool] = True
    split_strategy: Optional[str] = None


class HealthResponse(BaseModel):
    """
    Output payload for GET /health
    """
    status: str = Field(..., example="healthy")
    model_loaded: bool
    firebase_connected: bool
    service: str = "Fabric Identification ML Backend"
