/**
 * COBALTO HUB - Módulo de Monitoreo Longitudinal (Timeline)
 * Gestiona la visualización temporal de las métricas tácticas y campañas CIB.
 */

window.CobaltoTimeline = {
    isLoaded: false,
    chartMacro: null,
    _historyData: [],
    _isScrubbing: false,
    _scrubberTimeout: null,

    init: function() {
        if (!this.isLoaded) {
            this.isLoaded = true;
            this.refresh();
        } else {
            this.refresh(true); // background refresh
        }
    },

    refresh: async function(isBackground = false) {
        try {
            const btn = document.querySelector("#tab-timeline .btn-tactical");
            if(btn) btn.innerText = "⏳ SINCRONIZANDO...";

            const res = await fetch("/api/timeline?hours=168");
            if (!res.ok) throw new Error("Error en red: " + res.status);
            
            const data = await res.json();
            this._historyData = data.history || [];
            
            this.renderMacroChart(this._historyData);
            this.renderCibTracker(data.cib_tracker || []);
            this.renderAlerts(this._historyData);
            this.initScrubber(this._historyData);

            this.isLoaded = true;
            if(btn) btn.innerText = "🔄 SINCRONIZAR CRONOLOGÍA";
        } catch (e) {
            console.error("[TIMELINE] Error cargando cronología:", e);
            document.getElementById("timeline-cib-container").innerHTML = `<div class="error-msg text-center text-muted" style="padding:1rem;">Error de conexión con el Mando Central: ${e.message}</div>`;
        }
    },

    initScrubber: function(history) {
        const scrubber = document.getElementById('timeline-scrubber');
        if (!scrubber) return;

        var now = Date.now();
        var maxHours = 168;
        var startTime = now - maxHours * 3600 * 1000;

        document.getElementById('scrubber-label-start').textContent = this._fmtDate(new Date(startTime));
        document.getElementById('scrubber-label-end').textContent = this._fmtDate(new Date(now));
        document.getElementById('scrubber-timestamp').textContent = this._fmtDate(new Date(now));
        document.getElementById('scrubber-mode').textContent = '🔴 EN VIVO';

        var self = this;
        scrubber.oninput = function() {
            var pct = parseInt(this.value) / parseInt(this.max);
            var ts = new Date(startTime + pct * (now - startTime));
            document.getElementById('scrubber-timestamp').textContent = self._fmtDate(ts);

            // Tooltip: muestra la fecha exacta al arrastrar
            var tooltip = document.getElementById('scrubber-tooltip');
            if (tooltip) {
                tooltip.textContent = self._fmtDate(ts);
                tooltip.style.display = 'block';
                var rect = this.getBoundingClientRect();
                var pctPos = (parseInt(this.value) - parseInt(this.min)) / (parseInt(this.max) - parseInt(this.min));
                var thumbX = pctPos * rect.width;
                tooltip.style.left = Math.max(0, Math.min(rect.width - 80, thumbX)) + 'px';
            }

            if (parseInt(this.value) >= parseInt(this.max) - 1) {
                document.getElementById('scrubber-mode').textContent = '🔴 EN VIVO';
                var entriesEl = document.getElementById('scrubber-entries-count');
                if (entriesEl) entriesEl.textContent = '📰 ' + (self._historyData.length || 0) + ' ciclos';
                return;
            }
            document.getElementById('scrubber-mode').textContent = '⏪ HISTÓRICO';

            clearTimeout(self._scrubberTimeout);
            self._scrubberTimeout = setTimeout(function() {
                self._fetchHistorical(ts.toISOString());
            }, 400);
        };
        scrubber.onblur = function() {
            var tooltip = document.getElementById('scrubber-tooltip');
            if (tooltip) tooltip.style.display = 'none';
        };
    },

    _fetchHistorical: async function(timestamp) {
        try {
            var res = await fetch('/api/historical?timestamp=' + encodeURIComponent(timestamp) + '&hours=48');
            if (!res.ok) throw new Error('Error: ' + res.status);
            var data = await res.json();
            var entriesEl = document.getElementById('scrubber-entries-count');
            if (entriesEl) entriesEl.textContent = '📰 ' + (data.total_entries || 0) + ' entradas';
        } catch (e) {
            console.error('[SCRUBBER] Error:', e);
        }
    },

    _fmtDate: function(d) {
        if (!d || isNaN(d.getTime())) return '?';
        return d.getDate() + '/' + (d.getMonth()+1) + '/' + d.getFullYear() + ' ' +
               String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
    },

    
    renderMacroChart: function(history) {
        const canvas = document.getElementById('timeline-chart-macro');
        if (!canvas) return;

        // Limpiar gráfico anterior
        if (this.chartMacro) {
            this.chartMacro.destroy();
        }

        if (!history || history.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#8892b0';
            ctx.font = '14px "Roboto Mono"';
            ctx.textAlign = 'center';
            ctx.fillText('EN ESPERA DE TELEMETRÍA TEMPORAL...', canvas.width / 2, canvas.height / 2);
            return;
        }

        // history viene ordenado DESC por defecto en get_history(), hay que invertirlo a ASC para el timeline
        const sorted = [...history].reverse();
        
        const labels = sorted.map(h => {
            const d = typeof h.ts === 'number' ? new Date(h.ts * 1000) : new Date(h.ts);
            if (isNaN(d.getTime())) return h.ts || '?';
            return `${d.getDate()}/${d.getMonth()+1} ${d.getHours()}:00`;
        });
        
        const scores = sorted.map(h => h.score_global);
        const bots = sorted.map(h => h.bots_detectados);
        const bot_rates = sorted.map(h => h.bot_rate || 0); // Nueva métrica: Entropía/Tasa bot
        
        // Mapear niveles de alerta para pintar el fondo o marcar puntos
        const alertColors = sorted.map(h => h.color_alerta);

        const ctx = canvas.getContext('2d');
        
        // Crear gradiente para la tasa de astroturfing
        const gradBots = ctx.createLinearGradient(0, 0, 0, 400);
        gradBots.addColorStop(0, 'rgba(255, 68, 68, 0.5)');
        gradBots.addColorStop(1, 'rgba(255, 68, 68, 0.0)');

        this.chartMacro = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Sentimiento Táctico Global',
                        data: scores,
                        borderColor: '#00e5ff',
                        backgroundColor: 'rgba(0, 229, 255, 0.15)',
                        borderWidth: 2,
                        tension: 0.4,
                        yAxisID: 'y',
                        fill: true,
                        pointBackgroundColor: alertColors,
                        pointRadius: 3,
                        pointBorderColor: '#05060a'
                    },
                    {
                        label: 'Densidad de Astroturfing (%)',
                        data: bot_rates,
                        borderColor: '#ff9500',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [4, 4],
                        tension: 0.4,
                        yAxisID: 'y2',
                        fill: false,
                        pointRadius: 0
                    },
                    {
                        label: 'CIB Volumen Activo (Nodos)',
                        data: bots,
                        borderColor: '#ff4444',
                        backgroundColor: gradBots,
                        borderWidth: 2,
                        tension: 0.3,
                        yAxisID: 'y1',
                        fill: true,
                        pointRadius: 2,
                        pointBackgroundColor: '#ff4444'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#8892b0', maxTicksLimit: 12, font: { family: 'Roboto Mono' } }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Sentimiento / Overton', color: '#00e5ff', font: { family: 'Roboto Mono' } },
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#00e5ff' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Volumen Bots (Absoluto)', color: '#ff4444', font: { family: 'Roboto Mono' } },
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#ff4444' }
                    },
                    y2: {
                        type: 'linear',
                        display: false,
                        position: 'right',
                        min: 0,
                        max: 100
                    }
                },
                plugins: {
                    legend: { labels: { color: '#f0f0f0', font: { family: 'Roboto Mono' } } },
                    tooltip: {
                        backgroundColor: 'rgba(5, 6, 10, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#ccd6f6',
                        borderColor: 'rgba(0, 229, 255, 0.3)',
                        borderWidth: 1,
                        titleFont: { family: 'Roboto Mono' }
                    }
                }
            }
        });
    },
renderCibTracker: function(cib_history) {
        const container = document.getElementById('timeline-cib-container');
        if (!container) return;

        if (!cib_history || cib_history.length === 0) {
            container.innerHTML = `<div class="empty-state text-center text-muted" style="padding:1.5rem;font-size:0.85rem;">Radar limpio. Sin operaciones inauténticas persistentes detectadas en 72h.</div>`;
            return;
        }

        // Deduplicar mostrando la actualización más reciente por narrativa
        let uniqueCamps = {};
        cib_history.forEach(c => {
            if (!uniqueCamps[c.narrativa] || uniqueCamps[c.narrativa].ts < c.ts) {
                uniqueCamps[c.narrativa] = c;
            }
        });

        const sorted = Object.values(uniqueCamps).sort((a,b) => b.ts - a.ts);
        
        let html = '';
        sorted.forEach(c => {
            const date = (typeof c.ts === 'number' ? new Date(c.ts * 1000) : new Date(c.ts)).toLocaleString();
            let statusBadge = '';
            let borderStyle = '';
            
            if (c.estado === 'ESCALANDO') {
                statusBadge = '<span style="background: rgba(255, 59, 48, 0.2); color: #ff4444; padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #ff4444; font-size: 0.7rem;">⚠️ ESCALANDO</span>';
                borderStyle = 'border-left: 3px solid #ff4444;';
            } else if (c.estado === 'PERSISTENTE') {
                statusBadge = '<span style="background: rgba(255, 149, 0, 0.2); color: #ff9500; padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #ff9500; font-size: 0.7rem;">⏳ PERSISTENTE</span>';
                borderStyle = 'border-left: 3px solid #ff9500;';
            } else {
                statusBadge = '<span style="background: rgba(0, 229, 255, 0.2); color: #00e5ff; padding: 2px 6px; border-radius: 4px; border: 1px solid #00e5ff; font-size: 0.7rem;">🟢 NUEVA</span>';
                borderStyle = 'border-left: 3px solid #00e5ff;';
            }

            html += `
                <div style="background: rgba(255,255,255,0.02); padding: 0.8rem; border-radius: 6px; ${borderStyle} margin-bottom: 0.5rem;">
                    <div class="flex-between" style="margin-bottom: 0.3rem;">
                        <span style="color: var(--text-muted); font-size: 0.75rem; font-family: monospace;">${date}</span>
                        ${statusBadge}
                    </div>
                    <div style="font-size: 0.85rem; margin-bottom: 0.4rem;">
                        <strong>Firma de Intervención:</strong> <span style="color: #ccd6f6;">${c.narrativa || 'Sin firma definida'}</span>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                        <span>Volumen Táctico: <strong style="color:var(--primary);">${c.tamaño}</strong></span>
                        <span>Ciclos de vida: <strong>${c.ciclos_detectada}</strong></span>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    },

    renderAlerts: function(history) {
        const container = document.getElementById('timeline-alerts-container');
        if (!container) return;

        // Filtrar ciclos que tuvieron alertas Críticas o Bot-Storm
        const criticas = history.filter(h => h.nivel_alerta === 'CRÍTICO' || h.nivel_alerta === 'BOT-STORM');
        
        if (criticas.length === 0) {
            container.innerHTML = `<div class="empty-state text-center text-muted" style="padding:1.5rem;font-size:0.85rem;">Sistema en parámetros nominales. No hay crisis registradas en el período.</div>`;
            return;
        }

        let html = '';
        // Mostramos las últimas 10
        criticas.slice(0, 10).forEach(h => {
            const date = (typeof h.ts === 'number' ? new Date(h.ts * 1000) : new Date(h.ts)).toLocaleString();
            html += `
                <div style="background: rgba(255,59,48,0.05); padding: 0.8rem; border-radius: 6px; border-left: 3px solid ${h.color_alerta}; margin-bottom: 0.5rem;">
                    <div class="flex-between" style="margin-bottom: 0.3rem;">
                        <span style="color: #ff4444; font-size: 0.75rem; font-weight: bold;">${h.nivel_alerta}</span>
                        <span style="color: var(--text-muted); font-size: 0.7rem; font-family: monospace;">${date}</span>
                    </div>
                    <div class="grid-2 gap-1" style="font-size: 0.75rem;">
                        <div>Score: <strong>${h.score_global.toFixed(2)}</strong></div>
                        <div>Bots: <strong>${h.bots_detectados}</strong></div>
                        <div style="grid-column: span 2; color: var(--text-muted); font-size: 0.7rem; margin-top: 0.3rem;">
                            Palabras Críticas: ${h.top_palabras_neg && h.top_palabras_neg.length ? h.top_palabras_neg.slice(0,4).map(k=>k.word || k[0] || k).join(', ') : 'N/A'}
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
};

// Auto-resolución: si el tab Timeline ya estaba activo al cargar este script defer
(function() {
    var tab = document.getElementById('tab-timeline');
    if (window._pendingTimelineInit || (tab && tab.classList.contains('active'))) {
        window._pendingTimelineInit = false;
        window.CobaltoTimeline.init();
    }
})();
