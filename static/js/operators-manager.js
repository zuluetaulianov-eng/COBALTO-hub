/**
 * COBALTO HUB — OperatorsManager (Blue Force Tracking - BFT)
 * Gestor de monitoreo de operadores de campo COBALTO Mobile
 */

window.OperatorsManager = {
    operators: [],
    filterText: '',
    pollingInterval: null,

    init: function() {
        this.refresh();
        if (!this.pollingInterval) {
            var self = this;
            this.pollingInterval = setInterval(function() {
                self.refresh(true);
            }, 10000);
        }
    },

    refresh: function(silent) {
        var self = this;
        fetch('/api/telemetry/operators')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data && Array.isArray(data.operators)) {
                    self.operators = data.operators;
                    self.render();
                    self.updateStats();
                }
            })
            .catch(function(err) {
                if (!silent) console.warn('[BFT] Error cargando operadores:', err);
            });
    },

    updateStats: function() {
        var total = this.operators.length;
        var active = 0;
        var idle = 0;
        var sos = 0;

        var now = new Date().getTime();
        this.operators.forEach(function(op) {
            var lastSeen = op.last_seen_iso ? new Date(op.last_seen_iso).getTime() : 0;
            var diffMin = (now - lastSeen) / 60000;

            if (op.status === 'EMERGENCY_SOS' || op.status === 'DEAD_MAN_TRIGGERED') {
                sos++;
            } else if (diffMin > 5) {
                idle++;
            } else {
                active++;
            }
        });

        var elTotal = document.getElementById('bft-stat-total');
        if (elTotal) elTotal.textContent = total;
        var elActive = document.getElementById('bft-stat-active');
        if (elActive) elActive.textContent = active;
        var elIdle = document.getElementById('bft-stat-idle');
        if (elIdle) elIdle.textContent = idle;
        var elSos = document.getElementById('bft-stat-sos');
        if (elSos) elSos.textContent = sos;

        var badge = document.getElementById('bft-badge');
        if (badge) {
            if (total > 0) {
                badge.style.display = 'inline-block';
                badge.textContent = total;
                badge.style.background = sos > 0 ? '#FF2D55' : '#00E5FF';
                badge.style.color = sos > 0 ? '#FFFFFF' : '#000000';
            } else {
                badge.style.display = 'none';
            }
        }
    },

    filter: function(text) {
        this.filterText = (text || '').toLowerCase().trim();
        this.render();
    },

    render: function() {
        var grid = document.getElementById('bft-operators-grid');
        if (!grid) return;

        var self = this;
        var list = this.operators;

        if (this.filterText) {
            list = list.filter(function(op) {
                var name = (op.operator_name || '').toLowerCase();
                var id = (op.operator_id || '').toLowerCase();
                var group = (op.unit_group || '').toLowerCase();
                return name.includes(self.filterText) || id.includes(self.filterText) || group.includes(self.filterText);
            });
        }

        if (list.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column:1/-1; padding:3rem; text-align:center;">
                    <div style="font-size:2.5rem; margin-bottom:0.5rem;">📡</div>
                    <p style="color:var(--primary); font-family:'Roboto Mono',monospace;">SIN OPERADORES REGISTRADOS</p>
                    <p style="font-size:0.8rem; color:var(--text-muted);">Los dispositivos COBALTO Mobile aparecerán aquí al transmitir telemetría.</p>
                </div>`;
            return;
        }

        var html = '';
        var now = new Date().getTime();

        list.forEach(function(op) {
            var lastSeen = op.last_seen_iso ? new Date(op.last_seen_iso).getTime() : 0;
            var diffMin = Math.floor((now - lastSeen) / 60000);
            var isOffline = diffMin > 5;
            var isSos = op.status === 'EMERGENCY_SOS' || op.status === 'DEAD_MAN_TRIGGERED';

            var cardBorder = isSos ? '1px solid #FF2D55' : (isOffline ? '1px solid #FF9500' : '1px solid rgba(0,229,255,0.3)');
            var glow = isSos ? 'box-shadow: 0 0 15px rgba(255,45,85,0.4);' : (isOffline ? '' : 'box-shadow: 0 0 10px rgba(0,229,255,0.1);');

            var statusBadge = '';
            if (isSos) {
                statusBadge = '<span class="badge-tactical" style="background:#FF2D55; color:#fff; font-size:0.65rem; padding:2px 6px; animation:pulse 1s infinite;">🚨 SOS EMERGENCIA</span>';
            } else if (isOffline) {
                statusBadge = `<span class="badge-tactical" style="background:#FF9500; color:#000; font-size:0.65rem; padding:2px 6px;">🟡 HACE ${diffMin}M</span>`;
            } else {
                statusBadge = '<span class="badge-tactical" style="background:#00FFAA; color:#000; font-size:0.65rem; padding:2px 6px;">🟢 EN LÍNEA</span>';
            }

            var batColor = op.battery_level > 50 ? '#00FFAA' : (op.battery_level > 20 ? '#FF9500' : '#FF2D55');

            html += `
            <div class="panel-glass" style="padding:1rem; border-radius:8px; border:${cardBorder}; ${glow} display:flex; flex-direction:column; justify-content:space-between; gap:0.8rem;">
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
                        <div>
                            <div style="font-weight:bold; color:var(--primary); font-size:1rem; font-family:'Roboto Mono',monospace; display:flex; align-items:center; gap:0.4rem;">
                                👤 ${self.escapeHTML(op.operator_name || 'Operador')}
                            </div>
                            <div style="font-size:0.7rem; color:var(--text-muted);">ID: ${self.escapeHTML(op.operator_id)} | ${self.escapeHTML(op.unit_group)}</div>
                        </div>
                        ${statusBadge}
                    </div>

                    <!-- TELEMETRÍA RÁPIDA -->
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; background:rgba(0,0,0,0.3); padding:0.6rem; border-radius:4px; margin-bottom:0.5rem; font-size:0.75rem;">
                        <div>
                            <span style="color:var(--text-muted);">🔋 Batería:</span>
                            <span style="font-weight:bold; color:${batColor}; font-family:'Roboto Mono',monospace;">${op.battery_level}%</span>
                        </div>
                        <div>
                            <span style="color:var(--text-muted);">📶 Red:</span>
                            <span style="font-weight:bold; color:#00E5FF;">${self.escapeHTML(op.network_type)}</span>
                        </div>
                        <div style="grid-column:1/-1;">
                            <span style="color:var(--text-muted);">📍 Posición:</span>
                            <span style="font-family:'Roboto Mono',monospace; color:#fff;">${op.latitude.toFixed(4)}, ${op.longitude.toFixed(4)}</span>
                        </div>
                    </div>
                </div>

                <!-- BOTONES DE ACCIÓN -->
                <div style="display:flex; gap:0.5rem;">
                    <button onclick="OperatorsManager.focusOnMap(${op.latitude}, ${op.longitude}, '${self.escapeHTML(op.operator_name)}')" class="btn-tactical" style="flex:1; font-size:0.7rem; padding:4px 8px; border-color:#00E5FF; color:#00E5FF;">
                        🗺️ MAPA
                    </button>
                    <button onclick="OperatorsManager.showDetail('${self.escapeHTML(op.operator_id)}')" class="btn-tactical" style="flex:1; font-size:0.7rem; padding:4px 8px;">
                        📋 DETALLES
                    </button>
                </div>
            </div>`;
        });

        grid.innerHTML = html;
    },

    focusOnMap: function(lat, lon, name) {
        if (window.CobaltoCore) {
            window.CobaltoCore.switchTab('tab-map');
        }
        setTimeout(function() {
            if (window.UnifiedMap && window.UnifiedMap.map) {
                window.UnifiedMap.map.setView([lat, lon], 14);
            }
        }, 300);
    },

    showDetail: function(operatorId) {
        var op = this.operators.find(function(o) { return o.operator_id === operatorId; });
        if (!op) return;

        var modal = document.getElementById('bft-detail-modal');
        var title = document.getElementById('bft-modal-title');
        var body = document.getElementById('bft-modal-body');
        if (!modal || !body) return;

        if (title) title.textContent = '👥 ' + op.operator_name;

        var self = this;
        body.innerHTML = '<p style="color:var(--primary);">Cargando rastro de telemetría GPS...</p>';
        modal.style.display = 'flex';

        fetch('/api/telemetry/operators/' + encodeURIComponent(operatorId) + '/trail')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var trail = data.trail || [];
                var trailHtml = '';
                trail.slice(0, 8).forEach(function(t) {
                    trailHtml += `<div style="font-family:'Roboto Mono',monospace; font-size:0.75rem; border-bottom:1px solid rgba(255,255,255,0.05); padding:3px 0;">
                        <span>📍 ${t.latitude.toFixed(5)}, ${t.longitude.toFixed(5)}</span> | 
                        <span style="color:var(--text-muted);">${t.timestamp}</span> | 
                        <span>🔋 ${t.battery_level}%</span>
                    </div>`;
                });

                body.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.8rem;">
                    <div style="background:rgba(0,229,255,0.05); padding:0.8rem; border-radius:6px; border:1px solid rgba(0,229,255,0.2);">
                        <div><strong>Indicativo / Nombre:</strong> ${self.escapeHTML(op.operator_name)}</div>
                        <div><strong>ID Único Dispositivo:</strong> ${self.escapeHTML(op.operator_id)}</div>
                        <div><strong>Modelo del Móvil:</strong> ${self.escapeHTML(op.device_model)}</div>
                        <div><strong>Grupo de Trabajo:</strong> ${self.escapeHTML(op.unit_group)}</div>
                        <div><strong>Último Latido:</strong> ${self.escapeHTML(op.last_seen_iso)}</div>
                    </div>

                    <div style="font-weight:bold; color:var(--primary); margin-top:0.4rem;">📍 HISTÓRICO DE RASTRO GPS (BREADCRUMBS):</div>
                    <div style="max-height:160px; overflow-y:auto; background:rgba(0,0,0,0.4); padding:0.5rem; border-radius:4px;">
                        ${trailHtml || '<div style="color:var(--text-muted);">Sin historial de rastro GPS reciente.</div>'}
                    </div>

                    <div style="display:flex; justify-content:flex-end; gap:0.5rem; margin-top:0.8rem;">
                        <button onclick="OperatorsManager.focusOnMap(${op.latitude}, ${op.longitude}, '${self.escapeHTML(op.operator_name)}')" class="btn-tactical" style="padding:6px 12px; border-color:#00E5FF; color:#00E5FF;">
                            🗺️ CENTRAR EN MAPA UNIFICADO
                        </button>
                    </div>
                </div>`;
            })
            .catch(function(err) {
                body.innerHTML = '<p style="color:#FF2D55;">Fallo al cargar rastro del operador.</p>';
            });
    },

    escapeHTML: function(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
};
