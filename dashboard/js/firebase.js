/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - FIREBASE CLIENT SERVICE (PURE REAL-TIME)
 * ============================================================================
 * Handles live communication with Firebase Realtime Database.
 * 
 * Supports:
 *  - Real-time polling and streaming for scans under /fabric_scans
 *  - Real-time listening for ESP32 device status under /device/esp32
 *  - Writing ML predictions back to Firebase
 * ============================================================================
 */

class FirebaseService {
    constructor() {
        let savedUrl = localStorage.getItem('fabric_firebase_url');
        if (!savedUrl) {
            // Default to configured database URL
            savedUrl = 'https://fabric-identification-da466-default-rtdb.asia-southeast1.firebasedatabase.app';
        }
        this.databaseUrl = this.sanitizeUrl(savedUrl);
        
        this.onNewScanCallback = null;
        this.onDeviceStatusCallback = null;
        this.onConnectionChangeCallback = null;

        this.eventSource = null;
        this.pollInterval = null;
        this.heartbeatInterval = null;
        this.isConnected = false;
        this.latestScanId = null;
    }

    sanitizeUrl(url) {
        if (!url) return '';
        let clean = url.trim().replace(/\/+$/, '');
        if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
            clean = 'https://' + clean;
        }
        return clean;
    }

    /**
     * Configure Firebase parameters and persist to localStorage
     */
    configure(databaseUrl) {
        this.databaseUrl = this.sanitizeUrl(databaseUrl);
        localStorage.setItem('fabric_firebase_url', this.databaseUrl);
        localStorage.removeItem('fabric_simulation_mode');

        this.disconnect();
        this.connect();
    }

    /**
     * Connect to Firebase Realtime Database
     */
    connect() {
        if (!this.databaseUrl) {
            console.log('[FirebaseService] Firebase URL not configured. Click Settings to enter URL.');
            this.setConnected(false, 'Not Configured');
            return;
        }

        console.log(`[FirebaseService] Connecting to Firebase Realtime DB: ${this.databaseUrl}`);
        this.startPolling();
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
        this.setConnected(false, 'Disconnected');
    }

    setConnected(connected, statusText) {
        this.isConnected = connected;
        if (this.onConnectionChangeCallback) {
            this.onConnectionChangeCallback(connected, statusText);
        }
    }

    /**
     * Fast 1.2-second polling of the latest scan under /fabric_scans
     */
    startPolling() {
        const fetchLatest = async () => {
            if (!this.databaseUrl) return;
            try {
                // Fetch recent scans with proper JSON quoting
                const url = `${this.databaseUrl}/fabric_scans.json?shallow=false`;
                const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
                
                if (response.status === 401) {
                    this.setConnected(false, 'Rules Locked (401)');
                    return;
                }

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();
                this.setConnected(true, 'Connected');

                if (data && typeof data === 'object') {
                    const keys = Object.keys(data);
                    if (keys.length > 0) {
                        // Pick the latest key
                        const scanKey = keys[keys.length - 1];
                        const scan = data[scanKey];
                        
                        if (scan && scan.scan_id) {
                            // Normalize clean spectrum map ("410nm": 219.5) back into arrays for dashboard
                            if (!scan.wavelength && scan.spectrum && typeof scan.spectrum === 'object') {
                                const entries = Object.entries(scan.spectrum)
                                    .map(([k, v]) => [parseFloat(k.replace(/nm$/i, '')), Number(v)])
                                    .sort((a, b) => a[0] - b[0]);
                                scan.wavelength = entries.map(e => e[0]);
                                scan.intensity = entries.map(e => e[1]);
                            }
                            if (!scan.prediction && scan.fabric) {
                                const confNum = typeof scan.confidence === 'string'
                                    ? parseFloat(scan.confidence.replace('%', ''))
                                    : Number(scan.confidence || 0);
                                scan.prediction = {
                                    fabric: scan.fabric,
                                    confidence: confNum,
                                    model_version: 'svm_v1'
                                };
                            }

                            if (this.latestScanId !== scan.scan_id || (scan.prediction && scan.prediction.fabric)) {
                                this.latestScanId = scan.scan_id;
                                if (this.onNewScanCallback) {
                                    this.onNewScanCallback(scan);
                                }
                            }
                        }
                    }
                }
            } catch (err) {
                this.setConnected(false, 'Offline');
            }
        };

        fetchLatest();
        this.pollInterval = setInterval(fetchLatest, 1500);
    }

    /**
     * Monitor ESP32 device status node: /device/esp32.json
     */
    startDeviceHeartbeatCheck() {
        const checkHeartbeat = async () => {
            if (!this.databaseUrl) return;
            try {
                const response = await fetch(`${this.databaseUrl}/device/esp32.json`);
                if (response.ok) {
                    const status = await response.json();
                    if (this.onDeviceStatusCallback && status) {
                        this.onDeviceStatusCallback(status);
                    }
                }
            } catch (err) {
                // Handled gracefully
            }
        };

        checkHeartbeat();
        this.heartbeatInterval = setInterval(checkHeartbeat, 3000);
    }

    /**
     * Push a scan to Firebase
     */
    async pushScan(scanPayload) {
        if (!this.databaseUrl) return { success: false, error: 'Firebase URL not configured' };

        try {
            const url = `${this.databaseUrl}/fabric_scans/${scanPayload.scan_id}.json`;
            const response = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scanPayload)
            });
            return { success: response.ok, status: response.status };
        } catch (err) {
            console.error('[FirebaseService] pushScan error:', err);
            return { success: false, error: err.message };
        }
    }

    /**
     * Write prediction back to Firebase for a given scan ID
     */
    async writePrediction(scanId, predictionData) {
        if (!this.databaseUrl) return { success: false };

        try {
            const patchPayload = {
                status: 'processed',
                prediction: predictionData
            };
            const url = `${this.databaseUrl}/fabric_scans/${scanId}.json`;
            const response = await fetch(url, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patchPayload)
            });
            return { success: response.ok };
        } catch (err) {
            console.error('[FirebaseService] writePrediction error:', err);
            return { success: false, error: err.message };
        }
    }

    /**
     * Register Callbacks
     */
    onNewScan(callback) {
        this.onNewScanCallback = callback;
    }

    onDeviceStatus(callback) {
        this.onDeviceStatusCallback = callback;
    }

    onConnectionChange(callback) {
        this.onConnectionChangeCallback = callback;
    }
}

// Global instance
window.firebaseService = new FirebaseService();
