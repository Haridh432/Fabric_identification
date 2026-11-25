/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - MAIN DASHBOARD CONTROLLER (PURE REAL-TIME)
 * ============================================================================
 * Orchestrates real-time hardware data:
 *  - Real-time spectrum visualization from physical ESP32 measurements
 *  - Raw data table rendering & filtering
 *  - Device and service connectivity status checks (ESP32, Sensor, Firebase, ML)
 *  - Integration with Python FastAPI ML Backend for live SVM inference
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    // ------------------------------------------------------------------------
    // Elements & State
    // ------------------------------------------------------------------------
    const statusEsp32El = document.getElementById('statusEsp32');
    const statusSensorEl = document.getElementById('statusSensor');
    const statusFirebaseEl = document.getElementById('statusFirebase');
    const statusMLEl = document.getElementById('statusML');

    const modePillEl = document.getElementById('modePill');
    const modeTextEl = document.getElementById('modeText');

    const tableBodyEl = document.getElementById('rawDataTableBody');
    const tableFilterEl = document.getElementById('tableFilterInput');
    const tableRowCountEl = document.getElementById('tableRowCount');

    const predictedFabricEl = document.getElementById('predictedFabric');
    const confidenceTextEl = document.getElementById('confidenceText');
    const confidenceBarEl = document.getElementById('confidenceBar');
    const resultBoxEl = document.getElementById('resultDisplayBox');
    const predictionStatusTagEl = document.getElementById('predictionStatus');

    const metaScanIdEl = document.getElementById('metaScanId');
    const metaTimestampEl = document.getElementById('metaTimestamp');
    const metaModelVersionEl = document.getElementById('metaModelVersion');
    const metaStatusEl = document.getElementById('metaStatus');

    const btnRequestPrediction = document.getElementById('btnRequestPrediction');

    // Config Modal Elements
    const configModalEl = document.getElementById('configModal');
    const btnConfigModal = document.getElementById('btnConfigModal');
    const btnCloseConfig = document.getElementById('btnCloseConfig');
    const btnCancelConfig = document.getElementById('btnCancelConfig');
    const btnSaveConfig = document.getElementById('btnSaveConfig');
    const cfgFirebaseUrlInput = document.getElementById('cfgFirebaseUrl');
    const cfgBackendUrlInput = document.getElementById('cfgBackendUrl');

    let currentScan = null;
    let currentRawTableData = [];
    let backendUrl = localStorage.getItem('fabric_backend_url') || 'http://localhost:8000';

    // ------------------------------------------------------------------------
    // Status Helpers
    // ------------------------------------------------------------------------
    function setStatus(element, state, text) {
        if (!element) return;
        element.classList.remove('online', 'offline', 'standby');
        element.classList.add(state);
        const val = element.querySelector('.status-val');
        if (val) val.textContent = text;
    }

    // ------------------------------------------------------------------------
    // Raw Table Population & Filtering
    // ------------------------------------------------------------------------
    function renderTable(wavelengths, intensities) {
        currentRawTableData = [];
        if (!wavelengths || !intensities || wavelengths.length === 0) {
            tableBodyEl.innerHTML = '<tr><td colspan="4" class="empty-state">Waiting for real-time spectral data from ESP32 sensor...</td></tr>';
            tableRowCountEl.textContent = '0 Bands';
            return;
        }

        const maxInt = Math.max(...intensities, 1);
        for (let i = 0; i < wavelengths.length; i++) {
            currentRawTableData.push({
                index: i + 1,
                wavelength: wavelengths[i],
                intensity: intensities[i],
                percent: ((intensities[i] / maxInt) * 100).toFixed(1)
            });
        }

        applyTableFilter();
    }

    function applyTableFilter() {
        const query = tableFilterEl ? tableFilterEl.value.trim().toLowerCase() : '';
        const filtered = currentRawTableData.filter(d => {
            if (!query) return true;
            return d.wavelength.toString().includes(query);
        });

        tableRowCountEl.textContent = `${filtered.length} / ${currentRawTableData.length} Bands`;

        if (filtered.length === 0) {
            tableBodyEl.innerHTML = '<tr><td colspan="4" class="empty-state">No matching wavelengths found.</td></tr>';
            return;
        }

        const html = filtered.map(d => `
            <tr>
                <td>${d.index}</td>
                <td><strong>${d.wavelength.toFixed(1)}</strong></td>
                <td>${Math.round(d.intensity).toLocaleString()}</td>
                <td>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="width:38px;">${d.percent}%</span>
                        <div style="flex:1; height:4px; background:rgba(255,255,255,0.08); border-radius:2px; overflow:hidden;">
                            <div style="width:${d.percent}%; height:100%; background:#38BDF8;"></div>
                        </div>
                    </div>
                </td>
            </tr>
        `).join('');

        tableBodyEl.innerHTML = html;
    }

    if (tableFilterEl) {
        tableFilterEl.addEventListener('input', applyTableFilter);
    }

    // ------------------------------------------------------------------------
    // Process Real-Time Incoming Scan from Physical ESP32
    // ------------------------------------------------------------------------
    function handleIncomingScan(scan) {
        if (!scan) return;
        currentScan = scan;

        // 1. Update Graph with real sensor wavelengths and intensities
        if (window.spectrumChart && scan.wavelength && scan.intensity) {
            window.spectrumChart.updateSpectrum(scan.wavelength, scan.intensity);
        }

        // 2. Update Table
        renderTable(scan.wavelength, scan.intensity);

        // 3. Inform Dataset Capture Manager
        if (window.captureManager) {
            window.captureManager.recordScan(scan);
        }

        // 4. Update Meta fields
        if (metaScanIdEl) metaScanIdEl.textContent = scan.scan_id || '--';
        if (metaTimestampEl) {
            const date = scan.timestamp ? new Date(scan.timestamp) : new Date();
            metaTimestampEl.textContent = date.toLocaleTimeString();
        }
        if (metaStatusEl) metaStatusEl.textContent = scan.status || 'raw';

        // 5. Check if prediction exists already in scan payload
        if (scan.prediction && scan.prediction.fabric) {
            displayPrediction(scan.prediction);
        } else {
            resetPredictionDisplay(scan.status || 'raw');
            autoTriggerBackendPrediction(scan);
        }
    }

    // ------------------------------------------------------------------------
    // Prediction Display
    // ------------------------------------------------------------------------
    function displayPrediction(pred) {
        if (!pred || !pred.fabric) return;

        const fabric = pred.fabric;
        const confidence = typeof pred.confidence === 'number' ? pred.confidence : 0;
        const version = pred.model_version || 'svm_v1';

        if (predictedFabricEl) predictedFabricEl.textContent = fabric;
        if (confidenceTextEl) confidenceTextEl.textContent = `${confidence.toFixed(1)}%`;
        if (confidenceBarEl) confidenceBarEl.style.width = `${Math.min(100, Math.max(0, confidence))}%`;
        if (metaModelVersionEl) metaModelVersionEl.textContent = version;

        if (predictionStatusTagEl) {
            predictionStatusTagEl.textContent = 'PROCESSED';
            predictionStatusTagEl.className = 'status-tag processed';
        }
        if (metaStatusEl) metaStatusEl.textContent = 'processed';

        // Apply theme color based on fabric
        if (resultBoxEl) {
            resultBoxEl.className = 'result-display-box';
            resultBoxEl.classList.add(fabric.toLowerCase());
        }
    }

    function resetPredictionDisplay(status) {
        if (predictedFabricEl) predictedFabricEl.textContent = '--';
        if (confidenceTextEl) confidenceTextEl.textContent = '0.0%';
        if (confidenceBarEl) confidenceBarEl.style.width = '0%';
        if (resultBoxEl) resultBoxEl.className = 'result-display-box';

        if (predictionStatusTagEl) {
            predictionStatusTagEl.textContent = (status || 'WAITING').toUpperCase();
            predictionStatusTagEl.className = `status-tag ${status || 'raw'}`;
        }
    }

    // ------------------------------------------------------------------------
    // ML Backend Real-Time Prediction
    // ------------------------------------------------------------------------
    async function autoTriggerBackendPrediction(scan) {
        if (!scan || !scan.wavelength || !scan.intensity) return;

        try {
            const response = await fetch(`${backendUrl}/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scan_id: scan.scan_id,
                    wavelength: scan.wavelength,
                    intensity: scan.intensity
                })
            });

            if (response.ok) {
                const result = await response.json();
                displayPrediction(result);
                if (window.firebaseService) {
                    window.firebaseService.writePrediction(scan.scan_id, result);
                }
            }
        } catch (err) {
            // Handled gracefully when backend is offline
        }
    }

    if (btnRequestPrediction) {
        btnRequestPrediction.addEventListener('click', async () => {
            if (!currentScan) {
                alert('No real-time scan available yet. Power on ESP32 or connect via USB.');
                return;
            }

            btnRequestPrediction.disabled = true;
            btnRequestPrediction.textContent = '⏳ Processing SVM...';

            try {
                const response = await fetch(`${backendUrl}/predict`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        scan_id: currentScan.scan_id,
                        wavelength: currentScan.wavelength,
                        intensity: currentScan.intensity
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    displayPrediction(result);
                    if (window.firebaseService) {
                        window.firebaseService.writePrediction(currentScan.scan_id, result);
                    }
                } else {
                    const errData = await response.json().catch(() => ({}));
                    alert(`Prediction failed: ${errData.detail || response.statusText}`);
                }
            } catch (err) {
                alert(`Could not connect to ML Backend at ${backendUrl}.\nRun: uvicorn backend.main:app --port 8000`);
            } finally {
                btnRequestPrediction.disabled = false;
                btnRequestPrediction.textContent = '🔍 Request SVM Prediction';
            }
        });
    }

    // ------------------------------------------------------------------------
    // Connectivity & Health Checks
    // ------------------------------------------------------------------------
    async function checkBackendHealth() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);
            const res = await fetch(`${backendUrl}/health`, { signal: controller.signal });
            clearTimeout(timeoutId);

            if (res.ok) {
                setStatus(statusMLEl, 'online', 'Connected');
            } else {
                setStatus(statusMLEl, 'offline', 'Error');
            }
        } catch (err) {
            setStatus(statusMLEl, 'offline', 'Offline');
        }
    }

    // ------------------------------------------------------------------------
    // Local Backend Real-Time Polling & Device Status
    // ------------------------------------------------------------------------
    let lastBackendScanId = null;

    async function pollLocalBackendRealtime() {
        try {
            // 1. Device status check
            const statusRes = await fetch(`${backendUrl}/device-status`);
            if (statusRes.ok) {
                const dev = await statusRes.json();
                if (dev.connected) {
                    setStatus(statusEsp32El, 'online', 'Connected');
                    setStatus(statusSensorEl, dev.sensor_status === 'online' ? 'online' : 'offline', dev.sensor_status === 'online' ? 'Online' : 'Offline');
                } else if (!window.firebaseService.isConnected) {
                    setStatus(statusEsp32El, 'offline', 'Waiting for ESP32...');
                    setStatus(statusSensorEl, 'offline', 'Offline');
                }
            }

            // 2. Real-time scan check
            const scanRes = await fetch(`${backendUrl}/latest-scan`);
            if (scanRes.ok) {
                const scan = await scanRes.json();
                if (scan && scan.scan_id && scan.scan_id !== lastBackendScanId && scan.wavelength) {
                    lastBackendScanId = scan.scan_id;
                    handleIncomingScan(scan);
                }
            }
        } catch (err) {
            // Handled
        }
    }

    // ------------------------------------------------------------------------
    // Firebase Listeners for Live ESP32
    // ------------------------------------------------------------------------
    window.firebaseService.onNewScan((scan) => {
        handleIncomingScan(scan);
    });

    window.firebaseService.onDeviceStatus((status) => {
        if (status && status.connected) {
            setStatus(statusEsp32El, 'online', 'Connected');
            setStatus(statusSensorEl, status.sensor_status === 'online' ? 'online' : 'offline', status.sensor_status === 'online' ? 'Online' : 'Offline');
        } else {
            setStatus(statusEsp32El, 'offline', 'Offline');
            setStatus(statusSensorEl, 'offline', 'Offline');
        }
    });

    window.firebaseService.onConnectionChange((connected, statusText) => {
        if (!window.firebaseService.databaseUrl) {
            setStatus(statusFirebaseEl, 'standby', 'Not Configured');
            statusFirebaseEl.title = 'Firebase URL is empty. Click Settings to enter URL.';
        } else if (connected) {
            setStatus(statusFirebaseEl, 'online', 'Connected');
            statusFirebaseEl.title = 'Firebase Realtime Database is connected!';
        } else if (statusText && statusText.includes('401')) {
            setStatus(statusFirebaseEl, 'standby', 'Rules Locked (401)');
            statusFirebaseEl.title = 'Firebase Permission Denied! In Firebase Console > Realtime Database > Rules, set .read: true, .write: true.';
        } else {
            setStatus(statusFirebaseEl, 'offline', statusText || 'Offline');
            statusFirebaseEl.title = 'Could not reach Firebase database.';
        }
    });

    // ------------------------------------------------------------------------
    // Settings Modal
    // ------------------------------------------------------------------------
    function openConfigModal() {
        if (cfgFirebaseUrlInput) cfgFirebaseUrlInput.value = window.firebaseService.databaseUrl || '';
        if (cfgBackendUrlInput) cfgBackendUrlInput.value = backendUrl;
        if (configModalEl) configModalEl.classList.add('open');
    }

    function closeConfigModal() {
        if (configModalEl) configModalEl.classList.remove('open');
    }

    if (btnConfigModal) btnConfigModal.addEventListener('click', openConfigModal);
    if (btnCloseConfig) btnCloseConfig.addEventListener('click', closeConfigModal);
    if (btnCancelConfig) btnCancelConfig.addEventListener('click', closeConfigModal);

    if (btnSaveConfig) {
        btnSaveConfig.addEventListener('click', () => {
            const newFbUrl = cfgFirebaseUrlInput ? cfgFirebaseUrlInput.value.trim() : '';
            const newBackend = cfgBackendUrlInput ? cfgBackendUrlInput.value.trim() : '';

            backendUrl = newBackend || 'http://localhost:8000';
            localStorage.setItem('fabric_backend_url', backendUrl);

            window.firebaseService.configure(newFbUrl);
            closeConfigModal();
            checkBackendHealth();
        });
    }

    // ------------------------------------------------------------------------
    // Initialization
    // ------------------------------------------------------------------------
    window.firebaseService.connect();
    checkBackendHealth();
    pollLocalBackendRealtime();
    setInterval(checkBackendHealth, 4000);
    setInterval(pollLocalBackendRealtime, 1200);
});
