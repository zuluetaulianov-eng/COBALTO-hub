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
        healthMap: {},
        healthOnline: 0,
        healthTotal: 0,
        healthLastCheck: null,
        searchQuery: '',
        searchTimer: null,
        sortMode: 'online',
        hlsInstances: {},
        countryStats: {},
        observer: null,
    },

    init: function() {
        var self = this;
        this.state.active = true;

        var filter = document.getElementById('osiris-cctv-filter');
        if (filter) {
            filter.addEventListener('change', function() { self.setCCTVFilter(this.value); });
        }

        var sortSel = document.getElementById('osiris-cctv-sort');
        if (sortSel) {
            sortSel.addEventListener('change', function() {
                self.state.sortMode = this.value;
                self.state.cctvPage = 0;
                self._renderCCTV();
            });
        }

        var searchInput = document.getElementById('osiris-cctv-search');
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                var q = this.value;
                if (self.state.searchTimer) clearTimeout(self.state.searchTimer);
                self.state.searchTimer = setTimeout(function() {
                    self.state.searchQuery = q;
                    self.state.cctvPage = 0;
                    self._renderCCTV();
                }, 300);
            });
        }

        this.state.observer = this._buildObserver();

        this.loadCCTV();
        this.loadFeed();
        this.loadAerospace();
        this.loadHealth();

        this.state.pollTimers.push(setInterval(function() { self.loadFeed(); }, 120000));
        this.state.pollTimers.push(setInterval(function() { self.loadCCTV(); }, 300000));
        this.state.pollTimers.push(setInterval(function() { self.loadAerospace(); }, 120000));
        this.state.pollTimers.push(setInterval(function() { self.loadHealth(); }, 120000));

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
        if (this.state.searchTimer) {
            clearTimeout(this.state.searchTimer);
            this.state.searchTimer = null;
        }
        if (this.state.observer) {
            this.state.observer.disconnect();
            this.state.observer = null;
        }
        this._destroyAllHls();
    },

    _destroyAllHls: function() {
        for (var id in this.state.hlsInstances) {
            try {
                var inst = this.state.hlsInstances[id];
                if (inst && inst.destroy) inst.destroy();
            } catch(e) {}
        }
        this.state.hlsInstances = {};
        var vids = document.querySelectorAll('video.cctv-img, #cctv-modal-video');
        for (var i = 0; i < vids.length; i++) {
            try { vids[i].pause(); vids[i].removeAttribute('src'); vids[i].load(); } catch(e) {}
        }
    },

    _teardownGridMedia: function() {
        // Destruye los streams HLS de la grid y desregistra del observer al reconstruir (evita fugas)
        var cards = document.querySelectorAll('.cctv-card, .cctv-preview');
        if (this.state.observer) {
            for (var k = 0; k < cards.length; k++) {
                try { this.state.observer.unobserve(cards[k]); } catch(e) {}
            }
        }
        var ids = Object.keys(this.state.hlsInstances);
        for (var i = 0; i < ids.length; i++) {
            var id = ids[i];
            if (!document.getElementById(id)) {
                try {
                    var inst = this.state.hlsInstances[id];
                    if (inst && inst.destroy) inst.destroy();
                } catch(e) {}
                delete this.state.hlsInstances[id];
            }
        }
    },

    _buildObserver: function() {
        var self = this;
        self.state.observer = null;
        var io;
        try {
            io = new IntersectionObserver(function(entries) {
                self._onIntersection(entries);
            }, { root: document.getElementById('osiris-cctv-container'), rootMargin: '120px', threshold: 0 });
        } catch(e) { return null; }
        return io;
    },

    _onIntersection: function(entries) {
        var self = this;
        for (var i = 0; i < entries.length; i++) {
            var entry = entries[i];
            var el = entry.target;
            if (!el.contains) continue;
            var vid = el.querySelector ? el.querySelector('video.cctv-img') : null;
            var img = el.querySelector ? el.querySelector('img.cctv-img') : null;
            var card = el.closest ? el.closest('.cctv-card') : null;
            if (!vid && !img) continue;
            if (entry.isIntersecting) {
                if (card) card.setAttribute('data-visible', '1');
                if (vid) {
                    var hls = this.state.hlsInstances[vid.id];
                    if (hls && vid.paused) {
                        try { vid.play().catch(function() {}); } catch(e) {}
                    } else if (vid.getAttribute('data-hls') && !hls) {
                        this._playHls(vid, card);
                    }
                }
                // Para imágenes: si aún no trajo un frame válido, refrescar ahora
                if (img && img.getAttribute('data-loaded') !== '1') {
                    var base = img.getAttribute('data-base-src') || img.src;
                    img.setAttribute('data-loaded', '1');
                    img.src = base + (base.indexOf('?') !== -1 ? '&' : '?') + '_t=' + Date.now();
                }
            } else {
                if (card) card.removeAttribute('data-visible');
                if (vid) {
                    var hlsOff = this.state.hlsInstances[vid.id];
                    if (hlsOff) {
                        try { vid.pause(); } catch(e) {}
                    }
                }
            }
        }
        this._enforceHlsCap();
    },

    _enforceHlsCap: function() {
        var max = 6;
        var playing = [];
        for (var id in this.state.hlsInstances) {
            var v = document.getElementById(id);
            if (v && !v.paused) playing.push({ id: id, vid: v });
        }
        if (playing.length <= max) return;
        playing.sort(function(a, b) {
            var va = a.vid.closest('.cctv-card');
            var vb = b.vid.closest('.cctv-card');
            return ((vb && va && ia(vb)) - (va && ia(va)));
        });
        function ia(c){ return (c && c.closest('body')) ? 1 : 0; }
        var extra = playing.slice(max);
        for (var i = 0; i < extra.length; i++) {
            try { extra[i].vid.pause(); } catch(e) {}
        }
    },

    _playHls: function(vid, card) {
        var self = this;
        var url = vid.getAttribute('data-hls');
        if (!url) return;
        if (window.Hls && Hls.isSupported()) {
            try {
                var hls = new Hls({ enableWorker: true, lowLatencyMode: true, backBufferLength: 20, maxBufferLength: 15 });
                hls.loadSource(url);
                hls.attachMedia(vid);
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    self._setPhVisible(vid, false);
                    vid.play().catch(function() {});
                    self._setDot(vid, '#00FFAA');
                });
                hls.on(Hls.Events.ERROR, function(e, data) {
                    if (!data.fatal) return;
                    if (data.type === Hls.ErrorTypes.NETWORK_ERROR) { hls.startLoad(); }
                    else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) { hls.recoverMediaError(); }
                    else { try { hls.destroy(); } catch(ex) {} delete self.state.hlsInstances[vid.id]; self._setDot(vid, '#FF9500'); }
                });
                self.state.hlsInstances[vid.id] = hls;
            } catch(e) {
                self._setDot(vid, '#FF9500');
            }
        } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
            vid.src = url;
            vid.addEventListener('loadedmetadata', function() {
                self._setPhVisible(vid, false);
                vid.play().catch(function() {});
                self._setDot(vid, '#00FFAA');
            });
        } else {
            self._setPhVisible(vid, true);
            self._setDot(vid, '#FF9500');
        }
    },

    _setPhVisible: function(vid, show) {
        var wrapper = vid.closest('.cctv-preview');
        if (!wrapper) return;
        var ph = wrapper.querySelector('.cctv-ph');
        if (ph) ph.style.display = show ? 'flex' : 'none';
        vid.style.display = show ? 'none' : 'block';
    },

    _setDot: function(vid, color) {
        var wrapper = vid.closest('.cctv-preview');
        if (!wrapper) return;
        var dot = wrapper.querySelector('.cctv-dot');
        if (dot) {
            dot.style.background = color;
            dot.style.boxShadow = '0 0 8px ' + color;
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
            var imgs = document.querySelectorAll('img.cctv-img');
            var now = Date.now();
            for (var i = 0; i < imgs.length; i++) {
                var img = imgs[i];
                var card = img.closest('.cctv-card');
                // Solo refrescar feeds visibles en viewport (evita tráfico innecesario)
                if (card && card.getAttribute('data-visible') !== '1') continue;
                if (img.getAttribute('data-loading') === '1') continue;
                var baseSrc = img.getAttribute('data-base-src') || img.src;
                if (!img.getAttribute('data-base-src')) {
                    img.setAttribute('data-base-src', baseSrc);
                }
                var cleanUrl = baseSrc.replace(/([?&])_t=\d+/, '');
                var sep = cleanUrl.indexOf('?') !== -1 ? '&' : '?';
                img.setAttribute('data-loading', '1');
                img.onload = (function(el) { return function() { el.removeAttribute('data-loading'); }; })(img);
                img.onerror = (function(el) { return function() { el.removeAttribute('data-loading'); }; })(img);
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
                var grid = document.getElementById('osiris-cctv-grid');
                if (grid && !self.state.cameras.length) {
                    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:#FF4444;font-family:monospace;font-size:11px;">⚠️ ERROR AL CARGAR RED CCTV — '+self._esc(String(err))+'</div>';
                }
            });
    },

    loadHealth: function() {
        var self = this;
        if (!this.state.active) return;
        fetch('/api/osiris/cctv/health?check=auto&limit=120')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var map = {};
                var on = 0;
                var online = data.online_cameras || [];
                var offline = data.offline_cameras || [];
                for (var i = 0; i < online.length; i++) {
                    map[online[i].id] = { online: true, http: online[i].http_status };
                    on++;
                }
                for (var j = 0; j < offline.length; j++) {
                    map[offline[j].id] = { online: false, reason: offline[j].reason || 'offline' };
                }
                self.state.healthMap = map;
                self.state.healthOnline = on;
                self.state.healthTotal = data.checked || (online.length + offline.length);
                self.state.healthLastCheck = data.timestamp;
                self._renderHealthStatus();
                self._applyHealthDots();
            })
            .catch(function(err) {
                console.warn('[OSIRIS] Health load failed:', err);
            });
    },

    _renderHealthStatus: function() {
        var countEl = document.getElementById('osiris-cctv-count');
        if (!countEl) return;
        var online = this.state.healthOnline;
        var total = this.state.healthTotal;
        var text = this.state.cctvTotal + ' CÁMARAS';
        if (this.state.cctvFilter !== 'all') {
            text += ' [' + this.state.cctvFilter + ']';
        }
        if (this.state.healthLastCheck) {
            text += ' · <span style="color:#00FFAA;">' + online + ' online</span>/' + total + '';
        }
        countEl.innerHTML = text;
        this._updateStatsStrip();
    },

    _updateStatsStrip: function() {
        var onlineEl = document.getElementById('osiris-stats-online');
        var offlineEl = document.getElementById('osiris-stats-offline');
        var checkingEl = document.getElementById('osiris-stats-checking');
        if (!onlineEl) return;
        var online = 0, offline = 0, check = 0;
        var cards = document.querySelectorAll('.cctv-card');
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i];
            var camData = card.getAttribute('data-cam');
            if (!camData) continue;
            var cam;
            try { cam = JSON.parse(camData.replace(/&quot;/g, '"').replace(/&#39;/g, "'")); } catch(e) { continue; }
            var h = this.state.healthMap[cam.id];
            if (h && h.online) online++;
            else if (h && !h.online) offline++;
            else check++;
        }
        onlineEl.textContent = online;
        offlineEl.textContent = offline;
        checkingEl.textContent = check;
    },

    _applyHealthDots: function() {
        var self = this;
        var cards = document.querySelectorAll('.cctv-card');
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i];
            var camData = card.getAttribute('data-cam');
            if (!camData) continue;
            var dot = card.querySelector('.cctv-dot');
            var cam;
            try { cam = JSON.parse(camData.replace(/&quot;/g, '"').replace(/&#39;/g, "'")); } catch(e) { continue; }
            var h = self.state.healthMap[cam.id];
            if (!h) continue;
            if (dot) {
                if (h.online) {
                    dot.style.background = '#00FFAA';
                    dot.style.boxShadow = '0 0 8px #00FFAA';
                } else {
                    dot.style.background = '#FF4444';
                    dot.style.boxShadow = '0 0 8px #FF4444';
                }
            }
            var img = card.querySelector('.cctv-img');
            if (img && !h.online && !img.getAttribute('data-offline-badge')) {
                img.setAttribute('data-offline-badge', '1');
            }
        }
    },

    _updateCCTVStats: function() {
        var cams = this.state.cameras || [];
        var valid = 0, sources = {}, countries = {};
        for (var i = 0; i < cams.length; i++) {
            var c = cams[i];
            if (c.feed_url) valid++;
            var src = c.source || 'unknown';
            sources[src] = (sources[src] || 0) + 1;
            var ct = c.country || 'Unknown';
            countries[ct] = (countries[ct] || 0) + 1;
        }
        this.state.cctvTotal = cams.length;
        this.state.cctvValid = valid;
        this.state.cctvSources = sources;
        this.state.countryStats = countries;

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

        this._renderCountryStats();
    },

    _renderCountryStats: function() {
        var countries = this.state.countryStats || {};
        var el = document.getElementById('osiris-stats-sources');
        if (!el) return;
        var entries = Object.keys(countries).sort(function(a, b) { return countries[b] - countries[a]; }).slice(0, 6);
        var html = '';
        for (var i = 0; i < entries.length; i++) {
            html += '<span style="margin-right:6px;">📍 ' + this._esc(entries[i]) + ': <b style="color:#00E5FF;">' + countries[entries[i]] + '</b></span>';
        }
        el.innerHTML = html;
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
        var result = cams.filter(function(c) {
            var matchSource = filter === 'all' || (c.source || '') === filter;
            if (!matchSource) return false;
            if (!query) return true;
            var name = (c.name || '').toLowerCase();
            var city = (c.city || '').toLowerCase();
            var country = (c.country || '').toLowerCase();
            var src = (c.source || '').toLowerCase();
            return name.indexOf(query) !== -1 || city.indexOf(query) !== -1 || country.indexOf(query) !== -1 || src.indexOf(query) !== -1;
        });
        return this._sortCameras(result);
    },

    _sortCameras: function(cams) {
        var self = this;
        var mode = this.state.sortMode || 'online';
        var sorted = cams.slice();
        switch (mode) {
            case 'name':
                sorted.sort(function(a, b) { return String(a.name || '').localeCompare(String(b.name || '')); });
                break;
            case 'country':
                sorted.sort(function(a, b) {
                    var c = String(a.country || '').localeCompare(String(b.country || ''));
                    return c !== 0 ? c : String(a.city || '').localeCompare(String(b.city || ''));
                });
                break;
            case 'source':
                sorted.sort(function(a, b) { return String(a.source || '').localeCompare(String(b.source || '')); });
                break;
            case 'online':
            default:
                sorted.sort(function(a, b) {
                    var ha = self.state.healthMap[a.id];
                    var hb = self.state.healthMap[b.id];
                    var oa = ha && ha.online ? 1 : 0;
                    var ob = hb && hb.online ? 1 : 0;
                    return ob - oa;
                });
                break;
        }
        return sorted;
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
            img.onerror = function() {
                var base = this.getAttribute('data-base-src') || this.src;
                if (base && base.indexOf('_r=') === -1) {
                    this.src = base + (base.indexOf('?') !== -1 ? '&' : '?') + '_r=' + Date.now();
                }
            };
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

        if (!append) {
            this._teardownGridMedia();
        }

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
        if (countEl) {
            countEl.textContent = statusText;
            this._renderHealthStatus();
        }

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
            var isHls = this._isHlsStream(cam.feed_url);

            var mediaHtml;
            if (isHls) {
                mediaHtml = '<video id="' + camId + '-vid" class="cctv-img" data-hls="' + this._esc(cam.feed_url) + '" muted playsinline preload="none" style="display:none;width:100%;height:100%;object-fit:cover;"><track kind="captions" srclang="es" label="Español" src="data:text/vtt;charset=utf-8,WEBVTT"></video>';
            } else {
                mediaHtml = '<img id="' + camId + '-img" class="cctv-img" data-base-src="' + proxyUrl + '" src="' + proxyUrl + '" />';
            }

            html += '<div class="cctv-card" data-cam=\'' + camData + '\'>' +
                '<div class="cctv-preview" id="' + camId + '-wrapper">' +
                '<div class="cctv-ph" id="' + camId + '-ph">⟳</div>' +
                mediaHtml +
                '<div class="cctv-badge-src">' + this._esc(cam.source || '') + ' ' + (isHls ? '<span style="color:#00E5FF;">▶HLS</span>' : '') + '</div>' +
                '<div class="cctv-dot" id="' + camId + '-dot"></div>' +
                (isHls ? '' : '<div class="cctv-ai-chip idle" id="' + camId + '-ai" title="Análisis de visión por computadora">🧠 IDLE</div>') +
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
                    var vid = document.getElementById(id + '-vid');
                    var ph = document.getElementById(id + '-ph');
                    var dot = document.getElementById(id + '-dot');

                    var isHlsCam = window.OsirisGlobal && window.OsirisGlobal._isHlsStream(camObj.feed_url);

                    if (vid || img) {
                        // Lazy playback/refresh via IntersectionObserver para vídeo e imagen
                        if (window.OsirisGlobal && window.OsirisGlobal.state.observer && window.IntersectionObserver) {
                            window.OsirisGlobal.state.observer.observe(card);
                        } else if (vid) {
                            // Fallback: play de inmediato si sin observer (navegadores antiguos)
                            window.OsirisGlobal._playHls(vid, card);
                        }
                    }

                    if (img) {
                        img.onload = function() {
                            try { this.setAttribute('data-loaded', '1'); } catch(e) {}
                            try { ph.style.display = 'none'; } catch(e) {}
                            try { img.style.display = 'block'; } catch(e) {}
                            try { if (dot) { dot.style.background = '#00FFAA'; dot.style.boxShadow = '0 0 8px #00FFAA'; } } catch(e) {}
                        };
                        img.onerror = function() {
                            try { this.setAttribute('data-loaded', '1'); } catch(e) {}
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
                        var aiChip = document.getElementById(id + '-ai');
                        if (aiChip) {
                            aiChip.onclick = function(e) {
                                e.stopPropagation();
                                if (window.OsirisGlobal) window.OsirisGlobal.analyzeCCTV(camObj);
                            };
                        }
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

        this._applyHealthDots();
    },

    _renderCCTVInfo: function() {
        var panel = document.getElementById('cctv-info-panel');
        if (!panel) return;
        var cam = this.state.cctvSelected;
        if (!cam) {
            panel.innerHTML = '<div style="text-align:center;padding:20px;color:#64748B;font-size:9px;font-family:monospace;">SELECT A CAMERA</div>';
            return;
        }
        var h = this.state.healthMap[cam.id];
        var healthHtml = '';
        if (h) {
            if (h.online) {
                healthHtml = '<div class="cctv-meta-row"><span class="cctv-meta-label">Estado</span><span style="color:#00FFAA;">● EN LÍNEA' + (h.http ? ' (HTTP ' + h.http + ')' : '') + '</span></div>';
            } else {
                healthHtml = '<div class="cctv-meta-row"><span class="cctv-meta-label">Estado</span><span style="color:#FF4444;">● FUERA DE LÍNEA' + (h.reason ? ' — ' + this._esc(h.reason) : '') + '</span></div>';
            }
        } else {
            healthHtml = '<div class="cctv-meta-row"><span class="cctv-meta-label">Estado</span><span style="color:#64748B;">POR VERIFICAR</span></div>';
        }
        panel.innerHTML =
            '<div style="color:#00E5FF;font-weight:bold;font-size:10px;margin-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:6px;">📹 ' + this._esc(cam.name || 'Unknown') + '</div>' +
            healthHtml +
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
            '<button onclick="if(window.OsirisGlobal)window.OsirisGlobal.analyzeCCTV(window.OsirisGlobal.state.cctvSelected)" style="flex:1;min-width:65px;background:rgba(255,45,85,0.12);border:1px solid rgba(255,45,85,0.3);border-radius:4px;color:#FF2D55;padding:5px 2px;font-size:8px;font-family:monospace;cursor:pointer;">🧠 VISIÓN AI</button>' +
            '<button onclick="if(window.OsirisGlobal&&window.OsirisGlobal.state.cctvSelected){var c=window.OsirisGlobal.state.cctvSelected;if(window.switchTab)window.switchTab(\'tab-map\');setTimeout(function(){if(window.UnifiedMap&&window.UnifiedMap.focusLocation)window.UnifiedMap.focusLocation(c.lat,c.lng,c.name);},150);}" style="flex:1;min-width:65px;background:rgba(0,255,170,0.08);border:1px solid rgba(0,255,170,0.2);border-radius:4px;color:#00FFAA;padding:5px 2px;font-size:8px;font-family:monospace;cursor:pointer;">📍 MAPA</button>' +
            '</div>' +
            '<div id="cctv-ai-panel" style="margin-top:6px;display:none;padding:6px;background:rgba(255,45,85,0.05);border:1px dashed rgba(255,45,85,0.3);border-radius:4px;font-size:8px;"></div>';
    },

    analyzeCCTV: function(cam) {
        if (!cam) return;
        var panel = document.getElementById('cctv-ai-panel');
        var self = this;
        if (panel) {
            panel.style.display = 'block';
            panel.innerHTML = '<span style="color:#FF2D55;">⚡ EJECUTANDO VISIÓN POR COMPUTADORA (OpenCV HOG+MOG2)...</span>';
        }

        fetch('/api/osiris/cctv/analyze?camera_id=' + encodeURIComponent(cam.id || 'cam') + '&url=' + encodeURIComponent(cam.feed_url || ''))
            .then(function(r) { return r.json(); })
            .then(function(res) {
                var objs = res.objects_detected || {};
                var statusColor = res.anomaly_detected ? '#FF2D55' : '#00FFAA';
                var motion = typeof res.motion_score === 'number' ? res.motion_score.toFixed(1) : '?';
                var model = res.model || 'COBALTO-VISION';
                var conf = '?%';
                try { conf = Math.round((res.confidence || 0) * 100) + '%'; } catch(e) {}
                if (panel) {
                    panel.innerHTML =
                        '<div style="color:#FF2D55;font-weight:bold;margin-bottom:4px;">🧠 VISIÓN COMPUTADORA (' + conf + ' CONF)</div>' +
                        '<div>🚗 Vehículos: <b>' + (objs.vehicles || 0) + '</b> · 🚶 Peatones: <b>' + (objs.pedestrians || 0) + '</b> · 🚲 Bicis: <b>' + (objs.bicycles || 0) + '</b></div>' +
                        '<div>📊 Movimiento: <b style="color:#00E5FF;">' + motion + '%</b></div>' +
                        '<div>Tráfico: <b style="color:' + statusColor + ';">' + (res.traffic_density || 'NORMAL') + '</b> · Estado: <b style="color:' + statusColor + ';">' + (res.tactical_status || 'NORMAL') + '</b></div>' +
                        '<div style="margin-top:4px;color:#64748B;font-size:7px;">Modelo: ' + this._esc(model) + '</div>';
                }
                self._updateAiChip(cam, res);
            }.bind(this))
            .catch(function() {
                if (panel) panel.innerHTML = '<span style="color:#FF4444;">❌ Error en servidor de analítica</span>';
            });
    },

    _updateAiChip: function(cam, res) {
        // Actualiza el chip 🧠 de la tarjeta correspondiente en la grid (si existe)
        var cards = document.querySelectorAll('.cctv-card');
        var label = '🧠 IDLE';
        var color = '#64748B';
        var border = 'rgba(255,255,255,0.1)';
        if (res && res.error) {
            label = '🧠 N/D';
        } else if (res) {
            var motion = typeof res.motion_score === 'number' ? Math.round(res.motion_score) : 0;
            label = '🧠 ' + motion + '%';
            if (res.anomaly_detected) { color = '#FF2D55'; border = 'rgba(255,45,85,0.5)'; }
            else if (motion > 20) { color = '#FF9500'; border = 'rgba(255,149,0,0.5)'; }
            else if (motion > 5) { color = '#00E5FF'; border = 'rgba(0,229,255,0.4)'; }
            else { color = '#00FFAA'; border = 'rgba(0,255,170,0.4)'; }
        }
        for (var i = 0; i < cards.length; i++) {
            var c = cards[i];
            var camData = c.getAttribute('data-cam');
            if (!camData) continue;
            try {
                var parsed = JSON.parse(camData.replace(/&quot;/g, '"').replace(/&#39;/g, "'"));
                if (parsed && parsed.id === cam.id) {
                    var chip = c.querySelector('.cctv-ai-chip');
                    if (chip) {
                        chip.innerHTML = label;
                        chip.style.color = color;
                        chip.style.borderColor = border;
                        chip.classList.remove('idle');
                    }
                    break;
                }
            } catch(e) {}
        }
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
