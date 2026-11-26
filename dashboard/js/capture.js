/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - DATASET CAPTURE, LIST & RETRAIN SERVICE
 * ============================================================================
 * Handles:
 *  - Recording incoming spectral measurements (deduplicated by scan_id)
 *  - Auto-updating Physical_Sample_ID when Fabric Class changes
 *  - Rendering the live Collected Samples List table with row deletion
 *  - Exporting CSV (Long format & Wide/ML format)
 *  - Sending captured samples to backend (/dataset/train) to retrain SVM live
 * ============================================================================
 */

class DatasetCaptureManager {
    constructor() {
        this.isCapturing = false;
        this.buffer = [];
        this.sampleCounter = 0;

        // UI references
        this.btnStart = document.getElementById('btnStartCapture');
        this.btnStop = document.getElementById('btnStopCapture');
        this.btnTrain = document.getElementById('btnTrainFromCapture');
        this.btnDlWide = document.getElementById('btnDownloadWideCSV');
        this.btnClear = document.getElementById('btnClearCapture');
        this.badgeCount = document.getElementById('captureCounterBadge');
        this.selectFabric = document.getElementById('fabricClassSelect');
        this.inputPhysicalSample = document.getElementById('physicalSampleId');
        this.btnAddCustomClass = document.getElementById('btnAddCustomClass');
        this.capturedBodyEl = document.getElementById('capturedSamplesBody');

        this.bindEvents();
        this.syncPhysicalSampleId();
    }

    bindEvents() {
        if (this.btnStart) this.btnStart.addEventListener('click', () => this.startCapture());
        if (this.btnStop) this.btnStop.addEventListener('click', () => this.stopCapture());
        if (this.btnTrain) this.btnTrain.addEventListener('click', () => this.trainFromCaptured());
        if (this.btnDlWide) this.btnDlWide.addEventListener('click', () => this.downloadWideCSV());
        if (this.btnClear) this.btnClear.addEventListener('click', () => this.clearBuffer());
        if (this.btnAddCustomClass) this.btnAddCustomClass.addEventListener('click', () => this.promptAddCustomClass());
        if (this.selectFabric) {
            this.selectFabric.addEventListener('change', () => this.syncPhysicalSampleId());
        }
    }

    syncPhysicalSampleId() {
        if (!this.selectFabric || !this.inputPhysicalSample) return;
        const fab = this.selectFabric.value.trim().toUpperCase().replace(/\s+/g, '_');
        this.inputPhysicalSample.value = `SAMPLE_${fab}_01`;
    }

    startCapture() {
        this.isCapturing = true;
        this.btnStart.disabled = true;
        this.btnStop.disabled = false;
        this.btnStart.textContent = '● Capturing...';
    }

    stopCapture() {
        this.isCapturing = false;
        this.btnStart.disabled = false;
        this.btnStop.disabled = true;
        this.btnStart.textContent = '▶ Start Capture';
    }

    /**
     * Called whenever a scan arrives. Buffers unique scans when capturing is active.
     */
    recordScan(scan) {
        if (!this.isCapturing) return;
        if (!scan || !scan.wavelength || !scan.intensity) return;

        const sid = scan.scan_id || `SCAN_${String(this.sampleCounter + 1).padStart(6, '0')}`;
        // Prevent duplicate capture of the same scan_id
        if (this.buffer.some(item => item.sample_id === sid)) {
            return;
        }

        this.sampleCounter++;
        const fabricLabel = this.selectFabric ? this.selectFabric.value : 'Unknown';
        const physicalId = this.inputPhysicalSample ? this.inputPhysicalSample.value.trim() : `SAMPLE_${fabricLabel.toUpperCase()}_01`;

        // Calculate peak wavelength
        let maxIdx = 0;
        for (let i = 1; i < scan.intensity.length; i++) {
            if (scan.intensity[i] > scan.intensity[maxIdx]) maxIdx = i;
        }
        const peakWl = scan.wavelength[maxIdx];

        const record = {
            sample_id: sid,
            fabric: fabricLabel,
            physical_sample_id: physicalId || `SAMPLE_${fabricLabel.toUpperCase()}_01`,
            timestamp: scan.timestamp || Date.now(),
            peak_wl: peakWl,
            wavelength: [...scan.wavelength],
            intensity: [...scan.intensity]
        };

        this.buffer.push(record);
        this.updateUIState();
    }

    removeSample(index) {
        if (index >= 0 && index < this.buffer.length) {
            this.buffer.splice(index, 1);
            this.updateUIState();
        }
    }

    renderCapturedList() {
        if (!this.capturedBodyEl) return;

        if (this.buffer.length === 0) {
            this.capturedBodyEl.innerHTML = '<tr><td colspan="6" class="empty-state">No samples captured yet. Select a fabric & click "Start Capture".</td></tr>';
            return;
        }

        const rowsHtml = this.buffer.map((item, idx) => `
            <tr>
                <td>${idx + 1}</td>
                <td>${item.sample_id}</td>
                <td><span class="fabric-pill">${item.fabric}</span></td>
                <td>${item.physical_sample_id}</td>
                <td>${item.peak_wl ? item.peak_wl.toFixed(0) + ' nm' : '--'}</td>
                <td><button class="btn-row-del" data-idx="${idx}" title="Remove sample">✕</button></td>
            </tr>
        `).join('');

        this.capturedBodyEl.innerHTML = rowsHtml;

        this.capturedBodyEl.querySelectorAll('.btn-row-del').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const i = parseInt(e.currentTarget.getAttribute('data-idx'), 10);
                this.removeSample(i);
            });
        });
    }

    updateUIState() {
        const count = this.buffer.length;
        if (this.badgeCount) {
            this.badgeCount.textContent = `${count} Samples Captured`;
        }
        if (this.btnTrain) this.btnTrain.disabled = count === 0;
        if (this.btnDlWide) this.btnDlWide.disabled = count === 0;
        if (this.btnClear) this.btnClear.disabled = count === 0;

        this.renderCapturedList();
    }

    clearBuffer() {
        if (confirm('Are you sure you want to clear the captured dataset buffer?')) {
            this.buffer = [];
            this.updateUIState();
        }
    }

    /**
     * Send captured samples to backend /dataset/train to update the SVM model live
     */
    async trainFromCaptured() {
        if (this.buffer.length === 0) return;

        const backendUrl = localStorage.getItem('fabric_backend_url') || 'http://localhost:8000';
        this.btnTrain.disabled = true;
        const origText = this.btnTrain.textContent;
        this.btnTrain.textContent = '⏳ Training SVM...';

        try {
            const payload = {
                samples: this.buffer.map(item => ({
                    sample_id: item.sample_id,
                    fabric: item.fabric,
                    physical_sample_id: item.physical_sample_id,
                    wavelength: item.wavelength,
                    intensity: item.intensity
                })),
                replace_existing: false
            };

            const res = await fetch(`${backendUrl}/dataset/train`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || res.statusText);
            }

            const data = await res.json();
            alert(`SVM Model Retrained Successfully!\nTotal Training Samples: ${data.total_samples}\nClasses: ${data.classes.join(', ')}\nHoldout Accuracy: ${(data.accuracy * 100).toFixed(1)}%`);
        } catch (err) {
            alert(`Training failed: ${err.message}`);
        } finally {
            this.btnTrain.disabled = this.buffer.length === 0;
            this.btnTrain.textContent = origText;
        }
    }

    downloadWideCSV() {
        if (this.buffer.length === 0) return;

        const referenceWavelengths = this.buffer[0].wavelength.map(wl => Math.round(wl * 10) / 10);
        const header = ['Sample_ID', 'Fabric', 'Physical_Sample_ID', ...referenceWavelengths].join(',');
        const rows = [header];

        for (const item of this.buffer) {
            const intensities = item.intensity.map(v => typeof v === 'number' ? v.toFixed(2) : v);
            rows.push([item.sample_id, item.fabric, item.physical_sample_id, ...intensities].join(','));
        }
        this.triggerDownload(rows.join('\n'), `fabric_dataset_wide_${Date.now()}.csv`);
    }

    triggerDownload(content, filename) {
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    promptAddCustomClass() {
        const newClass = prompt('Enter new Fabric Class Name (e.g., Denim, Wool, Rayon):');
        if (newClass && newClass.trim()) {
            const clean = newClass.trim();
            const exists = Array.from(this.selectFabric.options).some(opt => opt.value.toLowerCase() === clean.toLowerCase());
            if (exists) {
                this.selectFabric.value = clean;
                this.syncPhysicalSampleId();
                return;
            }

            const option = document.createElement('option');
            option.value = clean;
            option.textContent = clean;
            option.selected = true;
            this.selectFabric.appendChild(option);
            this.syncPhysicalSampleId();
        }
    }
}

// Global instance
window.captureManager = new DatasetCaptureManager();
