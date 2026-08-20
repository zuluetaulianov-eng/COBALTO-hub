/**
 * COBALTO HUB - Módulo de Monitoreo Longitudinal e Incidentes (Incident Command & Timeline)
 * Gestiona el rastreo de eventos tácticos, matriz de incidentes y telemetría de opinión.
 */

window.CobaltoTimeline = {
    isLoaded: false,
    chartMacro: null,
    _historyData: [],
    _incidentsData: [],
    _activeFilter: "ALL",
    _searchQuery: "",
    _isScrubbing: false,
    _scrubberTimeout: null,

    init: function() {
        if (!this.isLoaded) {
            this.isLoaded = true;
            this.refresh();
        } else {
            this.refresh(true);
        }
    },

    refresh: async function(isBackground = false) {
        try {
            const btn = document.querySelector("#tab-timeline .btn-export-ia");
            if (btn && !isBackground) btn.innerText = "⏳ SINCRONIZANDO...";

            const res = await fetch("/api/timeline?hours=168");
            if (!res.ok) throw new Error("Error HTTP " + res.status);

            const data = await res.json();
            this._historyData = data.history || [];
            this._incidentsData = data.incidents || [];

            this.updateKpis();
            this.renderIncidents();
            this.renderMacroChart(this._historyData);
            this.renderCibTracker(data.cib_tracker || []);
            this.renderAlerts(this._historyData);
            this.initScrubber(this._historyData);

            this.isLoaded = true;
            if (btn) btn.innerText = "🔄 SINCRONIZAR";
        } catch (e) {
            console.error("[INCIDENT-COMMAND] Error sincronizando datos:", e);
            const container = document.getElementById("incidents-feed-container");
            if (container) {
                container.innerHTML = `<div class="error-msg text-center text-muted" style="padding: 1.5rem;">Error de conexión con el Mando Central: ${e.message}</div>`;
            }
        }
    },

    updateKpis: function() {
        const incidents = this._incidentsData || [];

        const criticalCount = incidents.filter(i => (i.severity === "CRITICAL" || i.severity === "HIGH") && i.status !== "CLOSED").length;
        const colCount = incidents.filter(i => i.theater === "COL").length;
        const venCount = incidents.filter(i => i.theater === "VEN").length;
        const cibCount = incidents.filter(i => i.category === "CIB" || i.category === "INFO_OP").length;

        const elCrit = document.getElementById("kpi-inc-critical");
        const elCol = document.getElementById("kpi-inc-col");
        const elVen = document.getElementById("kpi-inc-ven");
        const elCib = document.getElementById("kpi-inc-cib");

        if (elCrit) elCrit.textContent = criticalCount;
        if (elCol) elCol.textContent = colCount;
        if (elVen) elVen.textContent = venCount;
        if (elCib) elCib.textContent = cibCount;

        // Alerta de umbral si existen incidentes críticos abiertos
        if (criticalCount > 0 && !this._alertedCritical) {
            this._alertedCritical = true;
            this.playCriticalAlertSound();
            if (elCrit && elCrit.parentElement) {
                elCrit.parentElement.style.animation = "pulse 1.5s infinite alternate";
            }
        }
    },

    playCriticalAlertSound: function() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        } catch(e) {
            // Audio no soportado o bloqueado por navegador
        }
    },

    exportMacroChartPng: function() {
        const canvas = document.getElementById("timeline-chart-macro");
        if (!canvas) return;
        const link = document.createElement("a");
        link.download = `TENDENCIA_LONGITUDINAL_${new Date().toISOString().slice(0, 10)}.png`;
        link.href = canvas.toDataURL("image/png");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },

    setFilter: function(filterName) {
        this._activeFilter = filterName;

        const chips = document.querySelectorAll("#incident-filter-chips .config-chip");
        chips.forEach(chip => {
            if (chip.getAttribute("data-filter") === filterName) {
                chip.classList.add("active");
            } else {
                chip.classList.remove("active");
            }
        });

        this.renderIncidents();
    },

    searchIncidents: function(query) {
        this._searchQuery = (query || "").toLowerCase().trim();
        this.renderIncidents();
    },

    renderIncidents: function() {
        const container = document.getElementById("incidents-feed-container");
        const badge = document.getElementById("incidents-count-badge");
        if (!container) return;

        let filtered = [...(this._incidentsData || [])];

        // 1. Filtrar por chip activo
        if (this._activeFilter === "COL") {
            filtered = filtered.filter(i => i.theater === "COL");
        } else if (this._activeFilter === "VEN") {
            filtered = filtered.filter(i => i.theater === "VEN");
        } else if (this._activeFilter === "FRONTERA") {
            filtered = filtered.filter(i => i.theater === "FRONTERA" || i.theater === "BORDER");
        } else if (this._activeFilter === "CRITICAL") {
            filtered = filtered.filter(i => i.severity === "CRITICAL" || i.severity === "HIGH");
        } else if (this._activeFilter === "CIB") {
            filtered = filtered.filter(i => i.category === "CIB" || i.category === "INFO_OP");
        }

        // 2. Filtrar por búsqueda de texto
        if (this._searchQuery) {
            filtered = filtered.filter(i =>
                (i.title && i.title.toLowerCase().includes(this._searchQuery)) ||
                (i.summary && i.summary.toLowerCase().includes(this._searchQuery)) ||
                (i.source && i.source.toLowerCase().includes(this._searchQuery)) ||
                (i.theater && i.theater.toLowerCase().includes(this._searchQuery))
            );
        }

        if (badge) badge.textContent = `${filtered.length} cargados`;

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="empty-state text-center text-muted" style="padding: 2rem;">
                    <div class="empty-icon">🛡️</div>
                    <div class="empty-title">SIN INCIDENTES REGISTRADOS</div>
                    <div class="empty-desc">No se encontraron eventos coincidentes con los criterios de filtro seleccionados.</div>
                </div>
            `;
            return;
        }

        let html = "";
        filtered.forEach(inc => {
            const sevColor = inc.severity === "CRITICAL" ? "#ff4444" : (inc.severity === "HIGH" ? "#ffaa00" : (inc.severity === "MEDIUM" ? "#00e5ff" : "#888"));
            const sevBadge = `<span style="background: rgba(${inc.severity === 'CRITICAL' ? '255,68,68' : '255,170,0'}, 0.15); color: ${sevColor}; padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid ${sevColor}; font-size: 0.7rem;">${inc.severity || 'HIGH'}</span>`;
            
            let theaterFlag = "🌐 GLOBAL";
            if (inc.theater === "COL") theaterFlag = "🇨🇴 COLOMBIA";
            else if (inc.theater === "VEN") theaterFlag = "🇻🇪 VENEZUELA";
            else if (inc.theater === "FRONTERA") theaterFlag = "⚔️ FRONTERA";

            const statusColors = {
                "OPEN": "#ff4444",
                "INVESTIGATING": "#ffaa00",
                "CONTAINED": "#00e5ff",
                "CLOSED": "#64748b"
            };
            const statusNames = {
                "OPEN": "🔴 ABIERTO",
                "INVESTIGATING": "🟡 INVESTIGANDO",
                "CONTAINED": "🔵 MITIGADO",
                "CLOSED": "⚪ CERRADO"
            };
            const stColor = statusColors[inc.status] || "#888";
            const stName = statusNames[inc.status] || inc.status;

            const lat = parseFloat(inc.latitude || inc.lat || 0);
            const lng = parseFloat(inc.longitude || inc.lng || 0);
            const hasLocation = lat !== 0 && lng !== 0;

            const safeTitle = (inc.title || "").replace(/'/g, "\\'");
            const safeSummary = (inc.summary || "").replace(/'/g, "\\'");

            html += `
                <div class="panel-glass" style="padding: 0.9rem; margin-bottom: 0.6rem; border-left: 3px solid ${sevColor}; background: rgba(10, 11, 16, 0.6);">
                    <div class="flex-between items-center" style="margin-bottom: 0.4rem;">
                        <div class="flex items-center" style="gap: 0.5rem;">
                            ${sevBadge}
                            <span class="font-mono text-muted" style="font-size: 0.75rem;">${theaterFlag}</span>
                            <span class="font-mono text-muted" style="font-size: 0.75rem;">• ${inc.category || 'SECURITY'}</span>
                        </div>
                        <div class="flex items-center" style="gap: 0.4rem;">
                            <!-- SELECTOR ESTADO -->
                            <select onchange="CobaltoTimeline.updateStatus('${inc.id}', this.value)" 
                                    style="background: rgba(0,0,0,0.5); color: ${stColor}; border: 1px solid ${stColor}; border-radius: 4px; font-size: 0.7rem; font-family: monospace; padding: 2px 4px; cursor: pointer;">
                                <option value="OPEN" ${inc.status === 'OPEN' ? 'selected' : ''}>🔴 ABIERTO</option>
                                <option value="INVESTIGATING" ${inc.status === 'INVESTIGATING' ? 'selected' : ''}>🟡 INVESTIGANDO</option>
                                <option value="CONTAINED" ${inc.status === 'CONTAINED' ? 'selected' : ''}>🔵 MITIGADO</option>
                                <option value="CLOSED" ${inc.status === 'CLOSED' ? 'selected' : ''}>⚪ CERRADO</option>
                            </select>
                            <button onclick="CobaltoTimeline.deleteIncident('${inc.id}')" title="Eliminar Incidente" style="background:none; border:none; color:#ff4444; font-size:0.85rem; cursor:pointer; padding: 0 2px;">🗑️</button>
                        </div>
                    </div>

                    <div class="font-mono" style="font-weight: bold; font-size: 0.9rem; color: #fff; margin-bottom: 0.4rem;">
                        ${inc.title || 'Incidente Táctico'}
                    </div>

                    <div style="font-size: 0.8rem; color: #cbd5e1; line-height: 1.4; margin-bottom: 0.6rem;">
                        ${inc.summary || 'Sin detalles registrados.'}
                    </div>

                    <div class="flex-between items-center" style="border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.5rem; font-size: 0.75rem;">
                        <div class="font-mono text-muted">
                            📡 ${inc.source || 'Monitor OSINT'} • ${this._fmtDateStr(inc.timestamp)}
                        </div>
                        <div class="flex items-center" style="gap: 0.4rem;">
                            ${hasLocation ? `
                                <button class="btn-tactical" style="padding: 2px 8px; font-size: 0.7rem;" 
                                        onclick="CobaltoTimeline.focusIncidentOnMap(${lat}, ${lng}, '${safeTitle}')">
                                    📍 VER EN MAPA
                                </button>
                            ` : ''}
                            <button class="btn-tactical" style="padding: 2px 8px; font-size: 0.7rem;" 
                                    onclick="CobaltoTimeline.triggerRagAnalysis('${safeTitle}', '${safeSummary}')">
                                🎯 HIPÓTESIS RAG
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    focusIncidentOnMap: function(lat, lng, title) {
        if (window.CobaltoCore && window.CobaltoCore.switchTab) {
            window.CobaltoCore.switchTab("tab-map");
        }
        setTimeout(() => {
            if (window.UnifiedMap && window.UnifiedMap.flyToCoordinates) {
                window.UnifiedMap.flyToCoordinates(lat, lng, 12, title);
            }
        }, 300);
    },

    triggerRagAnalysis: function(title, summary) {
        if (window.CobaltoCore && window.CobaltoCore.switchTab) {
            window.CobaltoCore.switchTab("tab-ai-chat");
        }
        setTimeout(() => {
            const chatInput = document.getElementById("ai-chat-input") || document.getElementById("chat-input");
            if (chatInput) {
                chatInput.value = `/hypothesis Analizar antecedentes tácticos, posibles actores involucrados e impacto operacional del incidente: "${title}". Resumen: ${summary}`;
                chatInput.focus();
            }
        }, 300);
    },

    openNewIncidentModal: function() {
        const modal = document.getElementById("modal-create-incident");
        if (modal) modal.style.display = "flex";
    },

    closeNewIncidentModal: function() {
        const modal = document.getElementById("modal-create-incident");
        if (modal) modal.style.display = "none";
    },

    submitNewIncident: async function() {
        const title = document.getElementById("inc-form-title")?.value;
        const theater = document.getElementById("inc-form-theater")?.value || "GLOBAL";
        const category = document.getElementById("inc-form-category")?.value || "SECURITY";
        const severity = document.getElementById("inc-form-severity")?.value || "HIGH";
        const source = document.getElementById("inc-form-source")?.value || "Operador COBALTO";
        const lat = parseFloat(document.getElementById("inc-form-lat")?.value || "0");
        const lng = parseFloat(document.getElementById("inc-form-lng")?.value || "0");
        const summary = document.getElementById("inc-form-summary")?.value || "";

        if (!title) return;

        try {
            const res = await fetch("/api/incidents/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title, theater, category, severity, source,
                    latitude: lat, longitude: lng, summary
                })
            });

            if (res.ok) {
                this.closeNewIncidentModal();
                document.getElementById("form-create-incident")?.reset();
                this.refresh();
            } else {
                alert("Error al registrar el incidente");
            }
        } catch (e) {
            console.error("Error enviando incidente:", e);
        }
    },

    updateStatus: async function(incId, newStatus) {
        try {
            const res = await fetch("/api/incidents/status", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: incId, status: newStatus })
            });

            if (res.ok) {
                const inc = (this._incidentsData || []).find(i => i.id === incId);
                if (inc) inc.status = newStatus;
                this.updateKpis();
                this.renderIncidents();
            }
        } catch (e) {
            console.error("Error actualizando estado:", e);
        }
    },

    deleteIncident: async function(incId) {
        if (!confirm("¿Eliminar este incidente registrado?")) return;
        try {
            const res = await fetch("/api/incidents/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: incId })
            });

            if (res.ok) {
                this._incidentsData = (this._incidentsData || []).filter(i => i.id !== incId);
                this.updateKpis();
                this.renderIncidents();
            }
        } catch (e) {
            console.error("Error eliminando incidente:", e);
        }
    },

    initScrubber: function(history) {
        const scrubber = document.getElementById('timeline-scrubber');
        if (!scrubber) return;

        var now = Date.now();
        var maxHours = 168;
        var startTime = now - maxHours * 3600 * 1000;

        const lblStart = document.getElementById('scrubber-label-start');
        const lblEnd = document.getElementById('scrubber-label-end');
        const lblTs = document.getElementById('scrubber-timestamp');
        const lblMode = document.getElementById('scrubber-mode');

        if (lblStart) lblStart.textContent = this._fmtDate(new Date(startTime));
        if (lblEnd) lblEnd.textContent = this._fmtDate(new Date(now));
        if (lblTs) lblTs.textContent = this._fmtDate(new Date(now));
        if (lblMode) lblMode.textContent = '🔴 EN VIVO';

        var self = this;
        scrubber.oninput = function() {
            var pct = parseInt(this.value) / parseInt(this.max);
            var ts = new Date(startTime + pct * (now - startTime));
            if (lblTs) lblTs.textContent = self._fmtDate(ts);

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
                if (lblMode) lblMode.textContent = '🔴 EN VIVO';
                var entriesEl = document.getElementById('scrubber-entries-count');
                if (entriesEl) entriesEl.textContent = '📰 ' + (self._historyData.length || 0) + ' ciclos';
                return;
            }
            if (lblMode) lblMode.textContent = '⏪ HISTÓRICO';

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
        return d.getDate() + '/' + (d.getMonth() + 1) + '/' + d.getFullYear() + ' ' +
            String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    },

    _fmtDateStr: function(str) {
        if (!str) return 'Reciente';
        try {
            const d = new Date(str);
            if (isNaN(d.getTime())) return str;
            return this._fmtDate(d);
        } catch (e) {
            return str;
        }
    },

    renderMacroChart: function(history) {
        const canvas = document.getElementById('timeline-chart-macro');
        if (!canvas) return;

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

        const sorted = [...history].reverse();
        const labels = sorted.map(h => {
            const d = typeof h.ts === 'number' ? new Date(h.ts * 1000) : new Date(h.ts);
            if (isNaN(d.getTime())) return h.ts || '?';
            return `${d.getDate()}/${d.getMonth()+1} ${d.getHours()}:00`;
        });

        const scores = sorted.map(h => h.score_global);
        const bots = sorted.map(h => h.bots_detectados);
        const bot_rates = sorted.map(h => h.bot_rate || 0);
        const alertColors = sorted.map(h => h.color_alerta);

        const ctx = canvas.getContext('2d');
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
            container.innerHTML = `<div class="empty-state text-center text-muted" style="padding:1rem;font-size:0.8rem;">Radar limpio. Sin campañas CIB persistentes detectadas.</div>`;
            return;
        }

        let uniqueCamps = {};
        cib_history.forEach(c => {
            if (!uniqueCamps[c.narrativa] || uniqueCamps[c.narrativa].ts < c.ts) {
                uniqueCamps[c.narrativa] = c;
            }
        });

        const sorted = Object.values(uniqueCamps).sort((a, b) => b.ts - a.ts);

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
                <div style="background: rgba(255,255,255,0.02); padding: 0.7rem; border-radius: 6px; ${borderStyle} margin-bottom: 0.4rem;">
                    <div class="flex-between" style="margin-bottom: 0.2rem;">
                        <span style="color: var(--text-muted); font-size: 0.7rem; font-family: monospace;">${date}</span>
                        ${statusBadge}
                    </div>
                    <div style="font-size: 0.8rem; margin-bottom: 0.3rem;">
                        <strong style="color:#aaa;">Firma:</strong> <span style="color: #ccd6f6;">${c.narrativa || 'Sin firma definida'}</span>
                    </div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                        <span>Volumen: <strong style="color:var(--primary);">${c.tamaño}</strong></span>
                        <span>Ciclos: <strong>${c.ciclos_detectada}</strong></span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    renderAlerts: function(history) {
        const container = document.getElementById('timeline-alerts-container');
        if (!container) return;

        const criticas = (history || []).filter(h => h.nivel_alerta === 'CRÍTICO' || h.nivel_alerta === 'BOT-STORM');

        if (criticas.length === 0) {
            container.innerHTML = `<div class="empty-state text-center text-muted" style="padding:1rem;font-size:0.8rem;">Sin alertas críticas registradas.</div>`;
            return;
        }

        let html = '';
        criticas.slice(0, 10).forEach(h => {
            const date = (typeof h.ts === 'number' ? new Date(h.ts * 1000) : new Date(h.ts)).toLocaleString();
            html += `
                <div style="background: rgba(255,59,48,0.05); padding: 0.7rem; border-radius: 6px; border-left: 3px solid ${h.color_alerta}; margin-bottom: 0.4rem;">
                    <div class="flex-between" style="margin-bottom: 0.2rem;">
                        <span style="color: #ff4444; font-size: 0.7rem; font-weight: bold;">${h.nivel_alerta}</span>
                        <span style="color: var(--text-muted); font-size: 0.7rem; font-family: monospace;">${date}</span>
                    </div>
                    <div class="grid-2 gap-1" style="font-size: 0.7rem;">
                        <div>Score: <strong>${h.score_global ? h.score_global.toFixed(2) : '0'}</strong></div>
                        <div>Bots: <strong>${h.bots_detectados || 0}</strong></div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    exportTimelineReport: function() {
        const incidents = this._incidentsData || [];
        const history = this._historyData || [];

        let report = `========================================================\n`;
        report += `COBALTO HUB - AUDITORÍA CRONOLÓGICA DE INCIDENTES Y CRISIS\n`;
        report += `FECHA DE AUDITORÍA: ${new Date().toISOString()}\n`;
        report += `FILTRO ACTIVO: ${this._activeFilter}\n`;
        report += `========================================================\n\n`;

        report += `[1] RESUMEN DE INCIDENTES TÁCTICOS (${incidents.length} REGISTRADOS)\n`;
        report += `--------------------------------------------------------\n`;
        incidents.forEach((inc, idx) => {
            report += `${idx + 1}. [${inc.severity || 'HIGH'}] ${inc.title}\n`;
            report += `   • ID: ${inc.id} | Teatro: ${inc.theater} | Estado: ${inc.status}\n`;
            report += `   • Fuente: ${inc.source} | Fecha: ${inc.timestamp || inc.created_at}\n`;
            if (inc.summary) report += `   • Resumen: ${inc.summary}\n`;
            report += `\n`;
        });

        report += `[2] HISTORIAL DE CRISIS Y EVENTOS REGISTRADOS (${history.length} CICLOS)\n`;
        report += `--------------------------------------------------------\n`;
        history.slice(0, 20).forEach(h => {
            report += `• [${h.ts}] Alerta: ${h.nivel_alerta} | Score: ${h.score_global} | Bot Rate: ${h.bot_rate}%\n`;
        });

        report += `\n========================================================\n`;
        report += `FIN DE AUDITORÍA CRONOLÓGICA - COBALTO HUB\n`;

        const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `AUDITORIA_CRONOLOGICA_${new Date().toISOString().slice(0, 10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
};

// Auto-inicialización si el tab está activo
(function() {
    var tab = document.getElementById('tab-timeline');
    if (window._pendingTimelineInit || (tab && tab.classList.contains('active'))) {
        window._pendingTimelineInit = false;
        window.CobaltoTimeline.init();
    }
})();
