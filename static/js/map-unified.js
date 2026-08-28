window.UnifiedMap = {
    state: {
        map: null,
        layers: {},
        tileLayers: {},
        currentBasemap: 'dark',
        pollTimers: [],
        active: false,
        renderedMarkers: [],
        currentPoints: []
    },

    LAYER_DEFS: {
        cobato: { id: 'cobato', label: 'COBALTO Intel Points', icon: '📌', color: '#00E5FF', visible: true, localData: true, refreshMs: 60000 },
        flights: { id: 'flights', label: 'Military Flights', icon: '🛩️', color: '#00E5FF', endpoint: '/api/osiris/data/flights', dataPath: ['military_flights'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 60000 },
        satellites: { id: 'satellites', label: 'Satellites', icon: '🛰️', color: '#D4AF37', endpoint: '/api/osiris/data/satellites', dataPath: ['satellites'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 120000 },
        earthquakes: { id: 'earthquakes', label: 'Earthquakes', icon: '🌋', color: '#FF9500', endpoint: '/api/osiris/data/earthquakes', dataPath: ['earthquakes'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 120000 },
        fires: { id: 'fires', label: 'Active Fires', icon: '🔥', color: '#FF3B30', endpoint: '/api/osiris/data/fires', dataPath: ['fires'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 120000 },
        weather: { id: 'weather', label: 'Severe Weather', icon: '🌪️', color: '#FFD700', endpoint: '/api/osiris/data/weather', dataPath: ['events'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 300000 },
        cctv: { id: 'cctv', label: 'CCTV Cameras', icon: '📹', color: '#B388FF', endpoint: '/api/osiris/data/cctv', dataPath: ['cameras'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 300000 },
        operators: { id: 'operators', label: 'Operadores BFT', icon: '🔵', color: '#00E5FF', endpoint: '/api/telemetry/operators', dataPath: ['operators'], latField: 'latitude', lngField: 'longitude', visible: true, refreshMs: 10000 },
    },

    POPUP_FIELDS: {
        flights: { 'Callsign': 'callsign', 'Alt (ft)': 'alt', 'Speed (kts)': 'speed_knots', 'Heading': 'heading', 'Model': 'model', 'ICAO24': 'icao24', 'Squawk': 'squawk' },
        satellites: { 'Name': 'name', 'Mission': 'mission', 'Alt (km)': 'alt', 'NORAD ID': 'noradId' },
        earthquakes: { 'Magnitude': 'magnitude', 'Place': 'place', 'Depth (km)': 'depth', 'Tsunami': 'tsunami', 'Alert': 'alert' },
        fires: { 'Brightness': 'brightness', 'Confidence': 'confidence', 'FRP': 'frp' },
        weather: { 'Title': 'title', 'Category': 'category', 'Severity': 'severity' },
        cctv: { 'Name': 'name', 'City': 'city', 'Country': 'country' },
        cobato: { 'Title': 'title', 'Type': 'type', 'Source': 'source', 'Date': 'date' },
        operators: { 'Operador': 'operator_name', 'ID': 'operator_id', 'Grupo': 'unit_group', 'Batería (%)': 'battery_level', 'Estado': 'status', 'Red': 'network_type' },
    },

    THEATERS: {
        COL: { center: [4.5709, -74.2973], zoom: 6.0, name: 'Colombia' },
        VEN: { center: [7.5000, -66.5000], zoom: 6.5, name: 'Venezuela' },
        BORDER: { center: [7.1200, -71.2000], zoom: 8.5, name: 'Frontera Arauca-Apure-Cúcuta' },
        GLOBAL: { center: [6.5000, -70.0000], zoom: 5.0, name: 'Vista Global' }
    },

    init: function() {
        if (this.state.active) return;
        if (typeof L === 'undefined') {
            console.warn('[UNIFIED-MAP] Leaflet not loaded. Retrying...');
            setTimeout(function() { window.UnifiedMap.init(); }, 1000);
            return;
        }

        var container = document.getElementById('unified-map-container');
        if (!container || container.offsetWidth === 0) {
            console.warn('[UNIFIED-MAP] Container not visible yet. Retrying...');
            setTimeout(function() { window.UnifiedMap.init(); }, 300);
            return;
        }

        this.state.active = true;
        this._showLoading(true);
        var self = this;

        this.state.map = L.map('unified-map-container', {
            zoomControl: false,
            attributionControl: false,
        }).setView([6.5, -70.0], 5);

        // Tile basemaps
        this.state.tileLayers.dark = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, maxNativeZoom: 16, attribution: '&copy; Esri, HERE, Garmin, NGA' });
        this.state.tileLayers.satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, maxNativeZoom: 18, attribution: '&copy; Esri, Maxar, Earthstar' });
        this.state.tileLayers.light = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, maxNativeZoom: 16, attribution: '&copy; Esri, HERE, Garmin, NGA' });

        this.state.tileLayers[this.state.currentBasemap].addTo(this.state.map);
        L.control.zoom({ position: 'bottomright' }).addTo(this.state.map);

        // Mouse Telemetry Listener
        this.state.map.on('mousemove', function(e) {
            var coordsEl = document.getElementById('map-telemetry-coords');
            if (coordsEl) {
                var latStr = e.latlng.lat.toFixed(4) + '° ' + (e.latlng.lat >= 0 ? 'N' : 'S');
                var lngStr = e.latlng.lng.toFixed(4) + '° ' + (e.latlng.lng >= 0 ? 'E' : 'W');
                coordsEl.textContent = latStr + ', ' + lngStr;
            }
        });

        this.state.map.on('zoomend', function() {
            var zoomEl = document.getElementById('map-telemetry-zoom');
            if (zoomEl && self.state.map) {
                zoomEl.textContent = self.state.map.getZoom().toFixed(1) + 'x';
            }
        });

        // Create cluster groups
        Object.keys(this.LAYER_DEFS).forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            if (typeof L.markerClusterGroup === 'function') {
                self.state.layers[key] = L.markerClusterGroup({
                    showCoverageOnHover: false,
                    spiderfyOnMaxZoom: true,
                    maxClusterRadius: 45,
                    chunkedLoading: true,
                });
            } else {
                self.state.layers[key] = L.layerGroup();
            }
            if (def.visible) {
                self.state.map.addLayer(self.state.layers[key]);
            }
        });

        // Initial load
        this._loadAllLayers();

        // Polling
        Object.keys(this.LAYER_DEFS).forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            self.state.pollTimers.push(setInterval(function() {
                self._loadLayer(key);
            }, def.refreshMs));
        });

        this.state.map.on('resize', function() {
            self.state.map.invalidateSize();
        });

        this._showLoading(false);
        this._renderLayerPanel();
    },

    destroy: function() {
        this.state.active = false;
        this.state.pollTimers.forEach(function(t) { clearInterval(t); });
        this.state.pollTimers = [];
        if (this.state.map) {
            this.state.map.remove();
            this.state.map = null;
        }
    },

    switchBasemap: function(type) {
        if (!this.state.map || !this.state.tileLayers[type]) return;
        if (this.state.tileLayers[this.state.currentBasemap]) {
            this.state.map.removeLayer(this.state.tileLayers[this.state.currentBasemap]);
        }
        this.state.currentBasemap = type;
        this.state.tileLayers[type].addTo(this.state.map);
    },

    flyToTheater: function(code) {
        var t = this.THEATERS[code];
        if (!t || !this.state.map) return;
        this.state.map.flyTo(t.center, t.zoom, { duration: 1.5 });
        if (typeof window.showTacticalToast === 'function') {
            window.showTacticalToast('📍 Enfocando Teatro Táctico: ' + t.name, 'info');
        }
    },

    searchVector: function(query) {
        if (!query || !this.state.renderedMarkers.length || !this.state.map) return;
        var q = query.toLowerCase().trim();

        var match = this.state.renderedMarkers.find(function(m) {
            var text = (m.title || '' ) + ' ' + (m.summary || '') + ' ' + (m.source || '') + ' ' + (m.callsign || '');
            return text.toLowerCase().includes(q);
        });

        if (match && match.marker) {
            this.state.map.flyTo([match.lat, match.lng], 12, { duration: 1.2 });
            setTimeout(function() {
                match.marker.openPopup();
            }, 1300);
            if (typeof window.showTacticalToast === 'function') {
                window.showTacticalToast('🎯 Vector encontrado: ' + (match.title || match.callsign || query), 'info');
            }
        } else {
            if (typeof window.showTacticalToast === 'function') {
                window.showTacticalToast('⚠️ No se encontró vector coincidente para: ' + query, 'warning');
            }
        }
    },

    selectAllLayers: function(select) {
        var self = this;
        Object.keys(this.LAYER_DEFS).forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            var layer = self.state.layers[key];
            if (!def || !layer) return;
            def.visible = select;
            if (select) {
                if (!self.state.map.hasLayer(layer)) self.state.map.addLayer(layer);
            } else {
                if (self.state.map.hasLayer(layer)) self.state.map.removeLayer(layer);
            }
        });
        this._renderLayerPanel();
        this._updateLayerCount();
    },

    _loadAllLayers: function() {
        var self = this;
        Object.keys(this.LAYER_DEFS).forEach(function(key) {
            self._loadLayer(key);
        });
    },

    _loadLayer: function(key) {
        var self = this;
        var def = this.LAYER_DEFS[key];
        if (!def) return;

        if (def.localData) {
            this._loadLocalGeo(key);
            return;
        }

        fetch(def.endpoint)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!self.state.active) return;
                var items = self._getNested(data, def.dataPath) || [];
                self._renderItems(key, items);
            })
            .catch(function(err) {
                console.warn('[UNIFIED-MAP] Failed to load ' + key + ':', err);
            });
    },

    _loadLocalGeo: function(key) {
        var self = this;
        if (window._initialMapData) {
            var points = [];
            if (window._initialMapData.geo_points) points.push.apply(points, window._initialMapData.geo_points);
            if (window._initialMapData.ai_geopoints) points.push.apply(points, window._initialMapData.ai_geopoints);
            if (points.length) { self._renderItems(key, points); return; }
        }
        fetch('/api/map-data')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var points = [];
                if (data.geo_points) points.push.apply(points, data.geo_points);
                if (data.ai_geopoints) points.push.apply(points, data.ai_geopoints);
                self._renderItems(key, points);
            })
            .catch(function(err) {
                console.warn('[UNIFIED-MAP] COBALTO geo load failed:', err);
            });
    },

    _renderItems: function(key, items) {
        var def = this.LAYER_DEFS[key];
        if (!def || !this.state.map) return;

        var layer = this.state.layers[key];
        if (!layer) return;

        layer.clearLayers();

        // Filter out existing rendered markers for this layer
        this.state.renderedMarkers = this.state.renderedMarkers.filter(function(m) { return m.layerKey !== key; });

        if (!items || !items.length) {
            this._updateLayerCount();
            return;
        }

        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var lat = parseFloat(item[def.latField || 'lat']);
            var lng = item[def.lngField || 'lng'] != null ? parseFloat(item[def.lngField || 'lng']) : parseFloat(item.lon || item.longitude);
            if (isNaN(lat) || isNaN(lng)) continue;
            if (Math.abs(lat) > 90 || Math.abs(lng) > 180) continue;

            var marker = this._createMarker(def, item, lat, lng);

            var popupHtml = this._buildPopupHtml(item, def, lat, lng);
            marker.bindPopup(popupHtml, {
                className: 'unified-map-popup',
                closeButton: true,
                maxWidth: 320,
                minWidth: 220,
            });

            layer.addLayer(marker);

            this.state.renderedMarkers.push({
                layerKey: key,
                title: item.title || item.name || item.callsign || item.place || '',
                summary: item.summary || item.description || '',
                source: item.source || key,
                callsign: item.callsign || '',
                lat: lat,
                lng: lng,
                marker: marker
            });
        }

        this._updateLayerCount();
    },

    _createMarker: function(def, item, lat, lng) {
        if (def.id === 'cctv') {
            var marker = L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'cctv-marker',
                    html: '<div style="background:' + def.color + ';width:16px;height:16px;border-radius:4px;box-shadow:0 0 12px ' + def.color + ';display:flex;align-items:center;justify-content:center;font-size:10px;cursor:pointer;border:1px solid #fff;">📹</div>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10],
                }),
            });
            return marker;
        }

        var marker = L.circleMarker([lat, lng], {
            radius: this._getRadius(def, item),
            color: def.color,
            fillColor: def.color,
            fillOpacity: 0.4,
            weight: 1.5,
            opacity: 0.9,
        });

        return marker;
    },

    _getRadius: function(def, item) {
        var r = 6;
        if (def.id === 'earthquakes') {
            var mag = parseFloat(item.magnitude) || 0;
            r = Math.max(5, Math.min(26, mag * 3.5));
        } else if (def.id === 'fires') {
            r = 6;
        } else if (def.id === 'satellites') {
            r = 5;
        } else if (def.id === 'cctv') {
            r = 6;
        } else if (def.id === 'flights') {
            r = 8;
        }
        return r;
    },

    _buildPopupHtml: function(item, def, lat, lng) {
        var esc = function(s) {
            if (s === null || s === undefined) return '';
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        };
        var fields = this.POPUP_FIELDS[def.id] || {};
        var itemTitle = esc(item.title || item.name || item.callsign || def.label);
        var coordsStr = lat.toFixed(4) + ', ' + lng.toFixed(4);

        var html = '<div style="font-family:\'Roboto Mono\',monospace;font-size:11px;color:#fff;max-width:290px;">';
        html += '<div style="color:' + def.color + ';font-weight:bold;font-size:12px;margin-bottom:6px;border-bottom:1px solid rgba(0,229,255,0.2);padding-bottom:4px;display:flex;align-items:center;justify-content:space-between;">' +
            '<span>' + def.icon + ' ' + itemTitle + '</span>' +
            '<span style="font-size:9px;color:#94A3B8;">' + esc(def.label) + '</span>' +
            '</div>';

        if (def.id === 'cctv') {
            if (item.feed_url) {
                var camId = 'cctv-ph-' + Math.random().toString(36).slice(2,8);
                var proxyUrl = '/api/osiris/cctv/image?url=' + encodeURIComponent(item.feed_url);
                html += '<div style="margin-bottom:6px;position:relative;">' +
                    '<div id="' + camId + '" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#64748B;font-size:9px;font-family:monospace;background:#050505;border-radius:4px;z-index:1;">CONECTANDO TRANSMISIÓN...</div>' +
                    '<img src="' + proxyUrl + '" style="width:100%;border-radius:4px;max-height:130px;object-fit:cover;position:relative;z-index:2;" loading="lazy" onload="var p=document.getElementById(\'' + camId + '\');if(p)p.style.display=\'none\';" onerror="var p=document.getElementById(\'' + camId + '\');if(p){p.textContent=\'📹 OFFLINE\';p.style.color=\'#FF4444\';}" /></div>';
            } else {
                html += '<div style="margin-bottom:6px;padding:16px;text-align:center;color:#64748B;font-size:10px;font-family:monospace;background:#050505;border-radius:4px;">📹 TRANSMISIÓN EN VIVO NO DISPONIBLE</div>';
            }
            var itemJsonEscStr = JSON.stringify(item).replace(/'/g, "\\'").replace(/"/g, '&quot;');
            html += '<button onclick="if(window.switchTab)window.switchTab(\'tab-osiris-global\');setTimeout(function(){if(window.OsirisGlobal){var c=' + itemJsonEscStr + ';window.OsirisGlobal.selectCamera(c);window.OsirisGlobal.expandCamera(c);}},200);" style="width:100%;margin-top:4px;margin-bottom:6px;background:rgba(255,215,0,0.12);border:1px solid rgba(255,215,0,0.4);color:#FFD700;border-radius:4px;padding:4px;font-size:9px;font-family:monospace;cursor:pointer;">📹 VER EN VISOR FULLSCREEN CCTV</button>';
        }

        for (var f in fields) {
            var val = item[fields[f]];
            if (val === null || val === undefined || val === '') continue;
            var displayVal = typeof val === 'number' ? val.toLocaleString() : esc(val);
            html += '<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.03);"><span style="color:#94A3B8;">' + esc(f) + '</span><span style="color:#ddd;font-weight:bold;">' + displayVal + '</span></div>';
        }

        html += '<div style="margin-top:8px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.08);display:flex;gap:4px;flex-wrap:wrap;">' +
            '<button onclick="navigator.clipboard.writeText(\'' + coordsStr + '\');if(typeof showTacticalToast===\'function\')showTacticalToast(\'📍 Coordenadas copiadas: ' + coordsStr + '\',\'info\')" style="flex:1;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.3);color:#00E5FF;border-radius:4px;padding:3px;font-size:9px;font-family:monospace;cursor:pointer;">📍 Coordenadas</button>' +
            '<button onclick="if(window.sitrepInvestigateRAG)window.sitrepInvestigateRAG(\'' + itemTitle.replace(/'/g, "\\'") + '\')" style="flex:1;background:rgba(179,136,255,0.1);border:1px solid rgba(179,136,255,0.3);color:#B388FF;border-radius:4px;padding:3px;font-size:9px;font-family:monospace;cursor:pointer;">🎯 Investigar RAG</button>' +
            '</div>';

        html += '</div>';
        return html;
    },

    _getNested: function(obj, path) {
        try {
            return path.reduce(function(acc, key) { return acc ? acc[key] : undefined; }, obj);
        } catch (e) { return undefined; }
    },

    toggleLayer: function(key) {
        var def = this.LAYER_DEFS[key];
        var layer = this.state.layers[key];
        if (!def || !layer) return;

        def.visible = !def.visible;
        if (def.visible) {
            this.state.map.addLayer(layer);
        } else {
            this.state.map.removeLayer(layer);
        }
        this._renderLayerPanel();
        this._updateLayerCount();
    },

    refreshLayer: function(key) {
        this._loadLayer(key);
    },

    refreshAll: function() {
        this._loadAllLayers();
    },

    _showLoading: function(show) {
        var el = document.getElementById('unified-map-loading');
        if (el) el.style.display = show ? 'block' : 'none';
    },

    _renderLayerPanel: function() {
        var list = document.getElementById('unified-layer-list');
        if (!list) return;

        var self = this;
        var html = '';
        var keys = Object.keys(this.LAYER_DEFS);
        keys.forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            var checked = def.visible ? 'checked' : '';
            var itemCount = self.state.renderedMarkers.filter(function(m) { return m.layerKey === key; }).length;

            html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 6px;border-bottom:1px solid rgba(255,255,255,0.03);border-radius:6px;cursor:pointer;background:rgba(255,255,255,0.01);" onclick="window.UnifiedMap.toggleLayer(\'' + key + '\')">' +
                '<input type="checkbox" ' + checked + ' style="accent-color:' + def.color + ';width:14px;height:14px;cursor:pointer;" onclick="event.stopPropagation();window.UnifiedMap.toggleLayer(\'' + key + '\')" />' +
                '<span style="font-size:13px;">' + def.icon + '</span>' +
                '<span style="flex:1;font-size:0.7rem;color:#E2E8F0;">' + def.label + '</span>' +
                '<span style="font-size:0.65rem;color:var(--primary);background:rgba(0,229,255,0.08);padding:1px 5px;border-radius:4px;font-weight:bold;">' + itemCount + '</span>' +
                '<button onclick="event.stopPropagation();window.UnifiedMap.refreshLayer(\'' + key + '\')" style="background:none;border:none;color:#64748B;cursor:pointer;font-size:0.75rem;padding:2px;" title="Refrescar capa">⟳</button>' +
                '</div>';
        });
        list.innerHTML = html;
    },

    _updateLayerCount: function() {
        var countEl = document.getElementById('unified-layer-count');
        var hudMarkerCountEl = document.getElementById('map-hud-marker-count');

        var visible = 0;
        var total = 0;
        for (var key in this.LAYER_DEFS) {
            total++;
            if (this.LAYER_DEFS[key].visible) visible++;
        }
        if (countEl) countEl.textContent = visible + '/' + total;

        var totalMarkers = this.state.renderedMarkers.length;
        if (hudMarkerCountEl) hudMarkerCountEl.textContent = totalMarkers + ' VECTORES';
    },

    flyToCoordinates: function(lat, lng, zoom, label) {
        var mapObj = this.state.map || this.map;
        if (!mapObj) return;
        var z = zoom || 12;
        mapObj.flyTo([lat, lng], z, { animate: true, duration: 1.5 });
        if (label) {
            L.popup()
                .setLatLng([lat, lng])
                .setContent('<div class="font-mono" style="padding:4px;font-size:11px;color:#00e5ff;">📍 <strong>' + label + '</strong><br><span style="color:#aaa;">' + lat.toFixed(4) + ', ' + lng.toFixed(4) + '</span></div>')
                .openOn(mapObj);
        }
    },

    focusLocation: function(lat, lng, label) {
        var self = this;
        if (window.CobaltoCore && window.CobaltoCore.switchTab) {
            window.CobaltoCore.switchTab('tab-map');
        }
        setTimeout(function() {
            if (!self.state.active && typeof self.init === 'function') {
                self.init();
            }
            var mapObj = self.state.map || self.map;
            if (mapObj) {
                mapObj.flyTo([lat, lng], 14, { animate: true, duration: 1.5 });
                setTimeout(function() {
                    L.popup()
                        .setLatLng([lat, lng])
                        .setContent('<div style="font-family:\'Roboto Mono\',monospace;padding:6px;font-size:11px;color:#00E5FF;background:rgba(10,11,16,0.95);border-radius:4px;border:1px solid #00E5FF;">📍 <strong>' + (label || 'Ubicación Táctica') + '</strong><br><span style="color:#aaa;">' + lat.toFixed(4) + ', ' + lng.toFixed(4) + '</span></div>')
                        .openOn(mapObj);
                }, 1600);
                if (typeof window.showTacticalToast === 'function') {
                    window.showTacticalToast('📍 Posicionando vector en Mapa Unificado: ' + (label || ''), 'info');
                }
            }
        }, 200);
    },

    invalidateMap: function() {
        var m = this.state.map || this.map;
        if (m && typeof m.invalidateSize === 'function') {
            m.invalidateSize();
        }
    },

    get _map() {
        return this.state.map;
    }
};

window.UnifiedMap = window.UnifiedMap || UnifiedMap;
window.CobaltoMap = window.UnifiedMap;

