"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - MODEL EVALUATION MODULE
=============================================================================
Computes comprehensive performance metrics on test datasets:
  - Accuracy
  - Precision, Recall, F1-score (macro and per-class)
  - Confusion Matrix (clean ASCII formatting + JSON export)
  - Full Scikit-learn Classification Report
=============================================================================
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from preprocessing.preprocessor import SpectralPreprocessor
from train import load_dataset


def evaluate_model(
    model_dir: str = "ml/models",
    test_csv: str = "ml/dataset/fabric_dataset_wide.csv",
    output_report_path: str = "ml/models/evaluation_report.json"
):
    print("=================================================================")
    print("      FABRIC IDENTIFICATION SYSTEM - MODEL EVALUATION           ")
    print("=================================================================")

    # Load artifacts
    model_path = os.path.join(model_dir, "fabric_svm.pkl")
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    wl_path = os.path.join(model_dir, "wavelengths.json")
    classes_path = os.path.join(model_dir, "class_names.json")

    if not all(os.path.exists(p) for p in [model_path, scaler_path, wl_path, classes_path]):
        raise FileNotFoundError(f"Model artifacts not found in {model_dir}. Please run train.py first.")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    with open(wl_path, "r") as f:
        wavelengths = json.load(f)

    with open(classes_path, "r") as f:
        classes = json.load(f)

    # Load Dataset
    X, y, groups, _ = load_dataset(test_csv)

    # Preprocessing
    preprocessor = SpectralPreprocessor(reference_wavelengths=wavelengths)
    preprocessor.scaler = scaler
    preprocessor.is_fitted = True

    X_proc = preprocessor.transform(X)

    # Predictions
    y_pred = model.predict(X_proc)
    y_prob = model.predict_proba(X_proc) if hasattr(model, 'predict_proba') else None

    # Calculate Metrics
    accuracy = accuracy_score(y, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(y, y_pred, average='weighted')
    cm = confusion_matrix(y, y_pred, labels=classes)
    report_dict = classification_report(y, y_pred, labels=classes, output_dict=True)

    print(f"\nModel Performance Summary")
    print(f"-------------------------")
    print(f"Accuracy:  {accuracy * 100:.2f}%")
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall:    {recall * 100:.2f}%")
    print(f"F1-Score:  {f1 * 100:.2f}%")

    print("\nConfusion Matrix:")
    col_headers = " ".join([f"{c[:4]:>6}" for c in classes])
    print(f"              Predicted ->")
    print(f"              {col_headers}")
    for idx, true_class in enumerate(classes):
        row_vals = " ".join([f"{val:>6}" for val in cm[idx]])
        print(f"Actual {true_class[:4]:<6} {row_vals}")

    print("\nDetailed Classification Report:")
    print(classification_report(y, y_pred, labels=classes, digits=3))

    # Save to JSON
    eval_result = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "classes": classes,
        "confusion_matrix": cm.tolist(),
        "classification_report": report_dict
    }

    with open(output_report_path, "w") as f:
        json.dump(eval_result, f, indent=2)

    print(f"[OK] Evaluation results saved to {output_report_path}")
    return eval_result


if __name__ == "__main__":
    evaluate_model()
