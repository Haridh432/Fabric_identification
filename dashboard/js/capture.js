/**
 * ============================================================================
 * FABRIC SAMPLE COLLECTION - DATASET CAPTURE, LIST & WIDE CSV EXPORT
 * ============================================================================
 */

class DatasetCaptureManager {
    constructor() {
        // Auto-capture incoming scans during scanning time by default
        this.isCapturing = true;
        this.buffer = [];
        this.sampleCounter = 0;

        this.btnStart = document.getElementById('btnStartCapture');
        this.btnStop = document.getElementById('btnStopCapture');
        this.btnDlWide = document.getElementById('btnDownloadWideCSV');
        this.btnClear = document.getElementById('btnClearCapture');
        this.badgeCount = document.getElementById('captureCounterBadge');
        this.listBadge = document.getElementById('collectedListBadge');
        this.selectFabric = document.getElementById('fabricClassSelect');
        this.inputPhysicalSample = document.getElementById('physicalSampleId');
        this.btnAddCustomClass = document.getElementById('btnAddCustomClass');
        this.capturedBodyEl = document.getElementById('capturedSamplesBody');

        this.bindEvents();
        this.syncPhysicalSampleId();
        this.syncCaptureButtons();
    }

    bindEvents() {
        if (this.btnStart) this.btnStart.addEventListener('click', () => this.startCapture());
        if (this.btnStop) this.btnStop.addEventListener('click', () => this.stopCapture());
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

    syncCaptureButtons() {
        if (this.isCapturing) {
            if (this.btnStart) {
                this.btnStart.disabled = true;
                this.btnStart.textContent = '● Auto-Capturing...';
            }
            if (this.btnStop) {
                this.btnStop.disabled = false;
                this.btnStop.textContent = '⏸ Pause Capture';
            }
        } else {
            if (this.btnStart) {
                this.btnStart.disabled = false;
                this.btnStart.textContent = '▶ Start Capture';
            }
            if (this.btnStop) {
                this.btnStop.disabled = true;
                this.btnStop.textContent = '⏹ Stop Capture';
            }
        }
    }

    startCapture() {
        this.isCapturing = true;
        this.syncCaptureButtons();
    }

    stopCapture() {
        this.isCapturing = false;
        this.syncCaptureButtons();
    }

    recordScan(scan) {
        if (!this.isCapturing) return;
        if (!scan || !scan.wavelength || !scan.intensity) return;

        const sid = scan.scan_id || `SCAN_${String(this.sampleCounter + 1).padStart(6, '0')}`;
        if (this.buffer.some(item => item.sample_id === sid)) {
            return;
        }

        this.sampleCounter++;
        const fabricLabel = this.selectFabric ? this.selectFabric.value : 'Unknown';
        const physicalId = this.inputPhysicalSample ? this.inputPhysicalSample.value.trim() : `SAMPLE_${fabricLabel.toUpperCase()}_01`;

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
        if (this.badgeCount) this.badgeCount.textContent = `${count} Samples`;
        if (this.listBadge) this.listBadge.textContent = `${count} Stored`;
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

window.captureManager = new DatasetCaptureManager();
