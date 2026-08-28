window.OsirisGlobal = {
    state: {
        cameras: [],
        feed: [],
        pollTimers: [],
        active: false,
        cctvPage: 0,
        cctvPerPage: 12,
        cctvFilter: 'all',
        cctvTotal: 0,
        cctvValid: 0,
        cctvCols: 2,
        cctvSelected: null,
        liveVision: true,
        liveVisionTimer: null,
    },

    init: function() {
        var self = this;
        this.state.active = true;

        var filter = document.getElementById('osiris-cctv-filter');
        if (filter) {
            filter.addEventListener('change', function() { self.setCCTVFilter(this.value); });
        }

        var searchInput = document.getElementById('osiris-cctv-search');
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                self.state.searchQuery = this.value;
                self.state.cctvPage = 0;
                self._renderCCTV();
            });
        }

        this.loadCCTV();
        this.loadFeed();
        this.loadAerospace();

        this.state.pollTimers.push(setInterval(function() { self.loadFeed(); }, 120000));
        this.state.pollTimers.push(setInterval(function() { self.loadCCTV(); }, 300000));
        this.state.pollTimers.push(setInterval(function() { self.loadAerospace(); }, 120000));

        var refreshBtn = document.getElementById('osiris-cctv-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() { self.loadCCTV(); });
        }

        this.startLiveVisionStream();
    },

    destroy: function() {
        this.state.active = false;
        this.state.pollTimers.forEach(function(t) { clearInterval(t); });
        this.state.pollTimers = [];
        if (this.state.liveVisionTimer) {
            clearInterval(this.state.liveVisionTimer);
            this.state.liveVisionTimer = null;
        }
    },

    toggleLiveVision: function() {
        this.state.liveVision = !this.state.liveVision;
        var btn = document.getElementById('osiris-cctv-live-btn');
        if (btn) {
            if (this.state.liveVision) {
                btn.style.background = 'rgba(0,255,170,0.12)';
                btn.style.borderColor = 'rgba(0,255,170,0.4)';
                btn.style.color = '#00FFAA';
                btn.textContent = '🔴 LIVE STREAM: ON';
                this.startLiveVisionStream();
            } else {
                btn.style.background = 'rgba(255,255,255,0.05)';
                btn.style.borderColor = 'rgba(255,255,255,0.1)';
                btn.style.color = '#64748B';
                btn.textContent = '⚪ LIVE STREAM: OFF';
                if (this.state.liveVisionTimer) {
                    clearInterval(this.state.liveVisionTimer);
                    this.state.liveVisionTimer = null;
                }
            }
        }
    },

    captureSnapshot: function(camObj) {
        var cam = camObj || this.state.cctvSelected;
        if (!cam || !cam.feed_url) return;
        var proxyUrl = '/api/osiris/cctv/image?url=' + encodeURIComponent(cam.feed_url) + '&_t=' + Date.now();
        var a = document.createElement('a');
        a.href = proxyUrl;
        var cleanName = (cam.name || 'cctv_snapshot').replace(/[^a-zA-Z0-9_-]/g, '_');
        a.download = cleanName + '_' + Date.now() + '.jpg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        if (typeof showTacticalToast === 'function') {
            showTacticalToast('📸 Snapshot descargado: ' + cleanName + '.jpg', 'success');
        }
    },

    startLiveVisionStream: function() {
        var self = this;
        if (this.state.liveVisionTimer) clearInterval(this.state.liveVisionTimer);
        this.state.liveVisionTimer = setInterval(function() {
            if (!self.state.active || !self.state.liveVision) return;
            var imgs = document.querySelectorAll('.cctv-img');
            var now = Date.now();
            for (var i = 0; i < imgs.length; i++) {
                var img = imgs[i];
                var baseSrc = img.getAttribute('data-base-src') || img.src;
                if (!img.getAttribute('data-base-src')) {
                    img.setAttribute('data-base-src', baseSrc);
                }
                var cleanUrl = baseSrc.replace(/([?&])_t=\d+/, '');
                var sep = cleanUrl.indexOf('?') !== -1 ? '&' : '?';
                img.src = cleanUrl + sep + '_t=' + now;
            }
            var modalImg = document.getElementById('cctv-modal-img');
            var modal = document.getElementById('cctv-modal');
            if (modal && modal.style.display !== 'none' && modalImg && modalImg.src) {
                var modalBase = modalImg.getAttribute('data-base-src') || modalImg.src;
                if (!modalImg.getAttribute('data-base-src')) {
                    modalImg.setAttribute('data-base-src', modalBase);
                }
                var cleanModalUrl = modalBase.replace(/([?&])_t=\d+/, '');
                var sepM = cleanModalUrl.indexOf('?') !== -1 ? '&' : '?';
                modalImg.src = cleanModalUrl + sepM + '_t=' + now;
            }
        }, 3200);
    },

    // ── CCTV Layout ──────────────────────────────────────────

    setCCTVCols: function(n) {
        this.state.cctvCols = n;
        this.state.cctvPage = 0;
        this._renderCCTV();
        var btns = document.querySelectorAll('.cctv-layout-btn');
        for (var i = 0; i < btns.length; i++) {
            var b = btns[i];
            var val = parseInt(b.getAttribute('data-cols'));
            b.style.borderColor = val === n ? 'rgba(0,229,255,0.5)' : 'rgba(255,255,255,0.1)';
            b.style.color = val === n ? '#00E5FF' : '#64748B';
        }
    },

    // ── CCTV Data ────────────────────────────────────────────

    loadCCTV: function() {
        var self = this;
        if (!this.state.active) return;
        fetch('/api/osiris/data/cctv?region=all')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.cameras = data.cameras || [];
                self.state.cctvPage = 0;
                self._updateCCTVStats();
                self._renderCCTV();
            })
            .catch(function(err) {
                console.warn('[OSIRIS] CCTV load failed:', err);
            });
    },

    _updateCCTVStats: function() {
        var cams = this.state.cameras || [];
        var valid = 0, sources = {};
        for (var i = 0; i < cams.length; i++) {
            var c = cams[i];
            if (c.feed_url) valid++;
            var src = c.source || 'unknown';
            sources[src] = (sources[src] || 0) + 1;
        }
        this.state.cctvTotal = cams.length;
        this.state.cctvValid = valid;
        this.state.cctvSources = sources;

        var filter = document.getElementById('osiris-cctv-filter');
        if (filter) {
            var current = filter.value;
            var html = '<option value="all">ALL SOURCES</option>';
            for (var s in sources) {
                html += '<option value="' + this._esc(s) + '">' + this._esc(s) + ' (' + sources[s] + ')</option>';
            }
            filter.innerHTML = html;
            filter.value = sources[current] ? current : 'all';
        }
    },

    setCCTVFilter: function(source) {
        this.state.cctvFilter = source;
        this.state.cctvPage = 0;
        this._renderCCTV();
    },

    loadMoreCCTV: function() {
        this.state.cctvPage++;
        this._renderCCTV(true);
    },

    _getFilteredCameras: function() {
        var cams = this.state.cameras || [];
        var filter = this.state.cctvFilter;
        var query = (this.state.searchQuery || '').toLowerCase().trim();
        return cams.filter(function(c) {
            var matchSource = filter === 'all' || (c.source || '') === filter;
            if (!matchSource) return false;
            if (!query) return true;
            var name = (c.name || '').toLowerCase();
            var city = (c.city || '').toLowerCase();
            var country = (c.country || '').toLowerCase();
            var src = (c.source || '').toLowerCase();
            return name.indexOf(query) !== -1 || city.indexOf(query) !== -1 || country.indexOf(query) !== -1 || src.indexOf(query) !== -1;
        });
    },

    selectCamera: function(cam) {
        this.state.cctvSelected = cam;
        this._renderCCTVInfo();
    },

    _isHlsStream: function(url) {
        if (!url) return false;
        var clean = String(url).toLowerCase().split('?')[0];
        return clean.indexOf('.m3u8') !== -1 || clean.indexOf('/hls/') !== -1 || clean.indexOf('m3u8=') !== -1;
    },

    expandCamera: function(cam) {
        var modal = document.getElementById('cctv-modal');
        var img = document.getElementById('cctv-modal-img');
        var video = document.getElementById('cctv-modal-video');
        var name = document.getElementById('cctv-modal-name');
        var meta = document.getElementById('cctv-modal-meta');
        if (!modal || !img) return;

        name.textContent = cam.name || 'Unknown';
        
        if (this.state.modalHls) {
            try { this.state.modalHls.destroy(); } catch(e) {}
            this.state.modalHls = null;
        }

        var isHls = this._isHlsStream(cam.feed_url);

        if (isHls && video) {
            img.style.display = 'none';
            video.style.display = 'block';
            if (window.Hls && Hls.isSupported()) {
                var hls = new Hls({ enableWorker: true, lowLatencyMode: true, backBufferLength: 30 });
                hls.loadSource(cam.feed_url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    video.play().catch(function() {});
                });
                hls.on(Hls.Events.ERROR, function(e, data) {
                    if (data.fatal) {
                        switch(data.type) {
                            case Hls.ErrorTypes.NETWORK_ERROR: hls.startLoad(); break;
                            case Hls.ErrorTypes.MEDIA_ERROR: hls.recoverMediaError(); break;
                            default: hls.destroy(); break;
                        }
                    }
                });
                this.state.modalHls = hls;
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = cam.feed_url;
                video.play().catch(function() {});
            }
        } else {
            if (video) { video.style.display = 'none'; try { video.pause(); } catch(e) {} }
            img.style.display = 'block';
            var proxyUrl = '/api/osiris/cctv/image?url=' + encodeURIComponent(cam.feed_url || '');
            img.setAttribute('data-base-src', proxyUrl);
            img.src = proxyUrl + '&_t=' + Date.now();
        }

        meta.innerHTML =
            '<div><span style="color:#64748B;">Source:</span> ' + this._esc(cam.source || '') + ' ' + (isHls ? '<span style="color:#00E5FF;font-weight:bold;">[LIVE HLS STREAM]</span>' : '') + '</div>' +
            '<div><span style="color:#64748B;">Location:</span> ' + this._esc(cam.city || '') + (cam.country ? ', ' + this._esc(cam.country) : '') + '</div>' +
            '<div><span style="color:#64748B;">Lat:</span> ' + (cam.lat || 0) + ' <span style="color:#64748B;">Lng:</span> ' + (cam.lng || 0) + '</div>' +
            '<div style="margin-top:8px;display:flex;gap:6px;justify-content:center;">' +
            '<button onclick="if(window.OsirisGlobal)window.OsirisGlobal.captureSnapshot()" style="background:rgba(0,229,255,0.12);border:1px solid rgba(0,229,255,0.4);border-radius:4px;color:#00E5FF;padding:4px 10px;font-size:10px;font-family:monospace;cursor:pointer;">📸 CAPTURAR SNAPSHOT</button>' +
            '</div>';
        modal.style.display = 'flex';
    },

    closeModal: function() {
        var modal = document.getElementById('cctv-modal');
        var video = document.getElementById('cctv-modal-video');
        if (this.state.modalHls) {
            try { this.state.modalHls.destroy(); } catch(e) {}
            this.state.modalHls = null;
        }
        if (video) {
            try { video.pause(); video.src = ''; } catch(e) {}
        }
        if (modal) modal.style.display = 'none';
    },

    // ── CCTV Render ──────────────────────────────────────────

    _renderCCTV: function(append) {
        var grid = document.getElementById('osiris-cctv-grid');
        var countEl = document.getElementById('osiris-cctv-count');
        var moreBtn = document.getElementById('osiris-cctv-more');
        if (!grid) return;

        var cols = this.state.cctvCols;
        grid.style.gridTemplateColumns = 'repeat(' + cols + ', 1fr)';

        var filtered = this._getFilteredCameras();
        var validCams = [];
        for (var ci = 0; ci < filtered.length; ci++) {
            if (filtered[ci].feed_url) validCams.push(filtered[ci]);
        }

        var statusText = this.state.cctvTotal + ' CÁMARAS';
        if (this.state.cctvFilter !== 'all') {
            statusText += ' [' + this.state.cctvFilter + ']';
        }
        statusText += ' · ' + validCams.length + ' feeds';
        if (countEl) countEl.textContent = statusText;

        if (!validCams.length) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);font-family:monospace;font-size:11px;">' +
                (this.state.cctvTotal ? '⚠️ NO HAY CÁMARAS CON FEED (' + this.state.cctvTotal + ' total)' : '⟳ LOADING CCTV FEEDS...') + '</div>';
            if (moreBtn) moreBtn.style.display = 'none';
            return;
        }

        var start = this.state.cctvPage * this.state.cctvPerPage;
        var end = start + this.state.cctvPerPage;
        var page = validCams.slice(start, end);
        var ts = Date.now();

        var html = '';
        for (var i = 0; i < page.length; i++) {
            var cam = page[i];
            var idx = start + i;
            var camId = 'cam-' + idx + '-' + ts;
            var proxyUrl = '/api/osiris/cctv/image?url=' + encodeURIComponent(cam.feed_url);
            var camData = this._esc(JSON.stringify(cam).replace(/'/g, '&#39;').replace(/"/g, '&quot;'));

            html += '<div class="cctv-card" data-cam=\'' + camData + '\'>' +
                '<div class="cctv-preview" id="' + camId + '-wrapper">' +
                '<div class="cctv-ph" id="' + camId + '-ph">⟳</div>' +
                '<img id="' + camId + '-img" class="cctv-img" data-base-src="' + proxyUrl + '" src="' + proxyUrl + '" />' +
                '<div class="cctv-badge-src">' + this._esc(cam.source || '') + '</div>' +
                '<div class="cctv-dot" id="' + camId + '-dot"></div>' +
                '</div>' +
                '<div class="cctv-info">' +
                '<div class="cctv-name">' + this._esc(cam.name || 'Unknown') + '</div>' +
                '<div class="cctv-loc">' + this._esc(cam.city || '') + (cam.country ? ', ' + this._esc(cam.country) : '') + '</div>' +
                '</div></div>';
        }

        if (append) {
            grid.insertAdjacentHTML('beforeend', html);
        } else {
            grid.innerHTML = html;
        }

        for (var i = 0; i < page.length; i++) {
            var idx = start + i;
            var camId = 'cam-' + idx + '-' + ts;
            var cam = page[i];
            (function(id, camObj) {
                setTimeout(function() {
                    var card = document.getElementById(id + '-wrapper');
                    var img = document.getElementById(id + '-img');
                    var ph = document.getElementById(id + '-ph');
                    var dot = document.getElementById(id + '-dot');
                    if (!img || !ph) return;

                    img.onload = function() {
                        try { ph.style.display = 'none'; } catch(e) {}
                        try { img.style.display = 'block'; } catch(e) {}
                        try { if (dot) { dot.style.background = '#00FFAA'; dot.style.boxShadow = '0 0 8px #00FFAA'; } } catch(e) {}
                    };
                    img.onerror = function() {
                        try {
                            var base = this.getAttribute('data-base-src') || this.src;
                            this.src = base + (base.indexOf('?') !== -1 ? '&' : '?') + '_r=' + Date.now();
                        } catch(e) {}
                        try { if (dot) { dot.style.background = '#FF9500'; dot.style.boxShadow = '0 0 8px #FF9500'; } } catch(e) {}
                    };
                    if (img.complete && img.naturalHeight > 1) {
                        try { ph.style.display = 'none'; } catch(e) {}
                        try { if (dot) { dot.style.background = '#00FFAA'; dot.style.boxShadow = '0 0 8px #00FFAA'; } } catch(e) {}
                    }

                    if (card) {
                        card.onclick = function(e) {
                            e.stopPropagation();
                            if (window.OsirisGlobal) window.OsirisGlobal.selectCamera(camObj);
                            var all = document.querySelectorAll('.cctv-card');
                            for (var ci = 0; ci < all.length; ci++) { all[ci].style.borderColor = 'rgba(255,255,255,0.05)'; }
                            var parent = card.closest('.cctv-card');
                            if (parent) parent.style.borderColor = '#00E5FF';
                        };
                        card.ondblclick = function(e) {
                            e.stopPropagation();
                            if (window.OsirisGlobal) window.OsirisGlobal.expandCamera(camObj);
                        };
                    }
                }, 10);
            })(camId, cam);
        }

        if (moreBtn) {
            var hasMore = end < validCams.length;
            moreBtn.style.display = hasMore ? 'block' : 'none';
            moreBtn.innerHTML = 'LOAD MORE (' + (validCams.length - end) + ' remaining)';
            moreBtn.onclick = function() { window.OsirisGlobal.loadMoreCCTV(); };
        }
    },

    _renderCCTVInfo: function() {
        var panel = document.getElementById('cctv-info-panel');
        if (!panel) return;
        var cam = this.state.cctvSelected;
        if (!cam) {
            panel.innerHTML = '<div style="text-align:center;padding:20px;color:#64748B;font-size:9px;font-family:monospace;">SELECT A CAMERA</div>';
            return;
        }
        panel.innerHTML =
            '<div style="color:#00E5FF;font-weight:bold;font-size:10px;margin-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:6px;">📹 ' + this._esc(cam.name || 'Unknown') + '</div>' +
            '<div class="cctv-meta-row"><span class="cctv-meta-label">Source</span><span>' + this._esc(cam.source || '') + '</span></div>' +
            '<div class="cctv-meta-row"><span class="cctv-meta-label">City</span><span>' + this._esc(cam.city || '') + '</span></div>' +
            '<div class="cctv-meta-row"><span class="cctv-meta-label">Country</span><span>' + this._esc(cam.country || '') + '</span></div>' +
            '<div class="cctv-meta-row"><span class="cctv-meta-label">Lat</span><span>' + (typeof cam.lat === 'number' ? cam.lat.toFixed(4) : cam.lat) + '</span></div>' +
            '<div class="cctv-meta-row"><span class="cctv-meta-label">Lng</span><span>' + (typeof cam.lng === 'number' ? cam.lng.toFixed(4) : cam.lng) + '</span></div>' +
            '<div class="cctv-meta-row"><span class="cctv-meta-label">Stream</span><span style="color:#76FF03;">' + (cam.stream_type || 'jpg').toUpperCase() + '</span></div>' +
            (cam.feed_url ? '<div style="margin-top:8px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.04);"><div style="color:#64748B;font-size:7px;margin-bottom:2px;">FEED URL</div><div style="font-size:7px;color:#555;word-break:break-all;">' + this._esc(cam.feed_url) + '</div></div>' : '') +
            '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;">' +
            '<button onclick="if(window.OsirisGlobal)window.OsirisGlobal.expandCamera(window.OsirisGlobal.state.cctvSelected)" style="flex:1;min-width:65px;background:rgba(0,229,255,0.08);border:1px solid rgba(0,229,255,0.2);border-radius:4px;color:#00E5FF;padding:5px 2px;font-size:8px;font-family:monospace;cursor:pointer;">🔍 EXPANDIR</button>' +
            '<button onclick="if(window.OsirisGlobal)window.OsirisGlobal.captureSnapshot(window.OsirisGlobal.state.cctvSelected)" style="flex:1;min-width:65px;background:rgba(255,215,0,0.1);border:1px solid rgba(255,215,0,0.3);border-radius:4px;color:#FFD700;padding:5px 2px;font-size:8px;font-family:monospace;cursor:pointer;">📸 CAPTURAR</button>' +
            '<button onclick="if(window.OsirisGlobal)window.OsirisGlobal.analyzeCCTV(window.OsirisGlobal.state.cctvSelected)" style="flex:1;min-width:65px;background:rgba(255,45,85,0.12);border:1px solid rgba(255,45,85,0.3);border-radius:4px;color:#FF2D55;padding:5px 2px;font-size:8px;font-family:monospace;cursor:pointer;">⚡ YOLOv8 AI</button>' +
            '<button onclick="if(window.OsirisGlobal&&window.OsirisGlobal.state.cctvSelected){var c=window.OsirisGlobal.state.cctvSelected;if(window.switchTab)window.switchTab(\'tab-map\');setTimeout(function(){if(window.UnifiedMap&&window.UnifiedMap.focusLocation)window.UnifiedMap.focusLocation(c.lat,c.lng,c.name);},150);}" style="flex:1;min-width:65px;background:rgba(0,255,170,0.08);border:1px solid rgba(0,255,170,0.2);border-radius:4px;color:#00FFAA;padding:5px 2px;font-size:8px;font-family:monospace;cursor:pointer;">📍 MAPA</button>' +
            '</div>' +
            '<div id="cctv-ai-panel" style="margin-top:6px;display:none;padding:6px;background:rgba(255,45,85,0.05);border:1px dashed rgba(255,45,85,0.3);border-radius:4px;font-size:8px;"></div>';
    },

    analyzeCCTV: function(cam) {
        if (!cam) return;
        var panel = document.getElementById('cctv-ai-panel');
        if (!panel) return;
        panel.style.display = 'block';
        panel.innerHTML = '<span style="color:#FF2D55;">⚡ EJECUTANDO ANALÍTICA YOLOv8-NANO...</span>';

        fetch('/api/osiris/cctv/analyze?camera_id=' + encodeURIComponent(cam.id || 'cam') + '&url=' + encodeURIComponent(cam.feed_url || ''))
            .then(function(r) { return r.json(); })
            .then(function(res) {
                var objs = res.objects_detected || {};
                var statusColor = res.anomaly_detected ? '#FF2D55' : '#00FFAA';
                panel.innerHTML =
                    '<div style="color:#FF2D55;font-weight:bold;margin-bottom:4px;">YOLOv8-NANO ANALYTICS (' + (res.confidence * 100).toFixed(0) + '% CONF)</div>' +
                    '<div>🚗 Vehículos: <b>' + (objs.vehicles || 0) + '</b> · 🚶 Peatones: <b>' + (objs.pedestrians || 0) + '</b></div>' +
                    '<div>Tráfico: <b style="color:' + statusColor + ';">' + (res.traffic_density || 'NORMAL') + '</b> · Estado: <b style="color:' + statusColor + ';">' + (res.tactical_status || 'NORMAL') + '</b></div>';
            })
            .catch(function() {
                panel.innerHTML = '<span style="color:#FF4444;">❌ Error en servidor de analítica</span>';
            });
    },


    // ── SIGINT Feed ──────────────────────────────────────────

    loadFeed: function() {
        var self = this;
        if (!this.state.active) return;
        fetch('/api/osiris/data/news')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.feed = data.news || [];
                self._renderFeed();
            })
            .catch(function(err) {
                console.warn('[OSIRIS] Feed load failed:', err);
            });
    },

    _renderFeed: function() {
        var container = document.getElementById('osiris-feed-container');
        var countEl = document.getElementById('osiris-feed-count');
        if (!container) return;

        var items = this.state.feed;
        if (countEl) countEl.textContent = (items ? items.length : 0) + ' ITEMS';

        if (!items || !items.length) {
            container.innerHTML = '<div style="text-align:center;padding:15px;color:var(--text-muted);font-size:10px;font-family:monospace;">AWAITING INTELLIGENCE...</div>';
            return;
        }

        var self = this;
        var html = '';
        items.slice(0, 15).forEach(function(item) {
            var riskColor = (item.risk_score || 0) >= 8 ? '#FF4444' : (item.risk_score || 0) >= 6 ? '#FF9500' : (item.risk_score || 0) >= 4 ? '#FFD700' : '#76FF03';
            var riskLabel = (item.risk_score || 0) >= 8 ? 'CRITICAL' : (item.risk_score || 0) >= 6 ? 'HIGH' : (item.risk_score || 0) >= 4 ? 'ELEVATED' : 'LOW';
            html += '<div style="padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.03);cursor:pointer;" onclick="if(this.nextUrl)window.open(this.nextUrl,\'_blank\');" nextUrl="' + self._esc(item.link || '') + '">' +
                '<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">' +
                '<span style="font-size:7px;font-weight:bold;color:' + riskColor + ';font-family:monospace;">' + riskLabel + '</span>' +
                '<span style="font-size:7px;color:var(--text-muted);background:rgba(255,255,255,0.05);padding:1px 4px;border-radius:2px;font-family:monospace;">' + self._esc(item.source || '') + '</span>' +
                '<span style="font-size:7px;color:var(--text-muted);margin-left:auto;font-family:monospace;">' + self._timeAgo(item.published || '') + '</span>' +
                '</div>' +
                '<div style="font-size:9px;color:#ddd;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + self._esc((item.title || '').substring(0, 100)) + '</div>' +
                '</div>';
        });

        container.innerHTML = html;
    },

    // ── Aerospace ────────────────────────────────────────────

    loadAerospace: function() {
        var self = this;
        if (!this.state.active) return;
        var p1 = fetch('/api/osiris/data/satellites').then(function(r) { return r.json(); }).catch(function() { return {}; });
        var p2 = fetch('/api/osiris/data/flights').then(function(r) { return r.json(); }).catch(function() { return {}; });
        Promise.all([p1, p2]).then(function(res) {
            var satData = res[0] || {};
            var fltData = res[1] || {};
            var c = document.getElementById('osiris-aerospace-container');
            if (!c) return;

            var cats = satData.category_counts || {};
            var htmlSats = '<div style="background:rgba(0,0,0,0.3);padding:8px;border-radius:8px;">' +
                '<div style="color:#D4AF37;margin-bottom:6px;">SATELLITES</div>' +
                '<div style="font-size:1.2rem;font-weight:bold;margin-bottom:8px;">' + (satData.total || 0) + '</div>';
            for (var k in cats) {
                htmlSats += '<div style="display:flex;justify-content:space-between;font-size:0.65rem;border-bottom:1px solid rgba(255,255,255,0.05);padding:2px 0;"><span>' + self._esc(k.toUpperCase()) + '</span><span>' + cats[k] + '</span></div>';
            }
            htmlSats += '</div>';

            var flights = fltData.military_flights || [];
            var htmlFlights = '<div style="background:rgba(0,0,0,0.3);padding:8px;border-radius:8px;">' +
                '<div style="color:#D4AF37;margin-bottom:6px;">MILITARY FLIGHTS</div>' +
                '<div style="font-size:1.2rem;font-weight:bold;margin-bottom:8px;">' + (fltData.total || 0) + '</div>';
            flights.slice(0, 6).forEach(function(f) {
                htmlFlights += '<div style="display:flex;justify-content:space-between;font-size:0.65rem;border-bottom:1px solid rgba(255,255,255,0.05);padding:2px 0;"><span>' + self._esc(f.callsign || 'UNKNOWN') + '</span><span style="color:#00FFAA;">' + (f.speed_knots || 0) + 'kts</span></div>';
            });
            htmlFlights += '</div>';

            c.innerHTML = htmlSats + htmlFlights;
        });
    },

    // ── Utilities ────────────────────────────────────────────

    _esc: function(s) {
        if (s === null || s === undefined) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    _timeAgo: function(dateStr) {
        try {
            if (!dateStr) return '';
            var diff = Date.now() - new Date(dateStr).getTime();
            var mins = Math.floor(diff / 60000);
            if (mins < 60) return mins + 'm';
            var hrs = Math.floor(mins / 60);
            if (hrs < 24) return hrs + 'h';
            return Math.floor(hrs / 24) + 'd';
        } catch(e) { return ''; }
    },
};
