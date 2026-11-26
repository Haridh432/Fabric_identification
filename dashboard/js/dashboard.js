/**
 * ============================================================================
 * FABRIC SAMPLE COLLECTION - DASHBOARD CONTROLLER (COLLECTION ONLY MODE)
 * ============================================================================
 * Streams real-time AS7265x spectral data for visualization, inspection,
 * sample labeling, and Wide/ML CSV export (no ML prediction displayed).
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    const statusEsp32El = document.getElementById('statusEsp32');
    const statusSensorEl = document.getElementById('statusSensor');
    const statusFirebaseEl = document.getElementById('statusFirebase');
    const statusMLEl = document.getElementById('statusML');

    const tableBodyEl = document.getElementById('rawDataTableBody');
    const tableFilterEl = document.getElementById('tableFilterInput');
    const tableRowCountEl = document.getElementById('tableRowCount');

    const metaScanIdEl = document.getElementById('metaScanId');
    const metaTimestampEl = document.getElementById('metaTimestamp');
    const metaPeakWlEl = document.getElementById('metaPeakWl');
    const metaMaxIntEl = document.getElementById('metaMaxInt');

    const liveFeedBodyEl = document.getElementById('liveFeedBody');
    const liveFeedCountEl = document.getElementById('liveFeedCount');

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

    function setStatus(element, state, text) {
        if (!element) return;
        element.classList.remove('online', 'offline', 'standby');
        element.classList.add(state);
        const val = element.querySelector('.status-val');
        if (val) val.textContent = text;
    }

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

    function handleIncomingScan(scan) {
        if (!scan || !scan.wavelength || !scan.intensity) return;

        // 1. Update Live Spectrum Graph
        if (window.spectrumChart) {
            window.spectrumChart.updateSpectrum(scan.wavelength, scan.intensity);
        }

        // 2. Update Raw 18-Ch Table
        renderTable(scan.wavelength, scan.intensity);

        // 3. Forward to Dataset Capture Manager
        if (window.captureManager) {
            window.captureManager.recordScan(scan);
        }

        // 4. Update Scan Meta Fields
        let maxIdx = 0;
        for (let i = 1; i < scan.intensity.length; i++) {
            if (scan.intensity[i] > scan.intensity[maxIdx]) maxIdx = i;
        }
        const peakWl = scan.wavelength[maxIdx];
        const maxInt = scan.intensity[maxIdx];

        if (metaScanIdEl) metaScanIdEl.textContent = scan.scan_id || '--';
        if (metaTimestampEl) {
            const date = scan.timestamp ? new Date(scan.timestamp) : new Date();
            metaTimestampEl.textContent = date.toLocaleTimeString();
        }
        if (metaPeakWlEl) metaPeakWlEl.textContent = peakWl !== undefined ? `${Math.round(peakWl)} nm` : '--';
        if (metaMaxIntEl) metaMaxIntEl.textContent = maxInt !== undefined ? maxInt.toFixed(2) : '--';
    }

    function renderLiveFeed(items) {
        if (!liveFeedBodyEl || !liveFeedCountEl) return;
        liveFeedCountEl.textContent = `${items.length} Scans`;

        if (!items || items.length === 0) {
            liveFeedBodyEl.innerHTML = '<tr><td colspan="5" class="empty-state">Waiting for live scans from AS7265x sensor...</td></tr>';
            return;
        }

        liveFeedBodyEl.innerHTML = items.map(item => {
            const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : '--';
            return `
                <tr>
                    <td>${timeStr}</td>
                    <td><strong>${item.scan_id}</strong></td>
                    <td>${item.peak_wavelength ? item.peak_wavelength + ' nm' : '--'}</td>
                    <td>${item.max_intensity !== null && item.max_intensity !== undefined ? Number(item.max_intensity).toFixed(2) : '--'}</td>
                    <td><span class="fabric-pill">${item.status || 'collected'}</span></td>
                </tr>
            `;
        }).join('');
    }

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

    async function pollLocalBackendRealtime() {
        try {
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

            const scanRes = await fetch(`${backendUrl}/latest-scan`);
            if (scanRes.ok) {
                const scan = await scanRes.json();
                if (scan && scan.scan_id && scan.scan_id !== lastBackendScanId && scan.wavelength) {
                    lastBackendScanId = scan.scan_id;
                    handleIncomingScan(scan);
                }
            }

            const feedRes = await fetch(`${backendUrl}/live-feed`);
            if (feedRes.ok) {
                const feedData = await feedRes.json();
                if (feedData && Array.isArray(feedData.items)) {
                    renderLiveFeed(feedData.items);
                }
            }
        } catch (err) {
            // Handled
        }
    }

    window.firebaseService.onNewScan((scan) => {
        handleIncomingScan(scan);
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
            statusFirebaseEl.title = 'Firebase Permission Denied! Set .read: true, .write: true in Firebase Console.';
        } else {
            setStatus(statusFirebaseEl, 'offline', statusText || 'Offline');
            statusFirebaseEl.title = 'Could not reach Firebase database.';
        }
    });

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

    window.firebaseService.connect();
    checkBackendHealth();
    pollLocalBackendRealtime();
    setInterval(checkBackendHealth, 4000);
    setInterval(pollLocalBackendRealtime, 1200);
});
