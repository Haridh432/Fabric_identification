/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - MAIN DASHBOARD CONTROLLER (SVM V2)
 * ============================================================================
 * Preserves all sample collection features while adding real-time SVM V2
 * fabric identification, 5-class probability bars, recent predictions (10),
 * mismatch warnings during capture, and developer spectrum testing.
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    const AS7265X_WAVELENGTHS = [
        410, 435, 460, 485, 510, 535,
        560, 585, 610, 645, 680, 705,
        730, 760, 810, 860, 900, 940
    ];

    const statusEsp32El = document.getElementById('statusEsp32');
    const statusSensorEl = document.getElementById('statusSensor');
    const statusFirebaseEl = document.getElementById('statusFirebase');
    const statusMLEl = document.getElementById('statusML');

    const mlStatusBadgeEl = document.getElementById('mlStatusBadge');
    const resultDisplayBoxEl = document.getElementById('resultDisplayBox');
    const predictedFabricEl = document.getElementById('predictedFabric');
    const confidenceTextEl = document.getElementById('confidenceText');
    const confidenceTierBadgeEl = document.getElementById('confidenceTierBadge');
    const probabilitiesListEl = document.getElementById('probabilitiesList');

    const mismatchWarningEl = document.getElementById('mismatchWarning');
    const mismatchDetailsEl = document.getElementById('mismatchDetails');
    const captureCompareTextEl = document.getElementById('captureCompareText');
    const fabricClassSelectEl = document.getElementById('fabricClassSelect');

    const metaScanIdEl = document.getElementById('metaScanId');
    const metaTimestampEl = document.getElementById('metaTimestamp');
    const metaModelInfoEl = document.getElementById('metaModelInfo');
    const metaModelAccEl = document.getElementById('metaModelAcc');

    const tableBodyEl = document.getElementById('rawDataTableBody');
    const tableFilterEl = document.getElementById('tableFilterInput');
    const tableRowCountEl = document.getElementById('tableRowCount');

    const recentPredBodyEl = document.getElementById('recentPredictionsBody');
    const recentPredCountEl = document.getElementById('recentPredCount');

    const liveFeedBodyEl = document.getElementById('liveFeedBody');
    const liveFeedCountEl = document.getElementById('liveFeedCount');

    // Settings & Developer Test Modal
    const configModalEl = document.getElementById('configModal');
    const btnConfigModal = document.getElementById('btnConfigModal');
    const btnCloseConfig = document.getElementById('btnCloseConfig');
    const btnCancelConfig = document.getElementById('btnCancelConfig');
    const btnSaveConfig = document.getElementById('btnSaveConfig');
    const cfgFirebaseUrlInput = document.getElementById('cfgFirebaseUrl');
    const cfgBackendUrlInput = document.getElementById('cfgBackendUrl');

    let currentRawTableData = [];
    let backendUrl = localStorage.getItem('fabric_backend_url') || 'http://localhost:8000';
    let lastBackendScanId = null;
    let lastPredictedFabric = null;
    let lastPredictedConfPct = null;

    function setStatus(element, state, text) {
        if (!element) return;
        element.classList.remove('online', 'offline', 'standby');
        element.classList.add(state);
        const val = element.querySelector('.status-val');
        if (val) val.textContent = text;
    }

    function updateMLStatusUI(online) {
        if (online) {
            setStatus(statusMLEl, 'online', 'ONLINE');
            if (mlStatusBadgeEl) {
                mlStatusBadgeEl.textContent = 'ML Status: ONLINE';
                mlStatusBadgeEl.className = 'status-tag processed';
            }
        } else {
            setStatus(statusMLEl, 'offline', 'OFFLINE');
            if (mlStatusBadgeEl) {
                mlStatusBadgeEl.textContent = 'ML Status: OFFLINE';
                mlStatusBadgeEl.className = 'status-tag error';
            }
        }
    }

    function getConfidenceTier(pct) {
        if (pct >= 75) return { label: 'HIGH CONFIDENCE', cls: 'high' };
        if (pct >= 50) return { label: 'MODERATE CONFIDENCE', cls: 'moderate' };
        return { label: 'LOW CONFIDENCE', cls: 'low' };
    }

    function formatPct(val) {
        // Backend returns 0..1 confidence; handle safely if >1 already
        const pct = val <= 1.0 ? val * 100.0 : val;
        return pct;
    }

    // ------------------------------------------------------------------------
    // Raw 18-Channel Sensor Data Table
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
        const filtered = currentRawTableData.filter(d => !query || d.wavelength.toString().includes(query));
        tableRowCountEl.textContent = `${filtered.length} / ${currentRawTableData.length} Bands`;

        if (filtered.length === 0) {
            tableBodyEl.innerHTML = '<tr><td colspan="4" class="empty-state">No matching wavelengths found.</td></tr>';
            return;
        }

        tableBodyEl.innerHTML = filtered.map(d => `
            <tr>
                <td>${d.index}</td>
                <td><strong>${d.wavelength.toFixed(1)}</strong></td>
                <td>${d.intensity.toFixed(2)}</td>
                <td>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="width:38px;">${d.percent}%</span>
                        <div style="flex:1; height:4px; background:var(--border-color); border-radius:2px; overflow:hidden;">
                            <div style="width:${d.percent}%; height:100%; background:var(--accent-blue);"></div>
                        </div>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    if (tableFilterEl) {
        tableFilterEl.addEventListener('input', applyTableFilter);
    }

    // ------------------------------------------------------------------------
    // Prediction Display, 5-Class Probabilities & Capture Mismatch Warning
    // ------------------------------------------------------------------------
    function updateCompareAndMismatch() {
        const selectedLabel = fabricClassSelectEl ? fabricClassSelectEl.value : '--';
        if (captureCompareTextEl) {
            if (lastPredictedFabric) {
                captureCompareTextEl.textContent = `Selected: ${selectedLabel} | ML: ${lastPredictedFabric} (${lastPredictedConfPct.toFixed(1)}%)`;
            } else {
                captureCompareTextEl.textContent = `Selected Label: ${selectedLabel}`;
            }
        }

        const isCapturing = window.captureManager && window.captureManager.isCapturing;
        if (isCapturing && lastPredictedFabric && selectedLabel &&
            selectedLabel.toLowerCase() !== lastPredictedFabric.toLowerCase()) {
            if (mismatchWarningEl) mismatchWarningEl.style.display = 'block';
            if (mismatchDetailsEl) {
                mismatchDetailsEl.textContent = `Selected: ${selectedLabel} | Predicted: ${lastPredictedFabric} (${lastPredictedConfPct.toFixed(1)}%)`;
            }
        } else {
            if (mismatchWarningEl) mismatchWarningEl.style.display = 'none';
        }
    }

    if (fabricClassSelectEl) {
        fabricClassSelectEl.addEventListener('change', updateCompareAndMismatch);
    }

    function renderProbabilities(probabilities, predictedFabric) {
        if (!probabilitiesListEl) return;
        if (!probabilities || typeof probabilities !== 'object') {
            probabilitiesListEl.innerHTML = '<div class="prob-empty">Probabilities unavailable.</div>';
            return;
        }

        const entries = Object.entries(probabilities);
        if (entries.length === 0) {
            probabilitiesListEl.innerHTML = '<div class="prob-empty">No class probabilities returned.</div>';
            return;
        }

        probabilitiesListEl.innerHTML = entries.map(([clsName, rawProb]) => {
            const pct = formatPct(rawProb);
            const isTop = clsName === predictedFabric;
            return `
                <div class="prob-row ${isTop ? 'top' : ''}">
                    <span class="prob-name">${clsName}</span>
                    <div class="prob-bar-bg">
                        <div class="prob-bar-fill" style="width: ${Math.min(100, Math.max(0, pct)).toFixed(1)}%;"></div>
                    </div>
                    <span class="prob-val">${pct.toFixed(1)}%</span>
                </div>
            `;
        }).join('');
    }

    function renderPredictionResult(scan) {
        const pred = scan.prediction || (scan.fabric ? scan : null);

        if (!pred || !pred.fabric) {
            lastPredictedFabric = null;
            lastPredictedConfPct = null;
            if (predictedFabricEl) predictedFabricEl.textContent = scan.prediction_error ? 'Unavailable' : '--';
            if (confidenceTextEl) confidenceTextEl.textContent = '0.0%';
            if (confidenceTierBadgeEl) {
                confidenceTierBadgeEl.textContent = scan.prediction_error ? 'UNAVAILABLE' : 'WAITING';
                confidenceTierBadgeEl.className = 'confidence-tier';
            }
            if (resultDisplayBoxEl) resultDisplayBoxEl.className = 'result-display-box';
            if (probabilitiesListEl) {
                probabilitiesListEl.innerHTML = `<div class="prob-empty">${scan.prediction_error || 'Waiting for 18-channel spectrum...'}</div>`;
            }
            updateCompareAndMismatch();
            return;
        }

        const fabric = pred.fabric;
        const confPct = formatPct(pred.confidence || 0);
        const tier = getConfidenceTier(confPct);

        lastPredictedFabric = fabric;
        lastPredictedConfPct = confPct;

        if (predictedFabricEl) predictedFabricEl.textContent = fabric;
        if (confidenceTextEl) confidenceTextEl.textContent = `${confPct.toFixed(1)}%`;
        if (confidenceTierBadgeEl) {
            confidenceTierBadgeEl.textContent = tier.label;
            confidenceTierBadgeEl.className = `confidence-tier ${tier.cls}`;
        }
        if (resultDisplayBoxEl) {
            resultDisplayBoxEl.className = `result-display-box ${fabric.toLowerCase()}`;
        }

        renderProbabilities(pred.probabilities, fabric);
        updateCompareAndMismatch();
    }

    function renderRecentPredictions(items) {
        if (!recentPredBodyEl || !recentPredCountEl) return;
        const capped = (items || []).slice(0, 10);
        recentPredCountEl.textContent = `${capped.length} / 10`;

        if (capped.length === 0) {
            recentPredBodyEl.innerHTML = '<tr><td colspan="4" class="empty-state">No predictions yet.</td></tr>';
            return;
        }

        recentPredBodyEl.innerHTML = capped.map(item => {
            const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : '--';
            const confPct = formatPct(item.confidence || 0);
            return `
                <tr>
                    <td>${timeStr}</td>
                    <td><strong>${item.scan_id}</strong></td>
                    <td><span class="fabric-pill">${item.fabric}</span></td>
                    <td>${confPct.toFixed(1)}%</td>
                </tr>
            `;
        }).join('');
    }

    function renderLiveFeed(items) {
        if (!liveFeedBodyEl || !liveFeedCountEl) return;
        liveFeedCountEl.textContent = `${items.length} Scans`;

        if (!items || items.length === 0) {
            liveFeedBodyEl.innerHTML = '<tr><td colspan="6" class="empty-state">Waiting for live scans from AS7265x sensor...</td></tr>';
            return;
        }

        liveFeedBodyEl.innerHTML = items.map(item => {
            const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : '--';
            const fabHtml = item.fabric ? `<span class="fabric-pill">${item.fabric}</span>` : '--';
            return `
                <tr>
                    <td>${timeStr}</td>
                    <td><strong>${item.scan_id}</strong></td>
                    <td>${item.peak_wavelength ? item.peak_wavelength + ' nm' : '--'}</td>
                    <td>${item.max_intensity !== null && item.max_intensity !== undefined ? Number(item.max_intensity).toFixed(2) : '--'}</td>
                    <td>${fabHtml}</td>
                    <td><span class="fabric-pill">${item.status || 'collected'}</span></td>
                </tr>
            `;
        }).join('');
    }

    // ------------------------------------------------------------------------
    // Handle Incoming Scan (from Backend Poll or Firebase)
    // ------------------------------------------------------------------------
    function handleIncomingScan(scan) {
        if (!scan || !scan.wavelength || !scan.intensity) return;

        // 1. Update shared Live Spectrum Chart
        if (window.spectrumChart) {
            window.spectrumChart.updateSpectrum(scan.wavelength, scan.intensity);
        }

        // 2. Update Raw 18-Channel Table
        renderTable(scan.wavelength, scan.intensity);

        // 3. Forward to Sample Capture Manager (keeps manual ground-truth label)
        if (window.captureManager) {
            window.captureManager.recordScan(scan);
        }

        // 4. Update Scan ID & Last Prediction Time
        if (metaScanIdEl) metaScanIdEl.textContent = scan.scan_id || '--';
        if (metaTimestampEl) {
            const date = scan.timestamp ? new Date(scan.timestamp) : new Date();
            metaTimestampEl.textContent = date.toLocaleTimeString();
        }

        // 5. Render SVM V2 prediction & 5-class probabilities
        if (scan.prediction || scan.fabric) {
            renderPredictionResult(scan);
        } else if (scan.status === 'raw') {
            autoPredictRawScan(scan);
        } else {
            renderPredictionResult(scan);
        }
    }

    async function autoPredictRawScan(scan) {
        try {
            const res = await fetch(`${backendUrl}/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scan_id: scan.scan_id,
                    timestamp: scan.timestamp || Date.now(),
                    wavelength: scan.wavelength,
                    intensity: scan.intensity
                })
            });

            if (res.ok) {
                const pred = await res.json();
                renderPredictionResult(pred);
                if (window.firebaseService && window.firebaseService.databaseUrl) {
                    window.firebaseService.writePrediction(scan.scan_id, {
                        fabric: pred.fabric,
                        confidence: pred.confidence,
                        probabilities: pred.probabilities,
                        model: pred.model,
                        status: 'predicted'
                    });
                }
            } else {
                const err = await res.json().catch(() => ({}));
                renderPredictionResult({ prediction_error: err.detail || 'Prediction failed' });
            }
        } catch (err) {
            renderPredictionResult({ prediction_error: 'ML Backend offline' });
        }
    }

    // ------------------------------------------------------------------------
    // Model Info & Unified Real-Time Polling (800 ms)
    // ------------------------------------------------------------------------
    function applyModelInfoUI(info) {
        updateMLStatusUI(Boolean(info.model_loaded));

        if (metaModelInfoEl) {
            const clsCount = (info.classes || []).length;
            metaModelInfoEl.textContent = `SVM (${clsCount} Classes)`;
        }
        if (metaModelAccEl) {
            const testAcc = ((info.test_accuracy || 0) * 100).toFixed(2);
            const cvAcc = ((info.cv_accuracy || 0) * 100).toFixed(2);
            metaModelAccEl.textContent = `${testAcc}% / ${cvAcc}%`;
        }
    }

    async function fetchModelInfo() {
        try {
            const res = await fetch(`${backendUrl}/model-info`);
            if (!res.ok) throw new Error('Model info unavailable');
            const info = await res.json();
            applyModelInfoUI(info);
        } catch (err) {
            updateMLStatusUI(false);
        }
    }

    async function pollLocalBackendRealtime() {
        try {
            const [statusRes, scanRes, feedRes] = await Promise.all([
                fetch(`${backendUrl}/device-status`),
                fetch(`${backendUrl}/latest-scan`),
                fetch(`${backendUrl}/live-feed`)
            ]);

            if (statusRes.ok) {
                const dev = await statusRes.json();
                if (dev.connected) {
                    setStatus(statusEsp32El, 'online', 'ONLINE');
                    setStatus(statusSensorEl, dev.sensor_status === 'online' ? 'online' : 'offline', dev.sensor_status === 'online' ? 'ONLINE' : 'OFFLINE');
                } else if (!window.firebaseService.isConnected) {
                    setStatus(statusEsp32El, 'offline', 'OFFLINE');
                    setStatus(statusSensorEl, 'offline', 'OFFLINE');
                }
            }

            if (scanRes.ok) {
                const scan = await scanRes.json();
                if (Array.isArray(scan.recent_predictions)) {
                    renderRecentPredictions(scan.recent_predictions);
                }
                if (scan && scan.scan_id && scan.scan_id !== lastBackendScanId && scan.wavelength) {
                    lastBackendScanId = scan.scan_id;
                    handleIncomingScan(scan);
                }
            }

            if (feedRes.ok) {
                const feedData = await feedRes.json();
                if (feedData && Array.isArray(feedData.items)) {
                    renderLiveFeed(feedData.items);
                }
            }
        } catch (err) {
            updateMLStatusUI(false);
        }
    }

    // ------------------------------------------------------------------------
    // Firebase Listeners (Preserved)
    // ------------------------------------------------------------------------
    window.firebaseService.onNewScan((scan) => {
        if (scan && scan.scan_id && scan.scan_id !== lastBackendScanId) {
            lastBackendScanId = scan.scan_id;
            handleIncomingScan(scan);
        }
    });

    window.firebaseService.onConnectionChange((connected, statusText) => {
        if (!window.firebaseService.databaseUrl) {
            setStatus(statusFirebaseEl, 'standby', 'Not Configured');
        } else if (connected) {
            setStatus(statusFirebaseEl, 'online', 'ONLINE');
        } else if (statusText && statusText.includes('401')) {
            setStatus(statusFirebaseEl, 'standby', 'Rules Locked (401)');
        } else {
            setStatus(statusFirebaseEl, 'offline', statusText || 'OFFLINE');
        }
    });

    // ------------------------------------------------------------------------
    // Settings & Developer Test Mode
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
            fetchModelInfo();
        });
    }

    // ------------------------------------------------------------------------
    // Initialization (Single Unified Polling Loop)
    // ------------------------------------------------------------------------
    window.firebaseService.connect();
    fetchModelInfo();
    pollLocalBackendRealtime();
    setInterval(fetchModelInfo, 5000);
    setInterval(pollLocalBackendRealtime, 800);
});
