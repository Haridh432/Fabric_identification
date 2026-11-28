import joblib
import json

MODEL_PATH = "models/fabric_svm_pipeline_v2.pkl"
METADATA_PATH = "models/model_metadata_v2.json"

# Load model
model = joblib.load(MODEL_PATH)

# Load metadata
with open(METADATA_PATH, "r") as f:
    metadata = json.load(f)

print("================================")
print("MODEL LOADED SUCCESSFULLY")
print("================================")

print("Classes:", metadata["classes"])
print("Wavelengths:", metadata["wavelengths"])
print("Preprocessing:", metadata["preprocessing"])

print(f"Test Accuracy: {metadata['test_accuracy'] * 100:.2f}%")
print(f"CV Accuracy: {metadata['cv_accuracy'] * 100:.2f}%")
print(f"CV Std: {metadata['cv_std'] * 100:.2f}%")

print("\nModel classes:")
print(model.classes_)

print("================================")