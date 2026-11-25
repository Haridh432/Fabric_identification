"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - ML INFERENCE SERVICE
=============================================================================
Wraps the FabricPredictor inference engine into a thread-safe singleton service.
Ensures zero re-training during runtime, fast response, and graceful error handling.
=============================================================================
"""

import os
import sys
from typing import Dict, Any, List

# Add ml directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml")))

from predict import FabricPredictor


class MLService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MLService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_dir: str = None):
        if self._initialized:
            return

        if model_dir is None:
            # Default path to ml/models relative to backend directory
            model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml", "models"))
        
        self.model_dir = model_dir
        self.predictor = None
        self.is_ready = False
        self.init_error = None

        try:
            self.predictor = FabricPredictor(model_dir=self.model_dir)
            self.is_ready = True
            print(f"[MLService] Loaded trained SVM model from {self.model_dir}")
        except Exception as e:
            self.init_error = str(e)
            print(f"[MLService WARNING] Could not load model: {e}. Inference will return error until model is trained.")

        self._initialized = True

    def predict(self, scan_id: str, wavelengths: List[float], intensities: List[float]) -> Dict[str, Any]:
        """
        Run inference using the trained SVM model.
        """
        if not self.is_ready:
            # Attempt to re-load if model was recently generated
            try:
                self.predictor = FabricPredictor(model_dir=self.model_dir)
                self.is_ready = True
                self.init_error = None
            except Exception as e:
                return {
                    "scan_id": scan_id,
                    "fabric": "Unknown",
                    "confidence": 0.0,
                    "model_version": "unavailable",
                    "error": f"Model not loaded: {str(e)}"
                }

        try:
            return self.predictor.predict(wavelengths=wavelengths, intensities=intensities, scan_id=scan_id)
        except Exception as e:
            return {
                "scan_id": scan_id,
                "fabric": "Error",
                "confidence": 0.0,
                "model_version": "svm_v1",
                "error": f"Prediction error: {str(e)}"
            }

    def get_metadata(self) -> Dict[str, Any]:
        if self.is_ready and self.predictor:
            return self.predictor.metadata
        return {
            "model": "SVM",
            "version": "not_loaded",
            "classes": ["Cotton", "Nylon", "Polyester", "Silk"],
            "accuracy": 0.0,
            "error": self.init_error
        }


# Global Singleton instance
ml_service = MLService()
