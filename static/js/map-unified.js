window.UnifiedMap = {
    state: {
        map: null,
        layers: {},
        pollTimers: [],
        active: false,
    },

    LAYER_DEFS: {
        cobato: { id: 'cobato', label: 'COBALTO Intel Points', icon: '📌', color: '#00E5FF', visible: true, localData: true, refreshMs: 60000 },
        flights: { id: 'flights', label: 'Military Flights', icon: '🛩️', color: '#00E5FF', endpoint: '/api/osiris/data/flights', dataPath: ['military_flights'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 60000 },
        satellites: { id: 'satellites', label: 'Satellites', icon: '🛰️', color: '#D4AF37', endpoint: '/api/osiris/data/satellites', dataPath: ['satellites'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 120000 },
        earthquakes: { id: 'earthquakes', label: 'Earthquakes', icon: '🌋', color: '#FF9500', endpoint: '/api/osiris/data/earthquakes', dataPath: ['earthquakes'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 120000 },
        fires: { id: 'fires', label: 'Active Fires', icon: '🔥', color: '#FF3B30', endpoint: '/api/osiris/data/fires', dataPath: ['fires'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 120000 },
        weather: { id: 'weather', label: 'Severe Weather', icon: '🌪️', color: '#FFD700', endpoint: '/api/osiris/data/weather', dataPath: ['events'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 300000 },
        cctv: { id: 'cctv', label: 'CCTV Cameras', icon: '📹', color: '#B388FF', endpoint: '/api/osiris/data/cctv', dataPath: ['cameras'], latField: 'lat', lngField: 'lng', visible: true, refreshMs: 300000 },
    },

    POPUP_FIELDS: {
        flights: { 'Callsign': 'callsign', 'Alt (ft)': 'alt', 'Speed (kts)': 'speed_knots', 'Heading': 'heading', 'Model': 'model', 'ICAO24': 'icao24', 'Squawk': 'squawk' },
        satellites: { 'Name': 'name', 'Mission': 'mission', 'Alt (km)': 'alt', 'NORAD ID': 'noradId' },
        earthquakes: { 'Magnitude': 'magnitude', 'Place': 'place', 'Depth (km)': 'depth', 'Tsunami': 'tsunami', 'Alert': 'alert' },
        fires: { 'Brightness': 'brightness', 'Confidence': 'confidence', 'FRP': 'frp' },
        weather: { 'Title': 'title', 'Category': 'category', 'Severity': 'severity' },
        cctv: { 'Name': 'name', 'City': 'city', 'Country': 'country' },
        cobato: { 'Title': 'title', 'Type': 'type', 'Source': 'source', 'Date': 'date' },
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
            zoomControl: true,
            attributionControl: true,
        }).setView([7.0, -66.0], 4);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
        }).addTo(this.state.map);

        this.state.map.addControl(L.control.zoom({ position: 'bottomright' }));

        // Create cluster groups
        Object.keys(this.LAYER_DEFS).forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            if (typeof L.markerClusterGroup === 'function') {
                self.state.layers[key] = L.markerClusterGroup({
                    showCoverageOnHover: false,
                    spiderfyOnMaxZoom: true,
                    maxClusterRadius: 50,
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

        if (!items || !items.length) {
            this._updateLayerCount();
            return;
        }

        var esc = function(s) {
            if (s === null || s === undefined) return '';
            return String(s).replace(/[&<>"']/g, function(m) {
                return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m];
            });
        };

        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var lat = parseFloat(item[def.latField || 'lat']);
            var lng = item[def.lngField || 'lng'] != null ? parseFloat(item[def.lngField || 'lng']) : parseFloat(item.lon || item.longitude);
            if (isNaN(lat) || isNaN(lng)) continue;
            if (Math.abs(lat) > 90 || Math.abs(lng) > 180) continue;

            var marker = this._createMarker(def, item, lat, lng);

            var popupHtml = this._buildPopupHtml(item, def);
            marker.bindPopup(popupHtml, {
                className: 'unified-map-popup',
                closeButton: true,
                maxWidth: 320,
                minWidth: 200,
            });

            layer.addLayer(marker);
        }

        this._updateLayerCount();
    },

    _createMarker: function(def, item, lat, lng) {
        if (def.id === 'cctv') {
            var feedStatus = item.feed_url ? 'live' : 'nofeed';
            var marker = L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'cctv-marker',
                    html: '<div style="background:' + def.color + ';width:14px;height:14px;border-radius:4px;box-shadow:0 0 12px ' + def.color + ';display:flex;align-items:center;justify-content:center;font-size:9px;cursor:pointer;">📹</div>',
                    iconSize: [18, 18],
                    iconAnchor: [9, 9],
                }),
            });
            var popupHtml = this._buildPopupHtml(item, def);
            marker.bindPopup(popupHtml, {
                className: 'unified-map-popup',
                closeButton: true,
                maxWidth: 320,
                minWidth: 200,
            });
            return marker;
        }

        var marker = L.circleMarker([lat, lng], {
            radius: this._getRadius(def, item),
            color: def.color,
            fillColor: def.color,
            fillOpacity: 0.35,
            weight: 1.5,
            opacity: 0.8,
        });

        var popupHtml = this._buildPopupHtml(item, def);
        marker.bindPopup(popupHtml, {
            className: 'unified-map-popup',
            closeButton: true,
            maxWidth: 320,
            minWidth: 200,
        });
        return marker;
    },

    _getRadius: function(def, item) {
        var r = 6;
        if (def.id === 'earthquakes') {
            var mag = parseFloat(item.magnitude) || 0;
            r = Math.max(4, Math.min(24, mag * 3));
        } else if (def.id === 'fires') {
            r = 5;
        } else if (def.id === 'satellites') {
            r = 4;
        } else if (def.id === 'cctv') {
            r = 5;
        } else if (def.id === 'flights') {
            r = 7;
        }
        return r;
    },

    _buildPopupHtml: function(item, def) {
        var esc = function(s) {
            if (s === null || s === undefined) return '';
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        };
        var fields = this.POPUP_FIELDS[def.id] || {};
        var html = '<div style="font-family:monospace;font-size:11px;color:#fff;max-width:280px;">';
        html += '<div style="color:' + def.color + ';font-weight:bold;font-size:12px;margin-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;">' + def.icon + ' ' + esc(def.label) + '</div>';

        if (def.id === 'cctv') {
            if (item.feed_url) {
                var camId = 'cctv-ph-' + Math.random().toString(36).slice(2,8);
                var proxyUrl = '/api/osiris/cctv/image?url=' + encodeURIComponent(item.feed_url);
                html += '<div style="margin-bottom:6px;position:relative;">' +
                    '<div id="' + camId + '" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#64748B;font-size:9px;font-family:monospace;background:#050505;border-radius:4px;z-index:1;">CONNECTING...</div>' +
                    '<img src="' + proxyUrl + '" style="width:100%;border-radius:4px;max-height:120px;object-fit:cover;position:relative;z-index:2;" loading="lazy" onload="var p=document.getElementById(\'' + camId + '\');if(p)p.style.display=\'none\';" onerror="var p=document.getElementById(\'' + camId + '\');if(p){p.textContent=\'📹 OFFLINE\';p.style.color=\'#FF4444\';}" /></div>';
            } else {
                html += '<div style="margin-bottom:6px;padding:20px;text-align:center;color:#64748B;font-size:10px;font-family:monospace;background:#050505;border-radius:4px;">📹 NO FEED URL</div>';
            }
        }

        for (var f in fields) {
            var val = item[fields[f]];
            if (val === null || val === undefined || val === '') continue;
            var displayVal = typeof val === 'number' ? val.toLocaleString() : esc(val);
            html += '<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.03);"><span style="color:#94A3B8;">' + esc(f) + '</span><span style="color:#ddd;">' + displayVal + '</span></div>';
        }

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
            html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px solid rgba(255,255,255,0.03);cursor:pointer;" onclick="window.UnifiedMap.toggleLayer(\'' + key + '\')">' +
                '<input type="checkbox" ' + checked + ' style="accent-color:' + def.color + ';width:14px;height:14px;cursor:pointer;" onclick="event.stopPropagation();window.UnifiedMap.toggleLayer(\'' + key + '\')" />' +
                '<span style="font-size:14px;">' + def.icon + '</span>' +
                '<span style="flex:1;font-size:0.7rem;color:#ddd;">' + def.label + '</span>' +
                '<button onclick="event.stopPropagation();window.UnifiedMap.refreshLayer(\'' + key + '\')" style="background:none;border:none;color:#64748B;cursor:pointer;font-size:0.7rem;padding:2px;">⟳</button>' +
                '</div>';
        });
        list.innerHTML = html;
    },

    _updateLayerCount: function() {
        var countEl = document.getElementById('unified-layer-count');
        if (!countEl) return;
        var visible = 0;
        var total = 0;
        for (var key in this.LAYER_DEFS) {
            total++;
            if (this.LAYER_DEFS[key].visible) visible++;
        }
        countEl.textContent = visible + '/' + total;
    },
};
