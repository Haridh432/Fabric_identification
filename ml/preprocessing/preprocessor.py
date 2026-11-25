"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - SPECTRAL PREPROCESSING MODULE
=============================================================================
Handles:
  1. Wavelength alignment & interpolation (aligns sensor input to model grid)
  2. Missing value detection & handling
  3. Standard Normal Variate (SNV) transformation (baseline & scatter correction)
  4. Feature scaling (StandardScaler / MinMaxScaler)
=============================================================================
"""

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler
from typing import List, Tuple, Union, Optional


class SNVTransformer(BaseEstimator, TransformerMixin):
    """
    Standard Normal Variate (SNV) Normalization.
    Commonly used in Near-Infrared (NIR) spectroscopy to remove scatter effects
    and baseline shifts caused by fabric surface roughness and particle size.
    Formula per spectrum: x_snv = (x - mean(x)) / std(x)
    """
    def __init__(self, eps: float = 1e-8):
        self.eps = eps

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=np.float64)
        mean = np.mean(X, axis=1, keepdims=True)
        std = np.std(X, axis=1, keepdims=True)
        std[std < self.eps] = 1.0  # Avoid zero division
        return (X - mean) / std


class SpectralPreprocessor:
    """
    Complete spectral pipeline for NIR data:
      - Wavelength grid alignment via linear or cubic interpolation
      - SNV scatter correction
      - Feature scaling via StandardScaler
    """
    def __init__(self, reference_wavelengths: Optional[List[float]] = None):
        self.reference_wavelengths = np.array(reference_wavelengths) if reference_wavelengths is not None else None
        self.snv = SNVTransformer()
        self.scaler = StandardScaler()
        self.is_fitted = False

    def align_wavelengths(self, 
                           input_wavelengths: Union[List[float], np.ndarray], 
                           intensities: Union[List[float], np.ndarray]) -> np.ndarray:
        """
        Interpolates sensor intensity readings onto the reference wavelength grid.
        Prevents shape mismatch if the sensor provides different resolution or range.
        """
        if self.reference_wavelengths is None:
            raise ValueError("Reference wavelengths not set on SpectralPreprocessor.")

        in_wl = np.asarray(input_wavelengths, dtype=np.float64)
        in_int = np.asarray(intensities, dtype=np.float64)

        if len(in_wl) != len(in_int):
            raise ValueError(f"Wavelength length ({len(in_wl)}) does not match intensity length ({len(in_int)}).")

        # Check if already aligned
        if len(in_wl) == len(self.reference_wavelengths) and np.allclose(in_wl, self.reference_wavelengths, atol=1e-2):
            return in_int

        # Perform 1D interpolation with boundary extrapolation if within small tolerance
        interpolator = interp1d(in_wl, in_int, kind='linear', fill_value='extrapolate', bounds_error=False)
        aligned_intensities = interpolator(self.reference_wavelengths)
        return aligned_intensities

    def fit(self, X: np.ndarray, y=None):
        """
        Fit SNV and StandardScaler on spectral matrix X (shape: [n_samples, n_wavelengths]).
        """
        X = np.asarray(X, dtype=np.float64)
        # Handle any NaN/Inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Apply SNV
        X_snv = self.snv.transform(X)
        # Fit scaler
        self.scaler.fit(X_snv)
        self.is_fitted = True
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Transform spectral matrix X through SNV and StandardScaler.
        """
        X = np.asarray(X, dtype=np.float64)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        X_snv = self.snv.transform(X)
        if self.is_fitted:
            return self.scaler.transform(X_snv)
        return X_snv

    def fit_transform(self, X: np.ndarray, y=None) -> np.ndarray:
        return self.fit(X, y).transform(X)
