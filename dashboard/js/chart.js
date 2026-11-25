/**
 * ============================================================================
 * FABRIC IDENTIFICATION SYSTEM - CHART MANAGER (CHART.JS)
 * ============================================================================
 * Renders and dynamically updates the high-resolution NIR spectral curve.
 * 
 * Features:
 *  - X-Axis: Wavelength (nm)
 *  - Y-Axis: Intensity
 *  - Gradient under the curve
 *  - Smooth real-time data streaming
 *  - Custom tooltip with nm formatting
 *  - Calculates peak wavelength and maximum intensity
 * ============================================================================
 */

class SpectrumChartManager {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.chart = null;
        this.initChart();
    }

    initChart() {
        if (!this.canvas) return;

        const ctx = this.canvas.getContext('2d');
        
        // Gradient fill
        const gradient = ctx.createLinearGradient(0, 0, 0, 320);
        gradient.addColorStop(0, 'rgba(59, 130, 246, 0.45)');
        gradient.addColorStop(0.7, 'rgba(6, 182, 212, 0.15)');
        gradient.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Spectral Intensity',
                    data: [],
                    borderColor: '#38BDF8',
                    borderWidth: 2.5,
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 2,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#38BDF8',
                    pointBorderColor: '#0B0F19',
                    pointBorderWidth: 1.5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 350
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(17, 24, 39, 0.95)',
                        titleColor: '#F9FAFB',
                        bodyColor: '#38BDF8',
                        borderColor: '#2D3748',
                        borderWidth: 1,
                        padding: 10,
                        displayColors: false,
                        callbacks: {
                            title: (tooltipItems) => `Wavelength: ${tooltipItems[0].label} nm`,
                            label: (tooltipItem) => `Intensity: ${Math.round(tooltipItem.raw).toLocaleString()} a.u.`
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Wavelength (nm)',
                            color: '#9CA3AF',
                            font: {
                                family: 'Inter',
                                size: 12,
                                weight: '500'
                            }
                        },
                        grid: {
                            color: 'rgba(45, 55, 72, 0.4)',
                            tickColor: 'transparent'
                        },
                        ticks: {
                            color: '#6B7280',
                            font: { family: 'JetBrains Mono', size: 11 },
                            maxTicksLimit: 12
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Intensity (Arbitrary Units)',
                            color: '#9CA3AF',
                            font: {
                                family: 'Inter',
                                size: 12,
                                weight: '500'
                            }
                        },
                        grid: {
                            color: 'rgba(45, 55, 72, 0.4)',
                            tickColor: 'transparent'
                        },
                        ticks: {
                            color: '#6B7280',
                            font: { family: 'JetBrains Mono', size: 11 },
                            callback: (val) => val.toLocaleString()
                        }
                    }
                }
            }
        });
    }

    /**
     * Update spectral curve with new wavelength and intensity arrays
     */
    updateSpectrum(wavelengths, intensities) {
        if (!this.chart || !wavelengths || !intensities) return;

        this.chart.data.labels = wavelengths.map(wl => Math.round(wl * 10) / 10);
        this.chart.data.datasets[0].data = intensities;
        this.chart.update('none'); // Fast update without full layout re-computation

        // Compute metrics
        let maxVal = -Infinity;
        let peakWl = null;

        for (let i = 0; i < intensities.length; i++) {
            if (intensities[i] > maxVal) {
                maxVal = intensities[i];
                peakWl = wavelengths[i];
            }
        }

        // Update metric labels in UI
        const metricPeakEl = document.getElementById('metricPeak');
        const metricMaxEl = document.getElementById('metricMaxIntensity');
        const metricRangeEl = document.getElementById('metricRange');
        const pointCountEl = document.getElementById('graphPointsCount');

        if (metricPeakEl && peakWl !== null) {
            metricPeakEl.textContent = `${Math.round(peakWl)} nm`;
        }
        if (metricMaxEl && maxVal !== -Infinity) {
            metricMaxEl.textContent = Math.round(maxVal).toLocaleString();
        }
        if (metricRangeEl && wavelengths.length > 0) {
            const minWl = Math.round(wavelengths[0]);
            const maxWl = Math.round(wavelengths[wavelengths.length - 1]);
            metricRangeEl.textContent = `${minWl} - ${maxWl} nm`;
        }
        if (pointCountEl) {
            pointCountEl.textContent = `${wavelengths.length} Wavelengths`;
        }
    }
}

// Global instance
window.spectrumChart = new SpectrumChartManager('spectrumChart');
