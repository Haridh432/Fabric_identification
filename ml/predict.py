"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - INFERENCE & PREDICTION MODULE
=============================================================================
Loads the trained SVM model, reference wavelengths, and preprocessor.
Performs real-time fabric classification given arbitrary wavelength/intensity
inputs from the sensor:
  - Dynamically interpolates/resamples to reference wavelengths
  - Applies identical SNV + StandardScaler transformations
  - Predicts fabric type and confidence percentage
=============================================================================
"""

import os
import sys
import json
import joblib
import numpy as np
from typing import List, Dict, Any, Union

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from preprocessing.preprocessor import SpectralPreprocessor


class FabricPredictor:
    """
    Production-ready fabric inference engine.
    Ensures that prediction preprocessing is 100% identical to training.
    """
    def __init__(self, model_dir: str = "ml/models"):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        self.wavelengths = None
        self.classes = None
        self.metadata = {}
        self.preprocessor = None
        self.is_loaded = False
        
        self.load_model_artifacts()

    def load_model_artifacts(self):
        """
        Load SVM model, scaler, reference wavelengths, class names, and metadata.
        """
        model_path = os.path.join(self.model_dir, "fabric_svm.pkl")
        scaler_path = os.path.join(self.model_dir, "scaler.pkl")
        wl_path = os.path.join(self.model_dir, "wavelengths.json")
        classes_path = os.path.join(self.model_dir, "class_names.json")
        meta_path = os.path.join(self.model_dir, "model_metadata.json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}. Train model first with train.py.")

        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)

        with open(wl_path, "r") as f:
            self.wavelengths = json.load(f)

        with open(classes_path, "r") as f:
            self.classes = json.load(f)

        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {"version": "svm_v1", "model": "SVM"}

        # Initialize preprocessor with trained reference grid and fitted scaler
        self.preprocessor = SpectralPreprocessor(reference_wavelengths=self.wavelengths)
        self.preprocessor.scaler = self.scaler
        self.preprocessor.is_fitted = True
        self.is_loaded = True

    def predict(self, 
                wavelengths: List[float], 
                intensities: List[float], 
                scan_id: str = "UNKNOWN") -> Dict[str, Any]:
        """
        Predict fabric type from spectral reading.
        
        Returns:
            Dict containing scan_id, fabric, confidence, and model_version.
        """
        if not self.is_loaded:
            self.load_model_artifacts()

        if len(wavelengths) == 0 or len(intensities) == 0:
            raise ValueError("Input wavelengths or intensities cannot be empty.")

        # 1. Align/resample wavelengths if different from training reference
        aligned_intensities = self.preprocessor.align_wavelengths(wavelengths, intensities)
        
        # 2. Reshape to 2D array [1, n_wavelengths]
        X = np.asarray(aligned_intensities, dtype=np.float64).reshape(1, -1)

        # 3. Apply identical preprocessing (SNV + StandardScaler)
        X_proc = self.preprocessor.transform(X)

        # 4. Predict class
        pred_class = self.model.predict(X_proc)[0]

        # 5. Calculate confidence score
        confidence = 0.0
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(X_proc)[0]
            max_prob = np.max(probs)
            confidence = round(float(max_prob * 100.0), 2)
        elif hasattr(self.model, "decision_function"):
            # Distance from decision boundary
            decision = self.model.decision_function(X_proc)
            confidence = round(float(min(99.9, max(50.0, 50.0 + np.max(np.abs(decision)) * 10.0))), 2)

        return {
            "scan_id": scan_id,
            "fabric": str(pred_class),
            "confidence": confidence,
            "model_version": self.metadata.get("version", "svm_v1")
        }


# Quick test execution
if __name__ == "__main__":
    predictor = FabricPredictor()
    # Test with dummy Cotton-like readings
    test_wl = list(range(900, 1720, 20))
    test_int = [12000.0] * len(test_wl)
    result = predictor.predict(test_wl, test_int, scan_id="TEST_001")
    print("Test Prediction Result:", result)
