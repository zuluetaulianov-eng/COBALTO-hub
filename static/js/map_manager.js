/**
 * Cobalto Hub - Map Manager v2.1
 * Mapa táctico con interpolación de coordenadas y persistencia de marcadores.
 */

window.CobaltoMap = {
    state: {
        map: null,
        markerLayers: {},
        markersStore: {}, // Almacén persistente de marcadores [id] => marker
        heatLayer: null,
        darkLayer: null,
        satelliteLayer: null,
        layerControl: null,
        autoRefreshTimer: null,
        currentPoints: []
    },

    CATEGORIES: {
        alert:     { color: '#FF1744', label: 'Alertas',       icon: '🔴' },
        flight:    { color: '#00E5FF', label: 'Vuelos',        icon: '✈️' },
        vessel:    { color: '#FFD740', label: 'Embarcaciones',  icon: '🚢' },
        event:     { color: '#FF9100', label: 'Eventos',       icon: '⚠️' },
        ai_geo:    { color: '#E040FB', label: 'Geo-IA',        icon: '🤖' },
        satellite: { color: '#69F0AE', label: 'Satélite',      icon: '🛰️' },
        default:   { color: '#00E5FF', label: 'Otros',         icon: '📌' }
    },

    utils: {
        _htmlEscaper: (str => String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[m]))),
        escapeHTML: function(s) {
            return (window.CobaltoCore && window.CobaltoCore.utils.escapeHTML) ? window.CobaltoCore.utils.escapeHTML(s) : this._htmlEscaper(s);
        },
        
        getPointId: function(p) {
            // Generar un ID único determinista basado en los metadatos si no viene ID explícito
            return p.id || (encodeURIComponent((p.title || '') + (p.source || '') + (p.type || '')));
        },

        /**
         * Interpola suavemente la posición de un marcador de A a B.
         */
        animateMarker: function(marker, destLatLng) {
            if (!destLatLng || isNaN(destLatLng.lat) || isNaN(destLatLng.lng)) return;
            const startLatLng = marker.getLatLng();
            if (!startLatLng || isNaN(startLatLng.lat) || isNaN(startLatLng.lng)) {
                marker.setLatLng(destLatLng);
                return;
            }
            if (startLatLng.lat === destLatLng.lat && startLatLng.lng === destLatLng.lng) return;

            // Cancelar cualquier animación activa previa en este marcador
            if (marker._animFrameId) {
                cancelAnimationFrame(marker._animFrameId);
                delete marker._animFrameId;
            }

            const duration = 2000; // 2 segundos para la transición
            const startTime = performance.now();

            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                
                // Easing (easeOutCubic)
                const t = progress - 1;
                const easedProgress = t * t * t + 1;

                const lat = startLatLng.lat + (destLatLng.lat - startLatLng.lat) * easedProgress;
                const lng = startLatLng.lng + (destLatLng.lng - startLatLng.lng) * easedProgress;
                
                if (!isNaN(lat) && !isNaN(lng)) {
                    marker.setLatLng([lat, lng]);
                }

                if (progress < 1) {
                    marker._animFrameId = requestAnimationFrame(animate);
                } else {
                    delete marker._animFrameId;
                }
            };

            marker._animFrameId = requestAnimationFrame(animate);
        }
    },

    getCategory: function(p) {
        const t = (p.type || '').toLowerCase();
        const s = (p.source || '').toLowerCase();
        if (t.includes('ai_geo') || s.includes('geo-ia')) return 'ai_geo';
        if (t.includes('flight') || t.includes('vuelo') || s.includes('vuelo') || s.includes('flight')) return 'flight';
        if (t.includes('vessel') || t.includes('barco') || t.includes('embarcacion') || s.includes('barco') || s.includes('vessel') || s.includes('embarcacion')) return 'vessel';
        if (t.includes('alert') || t.includes('critic') || t.includes('urgent')) return 'alert';
        if (t.includes('satellite') || s.includes('firms') || s.includes('nasa')) return 'satellite';
        return 'event';
    },

    init: function() {
        if (typeof L === 'undefined') {
            console.warn('[MAP] Leaflet no está cargado. Reintentando en 1 segundo...');
            setTimeout(() => this.init(), 1000);
            return;
        }
        if (this.state.map) return;

        const container = document.getElementById('map-container');
        if (!container) {
            console.warn('[MAP] Contenedor de mapa no encontrado.');
            return;
        }

        this.state.map = L.map('map-container', {
            zoomControl: true,
            attributionControl: true
        }).setView([7.0, -66.0], 6);

        this.state.darkLayer = L.tileLayer(
            'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            { maxZoom: 19, attribution: '&copy; <a href="https://carto.com/">CARTO</a>' }
        ).addTo(this.state.map);

        this.state.satelliteLayer = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            { maxZoom: 19, attribution: '&copy; Esri, Maxar, Earthstar, USDA' }
        );

        for (const key of Object.keys(this.CATEGORIES)) {
            if (typeof L.markerClusterGroup === 'function') {
                this.state.markerLayers[key] = L.markerClusterGroup({
                    showCoverageOnHover: false,
                    spiderfyOnMaxZoom: true,
                    maxClusterRadius: 50,
                    chunkedLoading: true
                });
            } else {
                this.state.markerLayers[key] = L.layerGroup();
            }
            this.state.map.addLayer(this.state.markerLayers[key]);
        }

        const overlays = {};
        for (const [key, cfg] of Object.entries(this.CATEGORIES)) {
            overlays[cfg.icon + ' ' + cfg.label] = this.state.markerLayers[key];
        }

        this.state.layerControl = L.control.layers(
            { '\uD83C\uDF11 Oscuro': this.state.darkLayer, '\uD83D\uDEF0 Satelital': this.state.satelliteLayer },
            overlays,
            { position: 'bottomleft' }
        ).addTo(this.state.map);

        this.addLegend();
        this.setupGeocoder();
        this.loadMapData();
        this.startAutoRefresh();
    },

    addLegend: function() {
        const ctrl = L.control({ position: 'bottomright' });
        const cats = this.CATEGORIES;
        ctrl.onAdd = function () {
            const div = L.DomUtil.create('div', 'map-legend');
            let html = '<div class="legend-title">Leyenda</div>';
            for (const cfg of Object.values(cats)) {
                html += '<div class="legend-item">' +
                    '<span class="legend-dot" style="background:' + cfg.color + ';box-shadow:0 0 6px ' + cfg.color + ';"></span>' +
                    cfg.icon + ' ' + cfg.label +
                    '</div>';
            }
            div.innerHTML = html;
            return div;
        };
        ctrl.addTo(this.state.map);
    },

    setupGeocoder: function() {
        const ctrl = L.control({ position: 'topleft' });
        ctrl.onAdd = () => {
            const div = L.DomUtil.create('div', 'map-geocoder');
            div.innerHTML =
                '<input type="text" id="geo-input" placeholder="Buscar lugar en Venezuela..." class="geo-input" />' +
                '<button id="geo-btn" class="geo-btn">\uD83D\uDD0D</button>' +
                '<div id="geo-results" class="geo-results"></div>';
            L.DomEvent.disableClickPropagation(div);
            return div;
        };
        ctrl.addTo(this.state.map);

        const container = this.state.map.getContainer();
        container.addEventListener('input', (e) => {
            if (e.target && e.target.id === 'geo-input') {
                clearTimeout(this._geoDebounce);
                this._geoDebounce = setTimeout(() => {
                    this.geocodeSearch(e.target.value);
                }, 400);
            }
        });
        container.addEventListener('click', (e) => {
            if (e.target && e.target.id === 'geo-btn') {
                var q = document.getElementById('geo-input');
                if (q && q.value) this.geocodeSearch(q.value);
            }
            var item = e.target && e.target.closest('.geo-result-item');
            if (item) {
                var lat = parseFloat(item.dataset.lat);
                var lon = parseFloat(item.dataset.lon);
                var q = document.getElementById('geo-input');
                this.state.map.setView([lat, lon], 13);
                L.circleMarker([lat, lon], {
                    radius: 8, color: '#00E5FF', fillColor: '#00E5FF', fillOpacity: 0.2, weight: 2
                }).addTo(this.state.map).bindPopup('<b>' + (q ? q.value : '') + '</b>').openPopup();
                var res = document.getElementById('geo-results');
                if (res) res.style.display = 'none';
                if (q) q.value = '';
            }
        });
    },

    geocodeSearch: async function(query) {
        var resultsDiv = document.getElementById('geo-results');
        if (!resultsDiv) return;
        if (!query || query.length < 2) {
            resultsDiv.style.display = 'none';
            return;
        }
        resultsDiv.innerHTML = '<div class="geo-result-item" style="color:#94A3B8;">Buscando...</div>';
        resultsDiv.style.display = 'block';
        try {
            var res = await fetch('https://nominatim.openstreetmap.org/search?format=json&q=' +
                encodeURIComponent(query) + '&limit=6&countrycodes=ve', {
                headers: {
                    'Accept': 'application/json',
                    'User-Agent': 'CobaltoHub_OSINT_Node/9.0'
                }
            });
            var data = await res.json();
            if (!data || !data.length) {
                resultsDiv.innerHTML = '<div class="geo-result-item" style="color:#94A3B8;">Sin resultados en Venezuela</div>';
                return;
            }
            resultsDiv.innerHTML = data.map(function (r) {
                return '<div class="geo-result-item" data-lat="' + r.lat + '" data-lon="' + r.lon + '">' +
                    r.display_name.split(',').slice(0, 3).join(',') +
                    '<span style="color:#64748B;font-size:0.6rem;display:block;">' + (r.type || '') + '</span></div>';
            }).join('');
        } catch (e) {
            resultsDiv.innerHTML = '<div class="geo-result-item" style="color:#EF4444;">Error de conexión</div>';
        }
    },

    loadMapData: async function() {
        if (!this.state.map) return;
        // Evitar recargas redundantes si los puntos ya están cargados en memoria
        if (this.state.currentPoints && this.state.currentPoints.length > 0) {
            this.renderMapPoints(this.state.currentPoints);
            return;
        }

        // 0. Si ya hay datos precargados inyectados por el servidor
        if (window._initialMapData) {
            this.state.currentPoints = [];
            if (window._initialMapData.geo_points) this.state.currentPoints.push(...window._initialMapData.geo_points);
            if (window._initialMapData.ai_geopoints) this.state.currentPoints.push(...window._initialMapData.ai_geopoints);
            this.renderMapPoints(this.state.currentPoints);
            return;
        }

        try {
            var res = await fetch('/api/map-data');
            if (!res.ok) throw new Error("HTTP error " + res.status);
            var data = await res.json();
            
            // UX FIX: No borrar el estado anterior hasta tener los nuevos datos asegurados
            let newPoints = [];
            if (data.geo_points) newPoints.push(...data.geo_points);
            if (data.ai_geopoints) newPoints.push(...data.ai_geopoints);
            
            this.state.currentPoints = newPoints;
            this.renderMapPoints(this.state.currentPoints);
        } catch (e) {
            console.error('[MAP] Error cargando datos:', e);
        }
    },

    renderMapPoints: function(points) {
        if (!this.state.map) return;
        // Rastrear marcadores activos para saber cuáles eliminar
        const activeIds = new Set();
        const heatPoints = [];
        const escapeFn = this.utils.escapeHTML;

        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            if (!p) continue;
            const lat = parseFloat(p.lat);
            const lng = parseFloat(p.lon != null ? p.lon : (p.lng != null ? p.lng : p.longitude));
            if (isNaN(lat) || isNaN(lng)) continue;

            const id = this.utils.getPointId(p);
            activeIds.add(id);
            heatPoints.push([lat, lng, 0.5]);

            const cat = this.getCategory(p);
            const cfg = this.CATEGORIES[cat] || this.CATEGORIES.default;
            const color = p.color || cfg.color;
            const destLatLng = L.latLng(lat, lng);

            // ¿Ya existe este marcador?
            if (this.state.markersStore[id]) {
                const marker = this.state.markersStore[id];
                
                // Si cambió de categoría, mover de capa
                if (marker.pointData.category !== cat) {
                    this.state.markerLayers[marker.pointData.category].removeLayer(marker);
                    this.state.markerLayers[cat].addLayer(marker);
                    marker.pointData.category = cat;
                }

                // Animar movimiento suave
                this.utils.animateMarker(marker, destLatLng);
                
                // Actualizar metadatos
                marker.pointData = { ...p, category: cat };
                
                // Actualizar Popup (por si cambió el título o fuente)
                marker.setPopupContent(`
                    <div style="font-family:'Inter',sans-serif;min-width:150px;">
                        <div style="font-size:0.65rem;color:${color};font-weight:700;margin-bottom:2px;">${cfg.icon} ${escapeFn(p.type || 'EVENTO')}</div>
                        <div style="font-size:0.8rem;font-weight:600;color:#fff;margin-bottom:4px;">${escapeFn(p.title || '')}</div>
                        <div style="font-size:0.7rem;color:#94A3B8;">${escapeFn(p.date || '')}</div>
                        <div style="font-size:0.7rem;color:#64748B;margin-top:4px;">${escapeFn(p.source || '')}</div>
                    </div>
                `);

            } else {
                // Crear nuevo marcador
                const marker = L.marker(destLatLng, {
                    icon: L.divIcon({
                        className: 'custom-div-icon',
                        html: `<div style="background:${color};width:12px;height:12px;border-radius:50%;box-shadow:0 0 10px ${color};"></div>`,
                        iconSize: [12, 12],
                        iconAnchor: [6, 6]
                    })
                });

                marker.pointData = { ...p, category: cat };
                marker.on('click', (e) => this.showPointDetail(e.target.pointData));

                marker.bindPopup(`
                    <div style="font-family:'Inter',sans-serif;min-width:150px;">
                        <div style="font-size:0.65rem;color:${color};font-weight:700;margin-bottom:2px;">${cfg.icon} ${escapeFn(p.type || 'EVENTO')}</div>
                        <div style="font-size:0.8rem;font-weight:600;color:#fff;margin-bottom:4px;">${escapeFn(p.title || '')}</div>
                        <div style="font-size:0.7rem;color:#94A3B8;">${escapeFn(p.date || '')}</div>
                        <div style="font-size:0.7rem;color:#64748B;margin-top:4px;">${escapeFn(p.source || '')}</div>
                    </div>
                `);

                this.state.markerLayers[cat].addLayer(marker);
                this.state.markersStore[id] = marker;
            }
        }

        // Eliminar marcadores que ya no están en el reporte actual
        for (const id in this.state.markersStore) {
            if (!activeIds.has(id)) {
                const marker = this.state.markersStore[id];
                const cat = marker.pointData.category;
                this.state.markerLayers[cat].removeLayer(marker);
                delete this.state.markersStore[id];
            }
        }

        // Actualizar capa de calor (esta no se anima punto a punto, pero se refresca)
        if (this.state.heatLayer) {
            this.state.heatLayer.setLatLngs(heatPoints);
        } else if (typeof L.heatLayer === 'function' && heatPoints.length > 0 && this.state.map.getContainer().clientWidth > 0) {
            this.state.heatLayer = L.heatLayer(heatPoints, {
                radius: 25,
                blur: 15,
                maxZoom: 10,
                gradient: { 0.4: 'blue', 0.65: 'lime', 1: 'red' }
            }).addTo(this.state.map);
        }
    },

    showPointDetail: function(p) {
        var panel = document.getElementById('map-detail-panel');
        if (!panel) return;
        var cat = this.getCategory(p);
        var cfg = this.CATEGORIES[cat] || this.CATEGORIES.default;
        const escapeFn = this.utils.escapeHTML;

        const latVal = parseFloat(p.lat);
        const lonVal = parseFloat(p.lon != null ? p.lon : (p.lng != null ? p.lng : p.longitude));
        const coordStr = (!isNaN(latVal) && !isNaN(lonVal)) ? `${latVal.toFixed(4)}, ${lonVal.toFixed(4)}` : '?';

        panel.innerHTML = `
            <div class="detail-header" style="border-left:4px solid ${cfg.color};">
                <span class="detail-type">${cfg.icon} ${escapeFn(p.type || 'EVENTO')}</span>
                <button onclick="CobaltoMap.closeDetailPanel()" class="detail-close">\u2715</button>
            </div>
            <div class="detail-body">
                <div class="detail-field"><span class="detail-label">Título</span><span class="detail-value">${escapeFn(p.title || '\u2014')}</span></div>
                <div class="detail-field"><span class="detail-label">Fuente</span><span class="detail-value">${escapeFn(p.source || '\u2014')}</span></div>
                <div class="detail-field"><span class="detail-label">Coordenadas</span><span class="detail-value">${coordStr}</span></div>
                <div class="detail-field"><span class="detail-label">Categoría</span><span class="detail-value">${escapeFn(cfg.label)}</span></div>
                <div class="detail-field"><span class="detail-label">Fecha</span><span class="detail-value">${escapeFn(p.date || '\u2014')}</span></div>
                ${p.summary ? `<div class="detail-field"><span class="detail-label">Resumen</span><span class="detail-value">${escapeFn(p.summary)}</span></div>` : ''}
            </div>`;
        panel.classList.add('visible');
    },

    closeDetailPanel: function() {
        var panel = document.getElementById('map-detail-panel');
        if (panel) panel.classList.remove('visible');
    },

    startAutoRefresh: function() {
        // UX HABILITADO: Sincronización continua en background.
        // El mapa NUNCA se detiene aunque el usuario cambie de pestaña.
        if (this.state.autoRefreshTimer) {
            clearInterval(this.state.autoRefreshTimer);
        }
        this.state.autoRefreshTimer = setInterval(() => {
            this.loadMapData();
        }, 8000); 
    },

    invalidateMap: function() {
        if (this.state.map) {
            // UX FIX: Forzar redibujado agresivo para evitar "baldosas grises" / recortes
            this.state.map.invalidateSize();
            setTimeout(() => { this.state.map.invalidateSize(); }, 100);
            setTimeout(() => { this.state.map.invalidateSize(); }, 300);
            setTimeout(() => { this.state.map.invalidateSize(); }, 600);
        }
    }
};
