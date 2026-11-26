"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - SVM MODEL TRAINING PIPELINE
=============================================================================
Trains an SVM classification model on NIR spectroscopy data with:
  1. Dataset loading (supports wide or long format CSV)
  2. Data validation & missing value handling
  3. DATA LEAKAGE PREVENTION:
     Grouping by 'Physical_Sample_ID' via GroupShuffleSplit so replicate
     scans of the same cloth piece are NEVER split across train and test!
  4. Spectral Preprocessing (SNV baseline correction + Feature Scaling)
  5. Kernel comparison (RBF vs Linear) & GridSearchCV hyperparameter tuning
  6. Artifact export (fabric_svm.pkl, scaler.pkl, wavelengths.json, 
     class_names.json, model_metadata.json)
=============================================================================
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from typing import Tuple, List

from sklearn.svm import SVC
from sklearn.model_selection import GroupShuffleSplit, StratifiedShuffleSplit, GridSearchCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Add parent directory to path to import preprocessor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from preprocessing.preprocessor import SpectralPreprocessor


def load_dataset(csv_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[float]]:
    """
    Load dataset from CSV. Handles both Wide format and Long format.
    Returns:
      X: Spectral intensity matrix (n_samples, n_wavelengths)
      y: Fabric class labels (n_samples,)
      groups: Physical sample IDs for leakage-free splitting (n_samples,)
      wavelengths: List of wavelength feature values (floats)
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}. Run generate_sample_dataset.py first.")

    df = pd.read_csv(csv_path)

    # Detect Long format vs Wide format
    if 'Wavelength' in df.columns and 'Intensity' in df.columns:
        print("[DATASET] Detected Long format CSV. Pivoting to wide format...")
        pivot_df = df.pivot_table(
            index=['Sample_ID', 'Fabric', 'Physical_Sample_ID'],
            columns='Wavelength',
            values='Intensity'
        ).reset_index()
        df = pivot_df

    # Extract meta columns
    meta_cols = ['Sample_ID', 'Fabric', 'Physical_Sample_ID', 'timestamp']
    wl_cols = [c for c in df.columns if c not in meta_cols]
    
    # Sort wavelength columns numerically
    try:
        wl_numeric = [float(c) for c in wl_cols]
        sorted_pairs = sorted(zip(wl_numeric, wl_cols))
        wavelengths = [p[0] for p in sorted_pairs]
        sorted_wl_cols = [p[1] for p in sorted_pairs]
    except ValueError:
        wavelengths = [float(i) for i in range(len(wl_cols))]
        sorted_wl_cols = wl_cols

    # Features, targets, and physical sample groups
    X = df[sorted_wl_cols].values.astype(np.float64)
    y = df['Fabric'].values.astype(str)

    if 'Physical_Sample_ID' in df.columns:
        groups = df['Physical_Sample_ID'].values
    else:
        print("[WARNING] 'Physical_Sample_ID' column missing. Using Sample_ID (sample grouping disabled).")
        groups = df['Sample_ID'].values

    # Handle missing / NaN values
    if np.isnan(X).any():
        print("[DATASET] Imputing missing values with column means...")
        col_means = np.nanmean(X, axis=0)
        inds = np.where(np.isnan(X))
        X[inds] = np.take(col_means, inds[1])

    return X, y, groups, wavelengths


def train_svm_pipeline(
    csv_path: str = "ml/dataset/collected_samples.csv",
    output_dir: str = "ml/models",
    test_size: float = 0.25,
    random_state: int = 42
):
    print("=================================================================")
    print("      FABRIC IDENTIFICATION SYSTEM - SVM TRAINING PIPELINE      ")
    print("=================================================================")

    # 1. Load Data
    X, y, groups, wavelengths = load_dataset(csv_path)
    classes = sorted(list(set(y)))
    print(f"[1] Loaded dataset: {X.shape[0]} samples, {X.shape[1]} wavelength bands.")
    print(f"    Classes: {classes}")
    print(f"    Unique physical fabric samples: {len(np.unique(groups))}")

    # 2. DATA LEAKAGE PREVENTION: Split by physical sample piece if >= 2 pieces per class
    # Ensure each class has at least 2 distinct physical pieces before using GroupShuffleSplit
    can_group_split = True
    for cls in classes:
        cls_groups = set(groups[y == cls])
        if len(cls_groups) < 2:
            can_group_split = False
            break

    if can_group_split:
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
        train_idx, test_idx = next(gss.split(X, y, groups=groups))
        split_strategy = "GroupShuffleSplit by Physical_Sample_ID"
        leakage_prevented = True
    else:
        print("[WARNING] Fewer than 2 physical pieces per class; using StratifiedShuffleSplit for initial training.")
        sss = StratifiedShuffleSplit(n_splits=1, test_size=max(test_size, len(classes) / len(y)), random_state=random_state)
        train_idx, test_idx = next(sss.split(X, y))
        split_strategy = "StratifiedShuffleSplit (single physical piece per class)"
        leakage_prevented = False

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    groups_train, groups_test = groups[train_idx], groups[test_idx]

    if can_group_split:
        train_pieces = set(groups_train)
        test_pieces = set(groups_test)
        overlap = train_pieces.intersection(test_pieces)
        assert len(overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping pieces: {overlap}"
        print(f"[2] Data Leakage Prevention verified: 0 overlapping physical pieces.")
    else:
        print(f"[2] Stratified split completed.")

    print(f"    Train set: {len(X_train)} scans | Test set: {len(X_test)} scans.")

    # 3. Preprocessing (SNV + Feature Scaling)
    preprocessor = SpectralPreprocessor(reference_wavelengths=wavelengths)
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    # 4. Kernel Comparison: Linear vs RBF
    print("\n[3] Comparing SVM Kernels...")
    svm_linear = SVC(kernel='linear', C=1.0, probability=True, random_state=random_state)
    svm_linear.fit(X_train_proc, y_train)
    acc_linear = accuracy_score(y_test, svm_linear.predict(X_test_proc))
    print(f"    Linear Kernel Test Accuracy: {acc_linear * 100:.2f}%")

    svm_rbf = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True, random_state=random_state)
    svm_rbf.fit(X_train_proc, y_train)
    acc_rbf = accuracy_score(y_test, svm_rbf.predict(X_test_proc))
    print(f"    RBF Kernel Test Accuracy:    {acc_rbf * 100:.2f}%")

    # 5. Hyperparameter Tuning via GridSearchCV
    min_class_count = min([np.sum(y_train == c) for c in classes])
    if min_class_count >= 2:
        cv_folds = min(3, int(min_class_count))
        print(f"\n[4] Optimizing Hyperparameters via GridSearchCV (cv={cv_folds})...")
        param_grid = {
            'C': [0.1, 1.0, 10.0, 100.0],
            'gamma': ['scale', 'auto', 0.01, 0.001],
            'kernel': ['rbf', 'linear']
        }

        grid = GridSearchCV(
            SVC(probability=True, random_state=random_state),
            param_grid,
            cv=cv_folds,
            n_jobs=-1,
            scoring='accuracy'
        )
        grid.fit(X_train_proc, y_train)
        best_svm = grid.best_estimator_
        best_params = grid.best_params_
        print(f"    Best Params: {best_params}")
    else:
        print("\n[4] Small sample count; using calibrated Linear/RBF SVM directly.")
        best_svm = svm_rbf if acc_rbf >= acc_linear else svm_linear
        best_params = {'kernel': best_svm.kernel, 'C': 1.0, 'gamma': 'scale'}

    # Re-fit final model on ALL collected samples so small datasets get maximum coverage,
    # while reporting the honest test_accuracy from the holdout split above.
    y_pred = best_svm.predict(X_test_proc)
    test_accuracy = accuracy_score(y_test, y_pred)
    print(f"\n[5] Holdout Test Accuracy: {test_accuracy * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, digits=3, zero_division=0))

    cm = confusion_matrix(y_test, y_pred, labels=classes)
    print("Confusion Matrix:")
    print(f"Classes: {classes}")
    print(cm)

    # Fit final production preprocessor & SVM on full dataset for best real-time generalization
    final_preprocessor = SpectralPreprocessor(reference_wavelengths=wavelengths)
    X_full_proc = final_preprocessor.fit_transform(X)
    final_svm = SVC(**{k: v for k, v in best_params.items() if k in ['C', 'gamma', 'kernel']},
                    probability=True, random_state=random_state)
    final_svm.fit(X_full_proc, y)

    # 7. Save Model Artifacts
    os.makedirs(output_dir, exist_ok=True)
    
    # Save model and preprocessor scaler
    model_path = os.path.join(output_dir, "fabric_svm.pkl")
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    wl_path = os.path.join(output_dir, "wavelengths.json")
    classes_path = os.path.join(output_dir, "class_names.json")
    meta_path = os.path.join(output_dir, "model_metadata.json")
    ref_path = os.path.join(output_dir, "reference_samples.json")

    joblib.dump(final_svm, model_path)
    joblib.dump(final_preprocessor.scaler, scaler_path)

    with open(wl_path, "w") as f:
        json.dump(wavelengths, f, indent=2)

    with open(classes_path, "w") as f:
        json.dump(classes, f, indent=2)

    # Save reference samples (class centroids + sample list) for similarity matching
    df_raw = pd.read_csv(csv_path)
    ref_samples = []
    for idx in range(len(X)):
        sample_id = str(df_raw.iloc[idx]['Sample_ID']) if 'Sample_ID' in df_raw.columns else f"REF_{idx+1:04d}"
        phys_id = str(groups[idx])
        ref_samples.append({
            "sample_id": sample_id,
            "fabric": str(y[idx]),
            "physical_sample_id": phys_id,
            "intensity": [round(float(v), 2) for v in X[idx]],
            "snv_vector": [round(float(v), 4) for v in final_preprocessor.snv.transform(X[idx:idx+1])[0]]
        })

    with open(ref_path, "w") as f:
        json.dump(ref_samples, f, indent=2)

    metadata = {
        "model": "SVM",
        "version": "svm_v1",
        "kernel": best_params.get('kernel', 'rbf'),
        "best_params": best_params,
        "classes": classes,
        "wavelength_range": [float(wavelengths[0]), float(wavelengths[-1])],
        "num_wavelengths": len(wavelengths),
        "num_training_samples": int(len(X)),
        "accuracy": round(float(test_accuracy), 4),
        "data_leakage_prevented": leakage_prevented,
        "split_strategy": split_strategy
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print("\n[6] Successfully saved model artifacts:")
    print(f"    - Model:        {model_path}")
    print(f"    - Scaler:       {scaler_path}")
    print(f"    - Wavelengths:  {wl_path}")
    print(f"    - Class Names:  {classes_path}")
    print(f"    - Reference:    {ref_path} ({len(ref_samples)} samples)")
    print(f"    - Metadata:     {meta_path}")

    return final_svm, metadata

if __name__ == "__main__":
    collected_file = "ml/dataset/collected_samples.csv"
    fallback_file = "ml/dataset/fabric_dataset_wide.csv"
    dataset_file = collected_file if os.path.exists(collected_file) else fallback_file

    if not os.path.exists(dataset_file):
        print("[TRAIN] Dataset missing. Generating benchmark...")
        from dataset.generate_sample_dataset import generate_benchmark_dataset
        generate_benchmark_dataset()
        dataset_file = fallback_file

    train_svm_pipeline(csv_path=dataset_file)
