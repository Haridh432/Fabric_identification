"""
=============================================================================
FABRIC IDENTIFICATION SYSTEM - FIREBASE SYNC & LISTENER SERVICE
=============================================================================
Monitors Firebase Realtime Database for new raw spectral scans:

1. Detects scans with status == "raw"
2. Reads wavelength and intensity data
3. Runs SVM V2 prediction
4. Writes a simple prediction result to the same scan node
5. Keeps the Firebase prediction structure simple
6. Updates backend heartbeat
=============================================================================
"""

import os
import time
import threading
import requests
from typing import Optional, Dict, Any

from ml_service import ml_service

class FirebaseSyncService:

    def __init__(self):
        self.database_url = os.getenv(
            "FIREBASE_DATABASE_URL",
            ""
        ).rstrip("/")

        self.credentials_path = os.getenv(
            "FIREBASE_CREDENTIALS_PATH",
            "serviceAccountKey.json"
        )

        self.is_running = False
        self.is_connected = False
        self.thread: Optional[threading.Thread] = None

        # Prevent processing the same scan repeatedly
        self.processed_scans = set()

        self.init_firebase()

    # =========================================================================
    # FIREBASE INITIALIZATION
    # =========================================================================

    def init_firebase(self):
        """
        Initialize Firebase connection.

        This project uses the Firebase Realtime Database REST API,
        so no Firebase Admin SDK is required here.
        """

        if not self.database_url:
            print(
                "[FirebaseSync] No FIREBASE_DATABASE_URL configured. "
                "Running in standalone API mode."
            )
            return

        print(
            f"[FirebaseSync] Using Firebase Realtime Database: "
            f"{self.database_url}"
        )

        self.is_connected = True

    # =========================================================================
    # START LISTENER
    # =========================================================================

    def start_listener(self):
        """
        Start background Firebase listener.
        """

        if self.is_running:
            return

        if not self.database_url:
            print(
                "[FirebaseSync] Cannot start listener: "
                "FIREBASE_DATABASE_URL is not set."
            )
            return

        self.is_running = True

        self.thread = threading.Thread(
            target=self._sync_loop,
            daemon=True
        )

        self.thread.start()

        print(
            "[FirebaseSync] Background sync listener thread started."
        )

    # =========================================================================
    # STOP LISTENER
    # =========================================================================

    def stop_listener(self):
        """
        Stop Firebase background listener.
        """

        self.is_running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        print(
            "[FirebaseSync] Background sync listener stopped."
        )

    # =========================================================================
    # MAIN SYNC LOOP
    # =========================================================================

    def _sync_loop(self):
        """
        Continuously check Firebase for raw scans.
        """

        last_heartbeat = 0

        while self.is_running:

            try:

                now = time.time()

                # Update backend heartbeat every 15 seconds
                if now - last_heartbeat > 15:

                    self.update_backend_heartbeat()

                    last_heartbeat = now

                # Process new scans
                self._process_pending_scans()

            except Exception as e:

                print(
                    f"[FirebaseSync ERROR] Sync cycle failed: {e}"
                )

            # Check Firebase every 2 seconds
            time.sleep(2.0)

    # =========================================================================
    # PROCESS RAW SCANS
    # =========================================================================

    def _process_pending_scans(self):
        """
        Find Firebase scans with:

            status == "raw"

        and run SVM prediction.
        """

        if not self.database_url:
            return

        url = (
            f"{self.database_url}"
            f"/fabric_scans.json"
            f"?orderBy=\"status\""
            f"&equalTo=\"raw\""
        )

        try:

            response = requests.get(
                url,
                timeout=5
            )

            if not response.ok:
                return

            scans = response.json()

            if not scans or not isinstance(scans, dict):
                return

            for scan_key, scan_data in scans.items():

                if not isinstance(scan_data, dict):
                    continue

                # Use scan_id if available
                scan_id = scan_data.get(
                    "scan_id",
                    scan_key
                )

                # Prevent duplicate processing
                if scan_id in self.processed_scans:
                    continue

                wavelengths = scan_data.get(
                    "wavelength"
                )

                intensities = scan_data.get(
                    "intensity"
                )

                # Validate spectral data
                if not wavelengths or not intensities:

                    print(
                        f"[FirebaseSync] Scan {scan_id} "
                        "missing wavelength/intensity data."
                    )

                    self._update_scan_error(
                        scan_id,
                        "Missing wavelength or intensity data"
                    )

                    self.processed_scans.add(scan_id)

                    continue

                print(
                    f"[FirebaseSync] New raw scan detected: "
                    f"{scan_id}"
                )

                print(
                    f"[FirebaseSync] Running SVM V2 prediction..."
                )

                try:

                    # ---------------------------------------------------------
                    # RUN ML PREDICTION
                    # ---------------------------------------------------------

                    prediction = ml_service.predict_fabric(
                        scan_id=scan_id,
                        wavelengths=wavelengths,
                        intensities=intensities,
                        timestamp=scan_data.get(
                            "timestamp"
                        )
                    )

                    fabric = prediction["fabric"]

                    confidence = float(
                        prediction["confidence"]
                    )

                    print(
                        f"[FirebaseSync] Prediction: "
                        f"{fabric} "
                        f"({confidence * 100:.2f}%)"
                    )

                    # ---------------------------------------------------------
                    # WRITE SIMPLE RESULT TO FIREBASE
                    # ---------------------------------------------------------

                    self._update_scan_prediction(
                        scan_id,
                        prediction,
                        scan_data
                    )

                except Exception as error:

                    print(
                        f"[FirebaseSync] Prediction error "
                        f"for {scan_id}: {error}"
                    )

                    self._update_scan_error(
                        scan_id,
                        str(error)
                    )

                # Mark as processed
                self.processed_scans.add(scan_id)

        except requests.exceptions.RequestException:
            # Temporary Firebase/network issue
            pass

    # =========================================================================
    # WRITE PREDICTION
    # =========================================================================

    def _update_scan_prediction(
        self,
        scan_id: str,
        prediction: Dict[str, Any],
        scan_data: Dict[str, Any]
    ):
        """
        Write ONLY the simple prediction result.

        Firebase structure:

        fabric_scans
        └── SCAN_000001
            ├── scan_id
            ├── time
            ├── predicted_fabric
            └── confidence

        No spectrum values.
        No probabilities.
        No model name.
        """

        # -------------------------------------------------------------
        # GET PREDICTION VALUES
        # -------------------------------------------------------------

        fabric = prediction["fabric"]

        # Convert 0.8245 → 82.45
        confidence = round(
            float(prediction["confidence"]) * 100,
            2
        )

        # -------------------------------------------------------------
        # GET TIME
        # -------------------------------------------------------------

        # If the incoming scan already has a timestamp,
        # use it. Otherwise use current local time.

        timestamp = scan_data.get("timestamp")

        if timestamp:

            try:

                # Handle milliseconds timestamp
                if timestamp > 100000000000:

                    prediction_time = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(
                            timestamp / 1000
                        )
                    )

                else:

                    prediction_time = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(timestamp)
                    )

            except Exception:

                prediction_time = time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        else:

            prediction_time = time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        # -------------------------------------------------------------
        # SIMPLE FIREBASE PAYLOAD
        # -------------------------------------------------------------

        payload = {

            "scan_id": scan_id,

            "time": prediction_time,

            "predicted_fabric": fabric,

            "confidence": confidence

        }

        # -------------------------------------------------------------
        # WRITE TO THE SAME SCAN NODE
        # -------------------------------------------------------------

        firebase_url = (
            f"{self.database_url}"
            f"/fabric_scans/{scan_id}.json"
        )

        try:

            response = requests.patch(
                firebase_url,
                json=payload,
                timeout=5
            )

            if response.ok:

                print(
                    f"[FirebaseSync] Firebase updated: "
                    f"{scan_id}"
                )

                print(
                    f"[FirebaseSync] "
                    f"Fabric = {fabric}, "
                    f"Confidence = {confidence}%"
                )

            else:

                print(
                    f"[FirebaseSync ERROR] "
                    f"Firebase returned HTTP "
                    f"{response.status_code}"
                )

        except Exception as error:

            print(
                f"[FirebaseSync ERROR] "
                f"Failed to write prediction "
                f"for {scan_id}: {error}"
            )

    # =========================================================================
    # ERROR UPDATE
    # =========================================================================

    def _update_scan_error(
        self,
        scan_id: str,
        error_message: str
    ):
        """
        Mark a scan as error.

        Note:
        This only adds error information to the scan.
        """

        payload = {

            "status": "error",

            "error_message": error_message

        }

        firebase_url = (
            f"{self.database_url}"
            f"/fabric_scans/{scan_id}.json"
        )

        try:

            requests.patch(
                firebase_url,
                json=payload,
                timeout=5
            )

        except Exception:
            pass

    # =========================================================================
    # BACKEND HEARTBEAT
    # =========================================================================

    def update_backend_heartbeat(self):
        """
        Check Firebase connectivity.
        """

        if not self.database_url:
            return

        try:

            response = requests.get(
                f"{self.database_url}"
                f"/fabric_scans.json"
                f"?shallow=true",
                timeout=5
            )

            self.is_connected = response.ok

        except Exception:

            self.is_connected = False


# =============================================================================
# GLOBAL FIREBASE SERVICE INSTANCE
# =============================================================================

firebase_sync_service = FirebaseSyncService()