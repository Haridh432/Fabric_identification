import joblib
import numpy as np

MODEL_PATH = "models/fabric_svm_pipeline_v2.pkl"

# Load trained model
model = joblib.load(MODEL_PATH)


def snv(X):
    X = np.asarray(X, dtype=np.float64)

    mean = np.mean(X, axis=1, keepdims=True)
    std = np.std(X, axis=1, keepdims=True)

    std[std == 0] = 1.0

    return (X - mean) / std


# 18-channel AS7265x spectrum
# Example spectrum
intensity = [
    172.98,
    41.50,
    55.11,
    16.23,
    46.58,
    28.37,
    17.73,
    26.02,
    43.21,
    8.73,
    5.46,
    2.79,
    83.44,
    74.15,
    13.17,
    7.84,
    29.16,
    117.75
]

# Check number of channels
if len(intensity) != 18:
    raise ValueError(
        f"Expected 18 wavelength values, got {len(intensity)}"
    )

# Convert to 2D array
spectrum = np.array(intensity, dtype=np.float64).reshape(1, -1)

# Apply SNV
spectrum_snv = snv(spectrum)

# Predict
prediction = model.predict(spectrum_snv)[0]

# Get probabilities
probabilities = model.predict_proba(spectrum_snv)[0]

print("\n================================")
print("     FABRIC IDENTIFICATION")
print("================================")

print(f"\nPredicted Fabric : {prediction}")

print("\nProbability:")
for fabric, probability in zip(model.classes_, probabilities):
    print(f"{fabric:12s}: {probability * 100:.2f}%")

print("\nConfidence      : "
      f"{np.max(probabilities) * 100:.2f}%")

print("================================")