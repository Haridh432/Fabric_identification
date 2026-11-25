/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - DATASET CAPTURE & EXPORT SERVICE
 * ============================================================================
 * Handles recording incoming spectral measurements, assigning fabric labels
 * and physical sample IDs (preventing data leakage), and exporting to CSV.
 * 
 * Supports two export formats:
 *  1. Long Format: Sample_ID,Fabric,Physical_Sample_ID,Wavelength,Intensity
 *  2. Wide / ML Format: Sample_ID,Fabric,Physical_Sample_ID,900,920,940...
 * ============================================================================
 */

class DatasetCaptureManager {
    constructor() {
        this.isCapturing = false;
        this.buffer = []; // Stores captured scan objects
        this.sampleCounter = 0;

        // UI references
        this.btnStart = document.getElementById('btnStartCapture');
        this.btnStop = document.getElementById('btnStopCapture');
        this.btnDlLong = document.getElementById('btnDownloadLongCSV');
        this.btnDlWide = document.getElementById('btnDownloadWideCSV');
        this.btnClear = document.getElementById('btnClearCapture');
        this.badgeCount = document.getElementById('captureCounterBadge');
        this.selectFabric = document.getElementById('fabricClassSelect');
        this.inputPhysicalSample = document.getElementById('physicalSampleId');
        this.btnAddCustomClass = document.getElementById('btnAddCustomClass');

        this.bindEvents();
    }

    bindEvents() {
        if (this.btnStart) this.btnStart.addEventListener('click', () => this.startCapture());
        if (this.btnStop) this.btnStop.addEventListener('click', () => this.stopCapture());
        if (this.btnDlLong) this.btnDlLong.addEventListener('click', () => this.downloadLongCSV());
        if (this.btnDlWide) this.btnDlWide.addEventListener('click', () => this.downloadWideCSV());
        if (this.btnClear) this.btnClear.addEventListener('click', () => this.clearBuffer());
        if (this.btnAddCustomClass) this.btnAddCustomClass.addEventListener('click', () => this.promptAddCustomClass());
    }

    startCapture() {
        this.isCapturing = true;
        this.btnStart.disabled = true;
        this.btnStop.disabled = false;
        this.btnStart.textContent = '● Capturing...';
        console.log('[CaptureManager] Capture started. Buffering incoming scans...');
    }

    stopCapture() {
        this.isCapturing = false;
        this.btnStart.disabled = false;
        this.btnStop.disabled = true;
        this.btnStart.textContent = '▶ Start Capture';
        console.log(`[CaptureManager] Capture stopped. Buffer has ${this.buffer.length} records.`);
    }

    /**
     * Called whenever a new scan arrives from ESP32 or Firebase.
     * If capture is active, saves record with assigned label and physical sample ID.
     */
    recordScan(scan) {
        if (!this.isCapturing) return;
        if (!scan || !scan.wavelength || !scan.intensity) return;

        this.sampleCounter++;
        const fabricLabel = this.selectFabric ? this.selectFabric.value : 'Unknown';
        const physicalId = this.inputPhysicalSample ? this.inputPhysicalSample.value.trim() : 'SAMPLE_01';

        const record = {
            sample_id: scan.scan_id || `SCAN_${String(this.sampleCounter).padStart(6, '0')}`,
            fabric: fabricLabel,
            physical_sample_id: physicalId || 'SAMPLE_UNKNOWN',
            timestamp: scan.timestamp || Date.now(),
            wavelength: [...scan.wavelength],
            intensity: [...scan.intensity]
        };

        this.buffer.push(record);
        this.updateUIState();
        console.log(`[CaptureManager] Recorded ${record.sample_id} [${fabricLabel}] - Total: ${this.buffer.length}`);
    }

    updateUIState() {
        const count = this.buffer.length;
        if (this.badgeCount) {
            this.badgeCount.textContent = `${count} Samples Captured`;
        }
        if (this.btnDlLong) this.btnDlLong.disabled = count === 0;
        if (this.btnDlWide) this.btnDlWide.disabled = count === 0;
        if (this.btnClear) this.btnClear.disabled = count === 0;
    }

    clearBuffer() {
        if (confirm('Are you sure you want to clear the captured dataset buffer?')) {
            this.buffer = [];
            this.updateUIState();
        }
    }

    /**
     * Download dataset in Long Format:
     * Sample_ID,Fabric,Physical_Sample_ID,Wavelength,Intensity
     */
    downloadLongCSV() {
        if (this.buffer.length === 0) {
            alert('No captured samples to export.');
            return;
        }

        const rows = ['Sample_ID,Fabric,Physical_Sample_ID,Wavelength,Intensity'];
        
        for (const item of this.buffer) {
            const sid = item.sample_id;
            const fab = item.fabric;
            const pid = item.physical_sample_id;

            for (let i = 0; i < item.wavelength.length; i++) {
                const wl = item.wavelength[i];
                const val = item.intensity[i];
                rows.push(`${sid},${fab},${pid},${wl},${val}`);
            }
        }

        const csvContent = rows.join('\n');
        this.triggerDownload(csvContent, `fabric_dataset_long_${Date.now()}.csv`);
    }

    /**
     * Download dataset in Wide / ML-ready Format:
     * Sample_ID,Fabric,Physical_Sample_ID,900,920,940...
     */
    downloadWideCSV() {
        if (this.buffer.length === 0) {
            alert('No captured samples to export.');
            return;
        }

        // Establish the reference wavelength header from the first sample
        const referenceWavelengths = this.buffer[0].wavelength.map(wl => Math.round(wl * 10) / 10);
        const header = ['Sample_ID', 'Fabric', 'Physical_Sample_ID', ...referenceWavelengths].join(',');
        const rows = [header];

        for (const item of this.buffer) {
            const sid = item.sample_id;
            const fab = item.fabric;
            const pid = item.physical_sample_id;
            
            // Map intensities matching the reference wavelengths
            const intensities = item.intensity.map(v => typeof v === 'number' ? v.toFixed(2) : v);
            rows.push([sid, fab, pid, ...intensities].join(','));
        }

        const csvContent = rows.join('\n');
        this.triggerDownload(csvContent, `fabric_dataset_wide_${Date.now()}.csv`);
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

    /**
     * Allow user to add additional custom fabric classes
     */
    promptAddCustomClass() {
        const newClass = prompt('Enter new Fabric Class Name (e.g., Linen, Wool, Rayon, Denim):');
        if (newClass && newClass.trim()) {
            const clean = newClass.trim();
            // Check if exists
            const exists = Array.from(this.selectFabric.options).some(opt => opt.value.toLowerCase() === clean.toLowerCase());
            if (exists) {
                alert(`Fabric class "${clean}" already exists.`);
                this.selectFabric.value = clean;
                return;
            }

            const option = document.createElement('option');
            option.value = clean;
            option.textContent = clean;
            option.selected = true;
            this.selectFabric.appendChild(option);
            alert(`Fabric class "${clean}" added successfully!`);
        }
    }
}

// Global instance
window.captureManager = new DatasetCaptureManager();
