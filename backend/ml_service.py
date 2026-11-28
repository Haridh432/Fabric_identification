"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - ML INFERENCE SERVICE (SVM V2 + V3 COMBINED)
=============================================================================
Loads both models/fabric_svm_pipeline_v2.pkl and models/fabric_svm_pipeline_v3.pkl
once at startup. Applies SNV preprocessing and combines class probabilities
via soft-voting ensemble across both models.
=============================================================================
"""

import os
import json
import joblib
import numpy as np
from typing import Dict, Any, List, Optional


def snv(X: np.ndarray) -> np.ndarray:
    """
    Standard Normal Variate (SNV) preprocessing.
    Matches the exact transformation applied during model training.
    """
    X = np.asarray(X, dtype=np.float64)
    mean = np.mean(X, axis=1, keepdims=True)
    std = np.std(X, axis=1, keepdims=True)
    std[std == 0] = 1.0
    return (X - mean) / std


class MLService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MLService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.models_dir = os.path.join(self.project_root, "models")

        self.models: Dict[str, Any] = {}
        self.metadatas: Dict[str, Dict[str, Any]] = {}
        self.is_ready: bool = False
        self.init_error: Optional[str] = None

        self.load_model()
        self._initialized = True

    def load_model(self) -> bool:
        """Load both V2 and V3 SVM pipelines and metadata once at startup."""
        self.models = {}
        self.metadatas = {}
        errors = []

        for ver in ["v2", "v3"]:
            model_path = os.path.join(self.models_dir, f"fabric_svm_pipeline_{ver}.pkl")
            meta_path = os.path.join(self.models_dir, f"model_metadata_{ver}.json")

            if os.path.exists(model_path):
                try:
                    loaded_model = joblib.load(model_path)
                    self.models[ver] = loaded_model

                    if os.path.exists(meta_path):
                        with open(meta_path, "r") as f:
                            self.metadatas[ver] = json.load(f)
                    else:
                        self.metadatas[ver] = {
                            "model": "SVM",
                            "version": ver,
                            "classes": list(loaded_model.classes_),
                            "wavelengths": [
                                "410", "435", "460", "485", "510", "535",
                                "560", "585", "610", "645", "680", "705",
                                "730", "760", "810", "860", "900", "940"
                            ],
                            "preprocessing": ["SNV", "StandardScaler"],
                            "test_accuracy": 0.0,
                            "cv_accuracy": 0.0,
                            "cv_std": 0.0
                        }
                    print(f"[MLService] Loaded SVM {ver.upper()} pipeline from {model_path}")
                except Exception as e:
                    errors.append(f"{ver}: {e}")
                    print(f"[MLService ERROR] Failed to load SVM {ver.upper()}: {e}")
            else:
                errors.append(f"{ver}: file not found")

        if self.models:
            self.is_ready = True
            self.init_error = None
            return True

        self.is_ready = False
        self.init_error = "; ".join(errors) if errors else "No model files found"
        return False

    def predict_fabric(
        self,
        scan_id: str,
        wavelengths: List[float],
        intensities: List[float],
        timestamp: Optional[int] = None,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate 18-channel spectrum, apply SNV, and run combined V2 + V3
        soft-voting ensemble prediction across all 5 classes.
        """
        if not self.is_ready or not self.models:
            raise RuntimeError(f"ML model unavailable: {self.init_error or 'No models loaded'}")

        if len(intensities) != 18:
            raise ValueError(f"Expected exactly 18 intensity values, got {len(intensities)}")

        if len(wavelengths) != 18:
            raise ValueError(f"Expected exactly 18 wavelength values, got {len(wavelengths)}")

        arr = np.array(intensities, dtype=np.float64)
        if not np.all(np.isfinite(arr)):
            raise ValueError("Invalid spectrum: contains NaN or infinite values")

        # Exact live preprocessing flow: Raw 18-channel -> SNV -> saved SVM pipelines
        spectrum = arr.reshape(1, -1)
        spectrum_snv = snv(spectrum)

        # Combine class probabilities across all loaded models (V2 + V3 soft voting)
        combined_probs: Dict[str, float] = {}
        model_count = 0

        for ver, model in self.models.items():
            probs_raw = model.predict_proba(spectrum_snv)[0]
            for cls_name, prob in zip(model.classes_, probs_raw):
                key = str(cls_name)
                combined_probs[key] = combined_probs.get(key, 0.0) + float(prob)
            model_count += 1

        # Average probabilities across models
        probabilities = {
            cls_name: round(total_prob / model_count, 4)
            for cls_name, total_prob in combined_probs.items()
        }

        prediction = max(probabilities, key=probabilities.get)
        confidence = round(float(probabilities[prediction]), 4)

        return {
            "scan_id": scan_id,
            "timestamp": timestamp,
            "wavelength": wavelengths,
            "intensity": intensities,
            "fabric": prediction,
            "confidence": confidence,
            "probabilities": probabilities,
            "model": "fabric_svm_combined_v2_v3",
            "version": "v2+v3",
            "status": "predicted"
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Return combined V2 + V3 metadata and load status."""
        if not self.metadatas:
            return {
                "model": "SVM Combined",
                "version": "v2+v3",
                "active_version": "v2+v3",
                "available_versions": [],
                "classes": ["Cotton", "Linen", "Nylon", "Polyester", "Silk"],
                "test_accuracy": 0.0,
                "cv_accuracy": 0.0,
                "model_loaded": False,
                "error": self.init_error
            }

        metas = list(self.metadatas.values())
        avg_test = sum(m.get("test_accuracy", 0.0) for m in metas) / len(metas)
        avg_cv = sum(m.get("cv_accuracy", 0.0) for m in metas) / len(metas)
        first = metas[0]

        return {
            "model": "SVM Combined",
            "version": "v2+v3",
            "active_version": "v2+v3",
            "available_versions": sorted(list(self.models.keys())),
            "classes": first.get("classes", ["Cotton", "Linen", "Nylon", "Polyester", "Silk"]),
            "wavelengths": first.get("wavelengths"),
            "preprocessing": first.get("preprocessing", ["SNV", "StandardScaler"]),
            "test_accuracy": round(avg_test, 4),
            "cv_accuracy": round(avg_cv, 4),
            "cv_std": first.get("cv_std"),
            "models_summary": {
                v: {
                    "version": v,
                    "test_accuracy": m.get("test_accuracy", 0.0),
                    "cv_accuracy": m.get("cv_accuracy", 0.0)
                }
                for v, m in self.metadatas.items()
            },
            "model_loaded": self.is_ready,
            "error": self.init_error
        }


# Global singleton loaded once on startup
ml_service = MLService()
