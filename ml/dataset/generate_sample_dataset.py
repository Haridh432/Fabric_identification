"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - BENCHMARK DATASET GENERATOR
=============================================================================
Generates a realistic NIR spectroscopy dataset based on established molecular
absorption bands for 4 fabric classes:
  - Cotton (Cellulose C-H / O-H overtone bands: 1200nm, 1480nm)
  - Polyester (Polyethylene terephthalate aromatic C-H / C=O: 1120nm, 1660nm)
  - Nylon (Polyamide N-H / C=O peptide linkage: 1220nm, 1500nm)
  - Silk (Natural protein Fibroin amide I/II/III combinations: 1420nm, 1630nm)

Crucially incorporates 'Physical_Sample_ID' grouping:
Multiple scan replicates are acquired per physical piece of fabric.
This allows demonstration of Data Leakage Prevention during Train/Test split!
=============================================================================
"""

import os
import json
import numpy as np
import pandas as pd

def generate_benchmark_dataset(
    output_wide_path: str = "ml/dataset/fabric_dataset_wide.csv",
    output_long_path: str = "data/raw/fabric_dataset_long.csv",
    samples_per_class: int = 10,
    scans_per_sample: int = 8,
    random_seed: int = 42
):
    np.random.seed(random_seed)

    classes = ["Cotton", "Nylon", "Polyester", "Silk"]
    
    # NIR spectral range: 900 nm to 1700 nm, 20 nm resolution (41 bands)
    wavelengths = np.arange(900, 1720, 20)
    wl_cols = [str(w) for w in wavelengths]

    wide_rows = []
    long_rows = []

    scan_counter = 1

    for fabric in classes:
        for sample_idx in range(1, samples_per_class + 1):
            physical_id = f"SAMPLE_{fabric.upper()}_{sample_idx:02d}"
            
            # Physical piece baseline variation (weave density, moisture level)
            piece_baseline_shift = np.random.uniform(-400, 400)
            piece_curve_tilt = np.random.uniform(0.95, 1.05)

            for scan_rep in range(1, scans_per_sample + 1):
                scan_id = f"SCAN_{scan_counter:06d}"
                scan_counter += 1

                # Generate spectral response
                norm_wl = (wavelengths - 900.0) / 800.0
                base_curve = (11500.0 + 3200.0 * np.sin(norm_wl * np.pi)) * piece_curve_tilt + piece_baseline_shift

                # Signature absorption bands
                if fabric == "Cotton":
                    dip1 = 2800.0 * np.exp(-((wavelengths - 1480.0) / 45.0) ** 2)
                    dip2 = 1200.0 * np.exp(-((wavelengths - 1200.0) / 30.0) ** 2)
                    dip3 = 800.0 * np.exp(-((wavelengths - 1050.0) / 25.0) ** 2)
                    spectrum = base_curve - dip1 - dip2 - dip3
                elif fabric == "Polyester":
                    dip1 = 2200.0 * np.exp(-((wavelengths - 1120.0) / 35.0) ** 2)
                    dip2 = 3100.0 * np.exp(-((wavelengths - 1660.0) / 40.0) ** 2)
                    dip3 = 900.0 * np.exp(-((wavelengths - 1380.0) / 30.0) ** 2)
                    spectrum = base_curve - dip1 - dip2 - dip3
                elif fabric == "Nylon":
                    dip1 = 2600.0 * np.exp(-((wavelengths - 1500.0) / 35.0) ** 2)
                    dip2 = 1700.0 * np.exp(-((wavelengths - 1220.0) / 30.0) ** 2)
                    dip3 = 1100.0 * np.exp(-((wavelengths - 1020.0) / 25.0) ** 2)
                    spectrum = base_curve - dip1 - dip2 - dip3
                elif fabric == "Silk":
                    dip1 = 2100.0 * np.exp(-((wavelengths - 1420.0) / 40.0) ** 2)
                    dip2 = 2400.0 * np.exp(-((wavelengths - 1630.0) / 35.0) ** 2)
                    dip3 = 1300.0 * np.exp(-((wavelengths - 1190.0) / 30.0) ** 2)
                    spectrum = base_curve - dip1 - dip2 - dip3

                # Sensor noise
                noise = np.random.normal(0, 45, size=len(wavelengths))
                final_intensities = np.clip(np.round(spectrum + noise), 100, 65000)

                # Add to wide format
                row = {
                    "Sample_ID": scan_id,
                    "Fabric": fabric,
                    "Physical_Sample_ID": physical_id
                }
                for w, val in zip(wl_cols, final_intensities):
                    row[w] = float(val)
                wide_rows.append(row)

                # Add to long format
                for w_val, val in zip(wavelengths, final_intensities):
                    long_rows.append({
                        "Sample_ID": scan_id,
                        "Fabric": fabric,
                        "Physical_Sample_ID": physical_id,
                        "Wavelength": float(w_val),
                        "Intensity": float(val)
                    })

    df_wide = pd.DataFrame(wide_rows)
    df_long = pd.DataFrame(long_rows)

    # Save to disk
    os.makedirs(os.path.dirname(output_wide_path), exist_ok=True)
    os.makedirs(os.path.dirname(output_long_path), exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)

    df_wide.to_csv(output_wide_path, index=False)
    # Also save a copy in data/raw
    df_wide.to_csv("data/raw/fabric_dataset_wide.csv", index=False)
    df_long.to_csv(output_long_path, index=False)

    print(f"[OK] Generated {len(df_wide)} spectral scans across {len(classes)} fabric types.")
    print(f"[OK] Total physical fabric pieces: {samples_per_class * len(classes)} ({scans_per_sample} scans each).")
    print(f"[OK] Wide dataset saved to: {output_wide_path} and data/raw/fabric_dataset_wide.csv")
    print(f"[OK] Long dataset saved to: {output_long_path}")

    return df_wide

if __name__ == "__main__":
    generate_benchmark_dataset()
