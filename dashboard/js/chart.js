/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - CHART MANAGER (AS7265x 18-CHANNEL)
 * ============================================================================
 * Renders and dynamically updates the 18-channel AS7265x spectral curve
 * across 410 nm - 940 nm with wavelength-accurate point colors.
 * ============================================================================
 */

const AS7265X_DEFAULT_WAVELENGTHS = [
    410, 435, 460, 485, 510, 535,
    560, 585, 610, 645, 680, 705,
    730, 760, 810, 860, 900, 940
];

function wavelengthToColor(wl) {
    if (wl < 450) return '#8B5CF6'; // Violet
    if (wl < 495) return '#3B82F6'; // Blue
    if (wl < 520) return '#06B6D4'; // Cyan
    if (wl < 570) return '#10B981'; // Green
    if (wl < 600) return '#EAB308'; // Yellow
    if (wl < 630) return '#F97316'; // Orange
    if (wl < 715) return '#EF4444'; // Red
    return '#F43F5E';               // NIR (730-940 nm)
}

class SpectrumChartManager {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.chart = null;
        this.initChart();
    }

    initChart() {
        if (!this.canvas) return;

        const ctx = this.canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 320);
        gradient.addColorStop(0, 'rgba(13, 148, 136, 0.25)');
        gradient.addColorStop(0.65, 'rgba(2, 132, 199, 0.08)');
        gradient.addColorStop(1, 'rgba(2, 132, 199, 0.0)');

        const pointColors = AS7265X_DEFAULT_WAVELENGTHS.map(wavelengthToColor);

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: AS7265X_DEFAULT_WAVELENGTHS,
                datasets: [{
                    label: 'Spectral Intensity',
                    data: new Array(AS7265X_DEFAULT_WAVELENGTHS.length).fill(null),
                    borderColor: '#0D9488',
                    borderWidth: 2.5,
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4.5,
                    pointHoverRadius: 7,
                    pointBackgroundColor: pointColors,
                    pointBorderColor: '#FFFFFF',
                    pointBorderWidth: 1.5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 250 },
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.94)',
                        titleColor: '#FFFFFF',
                        bodyColor: '#E2E8F0',
                        borderColor: '#CBD5E1',
                        borderWidth: 1,
                        padding: 10,
                        displayColors: true,
                        callbacks: {
                            title: (items) => `Channel: ${items[0].label} nm`,
                            label: (item) => `Intensity: ${item.raw !== null ? Number(item.raw).toFixed(2) : '--'} a.u.`
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'AS7265x Wavelength Channels (410 – 940 nm)',
                            color: '#475569',
                            font: { family: 'Inter', size: 12, weight: '600' }
                        },
                        grid: { color: 'rgba(203, 213, 225, 0.55)', tickColor: 'transparent' },
                        ticks: {
                            color: '#475569',
                            font: { family: 'JetBrains Mono', size: 11 },
                            autoSkip: false,
                            maxRotation: 45,
                            minRotation: 0
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Calibrated Intensity (a.u.)',
                            color: '#475569',
                            font: { family: 'Inter', size: 12, weight: '600' }
                        },
                        grid: { color: 'rgba(203, 213, 225, 0.55)', tickColor: 'transparent' },
                        ticks: {
                            color: '#475569',
                            font: { family: 'JetBrains Mono', size: 11 },
                            callback: (val) => val.toLocaleString()
                        }
                    }
                }
            }
        });
    }

    updateSpectrum(wavelengths, intensities) {
        if (!this.chart || !wavelengths || !intensities) return;

        const roundedWls = wavelengths.map(wl => Math.round(wl * 10) / 10);
        this.chart.data.labels = roundedWls;
        this.chart.data.datasets[0].data = intensities;
        this.chart.data.datasets[0].pointBackgroundColor = roundedWls.map(wavelengthToColor);
        this.chart.update('none');

        let maxVal = -Infinity;
        let peakWl = null;
        for (let i = 0; i < intensities.length; i++) {
            if (intensities[i] > maxVal) {
                maxVal = intensities[i];
                peakWl = wavelengths[i];
            }
        }

        const metricPeakEl = document.getElementById('metricPeak');
        const metricMaxEl = document.getElementById('metricMaxIntensity');
        const metricRangeEl = document.getElementById('metricRange');
        const pointCountEl = document.getElementById('graphPointsCount');

        if (metricPeakEl && peakWl !== null) metricPeakEl.textContent = `${Math.round(peakWl)} nm`;
        if (metricMaxEl && maxVal !== -Infinity) metricMaxEl.textContent = maxVal.toFixed(1);
        if (metricRangeEl && wavelengths.length > 0) {
            metricRangeEl.textContent = `${Math.round(wavelengths[0])} - ${Math.round(wavelengths[wavelengths.length - 1])} nm`;
        }
        if (pointCountEl) {
            pointCountEl.textContent = `${wavelengths.length} Channels`;
        }
    }
}

window.spectrumChart = new SpectrumChartManager('spectrumChart');
