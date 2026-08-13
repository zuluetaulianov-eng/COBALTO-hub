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
    },

    init: function() {
        var self = this;
        this.state.active = true;

        var filter = document.getElementById('osiris-cctv-filter');
        if (filter) {
            filter.addEventListener('change', function() { self.setCCTVFilter(this.value); });
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
    },

    destroy: function() {
        this.state.active = false;
        this.state.pollTimers.forEach(function(t) { clearInterval(t); });
        this.state.pollTimers = [];
    },

    // ── CCTV Layout ──────────────────────────────────────────

    setCCTVCols: function(n) {
        this.state.cctvCols = n;
        this.state.cctvPage = 0;
        this._renderCCTV();
        // Update toggle button styles
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
        if (filter === 'all') return cams;
        return cams.filter(function(c) { return (c.source || '') === filter; });
    },

    selectCamera: function(cam) {
        this.state.cctvSelected = cam;
        this._renderCCTVInfo();
    },

    expandCamera: function(cam) {
        var modal = document.getElementById('cctv-modal');
        var img = document.getElementById('cctv-modal-img');
        var name = document.getElementById('cctv-modal-name');
        var meta = document.getElementById('cctv-modal-meta');
        if (!modal || !img) return;

        name.textContent = cam.name || 'Unknown';
        var proxyUrl = '/api/osiris/cctv/image?url=' + encodeURIComponent(cam.feed_url || '');
        img.src = proxyUrl;
        meta.innerHTML =
            '<div><span style="color:#64748B;">Source:</span> ' + this._esc(cam.source || '') + '</div>' +
            '<div><span style="color:#64748B;">Location:</span> ' + this._esc(cam.city || '') + (cam.country ? ', ' + this._esc(cam.country) : '') + '</div>' +
            '<div><span style="color:#64748B;">Lat:</span> ' + (cam.lat || 0) + '</div>' +
            '<div><span style="color:#64748B;">Lng:</span> ' + (cam.lng || 0) + '</div>' +
            (cam.feed_url ? '<div style="margin-top:4px;font-size:8px;color:#555;">' + this._esc(cam.feed_url) + '</div>' : '');
        modal.style.display = 'flex';
    },

    closeModal: function() {
        var modal = document.getElementById('cctv-modal');
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
                '<img id="' + camId + '-img" class="cctv-img" src="' + proxyUrl + '" />' +
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

        // Attach image handlers + click/dblclick
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
                        try { if (dot) { dot.style.background = '#00FFAA'; dot.style.boxShadow = '0 0 8px #00FFAA'; } } catch(e) {}
                    };
                    img.onerror = function() {
                        try { ph.innerHTML = '📹'; ph.style.color = '#FF4444'; ph.style.fontSize = '16px'; } catch(e) {}
                        try { this.style.display = 'none'; } catch(e) {}
                        try { if (dot) { dot.style.background = '#FF4444'; dot.style.boxShadow = '0 0 8px #FF4444'; } } catch(e) {}
                    };
                    if (img.complete) {
                        if (img.naturalHeight > 1) {
                            try { ph.style.display = 'none'; } catch(e) {}
                            try { if (dot) { dot.style.background = '#00FFAA'; dot.style.boxShadow = '0 0 8px #00FFAA'; } } catch(e) {}
                        } else {
                            try { ph.innerHTML = '📹'; ph.style.color = '#FF4444'; ph.style.fontSize = '16px'; } catch(e) {}
                            try { if (dot) { dot.style.background = '#FF4444'; dot.style.boxShadow = '0 0 8px #FF4444'; } } catch(e) {}
                        }
                    }

                    // Click → select (show metadata)
                    if (card) {
                        card.onclick = function(e) {
                            e.stopPropagation();
                            if (window.OsirisGlobal) window.OsirisGlobal.selectCamera(camObj);
                            // Highlight selected card
                            var all = document.querySelectorAll('.cctv-card');
                            for (var ci = 0; ci < all.length; ci++) { all[ci].style.borderColor = 'rgba(255,255,255,0.05)'; }
                            var parent = card.closest('.cctv-card');
                            if (parent) parent.style.borderColor = '#00E5FF';
                        };
                        // Double-click → expand
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
            '<div style="margin-top:8px;"><button onclick="if(window.OsirisGlobal)window.OsirisGlobal.expandCamera(window.OsirisGlobal.state.cctvSelected)" style="width:100%;background:rgba(0,229,255,0.08);border:1px solid rgba(0,229,255,0.2);border-radius:4px;color:#00E5FF;padding:4px;font-size:8px;font-family:monospace;cursor:pointer;">🔍 EXPAND VIEW</button></div>';
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
