/**
 * osiris-recon.js — OSIRIS RECON Engine v2.0 for COBALTO HUB
 * Redesigned with modular layout, groups, and enhanced UX
 */
window.OsirisRecon = {
    state: {
        activeTab: 'dns',
        query: '',
        results: null,
        loading: false,
        error: '',
        history: [],
        queryTime: 0,
        scanType: 'quick',
        sweepCidr: 24,
    },

    GROUPS: [
        {
            id: 'domain',
            label: 'Domain Intelligence',
            tabs: [
                { id: 'dns', label: 'DNS Records', icon: '🌐', placeholder: 'example.com', color: '#448AFF', hint: 'Domain name' },
                { id: 'whois', label: 'WHOIS / RDAP', icon: '📄', placeholder: 'example.com', color: '#FFD700', hint: 'Domain name' },
                { id: 'ssl', label: 'SSL Certificates', icon: '🔒', placeholder: 'example.com', color: '#76FF03', hint: 'Domain name' },
                { id: 'certs', label: 'Cert Transparency', icon: '🔐', placeholder: 'example.com', color: '#E040FB', hint: 'Domain name' },
                { id: 'web', label: 'Web Reader (Jina)', icon: '📖', placeholder: 'https://example.com', color: '#00FFAA', hint: 'Full URL or Domain' },
                { id: 'youtube', label: 'YouTube Intel', icon: '📺', placeholder: 'https://youtube.com/watch?v=...', color: '#FF0000', hint: 'YouTube Video URL or ID' },
            ]
        },
        {
            id: 'network',
            label: 'Network Recon',
            tabs: [
                { id: 'ip', label: 'IP Intelligence', icon: '📍', placeholder: '1.1.1.1', color: '#00E5FF', hint: 'IPv4 or IPv6' },
                { id: 'bgp', label: 'BGP Routing', icon: '🌍', placeholder: '1.1.1.1 or AS13335', color: '#00E5FF', hint: 'IP or ASN' },
                { id: 'headers', label: 'HTTP Headers', icon: '📋', placeholder: 'https://example.com', color: '#87CEEB', hint: 'Full URL' },
                { id: 'mac', label: 'MAC Vendor', icon: '🖐️', placeholder: '00:00:00:00:00:00', color: '#FFD700', hint: 'MAC address' },
                { id: 'rss', label: 'RSS Reader', icon: '📡', placeholder: 'https://example.com/feed.xml', color: '#FF9500', hint: 'RSS/Atom Feed URL' },
            ]
        },
        {
            id: 'threat',
            label: 'Threat & Vuln',
            tabs: [
                { id: 'shodan', label: 'Shodan InternetDB', icon: '🔌', placeholder: '1.1.1.1', color: '#FF3D3D', hint: 'IP address' },
                { id: 'cve', label: 'CVE Lookup', icon: '🐛', placeholder: 'CVE-2021-44228', color: '#FF3D3D', hint: 'CVE ID' },
                { id: 'threats', label: 'Threat Pulses', icon: '⚠️', placeholder: '8.8.8.8 or example.com', color: '#FF9500', hint: 'IP or domain' },
                { id: 'sweep', label: 'IP Sweep', icon: '🎯', placeholder: '192.168.1.0', color: '#FF3D3D', hint: 'Network base IP' },
            ]
        },
        {
            id: 'identity',
            label: 'Identity & Intel',
            tabs: [
                { id: 'ivss', label: 'IVSS Institucional', icon: '🏛️', placeholder: 'opcional: V-12345678', color: '#00E5FF', hint: 'OSINT institucional público (comunicados, pensiones, salud)' },
                { id: 'seniat', label: 'SENIAT Institucional', icon: '📜', placeholder: 'opcional: J-30000000-1', color: '#FFD700', hint: 'OSINT institucional (comunicados, Unidad Tributaria, RIF)' },
                { id: 'saime', label: 'SAIME Institucional', icon: '🛂', placeholder: 'opcional: V-12345678', color: '#FF4081', hint: 'OSINT institucional público (comunicados, movilidad fronteriza, servicios)' },
                { id: 'cne', label: 'CNE OSINT / Votación', icon: '🗳️', placeholder: 'opcional: V-12345678', color: '#76FF03', hint: 'OSINT institucional o consulta de Centro de Votación por Cédula (Wayback Machine fallback)' },
                { id: 'github', label: 'GitHub Recon', icon: '💻', placeholder: 'torvalds', color: '#87CEEB', hint: 'Username' },
                { id: 'leaks', label: 'Breach Check', icon: '💀', placeholder: 'target@example.com', color: '#E040FB', hint: 'Email address' },
                { id: 'phone', label: 'Phone Carrier', icon: '📞', placeholder: '+1234567890', color: '#FF9500', hint: 'Intl format format' },
                { id: 'sanctions', label: 'OFAC Sanctions', icon: '⚖️', placeholder: 'Putin', color: '#D4AF37', hint: 'Entity name' },
                { id: 'search', label: 'Semantic Search', icon: '🔍', placeholder: 'cybersecurity threat actor colombia', color: '#00FFAA', hint: 'Search query' },
            ]
        }
    ],

    _getAllTabs: function() {
        var tabs = [];
        this.GROUPS.forEach(function(g) { tabs = tabs.concat(g.tabs); });
        return tabs;
    },

    _esc: function(s) {
        if (s === null || s === undefined) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    _copy: function(text) {
        return ' <button class="or-copy-btn" title="Copy" onclick="navigator.clipboard.writeText(\'' + this._esc(text).replace(/'/g, "\\'") + '\')">📋</button>';
    },

    init: function() {
        var self = this;
        var container = document.getElementById('tab-osiris-recon');
        if (!container || container.getAttribute('data-recon-init') === 'true') return;
        container.setAttribute('data-recon-init', 'true');

        try {
            var saved = localStorage.getItem('osiris_recon_history');
            if (saved) this.state.history = JSON.parse(saved);
        } catch(e) {}

        this._renderSidebar();
        this._renderSearchArea();
        this._renderHistory();

        // Event Delegation
        container.addEventListener('click', function(e) {
            var tabBtn = e.target.closest('.or-tool-btn');
            if (tabBtn) {
                self.switchTab(tabBtn.dataset.tab);
                return;
            }
            var searchBtn = e.target.closest('.or-search-btn');
            if (searchBtn) {
                self.runQuery();
                return;
            }
            var clearBtn = e.target.closest('.or-clear-btn');
            if (clearBtn) {
                self.clearResults();
                return;
            }
            var histBtn = e.target.closest('.or-hist-chip');
            if (histBtn) {
                self.state.query = histBtn.dataset.query;
                var input = document.getElementById('or-search-input');
                if (input) input.value = self.state.query;
                self.switchTab(histBtn.dataset.tab);
                self.runQuery();
                return;
            }
            var doctorBtn = e.target.closest('#or-run-doctor-btn');
            if (doctorBtn) {
                self._runDoctor();
                return;
            }
            var copyJsonBtn = e.target.closest('#or-export-json');
            if (copyJsonBtn && self.state.results) {
                navigator.clipboard.writeText(JSON.stringify(self.state.results, null, 2))
                    .then(function() {
                        var og = copyJsonBtn.innerHTML;
                        copyJsonBtn.innerHTML = 'COPIED!';
                        copyJsonBtn.style.color = '#00FFAA';
                        setTimeout(function() {
                            copyJsonBtn.innerHTML = og;
                            copyJsonBtn.style.color = '';
                        }, 2000);
                    });
            }
        });

        var input = document.getElementById('or-search-input');
        if (input) {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    self.state.query = input.value;
                    self.runQuery();
                }
            });
            input.addEventListener('input', function(e) {
                self.state.query = e.target.value;
            });
        }
    },

    _renderSidebar: function() {
        var sidebar = document.getElementById('or-sidebar');
        if (!sidebar) return;
        var html = '';
        var self = this;

        this.GROUPS.forEach(function(group) {
            html += '<div class="or-sidebar-group">';
            html += '<div class="or-sidebar-label">' + group.label + '</div>';
            group.tabs.forEach(function(tab) {
                var active = tab.id === self.state.activeTab ? ' active' : '';
                html += '<button class="or-tool-btn' + active + '" data-tab="' + tab.id + '">';
                html += '<span class="or-tool-icon">' + tab.icon + '</span>';
                html += '<span>' + tab.label + '</span>';
                html += '<span class="or-tool-color" style="background:' + tab.color + ';box-shadow:0 0 5px ' + tab.color + '"></span>';
                html += '</button>';
            });
            html += '</div>';
        });

        sidebar.innerHTML = html;
    },

    _renderSearchArea: function() {
        var area = document.getElementById('or-search-area');
        if (!area) return;
        var tab = this._getActiveTab();

        var html = '<div class="or-search-bar">';
        html += '<div class="or-input-wrap">';
        html += '<input id="or-search-input" class="or-search-input" type="text" placeholder="' + this._esc(tab.placeholder) + '" value="' + this._esc(this.state.query) + '" autocomplete="off" spellcheck="false" />';
        html += '<span id="or-input-hint" class="or-input-hint">' + tab.hint + '</span>';
        html += '</div>';
        html += '<button class="or-search-btn">EXECUTE_</button>';
        html += '<button class="or-clear-btn" title="Clear Results">✕</button>';
        html += '</div>';

        area.innerHTML = html;
    },

    _renderHistory: function() {
        var area = document.getElementById('or-history-area');
        if (!area) return;
        if (!this.state.history.length) {
            area.innerHTML = '';
            return;
        }

        var html = '<div class="or-history-bar">';
        var self = this;
        this.state.history.forEach(function(h) {
            var t = self._getAllTabs().find(function(tab) { return tab.id === h.tab; });
            if (!t) return;
            html += '<button class="or-hist-chip" data-tab="' + h.tab + '" data-query="' + self._esc(h.query) + '">';
            html += '<span style="color:' + t.color + '">' + t.icon + '</span> ' + self._esc(h.query);
            html += '</button>';
        });
        html += '</div>';
        area.innerHTML = html;
    },

    _getActiveTab: function() {
        var self = this;
        return this._getAllTabs().find(function(t) { return t.id === self.state.activeTab; }) || this.GROUPS[0].tabs[0];
    },

    switchTab: function(tabId) {
        this.state.activeTab = tabId;
        
        // Update sidebar UI
        document.querySelectorAll('.or-tool-btn').forEach(function(btn) {
            if (btn.dataset.tab === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Update search area placeholder
        var input = document.getElementById('or-search-input');
        var hint = document.getElementById('or-input-hint');
        var tab = this._getActiveTab();
        if (input) {
            input.placeholder = tab.placeholder;
            input.focus();
        }
        if (hint) {
            hint.innerHTML = tab.hint;
        }

        this.clearResults();
    },

    clearResults: function() {
        var resultsEl = document.getElementById('osiris-recon-container');
        if (resultsEl) {
            var tab = this._getActiveTab();
            resultsEl.innerHTML = '<div class="or-empty-state"><div class="or-empty-icon">' + tab.icon + '</div><div class="or-empty-title">AWAITING QUERY: ' + tab.label + '</div><div class="or-empty-hint">Enter a target ' + tab.hint.toLowerCase() + ' in the prompt above and execute to retrieve intelligence.</div></div>';
        }
        this.state.results = null;
        this.state.error = '';
        
        // Remove input value if clear button was clicked explicitly
        if (event && event.target && event.target.classList.contains('or-clear-btn')) {
            var input = document.getElementById('or-search-input');
            if (input) input.value = '';
            this.state.query = '';
        }
    },

    runQuery: function() {
        var self = this;
        var input = document.getElementById('or-search-input');
        if (input) this.state.query = input.value;
        
        var query = this.state.query.trim();
        if (!query) return;

        var tab = this._getActiveTab();
        
        if (tab.id === 'sweep') {
            this._runSweep(query);
            return;
        }
        if (tab.id === 'sanctions') {
            this._runSanctions(query);
            return;
        }

        this.state.loading = true;
        this._showLoading();

        var apiPath = this._getApiPath(tab.id, query);
        var startTime = performance.now();

        fetch(apiPath)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.queryTime = Math.round(performance.now() - startTime);
                self.state.loading = false;
                self.state.results = data;
                self._addHistory(tab.id, query);
                self._renderResults(data, tab.id, query);
            })
            .catch(function(err) {
                self.state.loading = false;
                self.state.error = 'Network error: ' + (err.message || 'Unknown');
                self._renderError(self.state.error);
            });
    },

    // Pivot helpers used by the Intel Graph 'Acciones de Inteligencia OSINT'.
    // Set the active tool and the query, then execute the lookup directly.
    switchSubTab: function(tabId) {
        this.switchTab(tabId);
    },

    runTool: function(tabId, query) {
        var self = this;
        this.switchTab(tabId);
        var input = document.getElementById('or-search-input');
        if (input) input.value = query;
        this.state.query = query;
        var tab = this._getActiveTab();
        if (!tab) return;
        if (query) {
            this.runQuery();
        } else if (tab.id === 'saime' || tab.id === 'ivss' || tab.id === 'seniat' || tab.id === 'cne') {
            // Institutional tabs allow an empty query -> blanket institutional fetch
            this.state.loading = true;
            this._showLoading();
            var apiPath = this._getApiPath(tab.id, '');
            var startTime = performance.now();
            fetch(apiPath)
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    self.state.queryTime = Math.round(performance.now() - startTime);
                    self.state.loading = false;
                    self.state.results = data;
                    self._renderResults(data, tab.id, tab.label.split(' ')[0]);
                })
                .catch(function(err) {
                    self.state.loading = false;
                    self.state.error = 'Network error: ' + (err.message || 'Unknown');
                    self._renderError(self.state.error);
                });
        }
    },

    _getApiPath: function(tabId, query) {
        var map = {
            'ivss': '/api/osiris/recon/ivss?cedula=' + encodeURIComponent(query) + '&scope=institucional',
            'seniat': '/api/osiris/recon/seniat/institucional?rif=' + encodeURIComponent(query) + '&scope=lleno',
            'saime': '/api/osiris/recon/saime?cedula=' + encodeURIComponent(query) + '&scope=institucional',
            'cne': query ? '/api/osiris/recon/cne?cedula=' + encodeURIComponent(query) : '/api/osiris/recon/cne?scope=institucional',
            'dns': '/api/osiris/recon/dns?domain=' + encodeURIComponent(query),
            'whois': '/api/osiris/recon/whois?domain=' + encodeURIComponent(query),
            'ip': '/api/osiris/recon/ip?ip=' + encodeURIComponent(query),
            'cve': '/api/osiris/recon/cve?cve=' + encodeURIComponent(query),
            'shodan': '/api/osiris/recon/shodan?ip=' + encodeURIComponent(query),
            'ssl': '/api/osiris/recon/ssl?domain=' + encodeURIComponent(query),
            'headers': '/api/osiris/recon/headers?url=' + encodeURIComponent(query),
            'bgp': '/api/osiris/recon/bgp?query=' + encodeURIComponent(query),
            'certs': '/api/osiris/recon/certs?domain=' + encodeURIComponent(query),
            'mac': '/api/osiris/recon/mac?mac=' + encodeURIComponent(query),
            'phone': '/api/osiris/recon/phone?number=' + encodeURIComponent(query),
            'github': '/api/osiris/recon/github?user=' + encodeURIComponent(query.replace('@', '')),
            'leaks': '/api/osiris/recon/leaks?email=' + encodeURIComponent(query),
            'threats': '/api/osiris/recon/threats?query=' + encodeURIComponent(query),
            'web': '/api/osiris/recon/web?url=' + encodeURIComponent(query),
            'search': '/api/osiris/recon/search?query=' + encodeURIComponent(query),
            'youtube': '/api/osiris/recon/youtube?url=' + encodeURIComponent(query),
            'rss': '/api/osiris/recon/rss?url=' + encodeURIComponent(query),
        };
        return map[tabId] || '';
    },

    _showLoading: function() {
        var resultsEl = document.getElementById('osiris-recon-container');
        if (resultsEl) {
            resultsEl.innerHTML = '<div class="or-loading"><div class="or-spinner"></div><div class="or-loading-text">ESTABLISHING CONNECTION...</div></div>';
        }
    },

    _renderError: function(msg) {
        var resultsEl = document.getElementById('osiris-recon-container');
        if (resultsEl) {
            resultsEl.innerHTML = '<div class="or-alert-box danger">⚠ ' + this._esc(msg) + '</div>';
        }
    },

    _renderResults: function(data, tabId, query) {
        var resultsEl = document.getElementById('osiris-recon-container');
        if (!resultsEl) return;

        if (!data || data.error) {
            this._renderError(data && data.error ? data.error : 'No data returned or target unavailable.');
            return;
        }

        var tab = this._getActiveTab();
        var esc = this._esc;
        var copy = this._copy.bind(this);
        
        var headerHtml = '<div class="or-result-header">';
        headerHtml += '<div class="or-result-title"><span style="color:' + tab.color + '">' + tab.icon + '</span> TARGET: <span style="color:#fff;font-weight:bold;">' + esc(query) + '</span></div>';
        headerHtml += '<div class="or-result-actions">';
        headerHtml += '<div class="or-timer">⏱️ ' + this.state.queryTime + 'ms</div>';
        headerHtml += '<button id="or-export-json" class="or-action-btn">{ } JSON</button>';
        headerHtml += '</div></div>';

        var contentHtml = '';

        // ── DNS ──
        if (tabId === 'dns') {
            if (data.summary) {
                contentHtml += '<div class="or-data-grid">';
                contentHtml += '<div class="or-data-card accent-left" style="border-left-color:#448AFF"><div class="or-data-label">IP Addresses</div><div class="or-data-value large">' + (data.summary.ip_addresses || []).length + '</div></div>';
                contentHtml += '<div class="or-data-card accent-left" style="border-left-color:#FFD700"><div class="or-data-label">Mail Servers</div><div class="or-data-value large">' + (data.summary.mail_servers || []).length + '</div></div>';
                contentHtml += '<div class="or-data-card accent-left" style="border-left-color:#76FF03"><div class="or-data-label">Nameservers</div><div class="or-data-value large">' + (data.summary.nameservers || []).length + '</div></div>';
                contentHtml += '</div>';
            }
            for (var rtype in data.records) {
                var records = data.records[rtype] || [];
                if (!records.length) continue;
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">' + rtype + ' RECORDS</div><div class="or-section-count">' + records.length + '</div></div>';
                records.forEach(function(r) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(r.data || '') + copy(r.data) + '</div><div class="or-record-meta">TTL: ' + (r.ttl || 0) + '</div></div>';
                });
                contentHtml += '</div>';
            }
        } 
        // ── IP ──
        else if (tabId === 'ip') {
            if (data.sanctions_match) {
                contentHtml += '<div class="or-alert-box danger">⚠ SANCTIONS MATCH: ' + esc(data.sanctions_match.source) + '</div>';
            }
            if (data.geo) {
                var g = data.geo;
                contentHtml += '<div class="or-data-grid">';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Country</div><div class="or-data-value">' + esc(g.country || '') + ' ' + esc(g.country_code || '') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">City / Region</div><div class="or-data-value">' + esc(g.city || '') + ', ' + esc(g.region || '') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">ISP / ORG</div><div class="or-data-value">' + esc(g.isp || g.org || '') + copy(g.isp || g.org) + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Coordinates</div><div class="or-data-value info">' + (g.lat || 0) + ', ' + (g.lon || 0) + '</div></div>';
                contentHtml += '</div>';
            }
            if (data.reputation) {
                var risk = data.reputation.risk_level || 'LOW';
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">REPUTATION</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Risk Level</div><div class="or-record-meta"><span class="or-data-value ' + (risk === 'HIGH' ? 'danger' : risk === 'MEDIUM' ? 'warning' : 'success') + '">' + risk + '</span></div></div>';
                contentHtml += '</div>';
            }
        } 
        // ── WHOIS ──
        else if (tabId === 'whois') {
            if (data.sanctions_match) {
                contentHtml += '<div class="or-alert-box danger">⚠ OFAC SDN MATCH ON REGISTRANT</div>';
            }
            if (data.rdap) {
                contentHtml += '<div class="or-data-grid">';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Registrant Name</div><div class="or-data-value">' + esc(data.rdap.name || 'REDACTED') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Registrar</div><div class="or-data-value">' + esc(data.rdap.registrar || 'Unknown') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Created</div><div class="or-data-value">' + esc(data.registration || 'N/A') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Expires</div><div class="or-data-value">' + esc(data.expiration || 'N/A') + '</div></div>';
                contentHtml += '</div>';
                if (data.rdap.nameservers && data.rdap.nameservers.length) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">NAMESERVERS</div></div>';
                    data.rdap.nameservers.forEach(function(ns) {
                        contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(ns) + copy(ns) + '</div></div>';
                    });
                    contentHtml += '</div>';
                }
            }
        } 
        // ── CVE ──
        else if (tabId === 'cve') {
            var sevClass = data.severity === 'CRITICAL' ? 'danger' : data.severity === 'HIGH' ? 'warning' : 'info';
            contentHtml += '<div class="or-data-grid" style="grid-template-columns: 1fr 1fr;">';
            contentHtml += '<div class="or-data-card accent-left" style="border-color: ' + (data.severity === 'CRITICAL' ? '#FF4444' : '#FF9500') + '"><div class="or-data-label">Severity</div><div class="or-data-value large ' + sevClass + '">' + (data.severity || 'UNKNOWN') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">CVSS Score</div><div class="or-data-value large">' + (data.cvss || 'N/A') + '</div></div>';
            contentHtml += '</div>';
            contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">DESCRIPTION</div></div>';
            contentHtml += '<div style="font-size:0.8rem;color:var(--text-muted);line-height:1.6;background:rgba(0,0,0,0.2);padding:14px;border-radius:8px;">' + esc(data.description || 'No description available.') + '</div></div>';
            if (data.references && data.references.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">REFERENCES</div><div class="or-section-count">' + data.references.length + '</div></div>';
                data.references.forEach(function(ref) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data"><a href="' + esc(ref) + '" target="_blank" style="color:#87CEEB;text-decoration:none;">' + esc(ref) + '</a></div></div>';
                });
                contentHtml += '</div>';
            }
        } 
        // ── SHODAN ──
        else if (tabId === 'shodan') {
            if (data.ports && data.ports.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">OPEN PORTS</div><div class="or-section-count">' + data.ports.length + '</div></div>';
                contentHtml += '<div>' + data.ports.map(function(p) { return '<span class="or-tag port">' + p + '</span>'; }).join(' ') + '</div></div>';
            }
            if (data.vulns && data.vulns.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title" style="color:#FF4444;">VULNERABILITIES</div><div class="or-section-count">' + data.vulns.length + '</div></div>';
                contentHtml += '<div>' + data.vulns.map(function(v) { return '<span class="or-tag vuln">' + esc(v) + '</span>'; }).join(' ') + '</div></div>';
            }
            if (data.hostnames && data.hostnames.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">HOSTNAMES</div><div class="or-section-count">' + data.hostnames.length + '</div></div>';
                contentHtml += '<div>' + data.hostnames.map(function(h) { return '<span class="or-tag hostname">' + esc(h) + '</span>'; }).join(' ') + '</div></div>';
            }
            if (!data.ports && !data.vulns && !data.hostnames) {
                contentHtml += '<div class="or-alert-box warning">Target not indexed by Shodan InternetDB.</div>';
            }
        } 
        // ── SSL ──
        else if (tabId === 'ssl') {
            if (data.valid) {
                contentHtml += '<div class="or-alert-box success">✓ Certificate is Valid</div>';
                contentHtml += '<div class="or-section"><div class="or-record-row"><div class="or-record-data">Subject</div><div class="or-record-meta" style="color:#fff">' + esc(data.subject || '') + '</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Issuer</div><div class="or-record-meta" style="color:#fff">' + esc(data.issuer || '') + '</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Valid Until</div><div class="or-record-meta ' + (data.expired ? 'or-data-value danger' : 'or-data-value success') + '">' + esc(data.not_after || '') + '</div></div></div>';
            } else {
                contentHtml += '<div class="or-alert-box danger">✕ ' + esc(data.error || 'Invalid Certificate') + '</div>';
            }
        } 
        // ── GITHUB ──
        else if (tabId === 'github') {
            contentHtml += '<div class="or-profile-header">';
            if (data.avatar_url) contentHtml += '<img src="' + esc(data.avatar_url) + '" class="or-avatar" />';
            contentHtml += '<div><div class="or-profile-name">' + esc(data.name || data.username || '') + '</div><div class="or-profile-handle">@' + esc(data.username || '') + '</div></div>';
            contentHtml += '</div>';

            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Public Repos</div><div class="or-data-value large">' + (data.public_repos || 0) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Followers</div><div class="or-data-value large">' + (data.followers || 0) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Joined</div><div class="or-data-value info">' + (data.created_at ? data.created_at.substring(0, 10) : '') + '</div></div>';
            contentHtml += '</div>';

            contentHtml += '<div class="or-section" style="background:rgba(0,0,0,0.2);padding:12px;border-radius:8px;">';
            if (data.location) contentHtml += '<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:6px;">📍 ' + esc(data.location) + '</div>';
            if (data.company) contentHtml += '<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:6px;">🏢 ' + esc(data.company) + '</div>';
            if (data.blog) contentHtml += '<div style="font-size:0.8rem;color:#448AFF;margin-bottom:6px;">🔗 <a href="' + esc(data.blog) + '" target="_blank" style="color:inherit;text-decoration:none;">' + esc(data.blog) + '</a></div>';
            contentHtml += '</div>';
        } 
        // ── LEAKS ──
        else if (tabId === 'leaks') {
            if (data.breached) {
                contentHtml += '<div class="or-alert-box danger" style="justify-content:center;font-size:1rem;font-weight:bold;">⚠ COMPROMISED</div>';
                if (data.breaches && data.breaches.length) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">SOURCES DETECTED</div><div class="or-section-count">' + data.breaches.length + '</div></div>';
                    data.breaches.forEach(function(b) { contentHtml += '<div class="or-record-row"><div class="or-record-data" style="color:#FF6666;">• ' + esc(b) + '</div></div>'; });
                    contentHtml += '</div>';
                }
                if (data.data_exposed && data.data_exposed.length) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">DATA EXPOSED</div></div>';
                    contentHtml += '<div>' + data.data_exposed.map(function(d) { return '<span class="or-tag data-type">' + esc(d) + '</span>'; }).join(' ') + '</div></div>';
                }
            } else {
                contentHtml += '<div class="or-alert-box success" style="justify-content:center;">✓ NO KNOWN BREACHES DETECTED</div>';
            }
        } 
        // ── CERTS (Cert Transparency) ──
        else if (tabId === 'certs') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Total Certificates</div><div class="or-data-value large">' + (data.total_certs || 0) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Unique Subdomains</div><div class="or-data-value large info">' + (data.unique_subdomains || 0) + '</div></div>';
            contentHtml += '</div>';
            if (data.subdomains && data.subdomains.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">DISCOVERED SUBDOMAINS</div><div class="or-section-count">' + data.subdomains.length + '</div></div>';
                contentHtml += '<div style="display:flex; flex-wrap:wrap; gap:6px;">' + data.subdomains.map(function(s) { return '<span class="or-tag hostname">' + esc(s) + copy(s) + '</span>'; }).join('') + '</div></div>';
            }
        }
        // ── BGP ──
        else if (tabId === 'bgp') {
            var asnObj = (data.asn || (data.ip && data.ip.asn)) || {};
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">ASN</div><div class="or-data-value large info">AS' + (asnObj.asn || 'N/A') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Organization</div><div class="or-data-value">' + esc(asnObj.name || asnObj.description || 'Unknown') + copy(asnObj.name || '') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Country</div><div class="or-data-value">' + esc(asnObj.country_code || 'N/A') + '</div></div>';
            contentHtml += '</div>';
            if (data.ip && data.ip.ptr_record) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">REVERSE DNS (PTR)</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(data.ip.ptr_record) + copy(data.ip.ptr_record) + '</div></div></div>';
            }
        }
        // ── HTTP HEADERS ──
        else if (tabId === 'headers') {
            var statusColor = data.status >= 200 && data.status < 300 ? '#76FF03' : data.status >= 300 && data.status < 400 ? '#FFD700' : '#FF4444';
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">HTTP Status</div><div class="or-data-value large" style="color:' + statusColor + '">' + (data.status || 'N/A') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Server Header</div><div class="or-data-value">' + esc(data.server || 'Undisclosed') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Content Type</div><div class="or-data-value">' + esc(data.content_type || 'N/A') + '</div></div>';
            contentHtml += '</div>';
            if (data.headers) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">RESPONSE HEADERS</div><div class="or-section-count">' + Object.keys(data.headers).length + '</div></div>';
                for (var hKey in data.headers) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data" style="color:var(--primary); font-family:\'Roboto Mono\',monospace;">' + esc(hKey) + '</div><div class="or-record-meta" style="color:#fff;">' + esc(data.headers[hKey]) + copy(data.headers[hKey]) + '</div></div>';
                }
                contentHtml += '</div>';
            }
        }
        // ── WEB READER (JINA) ──
        else if (tabId === 'web') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Source</div><div class="or-data-value info">' + esc(data.source || 'Jina Reader') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Content Length</div><div class="or-data-value large">' + (data.length || 0).toLocaleString() + ' chars</div></div>';
            contentHtml += '</div>';
            if (data.content) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">EXTRACTED MARKDOWN CONTENT</div>' + copy(data.content) + '</div>';
                contentHtml += '<pre style="font-size:0.8rem;color:#E0E0E0;max-height:600px;overflow-y:auto;background:rgba(0,0,0,0.4);padding:16px;border-radius:8px;border:1px solid rgba(0,229,255,0.2);white-space:pre-wrap;word-break:break-word;font-family:\'Roboto Mono\',monospace;">' + esc(data.content) + '</pre></div>';
            }
        }
        // ── SEMANTIC SEARCH ──
        else if (tabId === 'search') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Query</div><div class="or-data-value info">' + esc(data.query || query) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Source</div><div class="or-data-value success">' + esc(data.source || 'Jina Search') + '</div></div>';
            contentHtml += '</div>';
            if (data.content) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">SEARCH RESULTS MARKDOWN</div>' + copy(data.content) + '</div>';
                contentHtml += '<pre style="font-size:0.8rem;color:#E0E0E0;max-height:600px;overflow-y:auto;background:rgba(0,0,0,0.4);padding:16px;border-radius:8px;border:1px solid rgba(0,229,255,0.2);white-space:pre-wrap;word-break:break-word;font-family:\'Roboto Mono\',monospace;">' + esc(data.content) + '</pre></div>';
            }
        }
        // ── YOUTUBE INTEL ──
        else if (tabId === 'youtube') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Video Title</div><div class="or-data-value large" style="color:#FF4444;">' + esc(data.title || '') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Author / Channel</div><div class="or-data-value info">' + esc(data.author_name || 'Unknown') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Video ID</div><div class="or-data-value">' + esc(data.video_id || '') + copy(data.video_id) + '</div></div>';
            contentHtml += '</div>';
            if (data.thumbnail_url) {
                contentHtml += '<div class="or-section" style="text-align:center;"><img src="' + esc(data.thumbnail_url) + '" style="max-width:320px;border-radius:8px;border:1px solid rgba(255,0,0,0.4);" /></div>';
            }
            if (data.transcript) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">TRANSCRIPT / EXTRACTED CONTENT</div>' + copy(data.transcript) + '</div>';
                contentHtml += '<pre style="font-size:0.8rem;color:#E0E0E0;max-height:500px;overflow-y:auto;background:rgba(0,0,0,0.4);padding:16px;border-radius:8px;border:1px solid rgba(255,0,0,0.2);white-space:pre-wrap;word-break:break-word;font-family:\'Roboto Mono\',monospace;">' + esc(data.transcript) + '</pre></div>';
            }
        }
        // ── RSS READER ──
        else if (tabId === 'rss') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Feed URL</div><div class="or-data-value info">' + esc(data.url || query) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Articles Extracted</div><div class="or-data-value large success">' + (data.total_items || 0) + '</div></div>';
            contentHtml += '</div>';
            if (data.items && data.items.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">RECENT FEED ITEMS</div><div class="or-section-count">' + data.items.length + '</div></div>';
                data.items.forEach(function(item) {
                    contentHtml += '<div class="or-record-row" style="flex-direction:column; align-items:flex-start; gap:4px; margin-bottom:8px; padding:10px; background:rgba(0,0,0,0.2); border-radius:6px;">';
                    contentHtml += '<div style="color:#FF9500; font-weight:bold;"><a href="' + esc(item.link || '#') + '" target="_blank" style="color:inherit;text-decoration:none;">' + esc(item.title || 'Untitled') + '</a></div>';
                    if (item.published) contentHtml += '<div style="font-size:0.7rem; color:var(--text-muted);">' + esc(item.published) + '</div>';
                    if (item.description) contentHtml += '<div style="font-size:0.75rem; color:#aaa; margin-top:4px;">' + esc(item.description) + '</div>';
                    contentHtml += '</div>';
                });
                contentHtml += '</div>';
            }
        }
        // ── MAC VENDOR ──
        else if (tabId === 'mac') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">MAC Address</div><div class="or-data-value large info">' + esc(data.mac || query) + copy(data.mac || query) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Manufacturer / Vendor</div><div class="or-data-value large success">' + esc(data.vendor || 'Unknown') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">OUI Prefix</div><div class="or-data-value">' + esc(data.prefix || 'N/A') + '</div></div>';
            contentHtml += '</div>';
        }
        // ── IVSS INSTITUCIONAL ──
        else if (tabId === 'ivss') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card" style="grid-column: span 2;"><div class="or-data-label">Institución</div><div class="or-data-value large success">' + esc(data.institucion || 'IVSS — Venezuela') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Alcance</div><div class="or-data-value info">' + esc(data.alcance || 'OSINT institucional público') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Estatus</div><div class="or-data-value large ' + (data.status === 'CONSULTADO' ? 'success' : 'warning') + '">' + esc(data.status || 'N/A') + '</div></div>';
            contentHtml += '</div>';

            if (data.pensiones_y_pagos && data.pensiones_y_pagos.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">💵 PENSIONES Y PAGOS</div><div class="or-section-count">' + data.pensiones_y_pagos.length + '</div></div>';
                data.pensiones_y_pagos.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                });
                contentHtml += '</div>';
            }

            if (data.alertas_salud && data.alertas_salud.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🏥 ALERTAS DE SALUD</div><div class="or-section-count">' + data.alertas_salud.length + '</div></div>';
                data.alertas_salud.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data"> ' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                });
                contentHtml += '</div>';
            }

            if (data.tramites_y_servicios && data.tramites_y_servicios.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🧾 TRÁMITES Y SERVICIOS</div><div class="or-section-count">' + data.tramites_y_servicios.length + '</div></div>';
                data.tramites_y_servicios.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                });
                contentHtml += '</div>';
            }

            if (data.comunicados && data.comunicados.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📰 COMUNICADOS INSTITUCIONALES</div><div class="or-section-count">' + data.comunicados.length + '</div></div>';
                data.comunicados.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                });
                contentHtml += '</div>';
            } else {
                contentHtml += '<div class="or-alert-box info">ℹ️ Sin comunicados disponibles en este momento (portal inaccesible o sin novedades).</div>';
            }

            if (data.servicios_oficiales && data.servicios_oficiales.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🛠️ SERVICIOS OFICIALES</div></div>';
                data.servicios_oficiales.forEach(function(s) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data"><b>' + esc(s.nombre) + '</b> — ' + esc(s.descripcion) + '</div></div>';
                });
                contentHtml += '</div>';
            }

            contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">FUENTE</div></div>';
            contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(data.fuente || '🇻🇪 Portal Oficial IVSS') + '</div><div class="or-record-meta">' + esc(data.timestamp || '') + '</div></div>';
            contentHtml += '<div class="or-alert-box info">ℹ️ Inteligencia a nivel institucional: el portal público IVSS no expone expedientes individuales; la información personal de los ciudadanos no se consulta ni se fabrica.</div></div>';
        }
        // ── SENIAT INSTITUCIONAL ──
        else if (tabId === 'seniat') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card" style="grid-column: span 2;"><div class="or-data-label">Institución</div><div class="or-data-value large success">' + esc(data.institucion || 'SENIAT — Venezuela') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Unidad Tributaria (UT)</div><div class="or-data-value large info">Bs. ' + esc(data.unidad_tributaria || '43.00') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Estatus</div><div class="or-data-value large ' + (data.status === 'CONSULTADO' ? 'success' : 'warning') + '">' + esc(data.status || 'N/A') + '</div></div>';
            contentHtml += '</div>';

            if (data.comunicados && data.comunicados.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📰 COMUNICADOS INSTITUCIONALES</div><div class="or-section-count">' + data.comunicados.length + '</div></div>';
                data.comunicados.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(c.title) + '</div><div class="or-record-meta">' + esc((c.category || c.categoria || '')) + '</div></div>';
                });
                contentHtml += '</div>';
            }

            if (data.historico_ut && data.historico_ut.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📈 HISTÓRICO UNIDAD TRIBUTARIA</div><div class="or-section-count">' + data.historico_ut.length + '</div></div>';
                data.historico_ut.forEach(function(p) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(p.providencia) + '</div><div class="or-record-meta">Bs. ' + esc(p.valor_anterior) + ' → Bs. ' + esc(p.valor_nuevo) + '</div></div>';
                });
                contentHtml += '</div>';
            }

            if (data.calendario && data.calendario.meses_disponibles) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📅 CALENDARIO DE OBLIGACIONES ' + esc(data.calendario.anio || '') + '</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Meses: ' + data.calendario.meses_disponibles.join(', ') + '</div></div>';
                contentHtml += '</div>';
            }

            var rifd = data.rif_consultado;
            if (rifd) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🧾 RIF CONSULTADO (REGISTRO PÚBLICO)</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">RIF: <b>' + esc(rifd.rif || '') + '</b> — ' + esc(rifd.razon_social || '') + '</div></div>';
                if (rifd.condicion_iva) contentHtml += '<div class="or-record-row"><div class="or-record-data">Condición IVA: ' + esc(rifd.condicion_iva) + '</div></div>';
                if (rifd.tasa_retencion) contentHtml += '<div class="or-record-row"><div class="or-record-data">Retención: ' + esc(rifd.tasa_retencion) + '</div></div>';
                contentHtml += '</div>';
            }

            if (data.servicios_oficiales && data.servicios_oficiales.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🛠️ SERVICIOS OFICIALES</div></div>';
                data.servicios_oficiales.forEach(function(s) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data"><b>' + esc(s.nombre) + '</b> — ' + esc(s.descripcion) + '</div></div>';
                });
                contentHtml += '</div>';
            }

            contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">FUENTE</div></div>';
            contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(data.fuente || '🇻🇪 Portal Oficial SENIAT en Línea') + '</div><div class="or-record-meta">' + esc(data.timestamp || '') + '</div></div>';
            contentHtml += '<div class="or-alert-box info">ℹ️ Inteligencia a nivel institucional: el SENIAT expone el registro tributario (RIF) públicamente; la información personal fuera del registro tributario no se consulta ni se expone.</div></div>';
        }
        // ── SAIME INSTITUCIONAL ──
        else if (tabId === 'saime') {
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card" style="grid-column: span 2;"><div class="or-data-label">Institución</div><div class="or-data-value large success">' + esc(data.institucion || 'SAIME — Venezuela') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Alcance</div><div class="or-data-value info">' + esc(data.alcance || 'OSINT institucional público') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Estatus</div><div class="or-data-value large ' + (data.status === 'CONSULTADO' ? 'success' : 'danger') + '">' + esc(data.status || 'N/A') + '</div></div>';
            contentHtml += '</div>';

            if (data.alertas_movilidad_fronteriza && data.alertas_movilidad_fronteriza.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🚨 ALERTAS DE MOVILIDAD FRONTERIZA</div><div class="or-section-count">' + data.alertas_movilidad_fronteriza.length + '</div></div>';
                data.alertas_movilidad_fronteriza.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">⚠️ ' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                });
                contentHtml += '</div>';
            } else {
                contentHtml += '<div class="or-alert-box info">√ No hay alertas de movilidad fronteriza publicadas en este momento.</div>';
            }

            if (data.comunicados && data.comunicados.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📰 COMUNICADOS Y NOTICIAS INSTITUCIONALES</div><div class="or-section-count">' + data.comunicados.length + '</div></div>';
                data.comunicados.forEach(function(c) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                });
                contentHtml += '</div>';
            }

            if (data.servicios_oficiales && data.servicios_oficiales.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🛠️ SERVICIOS OFICIALES</div></div>';
                data.servicios_oficiales.forEach(function(s) {
                    contentHtml += '<div class="or-record-row"><div class="or-record-data"><b>' + esc(s.nombre) + '</b> — ' + esc(s.descripcion) + '</div></div>';
                });
                contentHtml += '</div>';
            }

            contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">FUENTE</div></div>';
            contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(data.fuente || '🇻🇪 Portal Oficial SAIME') + '</div><div class="or-record-meta">' + esc(data.timestamp || '') + '</div></div>';
            contentHtml += '<div class="or-alert-box info">ℹ️ Inteligencia a nivel institucional: la información personal de los ciudadanos no se consulta ni se expone.</div></div>';
        }
        // ── CNE OSINT / VOTACIÓN ──
        else if (tabId === 'cne') {
            if (data.status === 'ENCONTRADO') {
                contentHtml += '<div class="or-alert-box success">✓ REGISTRO ELECTORAL RECUPERADO DE ARCHIVO HISTÓRICO</div>';
                contentHtml += '<div class="or-data-grid">';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Cédula</div><div class="or-data-value large info">' + esc(data.cedula || query) + copy(data.cedula || query) + '</div></div>';
                contentHtml += '<div class="or-data-card" style="grid-column: span 2;"><div class="or-data-label">Elector</div><div class="or-data-value large success">' + esc(data.nombre || 'No especificado') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Estado</div><div class="or-data-value">' + esc(data.estado || 'Desconocido') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Municipio</div><div class="or-data-value">' + esc(data.municipio || 'Desconocido') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Parroquia</div><div class="or-data-value">' + esc(data.parroquia || 'Desconocido') + '</div></div>';
                contentHtml += '</div>';

                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🗳️ CENTRO Y MESA DE VOTACIÓN</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Centro de Votación: <b>' + esc(data.centro_votacion || 'Desconocido') + '</b></div></div>';
                if (data.direccion) contentHtml += '<div class="or-record-row"><div class="or-record-data">Dirección: ' + esc(data.direccion) + '</div></div>';
                if (data.mesa) contentHtml += '<div class="or-record-row"><div class="or-record-data">Mesa: <b>' + esc(data.mesa) + '</b></div></div>';
                contentHtml += '</div>';

                if (data.snapshot_url) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">CAPTURA HISTÓRICA WAYBACK</div></div>';
                    contentHtml += '<div class="or-record-row"><div class="or-record-data"><a href="' + esc(data.snapshot_url) + '" target="_blank" style="color:#76FF03;text-decoration:none;">🌐 Ver captura original en Wayback Machine (' + esc(data.snapshot_timestamp || '') + ')</a></div></div></div>';
                }
            } else if (data.status === 'SIN_REGISTRO_ARCHIVADO' || data.status === 'ERROR_DESCARGA_ARCHIVO' || data.status === 'CAPTURA_NO_PARSEABLE') {
                contentHtml += '<div class="or-alert-box warning">⚠️ ' + esc(data.mensaje || 'No se encontró captura web archivada para la cédula.') + '</div>';
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">INFORMACIÓN DE BÚSQUEDA</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Cédula consultada: <b>' + esc(data.cedula || query) + '</b></div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">Método: ' + esc(data.metodo || 'Archivos Históricos Wayback Machine (CDX API)') + '</div></div>';
                if (data.alternativa_recomendada) {
                    contentHtml += '<div class="or-alert-box info" style="margin-top:10px;">💡 ' + esc(data.alternativa_recomendada) + '</div>';
                }
                contentHtml += '</div>';
            } else {
                contentHtml += '<div class="or-data-grid">';
                contentHtml += '<div class="or-data-card" style="grid-column: span 2;"><div class="or-data-label">Institución</div><div class="or-data-value large success">' + esc(data.institucion || 'CNE — Venezuela') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Alcance</div><div class="or-data-value info">' + esc(data.alcance || 'OSINT institucional público') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Estatus</div><div class="or-data-value large ' + (data.status === 'CONSULTADO' ? 'success' : 'danger') + '">' + esc(data.status || 'N/A') + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Canal</div><div class="or-data-value info">' + esc(data.canal || '') + '</div></div>';
                contentHtml += '</div>';

                if (data.comunicados && data.comunicados.length) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📰 COMUNICADOS Y NOTICIAS INSTITUCIONALES</div><div class="or-section-count">' + data.comunicados.length + '</div></div>';
                    data.comunicados.forEach(function(c) {
                        contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(c.category || '') + ' — ' + esc(c.title) + '</div><div class="or-record-meta">' + esc(c.published || '') + '</div></div>';
                    });
                    contentHtml += '</div>';
                }

                if (data.avisos_oficiales && data.avisos_oficiales.length) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">📢 AVISOS OFICIALES</div><div class="or-section-count">' + data.avisos_oficiales.length + '</div></div>';
                    data.avisos_oficiales.forEach(function(av) {
                        contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(av.title) + '</div></div>';
                    });
                    contentHtml += '</div>';
                }

                if (data.secciones_institucionales && data.secciones_institucionales.length) {
                    contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">🏛️ SECCIONES INSTITUCIONALES DEL PORTAL</div></div>';
                    data.secciones_institucionales.forEach(function(s) {
                        contentHtml += '<div class="or-record-row"><div class="or-record-data"><b>' + esc(s.nombre) + '</b> — ' + esc(s.descripcion) + '</div><div class="or-record-meta">' + esc(s.ruta) + '</div></div>';
                    });
                    contentHtml += '</div>';
                }

                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">FUENTE</div></div>';
                contentHtml += '<div class="or-record-row"><div class="or-record-data">' + esc(data.fuente || '🇻🇪 Portal Oficial CNE (https://cne.gov.ve)') + '</div><div class="or-record-meta">' + esc(data.timestamp || '') + '</div></div>';
                contentHtml += '<div class="or-alert-box info">ℹ️ Ingresa una cédula en el buscador de arriba (ej: V-12345678) para consultar centros de votación en el archivo histórico web de Wayback Machine.</div></div>';
            }
        }
        // ── PHONE CARRIER ──
        else if (tabId === 'phone') {
            var validBadge = data.valid ? '<div class="or-alert-box success">✓ Valid International Phone Number</div>' : '<div class="or-alert-box danger">✕ Invalid or Unrecognized Phone Number</div>';
            contentHtml += validBadge;
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">International Format</div><div class="or-data-value large info">' + esc(data.international || data.number || query) + copy(data.international || data.number || query) + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Carrier / Provider</div><div class="or-data-value">' + esc(data.carrier || 'Unknown') + '</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Region / Country</div><div class="or-data-value">' + esc(data.region || '') + ' (' + esc(data.country_code || '') + ')</div></div>';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Line Type</div><div class="or-data-value">' + esc(data.line_type || 'UNKNOWN') + '</div></div>';
            contentHtml += '</div>';
        }
        // ── THREAT PULSES ──
        else if (tabId === 'threats') {
            var tLevel = data.threat_level || 'LOW';
            var tColor = tLevel === 'HIGH' ? '#FF4444' : tLevel === 'MEDIUM' ? '#FF9500' : '#76FF03';
            contentHtml += '<div class="or-data-grid">';
            contentHtml += '<div class="or-data-card"><div class="or-data-label">Threat Level</div><div class="or-data-value large" style="color:' + tColor + '">' + tLevel + '</div></div>';
            if (data.tor_exit_node !== null) {
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Tor Exit Node</div><div class="or-data-value ' + (data.tor_exit_node ? 'danger' : 'success') + '">' + (data.tor_exit_node ? 'YES (TOR DETECTED)' : 'NO') + '</div></div>';
            }
            contentHtml += '</div>';
            if (data.pulses && data.pulses.length) {
                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">ALIENVAULT OTX PULSES</div><div class="or-section-count">' + data.pulses.length + '</div></div>';
                data.pulses.forEach(function(p) {
                    contentHtml += '<div class="or-record-row" style="flex-direction:column; align-items:flex-start; gap:4px;">';
                    contentHtml += '<div style="color:#FF9500; font-weight:bold;">' + esc(p.name) + '</div>';
                    if (p.description) contentHtml += '<div style="font-size:0.75rem; color:var(--text-muted);">' + esc(p.description) + '</div>';
                    contentHtml += '</div>';
                });
                contentHtml += '</div>';
            }
        }
        // ── GENERIC JSON FALLBACK ──
        else {
            contentHtml += '<pre style="font-size:0.75rem;color:#A9B7C6;max-height:500px;overflow-y:auto;background:rgba(0,0,0,0.3);padding:16px;border-radius:8px;border:1px solid rgba(255,255,255,0.05);font-family:\'Roboto Mono\',monospace;">' + esc(JSON.stringify(data, null, 2)) + '</pre>';
        }


        resultsEl.innerHTML = headerHtml + contentHtml;
        this._renderHistory(); // Refresh history bar
    },

    // ── CUSTOM EXECUTION METHODS ──
    _runSweep: function(ip) {
        var self = this;
        this.state.loading = true;
        this._showLoading();
        var startTime = performance.now();
        fetch('/api/osiris/recon/sweep?ip=' + encodeURIComponent(ip) + '&cidr=' + this.state.sweepCidr)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.queryTime = Math.round(performance.now() - startTime);
                self.state.loading = false;
                self.state.results = data;
                self._addHistory('sweep', ip);
                self._renderResults(data, 'sweep', ip + '/' + self.state.sweepCidr);
            })
            .catch(function(err) {
                self.state.loading = false;
                self._renderError('Sweep failed: ' + (err.message || 'Unknown'));
            });
    },

    _runSanctions: function(query) {
        var self = this;
        this.state.loading = true;
        this._showLoading();
        var startTime = performance.now();
        fetch('/api/osiris/sanctions?query=' + encodeURIComponent(query) + '&limit=25')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.queryTime = Math.round(performance.now() - startTime);
                self.state.loading = false;
                self.state.results = data;
                self._addHistory('sanctions', query);
                
                // Custom render for sanctions
                var resultsEl = document.getElementById('osiris-recon-container');
                var headerHtml = '<div class="or-result-header"><div class="or-result-title"><span style="color:#D4AF37">⚖️</span> TARGET: <span style="color:#fff;font-weight:bold;">' + self._esc(query) + '</span></div><div class="or-result-actions"><div class="or-timer">⏱️ ' + self.state.queryTime + 'ms</div><button id="or-export-json" class="or-action-btn">{ } JSON</button></div></div>';
                
                var contentHtml = '';
                if (data.matches && data.matches.length) {
                    contentHtml += '<div class="or-alert-box danger">⚠ ' + data.total + ' MATCHES FOUND IN OFAC SDN LIST</div>';
                    data.matches.forEach(function(m) {
                        var schemaColor = m.schema === 'Person' ? '#448AFF' : m.schema === 'Organization' ? '#FFD700' : m.schema === 'Vessel' ? '#00E5FF' : m.schema === 'Airplane' ? '#76FF03' : '#aaa';
                        contentHtml += '<div class="or-data-card" style="margin-bottom:8px;border-left:3px solid ' + schemaColor + ';">';
                        contentHtml += '<div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span style="color:#fff;font-weight:bold;font-size:0.9rem;">' + self._esc(m.name || '') + '</span><span style="color:' + schemaColor + ';font-size:0.6rem;letter-spacing:1px;font-family:\'Roboto Mono\';">' + (m.schema || '').toUpperCase() + '</span></div>';
                        if (m.program) contentHtml += '<div style="font-size:0.75rem;color:#FF9500;margin-bottom:4px;">Program: ' + self._esc(m.program) + '</div>';
                        if (m.country) contentHtml += '<div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">Country: ' + self._esc(m.country) + '</div>';
                        if (m.listing_date) contentHtml += '<div style="font-size:0.75rem;color:var(--text-muted);">Listed: ' + self._esc(m.listing_date) + '</div>';
                        contentHtml += '</div>';
                    });
                } else {
                    contentHtml += '<div class="or-alert-box success">✓ NO SANCTIONS MATCHES FOUND</div>';
                }
                
                if (resultsEl) resultsEl.innerHTML = headerHtml + contentHtml;
                self._renderHistory();
            })
            .catch(function(err) {
                self.state.loading = false;
                self._renderError('Sanctions search failed: ' + (err.message || 'Unknown'));
            });
    },

    _addHistory: function(tabId, query) {
        // Prevent duplicates
        this.state.history = this.state.history.filter(function(h) { return !(h.tab === tabId && h.query === query); });
        this.state.history.unshift({ tab: tabId, query: query, time: new Date().toISOString() });
        if (this.state.history.length > 20) this.state.history.length = 20;
        try { localStorage.setItem('osiris_recon_history', JSON.stringify(this.state.history)); } catch(e) {}
    },

    _runDoctor: function() {
        var self = this;
        this.state.loading = true;
        this._showLoading();
        fetch('/api/osiris/doctor')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.loading = false;
                self.state.results = data;
                
                var resultsEl = document.getElementById('osiris-recon-container');
                if (!resultsEl) return;
                
                var statusColor = data.status === 'ONLINE' ? '#76FF03' : data.status === 'DEGRADED' ? '#FF9500' : '#FF4444';
                var headerHtml = '<div class="or-result-header"><div class="or-result-title"><span style="color:#00E5FF">🩺</span> OSIRIS DOCTOR: <span style="color:' + statusColor + ';font-weight:bold;">' + (data.status || 'UNKNOWN') + '</span> (' + data.healthy_services + '/' + data.total_services + ' Active - ' + data.health_percentage + '%)</div><div class="or-result-actions"><div class="or-timer">⏱️ ' + data.latency_ms + 'ms</div><button id="or-export-json" class="or-action-btn">{ } JSON</button></div></div>';
                
                var contentHtml = '<div class="or-data-grid" style="margin-bottom:16px;">';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Overall Health</div><div class="or-data-value large" style="color:' + statusColor + '">' + data.health_percentage + '%</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Operational Sources</div><div class="or-data-value large success">' + data.healthy_services + ' / ' + data.total_services + '</div></div>';
                contentHtml += '<div class="or-data-card"><div class="or-data-label">Diagnostic Latency</div><div class="or-data-value info">' + data.latency_ms + ' ms</div></div>';
                contentHtml += '</div>';

                contentHtml += '<div class="or-section"><div class="or-section-header"><div class="or-section-title">SERVICE STATUS MATRIX</div></div>';
                if (data.services && data.services.length) {
                    data.services.forEach(function(s) {
                        var sColor = s.status === 'ONLINE' ? '#76FF03' : s.status === 'DEGRADED' ? '#FF9500' : '#FF4444';
                        contentHtml += '<div class="or-record-row">';
                        contentHtml += '<div class="or-record-data" style="font-weight:bold;text-transform:uppercase;color:var(--primary);">' + self._esc(s.name) + '</div>';
                        contentHtml += '<div class="or-record-meta"><span class="or-tag" style="background:rgba(0,0,0,0.3);border:1px solid ' + sColor + ';color:' + sColor + ';">' + s.status + '</span> <span style="color:var(--text-muted);font-size:0.75rem;">' + self._esc(s.detail || '') + '</span></div>';
                        contentHtml += '</div>';
                    });
                }
                contentHtml += '</div>';
                
                resultsEl.innerHTML = headerHtml + contentHtml;
            })
            .catch(function(err) {
                self.state.loading = false;
                self._renderError('Doctor diagnostic scan failed: ' + (err.message || 'Unknown'));
            });
    }
};
