"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - FIREBASE SYNC & LISTENER SERVICE
=============================================================================
Automatically monitors Firebase Realtime Database for new spectral scans:
  1. Detects scans with status == "raw"
  2. Extracts wavelength & intensity arrays
  3. Invokes MLService (identical preprocessing + SVM prediction)
  4. Writes prediction result back to the same Firebase scan node
  5. Updates status to "processed" (or "error" with descriptive message)
  6. Sends device status heartbeat for backend: /device/backend
  7. Supports both Firebase Admin SDK (credentials file) AND direct REST API
     polling/streaming for zero-config local development!
=============================================================================
"""

import os
import time
import json
import threading
import requests
from typing import Optional, Dict, Any

from ml_service import ml_service

# Optional Firebase Admin SDK import
try:
    import firebase_admin
    from firebase_admin import credentials, db
    HAS_FIREBASE_ADMIN = True
except ImportError:
    HAS_FIREBASE_ADMIN = False


class FirebaseSyncService:
    def __init__(self):
        self.database_url = os.getenv("FIREBASE_DATABASE_URL", "").rstrip("/")
        self.credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
        
        self.is_running = False
        self.is_connected = False
        self.thread: Optional[threading.Thread] = None
        self.processed_scans = set()  # In-memory deduplication set
        self.admin_initialized = False

        self.init_firebase()

    def init_firebase(self):
        """
        Initialize Firebase Admin SDK if credentials file exists,
        otherwise fallback to resilient REST API mode.
        """
        if not self.database_url:
            print("[FirebaseSync] No FIREBASE_DATABASE_URL configured. Running in standalone API mode.")
            return

        if HAS_FIREBASE_ADMIN and os.path.exists(self.credentials_path):
            try:
                if not firebase_admin._apps:
                    cred = credentials.Certificate(self.credentials_path)
                    firebase_admin.initialize_app(cred, {
                        'databaseURL': self.database_url
                    })
                self.admin_initialized = True
                self.is_connected = True
                print(f"[FirebaseSync] Initialized Firebase Admin SDK for: {self.database_url}")
            except Exception as e:
                print(f"[FirebaseSync WARNING] Failed to initialize Firebase Admin SDK: {e}. Falling back to REST mode.")
                self.admin_initialized = False
        else:
            print(f"[FirebaseSync] Using Firebase Realtime Database REST API sync at: {self.database_url}")
            self.is_connected = True

    def start_listener(self):
        """
        Start background worker thread to listen for new scans.
        """
        if self.is_running:
            return

        if not self.database_url:
            print("[FirebaseSync] Cannot start listener: FIREBASE_DATABASE_URL is not set.")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        print("[FirebaseSync] Background sync listener thread started.")

    def stop_listener(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        print("[FirebaseSync] Background sync listener stopped.")

    def _sync_loop(self):
        """
        Continuous loop polling /fabric_scans for raw items and updating device heartbeat.
        """
        last_heartbeat = 0

        while self.is_running:
            try:
                now = time.time()
                # Update backend heartbeat every 15 seconds
                if now - last_heartbeat > 15:
                    self.update_backend_heartbeat()
                    last_heartbeat = now

                self._process_pending_scans()
            except Exception as e:
                print(f"[FirebaseSync ERROR] Sync cycle failed: {e}")

            time.sleep(2.0)

    def _process_pending_scans(self):
        """
        Fetch scans where status == 'raw' and process them with SVM.
        """
        if not self.database_url:
            return

        # Fetch recent scans
        url = f"{self.database_url}/fabric_scans.json?orderBy=\"status\"&equalTo=\"raw\""
        try:
            resp = requests.get(url, timeout=5)
            if not resp.ok:
                return

            scans = resp.json()
            if not scans or not isinstance(scans, dict):
                return

            for scan_key, scan_data in scans.items():
                if not isinstance(scan_data, dict):
                    continue

                scan_id = scan_data.get("scan_id", scan_key)
                
                # Check deduplication
                if scan_id in self.processed_scans:
                    continue

                wavelengths = scan_data.get("wavelength")
                intensities = scan_data.get("intensity")

                if not wavelengths or not intensities:
                    print(f"[FirebaseSync] Scan {scan_id} missing spectral arrays. Marking as error.")
                    self._update_scan_error(scan_id, "Missing wavelength or intensity data")
                    self.processed_scans.add(scan_id)
                    continue

                print(f"[FirebaseSync] Detected new raw scan {scan_id}. Running SVM prediction...")
                pred_result = ml_service.predict(scan_id, wavelengths, intensities)

                if pred_result.get("error"):
                    print(f"[FirebaseSync] Prediction error for {scan_id}: {pred_result['error']}")
                    self._update_scan_error(scan_id, pred_result["error"])
                else:
                    print(f"[FirebaseSync] Predicted {scan_id} -> {pred_result['fabric']} ({pred_result['confidence']}%)")
                    self._update_scan_prediction(scan_id, pred_result)

                self.processed_scans.add(scan_id)

        except requests.exceptions.RequestException as e:
            # Temporary network / connection issue
            pass

    def _update_scan_prediction(self, scan_id: str, prediction: Dict[str, Any]):
        patch_payload = {
            "status": "processed",
            "prediction": {
                "fabric": prediction["fabric"],
                "confidence": prediction["confidence"],
                "model_version": prediction["model_version"]
            }
        }
        patch_url = f"{self.database_url}/fabric_scans/{scan_id}.json"
        try:
            requests.patch(patch_url, json=patch_payload, timeout=5)
        except Exception as e:
            print(f"[FirebaseSync ERROR] Failed to write prediction to Firebase for {scan_id}: {e}")

    def _update_scan_error(self, scan_id: str, error_message: str):
        patch_payload = {
            "status": "error",
            "error_message": error_message
        }
        patch_url = f"{self.database_url}/fabric_scans/{scan_id}.json"
        try:
            requests.patch(patch_url, json=patch_payload, timeout=5)
        except Exception as e:
            pass

    def update_backend_heartbeat(self):
        """
        Report backend status to /device/backend in Firebase.
        """
        if not self.database_url:
            return

        payload = {
            "connected": True,
            "last_seen": int(time.time() * 1000),
            "status": "online",
            "model_ready": ml_service.is_ready
        }
        url = f"{self.database_url}/device/backend.json"
        try:
            requests.put(url, json=payload, timeout=5)
            self.is_connected = True
        except Exception:
            self.is_connected = False


# Global instance
firebase_sync_service = FirebaseSyncService()
