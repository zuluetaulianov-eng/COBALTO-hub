/**
 * map-osiris.js — OSIRIS MapLibre GL Map Manager for COBALTO HUB
 * Port of OsirisMap.tsx to Vanilla JS with maplibre-gl
 * Manages 6 geospatial data layers with auto-refresh
 */
window.OsirisMap = {
    state: {
        map: null,
        active: false,
        layers: {},
        pollTimers: [],
        loading: false,
    },

    LAYER_DEFS: {
        osiris_geo: {
            id: 'osiris_geo',
            label: 'COBALTO Intel Points',
            icon: '📌',
            color: '#00E5FF',
            endpoint: null,
            dataPath: [],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: 5,
            refreshMs: 60000,
            localData: true,
        },
        flights: {
            id: 'flights',
            label: 'Military Flights',
            icon: '🛩️',
            color: '#00E5FF',
            endpoint: '/api/osiris/data/flights',
            dataPath: ['military_flights'],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: 6,
            refreshMs: 60000,
        },
        satellites: {
            id: 'satellites',
            label: 'Satellites',
            icon: '🛰️',
            color: '#D4AF37',
            endpoint: '/api/osiris/data/satellites',
            dataPath: ['satellites'],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: 4,
            refreshMs: 120000,
        },
        earthquakes: {
            id: 'earthquakes',
            label: 'Earthquakes',
            icon: '🌋',
            color: '#FF9500',
            endpoint: '/api/osiris/data/earthquakes',
            dataPath: ['earthquakes'],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: { field: 'magnitude', scale: 3, min: 4, max: 24 },
            refreshMs: 120000,
        },
        fires: {
            id: 'fires',
            label: 'Active Fires',
            icon: '🔥',
            color: '#FF3B30',
            endpoint: '/api/osiris/data/fires',
            dataPath: ['fires'],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: 5,
            refreshMs: 120000,
        },
        weather: {
            id: 'weather',
            label: 'Severe Weather',
            icon: '🌪️',
            color: '#FFD700',
            endpoint: '/api/osiris/data/weather',
            dataPath: ['events'],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: 8,
            refreshMs: 300000,
        },
        cctv: {
            id: 'cctv',
            label: 'CCTV Cameras',
            icon: '📹',
            color: '#B388FF',
            endpoint: '/api/osiris/data/cctv',
            dataPath: ['cameras'],
            latField: 'lat', lngField: 'lng',
            visible: true,
            pointType: 'circle',
            radius: 3,
            refreshMs: 300000,
        },
    },

    init: function() {
        if (this.state.active) return;
        this.state.active = true;

        var container = document.getElementById('osiris-map-container');
        if (!container) return;

        if (typeof maplibregl === 'undefined') {
            console.warn('[OSIRIS-MAP] MapLibre GL not loaded. Retrying in 1s...');
            setTimeout(function() { window.OsirisMap.init(); }, 1000);
            return;
        }

        this._showLoading(true);

        console.log('[OSIRIS-MAP] Container:', container, container ? container.offsetWidth + 'x' + container.offsetHeight : 'null');

        this.state.map = new maplibregl.Map({
            container: 'osiris-map-container',
            style: this._buildStyle(),
            center: [-66.0, 7.0],
            zoom: 4,
            minZoom: 2,
            maxZoom: 18,
            attributionControl: true,
            failIfMajorPerformanceCaveat: false,
        });

        this.state.map.addControl(new maplibregl.NavigationControl(), 'bottom-right');
        this.state.map.addControl(new maplibregl.ScaleControl(), 'bottom-left');

        this.state.map.on('load', function() {
            window.OsirisMap.state.map.resize();
            window.OsirisMap._onMapLoaded();
        });

        this.state.map.on('click', function(e) {
            window.OsirisMap._onMapClick(e);
        });

        // Resize on container visibility
        var ro = new ResizeObserver(function() {
            if (window.OsirisMap.state.map) {
                window.OsirisMap.state.map.resize();
            }
        });
        ro.observe(container);
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

    _buildStyle: function() {
        return {
            version: 8,
            name: 'OSIRIS Tactical Dark',
            sources: {
                'carto-dark': {
                    type: 'raster',
                    tiles: [
                        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                    ],
                    tileSize: 256,
                    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
                },
            },
            layers: [
                { id: 'carto-dark-bg', type: 'raster', source: 'carto-dark' },
            ],
        };
    },

    _getLocalRefreshMs: function() {
        return 60000; // 1 minute for COBALTO geo-points
    },

    _onMapLoaded: function() {
        var self = this;
        // Create sources and layers for each data layer
        var layerIds = Object.keys(this.LAYER_DEFS);
        layerIds.forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            var sourceId = 'source-' + def.id;
            var layerId = 'layer-' + def.id;

            self.state.map.addSource(sourceId, {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] },
            });

            self.state.map.addLayer({
                id: layerId,
                type: 'circle',
                source: sourceId,
                paint: {
                    'circle-color': def.color,
                    'circle-radius': [
                        'case',
                        ['==', ['get', 'pointType'], 'scaled'],
                        ['max', ['coalesce', ['get', 'radiusValue'], 4], 4],
                        ['to-number', def.radius],
                    ],
                    'circle-opacity': 0.7,
                    'circle-stroke-width': 1,
                    'circle-stroke-color': def.color,
                    'circle-stroke-opacity': 0.9,
                },
            });

            self.state.layers[def.id] = {
                visible: def.visible,
                sourceId: sourceId,
                layerId: layerId,
            };
        });

        // Load initial data
        this._loadAllLayers();

        // Start polling
        layerIds.forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            var ms = def.localData ? self._getLocalRefreshMs() : def.refreshMs;
            self.state.pollTimers.push(setInterval(function() {
                self._loadLayer(key);
            }, ms));
        });

        this._showLoading(false);
        this._renderLayerPanel();
    },

    _loadAllLayers: function() {
        var self = this;
        Object.keys(this.LAYER_DEFS).forEach(function(key) {
            self._loadLayer(key);
        });
        this._updateLayerCount();
    },

    _loadLayer: function(key) {
        var self = this;
        var def = this.LAYER_DEFS[key];
        if (!def) return;

        // Handle local data sources (COBALTO geo-points)
        if (def.localData) {
            this._loadLocalGeo(key);
            return;
        }

        fetch(def.endpoint)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!self.state.active) return;
                var items = self._getNested(data, def.dataPath) || [];
                var features = [];

                items.forEach(function(item) {
                    var lat = parseFloat(item[def.latField]);
                    var lng = parseFloat(item[def.lngField]);
                    if (isNaN(lat) || isNaN(lng)) return;
                    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return;

                    var props = { ...item, pointType: 'fixed' };
                    var radius = def.radius;
                    if (typeof def.radius === 'object' && def.radius.field) {
                        var val = parseFloat(item[def.radius.field]) || 0;
                        radius = Math.max(def.radius.min, Math.min(def.radius.max, val * def.radius.scale));
                        props.pointType = 'scaled';
                        props.radiusValue = radius;
                    }

                    features.push({
                        type: 'Feature',
                        geometry: { type: 'Point', coordinates: [lng, lat] },
                        properties: props,
                    });
                });

                var geojson = { type: 'FeatureCollection', features: features };

                if (self.state.map && self.state.map.getSource('source-' + def.id)) {
                    self.state.map.getSource('source-' + def.id).setData(geojson);
                }

                if (self.state.layers[def.id]) {
                    self.state.layers[def.id].featureCount = features.length;
                }
                self._updateLayerCount();
            })
            .catch(function(err) {
                console.warn('[OSIRIS-MAP] Failed to load layer ' + key + ':', err);
            });
    },

    _loadLocalGeo: function(key) {
        var self = this;
        var def = this.LAYER_DEFS[key];
        if (!def) return;

        var points = [];
        if (window._initialMapData) {
            if (window._initialMapData.geo_points) points.push(...window._initialMapData.geo_points);
            if (window._initialMapData.ai_geopoints) points.push(...window._initialMapData.ai_geopoints);
        }

        if (!points.length) {
            fetch('/api/map-data')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var newPoints = [];
                    if (data.geo_points) newPoints.push(...data.geo_points);
                    if (data.ai_geopoints) newPoints.push(...data.ai_geopoints);
                    self._renderLocalGeo(key, newPoints);
                })
                .catch(function(err) {
                    console.warn('[OSIRIS-MAP] COBALTO geo load failed:', err);
                });
            return;
        }

        self._renderLocalGeo(key, points);
    },

    _renderLocalGeo: function(key, points) {
        var def = this.LAYER_DEFS[key];
        if (!def || !this.state.map) return;

        var features = [];
        var esc = function(s) { return String(s).replace(/[&<>"']/g, function(m) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"})[m]; }); };

        points.forEach(function(p) {
            var lat = parseFloat(p.lat);
            var lng = parseFloat(p.lon != null ? p.lon : (p.lng != null ? p.lng : p.longitude));
            if (isNaN(lat) || isNaN(lng)) return;

            features.push({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: [lng, lat] },
                properties: {
                    title: p.title || '',
                    type: p.type || 'INTEL',
                    source: p.source || '',
                    date: p.date || '',
                    summary: p.summary || '',
                    color: p.color || def.color,
                    pointType: 'fixed',
                },
            });
        });

        var geojson = { type: 'FeatureCollection', features: features };

        if (this.state.map.getSource('source-' + def.id)) {
            this.state.map.getSource('source-' + def.id).setData(geojson);
        }

        if (this.state.layers[def.id]) {
            this.state.layers[def.id].featureCount = features.length;
        }
        this._updateLayerCount();
    },

    _getNested: function(obj, path) {
        try {
            return path.reduce(function(acc, key) { return acc ? acc[key] : undefined; }, obj);
        } catch(e) { return undefined; }
    },

    _onMapClick: function(e) {
        var self = this;
        var features = this.state.map.queryRenderedFeatures(e.point);
        if (!features || !features.length) return;

        // Find first feature from our layers
        var osirisFeature = null;
        var layerKey = null;
        for (var i = 0; i < features.length; i++) {
            var fid = features[i].layer ? features[i].layer.id : '';
            for (var key in this.LAYER_DEFS) {
                if (fid === 'layer-' + this.LAYER_DEFS[key].id) {
                    osirisFeature = features[i];
                    layerKey = key;
                    break;
                }
            }
            if (osirisFeature) break;
        }

        if (!osirisFeature || !layerKey) return;

        var props = osirisFeature.properties;
        var def = this.LAYER_DEFS[layerKey];
        var html = this._buildPopupHtml(props, def);

        new maplibregl.Popup({ offset: 25 })
            .setLngLat(e.lngLat)
            .setHTML(html)
            .addTo(this.state.map);
    },

    _buildPopupHtml: function(props, def) {
        var esc = function(s) {
            if (s === null || s === undefined) return '';
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        };
        var html = '<div style="font-family:monospace;font-size:11px;color:#fff;max-width:280px;">';
        html += '<div style="color:' + def.color + ';font-weight:bold;font-size:12px;margin-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;">' + def.icon + ' ' + esc(def.label) + '</div>';

        var fields = {};

        switch (def.id) {
            case 'flights':
                fields = { 'Callsign': 'callsign', 'Alt (ft)': 'alt', 'Speed (kts)': 'speed_knots', 'Heading': 'heading', 'Model': 'model', 'ICAO24': 'icao24', 'Squawk': 'squawk' };
                break;
            case 'satellites':
                fields = { 'Name': 'name', 'Mission': 'mission', 'Alt (km)': 'alt', 'NORAD ID': 'noradId' };
                break;
            case 'earthquakes':
                fields = { 'Magnitude': 'magnitude', 'Place': 'place', 'Depth (km)': 'depth', 'Tsunami': 'tsunami', 'Alert': 'alert', 'Felt': 'felt' };
                break;
            case 'fires':
                fields = { 'Brightness': 'brightness', 'Confidence': 'confidence', 'FRP': 'frp', 'Date': 'date', 'Time': 'time' };
                break;
            case 'weather':
                fields = { 'Title': 'title', 'Category': 'category', 'Severity': 'severity', 'Source': 'source' };
                break;
            case 'cctv':
                fields = { 'Name': 'name', 'City': 'city', 'Country': 'country', 'Source': 'source' };
                if (props.feed_url) {
                    html += '<div style="margin-bottom:6px;"><img src="' + esc(props.feed_url) + '" style="width:100%;border-radius:4px;max-height:120px;object-fit:cover;" onerror="this.style.display=\'none\'" loading="lazy"/></div>';
                }
                break;
        }

        for (var f in fields) {
            var val = props[fields[f]];
            if (val === null || val === undefined || val === '') continue;
            var displayVal = typeof val === 'number' ? val.toLocaleString() : esc(val);
            html += '<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.03);"><span style="color:var(--text-muted);">' + esc(f) + '</span><span style="color:#ddd;">' + displayVal + '</span></div>';
        }

        html += '</div>';
        return html;
    },

    toggleLayer: function(key) {
        var layerState = this.state.layers[key];
        if (!layerState) return;
        var def = this.LAYER_DEFS[key];
        if (!def) return;

        layerState.visible = !layerState.visible;
        def.visible = layerState.visible;

        var visibility = layerState.visible ? 'visible' : 'none';
        if (this.state.map && this.state.map.getLayer(layerState.layerId)) {
            this.state.map.setLayoutProperty(layerState.layerId, 'visibility', visibility);
        }

        this._updateLayerCount();
        this._renderLayerPanel();
    },

    refreshLayer: function(key) {
        this._showLoading(true);
        var self = this;
        this._loadLayer(key);
        setTimeout(function() { self._showLoading(false); }, 500);
    },

    refreshAll: function() {
        this._showLoading(true);
        var self = this;
        this._loadAllLayers();
        setTimeout(function() { self._showLoading(false); }, 800);
    },

    _showLoading: function(show) {
        var el = document.getElementById('osiris-map-loading');
        if (el) el.style.display = show ? 'block' : 'none';
    },

    _renderLayerPanel: function() {
        var list = document.getElementById('osiris-layer-list');
        if (!list) return;

        var self = this;
        var html = '';
        var keys = Object.keys(this.LAYER_DEFS);

        keys.forEach(function(key) {
            var def = self.LAYER_DEFS[key];
            var layerState = self.state.layers[key];
            var isVisible = layerState ? layerState.visible : true;
            var count = layerState ? (layerState.featureCount || 0) : 0;
            var checked = isVisible ? 'checked' : '';

            html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px solid rgba(255,255,255,0.03);cursor:pointer;" onclick="window.OsirisMap.toggleLayer(\'' + key + '\')">' +
                '<input type="checkbox" ' + checked + ' style="accent-color:' + def.color + ';width:14px;height:14px;cursor:pointer;" onclick="event.stopPropagation();window.OsirisMap.toggleLayer(\'' + key + '\')" />' +
                '<span style="font-size:14px;">' + def.icon + '</span>' +
                '<span style="flex:1;font-size:0.7rem;color:#ddd;">' + def.label + '</span>' +
                '<span style="font-size:0.6rem;color:var(--text-muted);font-family:monospace;">' + count + '</span>' +
                '<button onclick="event.stopPropagation();window.OsirisMap.refreshLayer(\'' + key + '\')" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:0.7rem;padding:2px;">⟳</button>' +
                '</div>';
        });

        list.innerHTML = html;
    },

    _updateLayerCount: function() {
        var countEl = document.getElementById('osiris-layer-count');
        if (!countEl) return;
        var visible = 0;
        var total = 0;
        for (var key in this.LAYER_DEFS) {
            total++;
            var ls = this.state.layers[key];
            if (ls && ls.visible) visible++;
        }
        countEl.textContent = visible + '/' + total;
    },

    invalidateMap: function() {
        if (this.state.map) {
            this.state.map.resize();
        }
    },
};
