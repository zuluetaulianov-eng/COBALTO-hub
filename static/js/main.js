/**
 * Cobalto Hub - Core Application Controller
 * Encapsula el estado y la lógica principal para evitar contaminación del scope global.
 */

function renderAgentCard(agent, esc) {
    return '<div style="border-left: 3px solid ' + esc(agent.color) + '; background: rgba(0,0,0,0.35); padding: 15px; margin-bottom: 18px; border-radius: 0 8px 8px 0; transition: transform 0.2s; border: 1px solid rgba(255,255,255,0.03);">' +
        '<div style="color: ' + esc(agent.color) + '; font-weight: bold; margin-bottom: 8px; font-size: 0.85rem; letter-spacing: 1.5px; display: flex; align-items: center; font-family: \'Roboto Mono\', monospace;">' +
        '<span style="display:inline-block; width:8px; height:8px; background:' + esc(agent.color) + '; border-radius:50%; margin-right:10px; box-shadow: 0 0 10px ' + esc(agent.color) + ';"></span>' +
        esc(agent.agent) +
        (agent.role ? '<span style="color: rgba(255,255,255,0.3); font-size: 0.7rem; margin-left: 10px; font-weight: normal; letter-spacing: 0;">| ' + esc(agent.role) + '</span>' : '') +
        '</div>' +
        '<div style="color: #f0f0f0; font-size: 0.95rem; line-height: 1.6; text-align: justify; font-family: \'Inter\', sans-serif;">' + esc(agent.text) + '</div>' +
        '</div>';
}

window.currentTheater = 'ALL';
window.switchTheater = function(code) {
    window.currentTheater = code || 'ALL';
    console.log('[THEATER] Switched operational theater to:', window.currentTheater);

    var badge = document.getElementById('theater-active-badge');
    if (badge) badge.textContent = window.currentTheater;

    if (window.UnifiedMap && window.UnifiedMap.state && window.UnifiedMap.state.map) {
        if (window.currentTheater === 'COL') {
            window.UnifiedMap.state.map.flyTo([6.5, -70.0], 5);
        } else if (window.currentTheater === 'VEN') {
            window.UnifiedMap.state.map.flyTo([7.5, -66.5], 6);
        } else if (window.currentTheater === 'GLOBAL') {
            window.UnifiedMap.state.map.flyTo([7.0, -68.0], 4);
        }
    }

    var cards = document.querySelectorAll('.news-card, .intel-card');
    cards.forEach(function(card) {
        var tags = (card.getAttribute('data-country') || '').toUpperCase();
        if (window.currentTheater === 'ALL' || !tags || tags.includes(window.currentTheater) || tags.includes('GLOBAL')) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
};

window.CobaltoCore = {
    state: {
        ws: null,
        currentTimestamp: null,
        reconnectAttempts: 0,
        newsPage: 1,
        newsPerPage: 30,
        allNews: [],
        tabCache: {},
        tabLoading: {},
        tabRendered: {}
    },

    utils: {
        /**
         * Escapa caracteres HTML para prevenir XSS.
         */
        escapeHTML: function(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        /**
         * Fetch con timeout mediante AbortController.
         */
        fetchWithTimeout: function(url, options, timeout) {
            if (timeout === undefined || timeout === null) timeout = 30000;
            var controller = new AbortController();
            var timer = setTimeout(function() { controller.abort(); }, timeout);
            return fetch(url, Object.assign({}, options, { signal: controller.signal }))
                .then(function(response) {
                    clearTimeout(timer);
                    return response;
                })
                .catch(function(err) {
                    clearTimeout(timer);
                    throw err;
                });
        },

        /**
         * Poda el DOM para evitar fugas de memoria en sesiones largas.
         * Mantiene solo los últimos N elementos de un contenedor.
         */
        pruneDOM: function(containerId, maxItems = 200, selector = null) {
            const container = document.getElementById(containerId);
            if (!container) return;
            
            var children = selector ? [].slice.call(container.querySelectorAll(selector)) : [].slice.call(container.children);
            if (children.length > maxItems) {
                var toRemove = children.length - maxItems;
                for (var i = children.length - 1; i >= children.length - toRemove; i--) {
                    var el = children[i];
                    if (el && el.parentElement) el.parentElement.removeChild(el);
                }
            }
        }
    },

    /**
     * Gestión de base de datos local (IndexedDB) para persistencia offline.
     */
    db: {
        DB_NAME: 'CobaltoIntelligence',
        VERSION: 1,
        STORE: 'intelligence_cache',

        init: function() {
            return new Promise((resolve, reject) => {
                const req = indexedDB.open(this.DB_NAME, this.VERSION);
                req.onupgradeneeded = (e) => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains(this.STORE)) {
                        db.createObjectStore(this.STORE);
                    }
                };
                req.onsuccess = (e) => resolve(e.target.result);
                req.onerror = (e) => reject(e.target.error);
            });
        },

        get: async function(key) {
            try {
                const db = await this.init();
                return new Promise((resolve) => {
                    const tx = db.transaction(this.STORE, 'readonly');
                    const req = tx.objectStore(this.STORE).get(key);
                    req.onsuccess = () => resolve(req.result);
                    req.onerror = () => resolve(null);
                });
            } catch(e) { return null; }
        },

        set: async function(key, val) {
            try {
                const db = await this.init();
                return new Promise((resolve) => {
                    const tx = db.transaction(this.STORE, 'readwrite');
                    const req = tx.objectStore(this.STORE).put(val, key);
                    req.onsuccess = () => resolve(true);
                    req.onerror = () => resolve(false);
                });
            } catch(e) { return false; }
        },

        clear: async function() {
            try {
                const db = await this.init();
                const tx = db.transaction(this.STORE, 'readwrite');
                tx.objectStore(this.STORE).clear();
            } catch(e) {}
        }
    },

    init: function(timestamp) {
        this.state.currentTimestamp = timestamp;
        this.initWebSocket();
        this.initGarbageCollector();
        this.initResizeObservers();
        this.loadAllNews();
        this.loadBriefing();
        this.preloadAllTabs();
        // Carga única del sidebar al inicio (sin polling periódico)
        if (window._initialStatus) {
            this.updateSidebar(window._initialStatus);
        } else {
            var self = this;
            this.utils.fetchWithTimeout('/api/status')
                .then(function(r) { return r.json(); })
                .then(function(data) { self.updateSidebar(data); })
                .catch(function() {});
        }

        // Registrar Service Worker para PWA
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/service-worker.js')
                    .then(reg => {
                        reg.addEventListener('updatefound', () => {
                            const newWorker = reg.installing;
                            newWorker.addEventListener('statechange', () => {
                                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                    this.showUpdateNotification(reg);
                                }
                            });
                        });
                    })
                    .catch(err => console.log('[PWA] Error al registrar SW:', err));
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('search-input');
                if (searchInput) searchInput.focus();
            }
            if (e.key === 'Escape') {
                const active = document.activeElement;
                if (active && active.classList.contains('search-box')) active.blur();
            }
        });

        this.attachEventListeners();

        var splash = document.getElementById('splash-screen');
        if (splash) { splash.style.transition = 'opacity 0.5s'; splash.style.opacity = '0'; setTimeout(function() { if (splash.parentElement) splash.parentElement.removeChild(splash); }, 600); }
    },

    attachEventListeners: function() {
        var self = this;

        document.querySelectorAll('.nav-button[data-tab]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                self.switchTab(btn.getAttribute('data-tab'), btn);
            });
        });

        var searchHandlers = {
            'search-input': { fn: function() { self.filterNews(); } },
            'social-search': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.filterSocial(); } },
            'alert-search': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.filterAlerts(); } },
            'rt-search': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.filterRT(); } },
            'narrative-search': { fn: function() { self.filterNarratives(); } },
            'chat-input': { event: 'keypress', fn: function(e) { if (window.CobaltoChat) CobaltoChat.handleEnter(e); } },
            'new-keyword-input': { event: 'keypress', fn: function(e) { if (window.CobaltoConfig) CobaltoConfig.addKeywordFromInput(e); } },
            'new-target-input': { event: 'keypress', fn: function(e) { if (window.CobaltoConfig) CobaltoConfig.addTargetUserFromInput(e); } }
        };
        Object.keys(searchHandlers).forEach(function(id) {
            var el = document.getElementById(id);
            if (!el) return;
            var cfg = searchHandlers[id];
            el.removeAttribute('onkeyup');
            el.removeAttribute('onkeypress');
            el.addEventListener(cfg.event || 'input', cfg.fn);
        });

        var selectHandlers = {
            'alert-level-filter': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.filterAlerts(); } },
            'alert-sort': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.sortAlerts(); } },
            'rt-category': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.filterRT(); } },
            'rt-sort': { fn: function() { if (window.CobaltoIntel) CobaltoIntel.sortRT(); } },
            'analytics-timerange': { fn: function() { if (window.CobaltoAnalytics) CobaltoAnalytics.refreshData(); } }
        };
        Object.keys(selectHandlers).forEach(function(id) {
            var el = document.getElementById(id);
            if (!el) return;
            el.removeAttribute('onchange');
            el.addEventListener('change', selectHandlers[id].fn);
        });

        document.querySelectorAll('.config-subtab-btn').forEach(function(btn) {
            var subtab = btn.getAttribute('data-subtab');
            if (subtab) {
                btn.addEventListener('click', function() {
                    if (window.CobaltoConfig) {
                        CobaltoConfig.switchSubTab(subtab, btn);
                    }
                });
            }
        });

        var clickHandlers = {
            'sidebar-collapse-btn': function() { if (window.CobaltoLayout) CobaltoLayout.toggleSidebar(); },
            'sidebar-expand-btn': function() { if (window.CobaltoLayout) CobaltoLayout.toggleSidebar(); },
            'btn-mosaic-toggle': function() { window.toggleMosaicMode(); },
            'intel-history-toggle-btn': function() { if (window.CobaltoLayout) CobaltoLayout.toggleIntelHistory(); },
            'btn-express-briefing': function() { self.loadExpressBriefing(); },
            'btn-refresh-briefing': function() { self.handleUpdate(null); },
            'chat-send-btn': function() { if (window.CobaltoChat) CobaltoChat.sendMessage(); },
            'ai-expand-btn': function() { if (window.CobaltoChat) CobaltoChat.toggleAI(); },
            'fab-ai': function() { if (window.CobaltoChat) CobaltoChat.toggleAI(); },
            'btn-clear-chat': function() { if (window.CobaltoChat) CobaltoChat.clearChat(); }
        };
        Object.keys(clickHandlers).forEach(function(id) {
            var el = document.getElementById(id);
            if (el) {
                el.addEventListener('click', clickHandlers[id]);
            }
        });


        document.querySelectorAll('.btn-neo4j-graph').forEach(function(el) {
            el.addEventListener('click', function() {
                if (window.openNeo4jGraph) openNeo4jGraph();
            });
        });

        document.querySelectorAll('.btn-export-png').forEach(function(el) {
            el.addEventListener('click', function() {
                var chartId = el.getAttribute('data-chart-id');
                var label = el.getAttribute('data-label');
                if (chartId && label && window.CobaltoAnalytics) {
                    CobaltoAnalytics.exportChart(chartId, label);
                }
            });
        });

        document.querySelectorAll('#analytics-timerange').forEach(function(el) {
            el.addEventListener('change', function() {
                if (window.CobaltoAnalytics) CobaltoAnalytics.refreshData();
            });
        });

        var rangeSliderMap = {
            'cfg-similarity': 'sim-val-display',
            'cfg-ai-temperature': 'temp-val-display',
            'cfg-sent-threshold-positivo': 'sent-thr-pos-display',
            'cfg-sent-threshold-negativo': 'sent-thr-neg-display',
            'cfg-sent-crisis-score': 'sent-thr-crit-display',
            'cfg-sent-alerta-score': 'sent-thr-alert-display'
        };
        Object.keys(rangeSliderMap).forEach(function(sliderId) {
            var el = document.getElementById(sliderId);
            if (!el) return;
            el.removeAttribute('oninput');
            el.addEventListener('input', function() {
                var display = document.getElementById(rangeSliderMap[sliderId]);
                if (display) display.textContent = parseFloat(this.value).toFixed(2);
            });
        });

        document.querySelectorAll('.btn-toggle-password').forEach(function(btn) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', function() {
                var targetId = btn.getAttribute('data-target');
                var t = document.getElementById(targetId);
                if (t) t.type = t.type === 'password' ? 'text' : 'password';
            });
        });

        var clearBtn = document.getElementById('btn-clear-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                ['search-input','social-search','alert-search','rt-search','narrative-search'].forEach(function(id) {
                    var el = document.getElementById(id);
                    if (el) el.value = '';
                });
                if (window.CobaltoCore) { CobaltoCore.filterNews(); CobaltoCore.filterNarratives(); }
                if (window.CobaltoIntel) { CobaltoIntel.filterSocial(); CobaltoIntel.filterAlerts(); CobaltoIntel.filterRT(); }
            });
        }

        var socialList = document.getElementById('social-list');
        if (socialList) {
            socialList.addEventListener('click', function(e) {
                var target = e.target.closest('.social-show-more');
                if (!target) return;
                var container = target.parentElement.querySelector('.social-items');
                if (!container) return;
                try {
                    var items = JSON.parse(target.getAttribute('data-items') || '[]');
                    var html = '';
                    items.forEach(function(item) {
                        var searchText = ((item.title || '') + ' ' + (item.summary || '')).toLowerCase();
                        html += '<div class="social-item" data-search-text="' + self.utils.escapeHTML(searchText) + '"><a href="' + self.utils.escapeHTML(item.link || '#') + '" target="_blank" rel="noopener noreferrer">' + self.utils.escapeHTML(item.title || '') + '</a><p>' + self.utils.escapeHTML(item.summary || '') + '</p></div>';
                    });
                    container.insertAdjacentHTML('beforeend', html);
                    target.remove();
                } catch(e) {}
            });
        }
    },

    initResizeObservers: function() {
        console.log('[COBALTO] Fase 1 (Mosaico) iniciada: Activando ResizeObservers Tácticos.');
        if (window.ResizeObserver) {
            const ro = new ResizeObserver(entries => {
                for (let entry of entries) {
                    // Refrescar mapa si cambia su contenedor
                    if (entry.target.id === 'map-container' && window.CobaltoMap && window.CobaltoMap._map) {
                        window.CobaltoMap._map.invalidateSize();
                    }
                    // Refrescar gráficos si cambian sus contenedores
                    if (entry.target.classList.contains('chart-container') && window.Chart) {
                        for (let id in Chart.instances) {
                            Chart.instances[id].resize();
                        }
                    }
                }
            });

            // Observar contenedores clave preventivamente
            const mapEl = document.getElementById('map-container');
            if (mapEl) ro.observe(mapEl);
            
            document.querySelectorAll('.chart-container').forEach(el => ro.observe(el));
        }
    },

    initGarbageCollector: function() {
        // Ciclo de mantenimiento cada 5 minutos
        setInterval(() => {
            console.log('[GC] Ciclo de mantenimiento de memoria iniciado.');
            this.utils.pruneDOM('news-grid', 300, '.news-card');
            this.utils.pruneDOM('alert-list', 150, '.alert-card');
            this.utils.pruneDOM('rt-grid', 150, '.rt-card');
            
            // Poda profunda de redes sociales para evitar bloat en grupos colapsados
            document.querySelectorAll('.social-items').forEach(group => {
                const items = group.children;
                if (items.length > 50) {
                    for (let i = items.length - 1; i >= 50; i--) {
                        group.removeChild(items[i]);
                    }
                }
            });
        }, 300000);
    },

    showUpdateNotification: function(reg) {
        const hud = document.getElementById('hud-update');
        if (hud) {
            hud.innerText = 'Nueva versión disponible. Actualizando...';
            hud.style.display = 'block';
        }
        window.location.reload();
    },

    initWebSocket: function() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.state.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        
        this.state.ws.onopen = () => {
            console.log('[WS] Enlace táctico establecido');
            this.state.reconnectAttempts = 0;
        };
        
        this.state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'update' && data.timestamp && data.timestamp !== this.state.currentTimestamp) {
                    this.handleUpdate(data);
                }
                if (data.type === 'event' && data.event_type === 'predictive') {
                    this._updatePredictiveBadge();
                }
            } catch(e) {
                console.warn('[WS] Mensaje inválido:', e.message);
            }
        };
        
        this.state.ws.onclose = () => {
            this.state.reconnectAttempts++;
            const delay = Math.min(Math.pow(2, this.state.reconnectAttempts - 1) * 5000, 60000);
            console.log(`[WS] Enlace caído. Reintentando en ${delay/1000}s (Intento ${this.state.reconnectAttempts})`);
            setTimeout(() => this.initWebSocket(), delay);
        };
    },

    initStatusPolling: function() {
        // DESACTIVADO: El polling periódico ha sido eliminado.
        // El sidebar se actualiza una sola vez en init().
        // Las actualizaciones de datos solo ocurren al inicio del servidor.
    },

    updateSidebar: function(data) {
        var sourcesEl = document.getElementById('stat-total-sources');
        if (sourcesEl && data.total_sources !== undefined) sourcesEl.textContent = data.total_sources;
        var entriesEl = document.getElementById('stat-entries-count');
        if (entriesEl && data.total_entries !== undefined) entriesEl.textContent = data.total_entries;
        var tsEl = document.getElementById('stat-timestamp');
        if (tsEl && data.timestamp) tsEl.textContent = data.timestamp;
        var syncEl = document.getElementById('sync-status');
        if (syncEl) syncEl.style.display = data.updating ? 'flex' : 'none';
    },

    handleUpdate: function(dataPayload) {
        const newTimestamp = dataPayload ? dataPayload.timestamp : '';
        
        // Disparar Radar y Toasts
        if (typeof window.animateRadar === 'function') window.animateRadar();
        if (dataPayload && dataPayload.counts && dataPayload.counts.alerts > 0) {
            if (typeof window.showTacticalToast === 'function') {
                window.showTacticalToast(`Nuevo ciclo completado. Se detectaron ${dataPayload.counts.alerts} posibles amenazas/alertas.`, 'warning');
            }
            if (typeof window.playTacticalBeep === 'function') window.playTacticalBeep('warning');
            if (window.CobaltoVoice && typeof window.CobaltoVoice.announceCriticalAlert === 'function') {
                window.CobaltoVoice.announceCriticalAlert(`Atención operador. Se detectaron ${dataPayload.counts.alerts} nuevas alertas tácticas en el sistema.`);
            }
        } else {
            if (typeof window.showTacticalToast === 'function') {
                window.showTacticalToast('Ciclo de extracción completado. Nodos sincronizados.', 'info');
            }
            if (typeof window.playTacticalBeep === 'function') window.playTacticalBeep('info');
        }

        this.state.initialUpdateDone = true;
        this.state.currentTimestamp = newTimestamp;
        this.state.tabRendered = {};

        console.log('[COBALTO] Sincronizando datos de inteligencia en tiempo real desde servidor...');

        var hud = document.getElementById('hud-update');
        if (hud) {
            hud.innerText = '✅ Inteligencia sincronizada en tiempo real';
            hud.style.display = 'block';
            setTimeout(function() { hud.style.display = 'none'; }, 5000);
        }

        var self = this;
        // 1. Actualizar sidebar con datos finales
        this.utils.fetchWithTimeout('/api/status')
            .then(function(r) { return r.json(); })
            .then(function(data) { self.updateSidebar(data); })
            .catch(function() {});

        // 2. Recargar noticias con datos frescos del servidor
        this.utils.fetchWithTimeout('/api/news')
            .then(function(r) { return r.json(); })
            .then(function(entries) {
                if (entries && Array.isArray(entries)) {
                    self.state.allNews = entries;
                    self.db.set('allNews', entries);
                    self.resetNewsView();
                }
            })
            .catch(function() {});

        // 3. Recargar briefing con análisis IA final
        var briefingContainer = document.getElementById('main-briefing');
        if (briefingContainer) {
            self.utils.fetchWithTimeout('/api/briefing')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var briefing = (data.global_briefing && (data.global_briefing.agents || data.global_briefing.debate || data.global_briefing.consensus)) ? data.global_briefing : data;
                    if (briefing && (briefing.agents || briefing.debate || briefing.consensus)) {
                        self.renderBriefing(briefingContainer, briefing, data.reliability_score, data.reliability_color);
                    }
                })
                .catch(function() {});
        }

        // 4. Refrescar capas de Mapa Unificado si está activo
        if (window.UnifiedMap && typeof window.UnifiedMap.refreshAll === 'function') {
            try {
                window.UnifiedMap.refreshAll();
            } catch(e) {
                console.warn('[MAP] Error refrescando mapa unificado:', e);
            }
        }
    },

    loadAllNews: async function() {
        // 0. Si el servidor ya inyectó noticias precargadas
        if (window._initialNews && window._initialNews.length > 0) {
            this.state.allNews = window._initialNews;
            this.db.set('allNews', window._initialNews);
            this.renderNewsPage(1);
            this.initInfiniteScroll();
            return;
        }

        // 1. Carga inmediata desde IndexedDB (Rendimiento + Offline)
        const cached = await this.db.get('allNews');
        if (cached) {
            this.state.allNews = cached;
            this.renderNewsPage(1);
            this.initInfiniteScroll();
        }

        // 2. Sincronización en segundo plano
        this.utils.fetchWithTimeout('/api/news')
            .then(r => r.json())
            .then(entries => {
                this.state.allNews = entries;
                this.db.set('allNews', entries);
                
                const grid = document.getElementById('news-grid');
                if (grid && grid.children.length === 0) {
                    this.renderNewsPage(1);
                    this.initInfiniteScroll();
                }
                // Refrescar cyber si está visible
                var cyberTab = document.getElementById('tab-cyber');
                if (cyberTab && cyberTab.classList.contains('active')) {
                    if (window.CobaltoCore) window.CobaltoCore.renderCyberTab();
                }
            })
            .catch(() => {
                console.log('[Offline] Usando SitRep de la caché persistente.');
            });
    },

    loadBriefing: function() {
        var container = document.getElementById('main-briefing');
        if (!container) return;

        var self = this;

        // 0. Si el servidor ya inyectó el briefing precargado
        if (window._initialBriefing && window._initialBriefing.consensus) {
            this.db.set('tab-intel-briefing', { global_briefing: window._initialBriefing });
            this.renderBriefing(container, window._initialBriefing, window._initialBriefing.reliability_score, window._initialBriefing.reliability_color);
            return;
        }

        // 1. IndexedDB cache
        this.db.get('tab-intel-briefing').then(function(cached) {
            if (cached && cached.global_briefing && (cached.global_briefing.agents || cached.global_briefing.debate || cached.global_briefing.consensus)) {
                if (window.CobaltoCore) window.CobaltoCore.renderBriefing(container, cached.global_briefing);
            }
        });

        // 2. Red
        this.utils.fetchWithTimeout('/api/briefing')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!self) return;
                self.db.set('tab-intel-briefing', data);
                if (data.global_briefing && (data.global_briefing.agents || data.global_briefing.debate || data.global_briefing.consensus)) {
                    self.renderBriefing(container, data.global_briefing, data.reliability_score, data.reliability_color);
                } else {
                    self._startStreamingPoll();
                }
            })
            .catch(function() { self._startStreamingPoll(); });
    },

    _startStreamingPoll: function() {
        if (window._streamingPollTimer) return;
        var self = this;
        window._streamingPollTimer = setInterval(function() {
            var container = document.getElementById('main-briefing');
            if (container && container.getAttribute('data-briefing-loaded') === 'true') {
                clearInterval(window._streamingPollTimer);
                window._streamingPollTimer = null;
                return;
            }
            self.utils.fetchWithTimeout('/api/briefing/status')
                .then(function(r) { return r.json(); })
                .then(function(status) {
                    if (!status || !status.step) return;
                    var el = document.getElementById('briefing-agent-status');
                    if (!el) return;
                    var agentColors = {ARES: '#ff4444', MINERVA: '#44aaee', NEXUS: '#00ffaa', COORDINADOR: '#ffd700', EXPRESS: '#ffd700'};
                    var c = agentColors[status.step] || 'var(--primary)';
                    el.innerHTML = '<span style="color:' + c + ';font-weight:bold;">' + status.step + '</span> analizando... <span style="font-size:0.7rem;opacity:0.5;animation:pulse 1s infinite;">▌</span>';
                })
                .catch(function() {});
        }, 2000);
        setTimeout(function() {
            if (window._streamingPollTimer) {
                clearInterval(window._streamingPollTimer);
                window._streamingPollTimer = null;
            }
        }, 300000);
    },

    loadExpressBriefing: function() {
        var container = document.getElementById('main-briefing');
        if (!container) return;
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);"><div class="ai-status-dot" style="width:12px;height:12px;margin:0 auto 15px;animation:pulse 1.5s infinite;"></div><p>⚡ Generando resumen rápido...</p></div>';
        if (window.showAIThinkingToast) {
            window.showAIThinkingToast('IA GENERANDO RESUMEN...', 'Procesando síntesis ejecutiva táctica...');
        }
        var self = this;
        this.utils.fetchWithTimeout('/api/briefing/express')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!self) return;
                self.renderBriefing(container, data);
                if (window.hideAIThinkingToast) {
                    window.hideAIThinkingToast('Resumen táctico listo', false);
                }
            })
            .catch(function() {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:#FF2D55;"><p>Error generando resumen rápido.</p></div>';
                if (window.hideAIThinkingToast) {
                    window.hideAIThinkingToast('Error generando resumen', true);
                }
            });
    },

    initBriefingPolling: function() {
        // DESACTIVADO: El polling periódico del briefing ha sido eliminado.
        // El briefing se carga una sola vez en loadBriefing() y en handleUpdate().
    },

    renderNewsPage: function(page) {
        const grid = document.getElementById('news-grid');
        if (!grid || !this.state.allNews) return;
        const start = (page - 1) * this.state.newsPerPage;
        var rawItems = this.state.allNews.slice(start, start + this.state.newsPerPage);
        if (!rawItems.length) return;
        
        var items = window.clusterNewsItems ? window.clusterNewsItems(rawItems) : rawItems;

        const html = items.map(item => {
            var t = (item.title || '').toLowerCase();
            var s = (item.summary || '').toLowerCase();
            var countryTag = (item.country_tags && item.country_tags[0]) ? item.country_tags[0] : (t.includes('colombia') || s.includes('bogotá') || s.includes('eln') ? 'COL' : (t.includes('venezuela') || s.includes('caracas') || s.includes('fanb') ? 'VEN' : 'GLOBAL'));
            
            var countryFlag = countryTag === 'COL' ? '🇨🇴 COL' : (countryTag === 'VEN' ? '🇻🇪 VEN' : '🌐 INTL');
            var countryClass = countryTag.toLowerCase();
            
            var severity = 'INFO';
            if (item.level) {
                if (item.level.includes('CRÍTICO')) severity = 'CRITICAL';
                else if (item.level.includes('URGENTE') || item.level.includes('ALTO')) severity = 'HIGH';
                else if (item.level.includes('CYBER')) severity = 'CYBER';
                else if (item.level.includes('ATENCIÓN') || item.level.includes('MEDIO')) severity = 'MEDIUM';
            } else if (item.score && item.score >= 45) {
                severity = 'CRITICAL';
            } else if (item.score && item.score >= 28) {
                severity = 'HIGH';
            } else if (item.score && item.score >= 15) {
                severity = 'MEDIUM';
            } else {
                var textCombined = t + ' ' + s;
                if (/ataque|muerto|explosión|bomba|atentado|combate|masacre|crisis|0-day|ransomware|blackout|apagón/i.test(textCombined)) {
                    severity = 'CRITICAL';
                } else if (/fanb|eln|emc|fuerzas armadas|ejército|dron|captura|exfiltración|sanciones/i.test(textCombined)) {
                    severity = 'HIGH';
                } else if (/protesta|tensión|frontera|cierre|investigación|decreto/i.test(textCombined)) {
                    severity = 'MEDIUM';
                }
            }
            
            var severityLabel = severity === 'CRITICAL' ? '🔴 CRÍTICO' : (severity === 'HIGH' ? '🟠 URGENTE' : (severity === 'CYBER' ? '🔵 CYBER' : (severity === 'MEDIUM' ? '🟡 ATENCIÓN' : '⚪ INFO')));
            var severityClass = severity.toLowerCase();
            
            var category = 'GENERAL';
            if (/fanb|ejército|militar|combate|defensa|armadas/i.test(textCombined)) category = 'MILITARY';
            else if (/protesta|orden público|policía|manifestación|disturbio/i.test(textCombined)) category = 'SECURITY';
            else if (/apagón|blackout|redes|servicios|electricidad|infraestructura/i.test(textCombined)) category = 'INFRASTRUCTURE';
            else if (/clan del golfo|eln|emc|droga|narcotráfico|capturado|sicariato/i.test(textCombined)) category = 'CRIME';
            else if (/gobierno|presidente|cancillería|congreso|asamblea|política/i.test(textCombined)) category = 'POLITICS';
            else if (/dólar|sanción|economía|petróleo|inflación|banca/i.test(textCombined)) category = 'ECONOMY';
            
            var sourcesCount = item.sources_count || 1;
            var sourcesBadgeHtml = sourcesCount > 1 ? `<span class="config-chip" style="font-size:0.68rem; background:rgba(0,229,255,0.15); border:1px solid var(--primary); color:#00E5FF; font-weight:bold;">🌐 ${sourcesCount} FUENTES</span>` : '';
            var relatedJson = item.related_sources ? this.utils.escapeHTML(JSON.stringify(item.related_sources)) : '[]';

            var imgHtml = item.image ? `<img src="${this.utils.escapeHTML(item.image)}" class="card-image" style="margin-bottom: 0.8rem; border-radius: 8px; cursor:pointer;" alt="" loading="lazy" onclick="window.openSitrepReader(this.closest('.news-card'))">` : '';
            var titleClean = (item.title || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
            var linkEsc = this.utils.escapeHTML(item.link || '#');

            return `
                <div class="news-card" data-title="${this.utils.escapeHTML(t)}" data-summary="${this.utils.escapeHTML(s)}" data-country="${countryTag}" data-category="${category}" data-severity="${severity}" data-sources-count="${sourcesCount}" data-related="${relatedJson}">
                    <div>
                        <div class="news-header">
                            <div class="flex items-center gap-05 flex-wrap">
                                <span class="news-source">${this.utils.escapeHTML(item.source || '')}</span>
                                ${sourcesBadgeHtml}
                                <span class="news-country-tag ${countryClass}">${countryFlag}</span>
                                <span class="news-severity-tag ${severityClass}">${severityLabel}</span>
                            </div>
                            <span class="news-time">${this.utils.escapeHTML(item.published || '')}</span>
                        </div>
                        ${imgHtml}
                        <a href="javascript:void(0)" onclick="window.openSitrepReader(this.closest('.news-card'))" class="news-title" title="Clic para maximizar e inspeccionar la noticia">${this.utils.escapeHTML(item.title || '')}</a>
                        <p class="news-summary">${this.utils.escapeHTML(item.summary || '')}</p>
                    </div>
                    <div class="news-card-actions">
                        <div class="flex gap-05 flex-wrap">
                            <button type="button" class="news-action-btn" onclick="window.openSitrepReader(this.closest('.news-card'))" title="Maximizar noticia y analizar con IA">🔍 Maximizar</button>
                            <button type="button" class="news-action-btn" onclick="window.sitrepFocusMap('${countryTag}', '${titleClean}')" title="Ver ubicación en Mapa Táctico">📍 Mapa</button>
                            <button type="button" class="news-action-btn" onclick="window.sitrepInvestigateRAG('${titleClean}')" title="Investigar hipótesis con IA RAG Local">🎯 RAG</button>
                            <button type="button" class="news-action-btn" onclick="if(window.CobaltoNotes)window.CobaltoNotes._toggleNote(this.closest('.news-card'))" title="Añadir Nota Táctica Operativa">📝 Nota</button>
                        </div>
                        <button type="button" class="news-action-btn" onclick="window.sitrepCopyLink('${linkEsc}')" title="Copiar enlace canónico">🔗 Copiar</button>
                    </div>
                </div>
            `;
        }).join('');
        
        grid.insertAdjacentHTML('beforeend', html);
        this.state.newsPage = page;
        this.updateNewsLoader();
        this.updateSitrepKPIs();
        this.filterNews();
    },

    updateSitrepKPIs: function() {
        if (!this.state.allNews) return;
        var total = this.state.allNews.length;
        var col = 0, ven = 0, global = 0, highSevCol = 0, highSevVen = 0;
        
        this.state.allNews.forEach(function(item) {
            var tags = (item.country_tags || []).join(' ');
            var text = ((item.title || '') + ' ' + (item.summary || '')).toLowerCase();
            var isCol = tags.includes('COL') || text.includes('colombia') || text.includes('bogotá') || text.includes('eln');
            var isVen = tags.includes('VEN') || text.includes('venezuela') || text.includes('caracas') || text.includes('fanb');
            
            if (isCol) {
                col++;
                if (/ataque|muerto|combate|explosión|alerta/i.test(text)) highSevCol++;
            } else if (isVen) {
                ven++;
                if (/ataque|sanción|apagón|alerta|fanb/i.test(text)) highSevVen++;
            } else {
                global++;
            }
        });
        
        var totalEl = document.getElementById('sitrep-kpi-total');
        if (totalEl) totalEl.textContent = total;
        var colEl = document.getElementById('sitrep-kpi-col');
        if (colEl) colEl.textContent = col;
        var venEl = document.getElementById('sitrep-kpi-ven');
        if (venEl) venEl.textContent = ven;
        var globalEl = document.getElementById('sitrep-kpi-global');
        if (globalEl) globalEl.textContent = global;

        var defconColEl = document.getElementById('sitrep-defcon-col');
        if (defconColEl) {
            defconColEl.textContent = highSevCol > 3 ? 'DEFCON 2 · ALERTA ALTA' : 'DEFCON 3 · ELEVADO';
        }
        var defconVenEl = document.getElementById('sitrep-defcon-ven');
        if (defconVenEl) {
            defconVenEl.textContent = highSevVen > 3 ? 'DEFCON 2 · ALERTA SEVERA' : 'DEFCON 3 · ELEVADO';
        }
    },

    updateNewsLoader: function() {
        const loader = document.getElementById('news-loader');
        if (!loader || !this.state.allNews) return;
        const loaded = this.state.newsPage * this.state.newsPerPage;
        if (loaded >= this.state.allNews.length) {
            loader.textContent = '✓ Todas las noticias cargadas (' + this.state.allNews.length + ')';
            loader.style.opacity = '0.5';
        } else {
            loader.textContent = '⬇ ' + (this.state.allNews.length - loaded) + ' noticias más — desplázate';
            loader.style.opacity = '1';
        }
    },

    initInfiniteScroll: function() {
        const tabNews = document.getElementById('tab-news');
        if (!tabNews) return;
        if (this._scrollHandler) tabNews.removeEventListener('scroll', this._scrollHandler);
        this._scrollHandler = () => {
            if (!this.state.allNews || this.state.allNews.length === 0) return;
            if (tabNews.scrollTop + tabNews.clientHeight >= tabNews.scrollHeight - 100) {
                const loaded = this.state.newsPage * this.state.newsPerPage;
                if (loaded < this.state.allNews.length) {
                    this.renderNewsPage(this.state.newsPage + 1);
                }
            }
        };
        tabNews.addEventListener('scroll', this._scrollHandler);
    },

    resetNewsView: function() {
        const grid = document.getElementById('news-grid');
        if (!grid) return;
        
        grid.style.transition = 'opacity 0.2s ease';
        grid.style.opacity = '0';
        
        setTimeout(() => {
            grid.innerHTML = '';
            this.renderNewsPage(1);
            this.filterNews();
            grid.style.opacity = '1';
        }, 200);
    },

    _cleanOpacity: function() {
        var grid = document.getElementById('news-grid');
        if (grid) grid.style.opacity = '1';
    },

    preloadAllTabs: function() {
        console.log('[COBALTO] Precargando todos los módulos en un solo ciclo...');
        var self = this;

        var targets = [
            { tabId: 'tab-social', url: '/api/social', initialData: window._initialSocial, render: function(d) { self.renderSocialTab(d); } },
            { tabId: 'tab-realtime', url: '/api/realtime', initialData: window._initialRealtime, render: function(d) { self.renderRealtimeTab(d); } },
            { tabId: 'tab-narrative', url: '/api/narrative', initialData: window._initialNarratives, render: function(d) { self.renderNarrativeTab(d); } },
            { tabId: 'tab-cyber', url: '/api/cyber', initialData: window._initialCyber, render: function(d) { self._renderCyberGrid(d); } }
        ];

        targets.forEach(function(t) {
            // 0. Hidratar directamente si el servidor ya inyectó el payload inicial
            if (t.initialData) {
                self.state.tabCache[t.tabId] = t.initialData;
                self.db.set(t.tabId, t.initialData);
                // Renderizar siempre en background aunque el tab no esté visible
                t.render(t.initialData);
                if (!self.state.tabRendered) self.state.tabRendered = {};
                self.state.tabRendered[t.tabId] = true;
                return;
            }

            self.utils.fetchWithTimeout(t.url)
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    self.state.tabCache[t.tabId] = data;
                    self.db.set(t.tabId, data);
                    // Renderizar siempre en background — el tab ya tendrá datos cuando se abra
                    t.render(data);
                    if (!self.state.tabRendered) self.state.tabRendered = {};
                    self.state.tabRendered[t.tabId] = true;
                })
                .catch(function(e) {
                    console.warn('[COBALTO] Error precargando ' + t.tabId, e);
                });
        });

        if (window._initialMapData) {
            if (window.CobaltoMap) {
                window.CobaltoMap.state.currentPoints = [];
                if (window._initialMapData.geo_points) window.CobaltoMap.state.currentPoints.push.apply(window.CobaltoMap.state.currentPoints, window._initialMapData.geo_points);
                if (window._initialMapData.ai_geopoints) window.CobaltoMap.state.currentPoints.push.apply(window.CobaltoMap.state.currentPoints, window._initialMapData.ai_geopoints);
            }
        } else {
            self.utils.fetchWithTimeout('/api/map-data')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (window.CobaltoMap) {
                        window.CobaltoMap.state.currentPoints = [];
                        if (data.geo_points) window.CobaltoMap.state.currentPoints.push.apply(window.CobaltoMap.state.currentPoints, data.geo_points);
                        if (data.ai_geopoints) window.CobaltoMap.state.currentPoints.push.apply(window.CobaltoMap.state.currentPoints, data.ai_geopoints);
                    }
                })
                .catch(function() {});
        }
    },

    injectSkeletonLoader: function(tabId) {
        var containerId = {
            'tab-social': 'social-list',
            'tab-realtime': 'rt-grid',
            'tab-narrative': 'narrative-list',
            'tab-cyber': 'cyber-grid',
            'tab-timeline': 'timeline-cib-container',
            'tab-analytics': 'source-health-tbody',
            'tab-user-search': 'user-search-results'
        }[tabId];

        if (tabId === 'tab-timeline') {
            var cib = document.getElementById('timeline-cib-container');
            var alerts = document.getElementById('timeline-alerts-container');
            if (cib) cib.innerHTML = '<div class="skeleton-card"><div class="skeleton-line wide"></div><div class="skeleton-line medium"></div><div class="skeleton-line narrow"></div></div>';
            if (alerts) alerts.innerHTML = '<div class="skeleton-card"><div class="skeleton-line wide"></div><div class="skeleton-line medium"></div></div>';
            return;
        }

        if (tabId === 'tab-analytics') {
            var kpis = document.querySelector('.kpi-row') || document.querySelector('.grid-4');
            if (kpis) {
                kpis.innerHTML = '';
                for (var i = 0; i < 4; i++) {
                    kpis.innerHTML += '<div class="news-card" style="padding:1.2rem;"><div class="skeleton-line narrow"></div><div class="skeleton-line wide" style="height:2rem;margin-top:0.5rem;"></div></div>';
                }
            }
            var sh = document.getElementById('source-health-tbody');
            if (sh) {
                var rows = '';
                for (var i = 0; i < 5; i++) {
                    rows += '<tr><td colspan="4" style="padding:0.5rem;"><div class="skeleton-line wide"></div></td></tr>';
                }
                sh.innerHTML = rows;
            }
            return;
        }

        if (tabId === 'tab-user-search') {
            var us = document.getElementById('user-search-results');
            if (us) {
                var html = '';
                for (var i = 0; i < 3; i++) {
                    html += '<div class="skeleton-card"><div class="skeleton-line wide"></div><div class="skeleton-line medium"></div><div class="skeleton-line narrow"></div></div>';
                }
                us.innerHTML = html;
            }
            return;
        }

        var container = document.getElementById(containerId);
        if (!container) return;

        // Si ya hay datos reales cargados en memoria, no sobreescribir con skeletons
        if (this.state.tabCache[tabId]) return;

        var html = '';
        if (tabId === 'tab-cyber') {
            for (var i = 0; i < 4; i++) {
                html += '<div class="news-card skeleton-card">' +
                    '<div class="news-header">' +
                    '<span class="skeleton-line skeleton-source"></span>' +
                    '<span class="skeleton-line skeleton-time"></span></div>' +
                    '<div class="skeleton-line skeleton-title"></div>' +
                    '<div class="skeleton-line skeleton-text"></div>' +
                    '<div class="skeleton-line skeleton-text-short"></div></div>';
            }
        } else if (tabId === 'tab-social') {
            for (var i = 0; i < 3; i++) {
                html += '<div class="social-group skeleton-group" style="padding:15px; border:1px solid rgba(255,255,255,0.05); margin-bottom:15px; border-radius:10px;">' +
                    '<div class="skeleton-line skeleton-title" style="width:50%; height:20px;"></div>' +
                    '<div style="margin-top:15px;">' +
                    '<div class="skeleton-line skeleton-text"></div>' +
                    '<div class="skeleton-line skeleton-text-short"></div></div></div>';
            }
        } else if (tabId === 'tab-realtime') {
            for (var i = 0; i < 4; i++) {
                html += '<div class="rt-card skeleton-card" style="padding:15px; border:1px solid rgba(255,255,255,0.05); margin-bottom:10px; border-radius:10px;">' +
                    '<div style="display:flex; justify-content:space-between; margin-bottom:10px;">' +
                    '<div class="skeleton-line skeleton-source" style="width:60px;"></div>' +
                    '<div class="skeleton-line skeleton-time" style="width:40px;"></div></div>' +
                    '<div class="skeleton-line skeleton-title"></div>' +
                    '<div class="skeleton-line skeleton-text"></div></div>';
            }
        } else if (tabId === 'tab-narrative') {
            for (var i = 0; i < 3; i++) {
                html += '<div class="social-group skeleton-group" style="padding:15px; border:1px solid rgba(255,255,255,0.05); margin-bottom:15px; border-radius:10px;">' +
                    '<div class="skeleton-line skeleton-title" style="width:40%; height:22px;"></div>' +
                    '<div class="skeleton-line skeleton-text" style="margin-top:10px;"></div>' +
                    '<div class="skeleton-line skeleton-text-short"></div></div>';
            }
        }

        if (html) {
            container.innerHTML = html;
        }
    },

    removeSkeletonLoader: function(tabId) {
        var containerId = {'tab-social':'social-list','tab-realtime':'rt-grid','tab-narrative':'narrative-list','tab-cyber':'cyber-grid','tab-timeline':'timeline-cib-container','tab-analytics':'source-health-tbody','tab-user-search':'user-search-results'}[tabId];
        if (tabId === 'tab-timeline') {
            ['timeline-cib-container', 'timeline-alerts-container'].forEach(function(id) {
                var el = document.getElementById(id);
                if (el) {
                    var sk = el.querySelectorAll('.skeleton-card');
                    if (sk.length > 0 && !el.querySelector('.rt-card, .news-card')) {
                        sk.forEach(function(s) { s.remove(); });
                    }
                }
            });
            return;
        }
        if (tabId === 'tab-analytics') {
            var kpis = document.querySelector('.kpi-row') || document.querySelector('.grid-4');
            if (kpis) {
                var sk = kpis.querySelectorAll('.skeleton-card');
                if (sk.length > 0) sk.forEach(function(s) { s.remove(); });
            }
            var sh = document.getElementById('source-health-tbody');
            if (sh) {
                var sr = sh.querySelectorAll('.skeleton-line');
                if (sr.length > 0) sh.innerHTML = '';
            }
            return;
        }
        if (tabId === 'tab-user-search') {
            var us = document.getElementById('user-search-results');
            if (us) {
                var sk = us.querySelectorAll('.skeleton-card');
                if (sk.length > 0) sk.forEach(function(s) { s.remove(); });
            }
            return;
        }
        var container = document.getElementById(containerId);
        if (!container) return;
        var skeletonItems = container.querySelectorAll('.skeleton-group, .skeleton-card, .skeleton');
        if (skeletonItems.length > 0 && !container.querySelector('.news-card, .social-group, .rt-card')) {
            container.innerHTML = '';
        }
    },

    retryTabLoad: function(tabId, apiUrl) {
        var tab = document.getElementById(tabId);
        if (tab) {
            var retryEl = tab.querySelector('.tab-retry');
            if (retryEl) retryEl.remove();
        }
        this._fetchAndCacheTab(tabId, apiUrl, null);
    },

    lazyLoadTab: async function(tabId, apiUrl, renderFn) {
        // 1. Memoria + Ya renderizado
        if (this.state.tabRendered && this.state.tabRendered[tabId]) {
            return this.state.tabCache[tabId];
        }

        if (this.state.tabCache[tabId]) {
            renderFn(this.state.tabCache[tabId]);
            if (!this.state.tabRendered) this.state.tabRendered = {};
            this.state.tabRendered[tabId] = true;
            return this.state.tabCache[tabId];
        }

        // Mostrar esqueletos visuales mientras se consulta DB local o red
        this.injectSkeletonLoader(tabId);

        // 2. IndexedDB (Persistencia Offline)
        const cached = await this.db.get(tabId);
        if (cached) {
            this.state.tabCache[tabId] = cached;
            renderFn(cached);
            if (!this.state.tabRendered) this.state.tabRendered = {};
            this.state.tabRendered[tabId] = true;
            this._refreshTabInBackground(tabId, apiUrl, renderFn);
            return cached;
        }

        // 3. Red
        return this._fetchAndCacheTab(tabId, apiUrl, renderFn);
    },

    _fetchAndCacheTab: function(tabId, apiUrl, renderFn) {
        if (this.state.tabLoading[tabId]) return this.state.tabLoading[tabId];

        var self = this;
        this.state.tabLoading[tabId] = this.utils.fetchWithTimeout(apiUrl)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                delete self.state.tabLoading[tabId];
                self.state.tabCache[tabId] = data;
                self.db.set(tabId, data);
                if (renderFn) {
                    renderFn(data);
                    if (!self.state.tabRendered) self.state.tabRendered = {};
                    self.state.tabRendered[tabId] = true;
                }
                return data;
            })
            .catch(function() {
                delete self.state.tabLoading[tabId];
                var tab = document.getElementById(tabId);
                if (tab) {
                    var container = tab.querySelector('[data-skeleton]');
                    if (!container) {
                        var firstEl = tab.querySelector('.flex-column, .panel-tactical, .grid') || tab;
                        firstEl.insertAdjacentHTML('afterbegin', '<div class="tab-retry" style="text-align:center;padding:3rem;"><div style="font-size:2rem;margin-bottom:1rem;opacity:0.5;">📡</div><div style="color:var(--text-muted);margin-bottom:1rem;">No se pudieron cargar los datos tácticos.</div><button onclick="CobaltoCore.retryTabLoad(\'' + tabId + '\',\'' + apiUrl + '\',\'error\')" class="btn-tactical">↻ REINTENTAR</button></div>');
                    }
                }
                self.removeSkeletonLoader(tabId);
                return self.state.tabCache[tabId] || null;
            });
        return this.state.tabLoading[tabId];
    },

    _refreshTabInBackground: function(tabId, apiUrl, renderFn) {
        var self = this;
        this.utils.fetchWithTimeout(apiUrl)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.state.tabCache[tabId] = data;
                self.db.set(tabId, data);
            })
            .catch(function() {});
    },

    _cyberItems: [],
    _cyberFilterCategory: 'ALL',
    _cyberSearchQuery: '',

    _stripHtml: function(str) {
        if (!str) return '';
        return String(str)
            .replace(/<br\s*\/?>/gi, ' ')
            .replace(/<\/p>/gi, ' ')
            .replace(/<[^>]*>/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    },

    _getCyberCategory: function(item) {
        var txt = ((item.title || '') + ' ' + (item.summary || '') + ' ' + (item.source || '')).toLowerCase();
        if (txt.includes('ransomware') || txt.includes('0day') || txt.includes('zero-day') || txt.includes('exploit') || txt.includes('lockbit') || txt.includes('blackcat') || item.severity === 'ALTA' || item.severity === 'CRÍTICO') return 'CRITICAL';
        if (txt.includes('darknet') || txt.includes('pastebin') || txt.includes('leak') || txt.includes('dump') || txt.includes('credenciales')) return 'DARKNET';
        if (txt.includes('vencert') || txt.includes('cert') || txt.includes('advisory') || txt.includes('boletín')) return 'VENCERT';
        return 'CYBER';
    },

    renderCyberTab: function() {
        var self = this;
        this.lazyLoadTab('tab-cyber', '/api/cyber', function(data) {
            self._cyberItems = data || [];
            self._updateCyberKPIs(self._cyberItems);
            self._renderCyberGrid(self._cyberItems);
        });
    },

    _updateCyberKPIs: function(items) {
        var self = this;
        var total = items.length;
        var r = 0, d = 0, v = 0;
        items.forEach(function(item) {
            var cat = item.category || self._getCyberCategory(item);
            if (cat === 'CRITICAL') r++;
            else if (cat === 'DARKNET') d++;
            else if (cat === 'VENCERT') v++;
        });
        var elTotal = document.getElementById('cyber-kpi-total');
        var elR = document.getElementById('cyber-kpi-ransomware');
        var elD = document.getElementById('cyber-kpi-darknet');
        var elV = document.getElementById('cyber-kpi-vencert');
        if (elTotal) elTotal.textContent = total;
        if (elR) elR.textContent = r;
        if (elD) elD.textContent = d;
        if (elV) elV.textContent = v;
    },

    filterCyber: function(category, btn) {
        this._cyberFilterCategory = category || 'ALL';
        if (btn && btn.parentElement) {
            btn.parentElement.querySelectorAll('.btn-cyber-filter').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
        }
        this._applyCyberFilters();
    },

    searchCyber: function(query) {
        this._cyberSearchQuery = (query || '').toLowerCase().trim();
        this._applyCyberFilters();
    },

    _applyCyberFilters: function() {
        var self = this;
        var cat = self._cyberFilterCategory || 'ALL';
        var q = self._cyberSearchQuery || '';
        var filtered = self._cyberItems.filter(function(item) {
            var itemCat = item.category || self._getCyberCategory(item);
            if (cat !== 'ALL' && itemCat !== cat) return false;
            if (q) {
                var txt = (self._stripHtml(item.title) + ' ' + self._stripHtml(item.summary) + ' ' + (item.source || '')).toLowerCase();
                if (!txt.includes(q)) return false;
            }
            return true;
        });
        self._renderCyberGrid(filtered);
    },

    _renderCyberGrid: function(data) {
        var grid = document.getElementById('cyber-grid');
        if (!grid) return;
        var self = this;
        var items = data || [];
        if (!items.length) {
            grid.innerHTML =
                '<div class="empty-state" id="cyber-empty" style="grid-column: 1 / -1;">' +
                '<div class="empty-icon">\uD83D\uDEE1\uFE0F</div>' +
                '<p style="color:#00ffaa;">NINGUNA ALERTA CIBERN\u00C9TICA COINCIDE CON EL FILTRO</p>' +
                '<p style="font-size:0.8rem; color:var(--text-muted);">Intente modificar los t\u00E9rminos de b\u00FAsqueda o cambiar el filtro de severidad.</p>' +
                '</div>';
            return;
        }
        var esc = self.utils.escapeHTML;
        var html = '';
        items.forEach(function(item) {
            var cat = item.category || self._getCyberCategory(item);
            var borderColor = '#00ffaa';
            var badgeText = '\uD83D\uDCBB CYBER INTEL';
            var badgeBg = 'rgba(0, 255, 170, 0.1)';
            var badgeColor = '#00ffaa';

            if (cat === 'CRITICAL') {
                borderColor = '#ff4444';
                badgeText = '\u2623\uFE0F RANSOMWARE / EXPLOIT';
                badgeBg = 'rgba(255, 68, 68, 0.15)';
                badgeColor = '#ff4444';
            } else if (cat === 'DARKNET') {
                borderColor = '#ffaa00';
                badgeText = '\uD83D\uDD03 DARKNET / LEAK';
                badgeBg = 'rgba(255, 170, 0, 0.15)';
                badgeColor = '#ffaa00';
            } else if (cat === 'VENCERT') {
                borderColor = '#44aaee';
                badgeText = '\uD83D\uDEE1\uFE0F CERT ADVISORY';
                badgeBg = 'rgba(68, 170, 238, 0.15)';
                badgeColor = '#44aaee';
            }

            var cleanTitle = self._stripHtml(item.title || 'Alerta Cibern\u00E9tica');
            var cleanSummary = self._stripHtml(item.summary || '');
            var titleStr = esc(cleanTitle);
            var summaryStr = esc(cleanSummary);
            var sourceStr = esc(item.source || 'SOC Cyber');
            var timeStr = esc(item.published || 'Reciente');
            var linkStr = esc(item.link || '#');

            html += '<div class="panel-glass" style="padding: 1rem; border-left: 4px solid ' + borderColor + '; display: flex; flex-direction: column; justify-content: space-between; position: relative;">' +
                '<div>' +
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; gap: 0.5rem;">' +
                '<span style="background:' + badgeBg + '; color:' + badgeColor + '; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; font-family: monospace; font-weight: bold;">' + badgeText + '</span>' +
                '<span style="font-size: 0.65rem; color: #888; font-family: monospace;">' + timeStr + '</span>' +
                '</div>' +
                '<a href="' + linkStr + '" target="_blank" rel="noopener noreferrer" style="font-weight: 600; font-size: 0.88rem; color: #f1f5f9; text-decoration: none; display: block; margin-bottom: 0.5rem; line-height: 1.3;">' + titleStr + '</a>' +
                '<p style="margin: 0; font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">' + summaryStr + '</p>' +
                '</div>' +
                '<div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.5rem;">' +
                '<span style="font-size: 0.68rem; color: var(--text-muted); font-family: monospace;">Fuente: ' + sourceStr + '</span>' +
                '<div style="display: flex; gap: 0.4rem;">' +
                '<button class="btn-tactical" style="padding: 2px 6px; font-size: 0.65rem;" data-title="' + titleStr + '" data-summary="' + summaryStr + '" onclick="if(window.CobaltoIntel) window.CobaltoIntel.sendItemToRag(this)">\uD83C\uDFAF RAG IA</button>' +
                '<a href="' + linkStr + '" target="_blank" rel="noopener noreferrer" style="font-size: 0.65rem; color: var(--primary); text-decoration: none; padding: 2px 6px; border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 4px;">Abrir \u2197</a>' +
                '</div>' +
                '</div>' +
                '</div>';
        });
        grid.innerHTML = html;
    },

    categorizeSource: function(srcName) {
        var srcLower = srcName.toLowerCase();
        var map = {
            "📱 Redes Sociales": ["extendidas", "especiales", "reddit", "telegram", "mastodon", "nitter", "tiktok", "instagram", "bluesky"],
            "📰 Noticias": ["news", "agregadores", "latinoam", "intl", "hub", "prensa"],
            "💻 Tecnología": ["github", "stackoverflow", "tech", "osint", "cyber", "hacker", "security"],
            "📊 Datos": ["datos", "crypto", "clima", "econom", "covid", "banca", "finanzas", "dolar"],
            "🕵️ OSINT Deep": ["onion", "dorks", "darkweb", "pastebin"],
            "🛰️ Realtime": ["satélite", "scanner", "radar", "realtime", "vuelos", "marítimo"]
        };
        for (var cat in map) {
            var keywords = map[cat];
            for (var i = 0; i < keywords.length; i++) {
                if (srcLower.indexOf(keywords[i]) !== -1) {
                    return cat;
                }
            }
        }
        return "🌎 Internacional";
    },

    renderSocialTab: function(data) {
        var list = document.getElementById('social-list');
        if (!list) return;
        var hasItems = data && data.sources ? Object.values(data.sources).some(function(v) { return Array.isArray(v) && v.length > 0; }) : false;
        if (!hasItems) {
            list.innerHTML =
                '<div class="empty-state" style="padding:2rem;">' +
                '<div class="empty-icon">📡</div>' +
                '<p style="color:var(--primary);">SIN DATOS SOCIALES</p>' +
                '<p style="font-size:0.8rem; color:var(--text-muted);">No hay publicaciones de redes sociales disponibles en este momento.</p>' +
                '</div>';
            const srcEl = document.getElementById('social-src-display');
            if (srcEl) srcEl.textContent = '0 categorías';
            const totalEl = document.getElementById('social-total-display');
            if (totalEl) totalEl.textContent = '0 items';
            return;
        }
        
        var groups = {};
        for (var src in data.sources) {
            if (!data.sources.hasOwnProperty(src)) continue;
            var items = data.sources[src] || [];
            if (items.length === 0) continue;
            var cat = this.categorizeSource(src);
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push({ name: src, items: items });
        }
        
        var html = '';
        var catCount = 0;
        var totalItems = 0;
        
        for (var cat in groups) {
            if (!groups.hasOwnProperty(cat)) continue;
            html += `<div class="social-category" style="margin-bottom:1.5rem;">
                <h3 style="color:var(--primary);font-family:'Roboto Mono',monospace;font-size:0.8rem;margin:0 0 0.5rem 0;padding-bottom:0.4rem;border-bottom:1px solid rgba(0,229,255,0.1);letter-spacing:1px;">${this.utils.escapeHTML(cat)}</h3>`;
            
            var sourcesList = groups[cat];
            sourcesList.forEach(srcObj => {
                var src = srcObj.name;
                var items = srcObj.items;
                totalItems += items.length;
                var prefix = src.split(':')[0].trim();
                
                html += `<div class="social-group" data-src="${this.utils.escapeHTML(src.toLowerCase())}" data-prefix="${this.utils.escapeHTML(prefix.toLowerCase())}">
                    <div class="social-header" onclick="CobaltoIntel.toggleSocialGroup(this)">
                        <span>${this.utils.escapeHTML(src)}</span>
                        <span class="social-count">${items.length}</span>
                        <span class="social-toggle" style="transition:transform 0.3s;margin-left:auto;font-size:0.8rem;">\u25B6</span>
                    </div>
                    <div class="social-items" style="display:none;">`;
                
                var maxItems = 10;
                var hiddenItems = [];
                var renderedCount = 0;
                for (var i = 0; i < items.length; i++) {
                    if (renderedCount >= maxItems) {
                        hiddenItems.push(items[i]);
                        continue;
                    }
                    var item = items[i];
                    var searchText = ((item.title || '') + ' ' + (item.summary || '') + ' ' + (item.source || '')).toLowerCase();
                    var itemSrc = item.source || src || '';
                    var itemLink = item.link || '#';
                    var isReddit = itemSrc.indexOf('Reddit') !== -1 || itemSrc.indexOf('r/') !== -1 || itemLink.indexOf('reddit.com') !== -1;
                    var isTelegram = itemSrc.indexOf('Telegram') !== -1 || itemLink.indexOf('t.me') !== -1;
                    var tagHtml = '';
                    if (isReddit) {
                        tagHtml = `<span class="social-tag social-tag-reddit">🤖 ${this.utils.escapeHTML(itemSrc)}</span>`;
                    } else if (isTelegram) {
                        tagHtml = `<span class="social-tag social-tag-telegram">✈️ ${this.utils.escapeHTML(itemSrc)}</span>`;
                    } else if (itemSrc) {
                        tagHtml = `<span class="social-tag">📡 ${this.utils.escapeHTML(itemSrc)}</span>`;
                    }
                    var pubTime = item.published ? `<span style="font-size:0.7rem; color:var(--text-muted); margin-left:auto; font-family:'Roboto Mono', monospace;">${this.utils.escapeHTML(item.published.substring(0, 16))}</span>` : '';

                    var cleanT = (item.title || '').trim();
                    var cleanS = (item.summary || '').trim();
                    var showSummary = cleanS && cleanS !== cleanT && !cleanS.startsWith(cleanT.substring(0, 60)) && !cleanT.startsWith(cleanS.substring(0, 60));

                    html += `<div class="social-item ${isReddit ? 'reddit-item' : ''}" data-search-text="${this.utils.escapeHTML(searchText)}">
                        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem; flex-wrap:wrap;">
                            ${tagHtml}
                            ${pubTime}
                        </div>
                        <a href="${this.utils.escapeHTML(itemLink)}" target="_blank" rel="noopener noreferrer" style="font-weight:600; text-decoration:none;">${this.utils.escapeHTML(item.title || '')}</a>
                        ${showSummary ? `<p style="margin-top:0.3rem; font-size:0.8rem; color:var(--text-muted); line-height:1.4;">${this.utils.escapeHTML(item.summary)}</p>` : ''}
                    </div>`;
                    renderedCount++;
                }
                
                if (hiddenItems.length > 0) {
                    html += '<div class="social-show-more" style="padding:0.5rem 1rem;font-size:0.75rem;color:var(--primary);border-top:1px solid rgba(255,255,255,0.04);cursor:pointer;text-align:center;" data-items=\'' + this.utils.escapeHTML(JSON.stringify(hiddenItems.map(function(h) { return {title: h.title, summary: h.summary, link: h.link}; }))) + '\'>+' + hiddenItems.length + ' m\u00E1s \u25BC</div>';
                }
                html += `</div></div>`;
            });
            
            html += `</div>`;
            catCount++;
        }
        
        list.style.opacity = '0';
        list.innerHTML = html;
        requestAnimationFrame(() => { list.style.transition = 'opacity 0.2s ease'; list.style.opacity = '1'; });
        
        const srcEl = document.getElementById('social-src-display');
        if (srcEl) srcEl.textContent = catCount + ' categorías';
        const totalEl = document.getElementById('social-total-display');
        if (totalEl) totalEl.textContent = totalItems + ' items';
        if (typeof window.CobaltoIntel?.filterSocial === 'function') window.CobaltoIntel.filterSocial();
    },

    fetchNarrativeData: function() {
        var self = this;
        this.utils.fetchWithTimeout('/api/narrative')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var container = document.getElementById('tab-narrative');
                if (container) self.renderNarrativeTab(data);
            })
            .catch(function() {});
    },

    renderNarrativeTab: function(data) {
        var container = document.getElementById('narrative-list');
        if (!container) return;
        if (!data || !data.narratives || !data.narratives.length) {
            container.innerHTML =
                '<div class="empty-state" style="padding:2rem;">' +
                '<div class="empty-icon">📊</div>' +
                '<p style="color:var(--primary);">SIN NARRATIVAS ACTIVAS</p>' +
                '<p style="font-size:0.8rem; color:var(--text-muted);">El motor de análisis lingüístico no ha detectado campañas de influencia activas en las últimas horas.</p>' +
                '</div>';
            return;
        }

        // Update KPI metrics in header if present
        var kpiCount = document.getElementById('narrative-kpi-count');
        var kpiTop = document.getElementById('narrative-kpi-top');
        var kpiSources = document.getElementById('narrative-kpi-sources');
        var kpiMentions = document.getElementById('narrative-kpi-mentions');

        var totalMentions = 0;
        var uniqueSources = new Set();
        data.narratives.forEach(n => {
            totalMentions += (n.count || 0);
            (n.sources || []).forEach(s => uniqueSources.add(s));
        });

        if (kpiCount) kpiCount.textContent = data.narratives.length;
        if (kpiTop) kpiTop.textContent = data.narratives[0] ? data.narratives[0].name : '--';
        if (kpiSources) kpiSources.textContent = uniqueSources.size || '--';
        if (kpiMentions) kpiMentions.textContent = totalMentions;

        var esc = this.utils.escapeHTML;
        var html = '';
        data.narratives.forEach(function(n) {
            var color = esc(n.color || 'var(--primary)');
            var nameStr = esc(n.name || 'Narrativa');
            var descStr = esc(n.description || '');
            var sourcesList = n.sources || [];
            
            html += '<div class="news-card narrative-card" style="border-left:3px solid ' + color + ';" data-search="' + esc((n.name + ' ' + n.description).toLowerCase()) + '" data-category="' + esc(n.name.substring(0, 2)) + '">';
            html += '<div class="news-header">';
            html += '<span class="news-source" style="font-weight:700; font-size:0.95rem;">' + nameStr + '</span>';
            html += '<span class="news-time" style="background:rgba(0,229,255,0.1); padding:0.2rem 0.55rem; border-radius:4px; font-weight:600; color:var(--primary);">' + (n.count || 0) + ' menciones</span>';
            html += '</div>';
            html += '<div style="margin-top:0.5rem;">';
            html += '<p style="color:var(--text-muted); font-size:0.85rem; margin:0 0 0.5rem 0;">' + descStr + '</p>';
            
            if (sourcesList.length) {
                html += '<div style="display:flex; gap:0.3rem; flex-wrap:wrap; margin-top:0.4rem;">';
                sourcesList.forEach(function(src) {
                    html += '<span style="font-size:0.7rem; background:rgba(255,255,255,0.05); color:var(--text-muted); border:1px solid var(--border-color); padding:0.1rem 0.4rem; border-radius:3px;">' + esc(src) + '</span>';
                });
                html += '</div>';
            }
            html += '</div>';

            if (n.articles && n.articles.length) {
                html += '<div style="margin-top:0.8rem; padding-top:0.8rem; border-top:1px solid var(--border-color); display:flex; flex-direction:column; gap:0.35rem;">';
                for (var i = 0; i < Math.min(n.articles.length, 5); i++) {
                    var a = n.articles[i];
                    var titleClean = esc(a.title || 'Artículo');
                    var sourceClean = esc(a.source || '');
                    var linkUrl = esc(a.link || '#');
                    html += '<div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem;">';
                    html += '<a href="' + linkUrl + '" target="_blank" class="narrative-article-link" style="color:var(--primary); font-size:0.8rem; text-decoration:none; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">' + titleClean + '</a>';
                    if (sourceClean) {
                        html += '<span style="font-size:0.7rem; color:var(--text-muted); white-space:nowrap;">' + sourceClean + '</span>';
                    }
                    html += '</div>';
                }
                html += '</div>';
            }

            var safePrompt = nameStr.replace(/'/g, "\\'");
            html += '<div style="margin-top:0.8rem; padding-top:0.6rem; border-top:1px dashed var(--border-color); display:flex; justify-content:flex-end;">';
            html += '<button class="btn-tactical" style="font-size:0.72rem; padding:0.25rem 0.6rem;" onclick="if(window.openRagModal){window.openRagModal(\'Analizar campaña narrativa: ' + safePrompt + '\');}">🎯 RAG IA</button>';
            html += '</div>';

            html += '</div>';
        });
        container.innerHTML = html;
        this.filterNarratives();
    },

    filterNarratives: function() {
        var q = document.getElementById('narrative-search');
        var term = q ? q.value.trim().toLowerCase() : '';
        document.querySelectorAll('.narrative-card').forEach(function(card) {
            var search = card.getAttribute('data-search') || '';
            card.style.display = !term || search.includes(term) ? 'block' : 'none';
        });
    },

    filterNarrativeCategory: function(cat, btn) {
        if (btn && btn.parentNode) {
            btn.parentNode.querySelectorAll('.btn-tactical').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }
        document.querySelectorAll('.narrative-card').forEach(function(card) {
            if (cat === 'all') {
                card.style.display = 'block';
            } else {
                var search = card.getAttribute('data-search') || '';
                card.style.display = search.includes(cat.toLowerCase()) ? 'block' : 'none';
            }
        });
    },

    renderRealtimeTab: function(data) {
        if (window.CobaltoRT) {
            window.CobaltoRT.data = window.CobaltoRT.parseData(data);
            window.CobaltoRT.render(window.CobaltoRT.data);
            return;
        }
        var grid = document.getElementById('rt-content-area') || document.getElementById('rt-grid');
        if (!grid) return;
        var items = [];
        if (data) {
            if (data.flight_data && data.flight_data.flights) {
                data.flight_data.flights.forEach(f => { if (f && f.callsign) { f._rt_source = f.is_emergency ? '🚨 Vuelo en Emergencia' : 'Vuelos'; f.severity = f.is_emergency ? 'critical' : 'info'; f.link = f.link || 'https://globe.adsbexchange.com/?icao=' + (f.icao || ''); items.push(f); } });
            }
            if (data.vessel_data && data.vessel_data.vessels) {
                data.vessel_data.vessels.forEach(v => { if (v && v.name) { v._rt_source = 'Embarcaciones'; v.link = v.link || '#'; items.push(v); } });
            }
            if (data.events_data) {
                (data.events_data.earthquakes || []).forEach(eq => { if (eq) { eq._rt_source = 'Eventos'; eq.link = eq.link || eq.url || 'https://earthquake.usgs.gov/'; items.push(eq); } });
                (data.events_data.weather_alerts || []).forEach(wa => { if (wa) { wa._rt_source = 'Eventos: Clima'; wa.link = wa.link || '#'; items.push(wa); } });
                (data.events_data.security_incidents || []).forEach(si => { if (si) { si._rt_source = 'Eventos: Seguridad'; si.link = si.link || '#'; items.push(si); } });
                (data.events_data.network_outages || []).forEach(no => { if (no) { no._rt_source = no._rt_source || 'Apagón de Red'; no.severity = no.severity || (no.drop_percentage > 60 ? 'critical' : 'warning'); items.push(no); } });
            }
            if (data.open_data) {
                (data.open_data.economic || []).forEach(d => { if (d && d.title) { d._rt_source = 'Open Data: Economía'; d.link = d.link || '#'; items.push(d); } });
                (data.open_data.conflict || []).forEach(d => { if (d && d.title) { d._rt_source = 'Open Data: Conflicto'; d.link = d.link || '#'; items.push(d); } });
                (data.open_data.demographic || []).forEach(d => { if (d && d.title) { d._rt_source = 'Open Data: Demografía'; d.link = d.link || '#'; items.push(d); } });
            }
        }
        if (!items.length) {
            grid.innerHTML =
                '<div class="empty-state" id="rt-empty">' +
                '<div class="empty-icon">\uD83D\uDCE1</div>' +
                '<p style="color:var(--primary);">SIN DATOS EN TIEMPO REAL</p>' +
                '<p style="font-size:0.8rem; color:var(--text-muted);">Los sensores de vuelos, embarcaciones, eventos y datos abiertos se actualizan cada 30 minutos.</p>' +
                '</div>';
            return;
        }
        var html = '';
        var outageIds = [];
        items.forEach(item => {
            var cat = (item._rt_source || 'General').split(':')[0];
            var severity = item.severity || '';
            if (!severity) {
                if (item.mag && item.mag >= 6) severity = 'critical';
                else if (item.mag && item.mag >= 4.5) severity = 'warning';
                else if (item.alert_level === 'Red' || item.alert_level === 'Orange') severity = 'warning';
                else severity = 'info';
            }
            var isOutage = item.type === 'network_outage';
            var outageClass = isOutage ? ' card-digital-outage' : '';
            var cardId = 'rt-card-' + (item.id || Date.now() + Math.random().toString(36).substr(2, 6));
            if (isOutage) outageIds.push(cardId);
            html += `<div id="${cardId}" class="rt-card severity-${severity}${outageClass}" data-title="${this.utils.escapeHTML((item.title||'').toLowerCase())}" data-source="${this.utils.escapeHTML((item.source||'').toLowerCase())}" data-category="${this.utils.escapeHTML(cat)}" data-published="${this.utils.escapeHTML(item.published||'')}" data-type="${this.utils.escapeHTML(item.type||'')}" data-severity="${severity}">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <span class="rt-source">${isOutage ? '⚡ ' : severity === 'critical' ? '🔴 ' : severity === 'warning' ? '🟠 ' : '🔵 '}${this.utils.escapeHTML(item._rt_source||'')}</span>
                    <span class="rt-time">${this.utils.escapeHTML(item.published||'')}</span>
                </div>
                <a href="${this.utils.escapeHTML(item.link||'#')}" target="_blank" rel="noopener noreferrer" class="rt-title">${this.utils.escapeHTML(item.title||'')}</a>
                ${isOutage ? `
                <div class="outage-telemetry-box" style="background:rgba(0,0,0,0.5);padding:8px;border-radius:4px;margin-top:8px;border-left:3px solid #ff0000;font-family:'Roboto Mono',monospace;font-size:0.8rem;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="color:#888;">INFRAESTRUCTURA:</span>
                        <span style="color:#fff;">${this.utils.escapeHTML(item.provider||'Desconocido')} (AS${this.utils.escapeHTML(item.asn||'N/A')})</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;">
                        <span style="color:#888;">PÉRDIDA DE TRÁFICO:</span>
                        <span class="metric-drop-value">▼ ${this.utils.escapeHTML(item.drop_percentage||'0')}%</span>
                    </div>
                </div>` : `<p class="rt-summary">${this.utils.escapeHTML(item.summary||'')}</p>`}
            </div>`;
        });
        grid.style.opacity = '0';
        grid.innerHTML = html;
        requestAnimationFrame(() => { grid.style.transition = 'opacity 0.2s ease'; grid.style.opacity = '1'; });
        const totalEl = document.getElementById('rt-total-display');
        if (totalEl) totalEl.textContent = items.length + ' items';
        if (typeof window.CobaltoIntel?.filterRT === 'function') window.CobaltoIntel.filterRT();

        this._updatePredictiveBadge();

        // Auto-silence visual: remover animación de parpadeo tras 45s
        if (outageIds.length) {
            setTimeout(function() {
                outageIds.forEach(function(id) {
                    var card = document.getElementById(id);
                    if (!card) return;
                    card.style.animation = 'none';
                    card.style.background = 'linear-gradient(180deg, rgba(40, 0, 0, 0.6) 0%, rgba(10, 15, 26, 1) 100%)';
                    var dropVal = card.querySelector('.metric-drop-value');
                    if (dropVal) dropVal.style.animation = 'none';
                });
            }, 45000);
        }
    },

    _updatePredictiveBadge: function() {
        var badge = document.getElementById('predictive-badge');
        if (!badge) return;
        fetch('/api/predictive/alerts').then(function(r) { return r.json(); }).then(function(data) {
            var active = (data.alerts || []).filter(function(a) { return a.status === 'active'; }).length;
            if (active > 0) {
                badge.textContent = active;
                badge.style.display = 'inline';
            } else {
                badge.style.display = 'none';
            }
        }).catch(function() {});
    },

    switchTab: function(tabId, btnElement) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.nav-button').forEach(b => b.classList.remove('active'));
        
        var targetTab = document.getElementById(tabId);
        if (targetTab) targetTab.classList.add('active');
        if (btnElement) btnElement.classList.add('active');
        
        if (tabId === 'tab-cyber' && !(this.state.tabRendered && this.state.tabRendered['tab-cyber'])) {
            this.lazyLoadTab('tab-cyber', '/api/cyber', data => this._renderCyberGrid(data));
        }

        var titles = {
            'tab-news': 'Reporte de Situación (' + (window._entryMaxAgeHours || 48) + 'h)',
            'tab-intel': 'Inteligencia Clasificada',
            'tab-social': 'Radar Social',
            'tab-alerts': 'Alertas Tácticas',
            'tab-cyber': 'Ciberseguridad',
            'tab-realtime': 'Intel Tiempo Real',
            'tab-narrative': 'Análisis de Narrativas',
            'tab-analytics': 'Analíticas Tácticas',
            'tab-sentiment': 'Análisis de Sentimientos NLP',
            'tab-timeline': 'Cronología Táctica (Timeline)',
            'tab-map': 'Mapa Unificado (OSIRIS + COBALTO)',
            'tab-graph': 'Grafo Social',
            'tab-user-search': 'Búsqueda de Usuarios',
            'tab-osiris-global': 'OSIRIS Global Intelligence',
            'tab-predictive': '⚠️ Alertas Predictivas',
            'tab-actors': 'Perfilamiento de Actores',
            'tab-osiris-recon': 'OSIRIS RECON Toolkit',
            'tab-operators': 'Monitoreo de Operadores BFT',
            'tab-finint': '💳 FININT & Dark Web',
            'tab-humint': '🕵️ HUMINT & Reportes de Campo',
            'tab-config': 'Configuración del Sistema'
        };
        
        var titleEl = document.getElementById('main-title');
        if (titleEl) titleEl.innerText = titles[tabId] || 'Dashboard';

        if (tabId === 'tab-news') this.filterNews();
        if (tabId === 'tab-social') { setTimeout(function() { if (window.CobaltoIntel) CobaltoIntel.filterSocial(); }, 100); }
        if (tabId === 'tab-alerts') { setTimeout(function() { if (window.CobaltoIntel) CobaltoIntel.filterAlerts(); }, 100); }

        if (tabId === 'tab-operators') { if (window.OperatorsManager) window.OperatorsManager.init(); }
        // Solo fetch si el preload aún no terminó (tabRendered protege contra doble petición)
        if (tabId === 'tab-social' && !(this.state.tabRendered && this.state.tabRendered['tab-social'])) this.lazyLoadTab('tab-social', '/api/social', data => this.renderSocialTab(data));
        if (tabId === 'tab-realtime' && !(this.state.tabRendered && this.state.tabRendered['tab-realtime'])) this.lazyLoadTab('tab-realtime', '/api/realtime', data => this.renderRealtimeTab(data));
        if (tabId === 'tab-narrative' && !(this.state.tabRendered && this.state.tabRendered['tab-narrative'])) this.lazyLoadTab('tab-narrative', '/api/narrative', data => this.renderNarrativeTab(data));
        if (tabId === 'tab-analytics') {
            if (window.CobaltoAnalytics) {
                window.CobaltoAnalytics.init();
            } else {
                window._pendingAnalyticsInit = true;
            }
            setTimeout(function() { window.refreshSourceHealth(); }, 300);
        }
        if (tabId === 'tab-user-search') this.loadInfluentialUsers();
        if (tabId === 'tab-sentiment') {
            if (window.CobaltaSentiment) {
                window.CobaltaSentiment.init();
            } else {
                window._pendingSentimentInit = true;
            }
        }
        if (tabId === 'tab-timeline') {
            if (window.CobaltoTimeline) {
                window.CobaltoTimeline.init();
            } else {
                window._pendingTimelineInit = true;
            }
        }
        if (tabId === 'tab-analytics' || tabId === 'tab-sentiment') {
            setTimeout(function() {
                if (window.Chart) {
                    for (var id in Chart.instances) {
                        if (Chart.instances[id].resize) Chart.instances[id].resize();
                    }
                }
            }, 200);
        }
        if (tabId === 'tab-entity-explorer' && window.EntityExplorer) {
            setTimeout(function() { window.EntityExplorer.init(); }, 100);
        }
        if (tabId === 'tab-agents') {
            if (window.AgentFeed) {
                setTimeout(function() { window.AgentFeed.init(); }, 100);
            }
        } else {
            if (window.AgentFeed) window.AgentFeed.destroy();
        }
        if (tabId === 'tab-predictive') {
            if (window.PredictiveIntel) {
                setTimeout(function() { window.PredictiveIntel.init(); }, 100);
            }
        } else {
            if (window.PredictiveIntel) window.PredictiveIntel.destroy();
        }
        if (tabId === 'tab-config' && window.CobaltoConfig) window.CobaltoConfig.loadConfig();
        if (tabId === 'tab-osiris-global' && window.OsirisGlobal) {
            setTimeout(function() { window.OsirisGlobal.init(); }, 100);
        }
        if (tabId === 'tab-osiris-recon' && window.OsirisRecon) {
            setTimeout(function() { window.OsirisRecon.init('osiris-recon-container'); }, 100);
        }
        if (tabId === 'tab-humint') {
            if (window.HumintIntel) {
                setTimeout(function() { window.HumintIntel.init(); }, 100);
            }
        } else {
            if (window.HumintIntel) window.HumintIntel.destroy();
        }
        if (tabId === 'tab-finint') {
            if (window.FinintIntel) {
                setTimeout(function() { window.FinintIntel.init(); }, 100);
            }
        } else {
            if (window.FinintIntel) window.FinintIntel.destroy();
        }
        if (tabId === 'tab-map') {
            setTimeout(function() {
                if (window.UnifiedMap) {
                    window.UnifiedMap.init();
                } else {
                    // Load script if not loaded
                    var s = document.createElement('script');
                    s.src = '/static/js/map-unified.js?v=' + encodeURIComponent(window._now || Date.now());
                    s.onload = function() { if (window.UnifiedMap) window.UnifiedMap.init(); };
                    document.body.appendChild(s);
                }
            }, 150);
        }
        if (tabId === 'tab-graph') {
            if (typeof window.initSocialGraph === 'function') {
                var container = document.getElementById('social-graph-container');
                if (container) {
                    var emptyState = container.querySelector('.empty-state');
                    if (emptyState || !container.querySelector('.vis-network')) {
                        if (window._socialGraph && window._socialGraph.nodes && window._socialGraph.nodes.length) {
                            window.initSocialGraph();
                        } else {
                            window.refreshGraphData();
                        }
                    }
                }
            } else {
                this.loadScript('/static/js/intel-graph.js').then(() => {
                    if (typeof window.initSocialGraph === 'function') {
                        var container = document.getElementById('social-graph-container');
                        if (container) {
                            var emptyState = container.querySelector('.empty-state');
                            if (emptyState || !container.querySelector('.vis-network')) {
                                if (window._socialGraph && window._socialGraph.nodes && window._socialGraph.nodes.length) {
                                    window.initSocialGraph();
                                } else {
                                    window.refreshGraphData();
                                }
                            }
                        }
                    }
                });
            }
        }
    },

    filterNews: function() {
        const searchEl = document.getElementById('search-input');
        const term = searchEl ? searchEl.value.toLowerCase() : '';
        const catSelect = document.getElementById('sitrep-category-select');
        const catFilter = catSelect ? catSelect.value : 'ALL';
        const sevSelect = document.getElementById('sitrep-severity-select');
        const sevFilter = sevSelect ? sevSelect.value : 'ALL';
        const currentTheater = window.currentTheater || 'ALL';

        document.querySelectorAll('.news-card').forEach(card => {
            const title = (card.getAttribute('data-title') || '').toLowerCase();
            const summary = (card.getAttribute('data-summary') || '').toLowerCase();
            const country = (card.getAttribute('data-country') || '').toUpperCase();
            const category = (card.getAttribute('data-category') || 'ALL').toUpperCase();
            const severity = (card.getAttribute('data-severity') || 'ALL').toUpperCase();

            const matchSearch = !term || title.includes(term) || summary.includes(term);
            const matchTheater = currentTheater === 'ALL' || country.includes(currentTheater) || country.includes('GLOBAL');
            const matchCat = catFilter === 'ALL' || category === catFilter;
            const matchSev = sevFilter === 'ALL' || severity === sevFilter;

            card.style.display = (matchSearch && matchTheater && matchCat && matchSev) ? 'flex' : 'none';
        });
    },

    preloadLazyTabs: function() {
        // DESACTIVADO
    },

    loadScript: function(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.onload = resolve;
            s.onerror = reject;
            document.body.appendChild(s);
        });
    },

    renderBriefing: function(container, data, reliabilityScore, reliabilityColor) {
        container.setAttribute('data-briefing-loaded', 'true');
        if (!data || (!data.agents && !data.debate && !data.consensus)) return;

        if (window._streamingPollTimer) {
            clearInterval(window._streamingPollTimer);
            window._streamingPollTimer = null;
        }

        var esc = this.utils.escapeHTML;
        var now = new Date().toLocaleTimeString('es-ES', {hour:'2-digit',minute:'2-digit'});
        var score = reliabilityScore || data.reliability_score || 0;
        var color = reliabilityColor || data.reliability_color || '#44aaee';
        var isExpress = data.mode === 'express';
        var html = '';

        // Badge de modo
        if (isExpress) {
            html += '<div style="margin-bottom: 15px; text-align: right;"><span style="background:rgba(255,215,0,0.1); color:#ffd700; padding:2px 10px; border-radius:4px; font-size:0.7rem; border:1px solid rgba(255,215,0,0.3);">⚡ MODO RÁPIDO</span></div>';
        }

        // Índice de Confiabilidad (solo en modo full)
        if (!isExpress) {
            html += '<div style="margin-bottom: 25px; background: rgba(0,0,0,0.5); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">';
            html += '<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">';
            html += '<span style="color: ' + esc(color) + '; font-family: \'Roboto Mono\', monospace; font-size: 0.8rem; letter-spacing: 1px;">ÍNDICE DE CONFIABILIDAD DE FUENTES</span>';
            html += '<span style="color: ' + esc(color) + '; font-weight: bold; font-family: \'Roboto Mono\', monospace;">' + score + '%</span>';
            html += '</div>';
            html += '<div style="width: 100%; background: rgba(255,255,255,0.1); border-radius: 4px; height: 6px; overflow: hidden;">';
            html += '<div style="width: ' + score + '%; background: ' + esc(color) + '; height: 100%; box-shadow: 0 0 10px ' + esc(color) + ';"></div>';
            html += '</div></div>';
        }

        // Agentes (ARES)
        if (data.agents) {
            for (var i = 0; i < data.agents.length; i++) {
                var agent = data.agents[i];
                if (agent.agent.startsWith('ARES') || agent.agent === 'Neutral') {
                    html += '<div style="border: 1px solid rgba(0, 255, 170, 0.25); background: linear-gradient(135deg, rgba(0, 255, 170, 0.05) 0%, rgba(10, 11, 16, 0.6) 100%); padding: 22px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border-left: 4px solid #00ffaa; position: relative;">' +
                        '<div style="color: #00ffaa; font-weight: bold; margin-bottom: 12px; font-size: 0.85rem; letter-spacing: 2px; display: flex; align-items: center; font-family: \'Roboto Mono\', monospace; text-transform: uppercase;">' +
                        '<span style="display:inline-block; width:10px; height:10px; background:#00ffaa; border-radius:50%; margin-right:10px; box-shadow: 0 0 10px #00ffaa;"></span>' +
                        esc(agent.agent) +
                        (agent.role ? '<span style="color: rgba(255,255,255,0.3); font-size: 0.7rem; margin-left: 10px; font-weight: normal; letter-spacing: 0;">| ' + esc(agent.role) + '</span>' : '') +
                        '</div>' +
                        '<div style="color: #F8FAFC; font-size: 0.95rem; line-height: 1.65; text-align: justify; font-family: \'Inter\', sans-serif;">' + esc(agent.text) + '</div>' +
                        '</div>';
                } else {
                    html += renderAgentCard(agent, esc);
                }
            }
        }

        // Debate (MINERVA, NEXUS)
        if (data.debate && data.debate.length > 0) {
            html += '<div style="text-align: center; margin: 35px 0 20px; position: relative;">' +
                '<span style="background: #0A0B10; padding: 0 15px; color: var(--primary); font-family: \'Roboto Mono\', monospace; font-size: 0.75rem; letter-spacing: 2px; position: relative; z-index: 10;">' +
                '[ CONFLICTO DIALÉCTICO: CONFRONTACIÓN DE NARRATIVAS ]' +
                '</span>' +
                '<div style="position: absolute; top: 50%; left: 0; width: 100%; height: 1px; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent); z-index: 1;"></div>' +
                '</div>';

            html += '<div class="debate-grid">';
            for (var i = 0; i < data.debate.length; i++) {
                var agent = data.debate[i];
                var isMinerva = agent.agent.startsWith('MINERVA');
                var badgeLabel = isMinerva ? 'Perspectiva Crítica' : 'Defensa Soberana';
                var borderCol = isMinerva ? 'rgba(68, 170, 238, 0.25)' : 'rgba(255, 68, 68, 0.25)';
                var bgCol = isMinerva ? 'rgba(68, 170, 238, 0.05)' : 'rgba(255, 68, 68, 0.05)';
                
                html += '<div style="border: 1px solid ' + borderCol + '; background: linear-gradient(135deg, ' + bgCol + ' 0%, rgba(10, 11, 16, 0.5) 100%); padding: 20px; border-radius: 12px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border-left: 4px solid ' + esc(agent.color) + ';">' +
                    '<div>' +
                    '<div style="color: ' + esc(agent.color) + '; font-weight: bold; margin-bottom: 12px; font-size: 0.85rem; letter-spacing: 1.5px; display: flex; align-items: center; font-family: \'Roboto Mono\', monospace;">' +
                    '<span style="display:inline-block; width:8px; height:8px; background:' + esc(agent.color) + '; border-radius:50%; margin-right:8px; box-shadow: 0 0 8px ' + esc(agent.color) + ';"></span>' +
                    esc(agent.agent) +
                    (agent.role ? '<span style="color: rgba(255,255,255,0.3); font-size: 0.7rem; margin-left: 10px; font-weight: normal; letter-spacing: 0;">| ' + esc(agent.role) + '</span>' : '') +
                    '</div>' +
                    '<div style="color: #E2E8F0; font-size: 0.9rem; line-height: 1.6; text-align: justify; font-family: \'Inter\', sans-serif;">' + esc(agent.text) + '</div>' +
                    '</div>' +
                    '<div style="margin-top: 15px; font-size: 0.65rem; color: ' + esc(agent.color) + '; opacity: 0.6; font-family: \'Roboto Mono\', monospace; text-align: right; text-transform: uppercase; letter-spacing: 1px;">' + badgeLabel + '</div>' +
                    '</div>';
            }
            html += '</div>';
        }

        // Consenso
        if (data.consensus) {
            html += '<div style="margin-top: 40px; border: 1px solid rgba(0, 229, 255, 0.35); background: linear-gradient(180deg, rgba(10, 11, 16, 0.95) 0%, rgba(15, 18, 27, 0.95) 100%); padding: 25px; border-radius: 12px; position: relative; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.6);">';
            html += '<div style="position: absolute; top: 0; left: 0; width: 100%; height: 3px; background: linear-gradient(90deg, transparent, var(--primary), transparent);"></div>';
            html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 12px; font-family: \'Roboto Mono\', monospace; font-size: 0.7rem; color: var(--primary);">';
            html += '<div style="display: flex; align-items: center; gap: 8px;"><span style="display: inline-block; width: 6px; height: 6px; background: var(--primary); border-radius: 50%; box-shadow: 0 0 8px var(--primary);"></span><span>SISTEMA DE MANDO Y CONTROL: OPERACIONAL</span></div>';
            html += '<div style="letter-spacing: 1px; font-weight: bold;">[ CLASIFICACIÓN: CONFIDENCIAL ]</div>';
            html += '</div>';
            html += '<div style="color: #ffffff; text-align: center; font-weight: bold; margin-bottom: 15px; letter-spacing: 3px; font-size: 1rem; font-family: \'Roboto Mono\', monospace; text-transform: uppercase;">[ DEBATE TÁCTICO FINALIZADO ]</div>';
            html += '<div style="color: #E2E8F0; font-size: 0.95rem; line-height: 1.65; text-align: justify; font-family: \'Inter\', sans-serif; margin-bottom: 20px;">' + esc(data.consensus) + '</div>';
            html += '<div style="margin-top: 20px; padding-top: 15px; border-top: 1px dashed rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; color: rgba(255,255,255,0.4); font-size: 0.7rem; font-family: monospace;">';
            html += '<span>ESTADO: SINTETIZADO CON ÉXITO</span>';
            html += '<span>SINCRO: ' + esc(data.timestamp || now) + ' | MANDO CENTRAL COBALTO</span>';
            html += '</div>';
            html += '</div>';
        } else {
            html += '<div style="margin-top: 40px; border: 1px solid rgba(0, 229, 255, 0.35); background: linear-gradient(180deg, rgba(10, 11, 16, 0.95) 0%, rgba(15, 18, 27, 0.95) 100%); padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.6);">';
            html += '<div style="color: #ffffff; font-weight: bold; letter-spacing: 2px; font-size: 0.8rem; font-family: \'Roboto Mono\', monospace; text-transform: uppercase;">[ DEBATE TÁCTICO FINALIZADO - VER REPORTE COBALTO EN PESTAÑA SENTIMIENTOS / PSYOPS ]</div>';
            html += '</div>';
        }

        container.innerHTML = html;
        container.setAttribute('data-briefing-loaded', 'true');
        container.setAttribute('data-briefing-mode', isExpress ? 'express' : 'full');
    },

    loadInfluentialUsers: function() {
        var container = document.getElementById('influential-users-container');
        if (!container) return;
        if (container.getAttribute('data-loaded') === 'true') return;
        container.setAttribute('data-loaded', 'true');
        container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted);"><p>Cargando usuarios influyentes...</p></div>';
        var self = this;
        this.utils.fetchWithTimeout('/api/influential')
            .then(function(r) { return r.json(); })
            .then(function(data) { self.renderInfluentialUsers(container, data); })
            .catch(function(err) {
                console.error('Error loading influential users:', err);
                container.innerHTML = '<div style="text-align:center;padding:2rem;color:#FF2D55;"><p>Error al cargar usuarios influyentes</p></div>';
            });
    },

    renderInfluentialUsers: function(container, data) {
        if (!data || !data.users || data.users.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted);"><p>No hay datos de usuarios influyentes</p></div>';
            return;
        }
        var esc = this.utils.escapeHTML;

        // Profile changes banner
        var changes = data.profile_changes || [];
        if (changes.length > 0) {
            var changesContainer = document.getElementById('profile-changes-container');
            var changesList = document.getElementById('profile-changes-list');
            if (changesContainer && changesList) {
                changesContainer.style.display = 'block';
                var chHtml = '';
                changes.forEach(function(c) {
                    var platIcon = {twitter:'𝕏',instagram:'📷',telegram:'✈',tiktok:'🎵',youtube:'▶'}[c.platform] || '🌐';
                    chHtml += '<div style="padding:0.4rem 0; border-bottom:1px solid rgba(255,255,255,0.05); display:flex; gap:0.5rem; align-items:flex-start;">';
                    chHtml += '<span style="color:#ffaa00;">⚠️</span>';
                    chHtml += '<div style="flex:1;">';
                    chHtml += '<div style="color:#fff; font-weight:600;">' + platIcon + ' @' + esc(c.username) + '</div>';
                    chHtml += '<div style="color:#ccd6f6; font-size:0.75rem;">' + esc(c.description) + '</div>';
                    chHtml += '</div></div>';
                });
                changesList.innerHTML = chHtml;
            }
        }

        var html = '<div style="margin-bottom:1rem;">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">';
        html += '<h3 style="color:#fff;margin:0;">USUARIOS INFLUYENTES</h3>';
        html += '<span style="color:var(--text-muted);font-size:0.8rem;">' + esc(data.total_found) + '/' + esc(data.total) + ' encontrados</span>';
        html += '</div>';
        html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0.8rem;">';
        data.users.forEach(function(u) {
            var statusColor = u.found ? '#4CD964' : '#FF2D55';
            var statusText = u.found ? '✓' : '✗';
            var platformIcon = {twitter:'𝕏',instagram:'📷',telegram:'✈',tiktok:'🎵',youtube:'▶'}[u.searched_platform] || '🌐';
            html += '<div class="panel-glass" style="padding:1rem;border-left:3px solid ' + statusColor + ';">';
            html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;">';
            html += '<div style="flex:1;">';
            html += '<div style="color:#fff;font-weight:700;font-size:0.9rem;">' + esc(u.display_name || u.name || u.username) + '</div>';
            html += '<div style="color:var(--text-muted);font-size:0.75rem;font-family:monospace;">' + platformIcon + ' ' + esc(u.searched_platform) + ' / @' + esc(u.username) + '</div>';
            if (u.found && u.followers) {
                var followers = typeof u.followers === 'number' ? u.followers.toLocaleString() : u.followers;
                html += '<div style="color:#94A3B8;font-size:0.8rem;margin-top:0.3rem;">👥 ' + esc(followers) + ' seguidores</div>';
            }
            html += '</div>';
            html += '<span style="color:' + statusColor + ';font-weight:700;">' + statusText + '</span>';
            html += '</div>';
            if (u.found && u.bio) {
                var bio = u.bio.length > 100 ? u.bio.substring(0, 100) + '…' : u.bio;
                html += '<div style="color:#94A3B8;font-size:0.75rem;margin-top:0.5rem;line-height:1.3;">' + esc(bio) + '</div>';
            }
            if (u.found && u.url) {
                html += '<a href="' + esc(u.url) + '" target="_blank" style="color:#00E5FF;text-decoration:none;font-size:0.75rem;margin-top:0.5rem;display:inline-block;">Ver perfil →</a>';
            }
            html += '</div>';
        });
        html += '</div></div>';
        container.innerHTML = html;
    }
};

window.CobaltoLayout = {
    init: function() {
        const sidebarCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
        const aiPanelCollapsed = localStorage.getItem('ai-panel-collapsed') === 'true';
        const intelHistoryCollapsed = localStorage.getItem('intel-history-collapsed') === 'true';
        
        const sidebar = document.querySelector('.sidebar');
        const sidebarExpandBtn = document.getElementById('sidebar-expand-btn');
        const aiPanel = document.getElementById('ai-panel');
        const aiExpandBtn = document.getElementById('ai-expand-btn');
        const intelHistoryPanel = document.getElementById('intel-history-panel');
        
        if (window.innerWidth > 768) {
            if (sidebar && sidebarCollapsed) {
                sidebar.classList.add('collapsed');
                if (sidebarExpandBtn) sidebarExpandBtn.style.display = 'flex';
            }
        }
        
        if (window.innerWidth > 1200) {
            if (aiPanel && aiPanelCollapsed) {
                aiPanel.classList.add('collapsed');
                if (aiExpandBtn) aiExpandBtn.style.display = 'flex';
            }
        }

        if (intelHistoryPanel && intelHistoryCollapsed) {
            intelHistoryPanel.classList.add('collapsed');
            const toggleBtn = document.getElementById('intel-history-toggle-btn');
            if (toggleBtn) {
                toggleBtn.style.borderColor = 'rgba(255,255,255,0.2)';
                toggleBtn.style.color = 'var(--text-muted)';
                toggleBtn.style.background = 'transparent';
            }
        }
    },
    
    toggleSidebar: function() {
        const sidebar = document.querySelector('.sidebar');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        if (!sidebar) return;
        
        if (window.innerWidth > 768) {
            sidebar.classList.toggle('collapsed');
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebar-collapsed', isCollapsed ? 'true' : 'false');
            
            if (expandBtn) {
                expandBtn.style.display = isCollapsed ? 'flex' : 'none';
            }
            
            // Trigger standard resize event to force vis-network, leaflet, and other responsive components to adapt
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
                if (window.CobaltoMap && window.CobaltoMap._map) {
                    window.CobaltoMap._map.invalidateSize();
                }
            }, 350);
        }
    },

    toggleIntelHistory: function() {
        const panel = document.getElementById('intel-history-panel');
        const toggleBtn = document.getElementById('intel-history-toggle-btn');
        if (!panel) return;

        panel.classList.toggle('collapsed');
        const isCollapsed = panel.classList.contains('collapsed');
        localStorage.setItem('intel-history-collapsed', isCollapsed ? 'true' : 'false');

        if (toggleBtn) {
            if (isCollapsed) {
                toggleBtn.style.borderColor = 'rgba(255,255,255,0.2)';
                toggleBtn.style.color = 'var(--text-muted)';
                toggleBtn.style.background = 'transparent';
            } else {
                toggleBtn.style.borderColor = 'var(--primary)';
                toggleBtn.style.color = 'var(--primary)';
                toggleBtn.style.background = 'rgba(0,229,255,0.05)';
            }
        }

        // Trigger resize event to let child components adapt
        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
        }, 350);
    }
};

// Global functions for Tactical UX (Fase 3.5)
window.animateRadar = function() {
    const wave = document.getElementById('radar-wave');
    const pulse = document.getElementById('radar-pulse');
    if (!wave || !pulse) return;

    pulse.style.background = '#FF9500';
    pulse.style.boxShadow = '0 0 15px #FF9500';
    
    wave.style.transition = 'none';
    wave.style.transform = 'translate(-50%, -50%) scale(0.1)';
    wave.style.opacity = '1';
    
    // Forzar reflow
    void wave.offsetWidth;
    
    wave.style.transition = 'transform 1s cubic-bezier(0.1, 0.8, 0.3, 1), opacity 1s ease-out';
    wave.style.transform = 'translate(-50%, -50%) scale(2.5)';
    wave.style.opacity = '0';

    setTimeout(() => {
        pulse.style.background = '#00ffaa';
        pulse.style.boxShadow = '0 0 10px #00ffaa';
    }, 1000);
};


// ── NOTIFICACIÓN FLOTANTE DE IA PENSANDO EN TIEMPO REAL ──
window._aiThinkingToastInstance = null;

window.showAIThinkingToast = function(title = "IA LOCAL PENSANDO...", subtitle = "Procesando inferencia Ollama & RAG fáctico") {
    if (window._aiThinkingToastInstance && window._aiThinkingToastInstance.element && document.body.contains(window._aiThinkingToastInstance.element)) {
        if (window._aiThinkingToastInstance.subtitleEl) {
            window._aiThinkingToastInstance.subtitleEl.textContent = subtitle;
        }
        return window._aiThinkingToastInstance;
    }

    const toast = document.createElement('div');
    toast.id = 'ai-thinking-floating-toast';
    toast.style.position = 'fixed';
    toast.style.bottom = '30px';
    toast.style.right = '30px';
    toast.style.zIndex = '999999';
    toast.style.background = 'linear-gradient(135deg, rgba(10, 15, 26, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%)';
    toast.style.backdropFilter = 'blur(12px)';
    toast.style.border = '1px solid rgba(0, 229, 255, 0.4)';
    toast.style.borderLeft = '4px solid #00E5FF';
    toast.style.borderRadius = '10px';
    toast.style.padding = '14px 20px';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '15px';
    toast.style.boxShadow = '0 10px 35px rgba(0, 0, 0, 0.7), 0 0 20px rgba(0, 229, 255, 0.25)';
    toast.style.transform = 'translateY(100px) scale(0.9)';
    toast.style.opacity = '0';
    toast.style.transition = 'transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.4s';
    toast.style.pointerEvents = 'auto';

    const startTime = Date.now();

    toast.innerHTML = `
        <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 34px; height: 34px;">
            <div style="width: 32px; height: 32px; border: 2px solid rgba(0,229,255,0.2); border-top-color: #00E5FF; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <div style="position: absolute; font-size: 15px; animation: pulse 1.2s ease-in-out infinite;">🧠</div>
        </div>
        <div style="flex: 1;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px; gap: 10px;">
                <span style="font-family: 'Roboto Mono', monospace; font-size: 0.85rem; font-weight: bold; color: #00E5FF; letter-spacing: 1px; text-transform: uppercase;">
                    ${title}
                </span>
                <span id="ai-timer-counter" style="font-family: monospace; font-size: 0.75rem; color: #79C0FF; background: rgba(0,229,255,0.1); padding: 1px 6px; border-radius: 4px;">
                    0.0s
                </span>
            </div>
            <div id="ai-thinking-subtitle" style="font-size: 0.78rem; color: #cbd5e1; font-family: 'Inter', sans-serif;">
                ${subtitle}
            </div>
        </div>
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.transform = 'translateY(0) scale(1)';
        toast.style.opacity = '1';
    }, 10);

    const timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        const counterEl = document.getElementById('ai-timer-counter');
        if (counterEl) counterEl.textContent = `${elapsed}s`;
    }, 100);

    window._aiThinkingToastInstance = {
        element: toast,
        timerInterval: timerInterval,
        startTime: startTime,
        subtitleEl: document.getElementById('ai-thinking-subtitle')
    };

    return window._aiThinkingToastInstance;
};

window.hideAIThinkingToast = function(message = "INFERENCIA COMPLETADA", isError = false) {
    if (!window._aiThinkingToastInstance || !window._aiThinkingToastInstance.element) return;

    const { element, timerInterval, startTime } = window._aiThinkingToastInstance;
    clearInterval(timerInterval);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    const color = isError ? '#FF2D55' : '#00ffaa';
    const icon = isError ? '❌' : '✅';

    element.style.borderLeft = `4px solid ${color}`;
    element.style.borderColor = color;
    element.style.boxShadow = `0 10px 35px rgba(0, 0, 0, 0.7), 0 0 20px ${color}44`;

    element.innerHTML = `
        <div style="font-size: 1.5rem; filter: drop-shadow(0 0 8px ${color});">${icon}</div>
        <div>
            <div style="font-family: 'Roboto Mono', monospace; font-size: 0.85rem; font-weight: bold; color: ${color}; letter-spacing: 1px;">
                ${isError ? 'ERROR EN INFERENCIA' : 'PROCESO COMPLETADO'}
            </div>
            <div style="font-size: 0.78rem; color: #f1f5f9; margin-top: 2px;">
                ${message} <span style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace;">(${elapsed}s)</span>
            </div>
        </div>
    `;

    setTimeout(() => {
        element.style.transform = 'translateY(30px) scale(0.95)';
        element.style.opacity = '0';
        setTimeout(() => {
            if (element.parentElement) element.parentElement.removeChild(element);
            window._aiThinkingToastInstance = null;
        }, 400);
    }, 3000);
};


window.showTacticalToast = function(message, type = 'info') {
    const container = document.getElementById('tactical-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.style.background = 'rgba(10, 11, 16, 0.9)';
    toast.style.backdropFilter = 'blur(10px)';
    toast.style.border = '1px solid rgba(255, 255, 255, 0.1)';
    toast.style.borderRadius = '8px';
    toast.style.padding = '12px 18px';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '12px';
    toast.style.boxShadow = '0 5px 20px rgba(0,0,0,0.5)';
    toast.style.transform = 'translateX(120%)';
    toast.style.transition = 'transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.4s';
    toast.style.opacity = '0';
    toast.style.pointerEvents = 'auto';

    let icon = 'ℹ️';
    let color = '#00E5FF';
    if (type === 'warning') { icon = '⚠️'; color = '#FF9500'; }
    if (type === 'critical') { icon = '🚨'; color = '#FF2D55'; }
    if (type === 'success') { icon = '✅'; color = '#00ffaa'; }

    toast.style.borderLeft = `4px solid ${color}`;

    toast.innerHTML = `
        <div style="font-size: 1.2rem; filter: drop-shadow(0 0 5px ${color});">${icon}</div>
        <div style="font-family: 'Roboto Mono', monospace; font-size: 0.85rem; color: #fff;">${message}</div>
    `;

    container.appendChild(toast);

    // Entrar
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    });

    // Salir y destruir
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400);
    }, 6000);
};

// ── Alerta Sonora Táctica (Web Audio API) ──
window._muteAlerts = localStorage.getItem('cobalto_mute_alerts') === 'true';
window.playTacticalBeep = function(type = 'warning') {
    if (window._muteAlerts) return;
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        if (type === 'warning') {
            osc.frequency.value = 880;
            osc.type = 'sawtooth';
            gain.gain.value = 0.15;
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.5);
        } else if (type === 'critical') {
            osc.frequency.value = 660;
            osc.type = 'square';
            gain.gain.value = 0.2;
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.8);
        } else {
            osc.frequency.value = 523;
            osc.type = 'sine';
            gain.gain.value = 0.08;
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.15);
        }
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
        setTimeout(() => ctx.close(), 1000);
    } catch(e) {
        console.warn('[AUDIO] Web Audio API no disponible:', e.message);
    }
};

window.toggleMuteAlert = function() {
    window._muteAlerts = !window._muteAlerts;
    localStorage.setItem('cobalto_mute_alerts', window._muteAlerts ? 'true' : 'false');
    const btn = document.getElementById('btn-mute-alerts');
    if (btn) {
        if (window._muteAlerts) {
            btn.innerHTML = '🔇 AUDIO';
            btn.style.borderColor = '#666';
            btn.style.color = '#666';
        } else {
            btn.innerHTML = '🔊 AUDIO';
            btn.style.borderColor = '#FF2D55';
            btn.style.color = '#FF2D55';
        }
    }
    window.showTacticalToast(window._muteAlerts ? 'Alertas sonoras silenciadas' : 'Alertas sonoras activadas', 'info');
};

// ── Descarga genérica de reportes ──
window.downloadReport = function(url, filename, toastMsg, method, body) {
    window.showTacticalToast(toastMsg || 'Generando reporte...', 'info');
    var options = { method: method || 'GET' };
    if (body) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(body);
    }
    fetch(url, options)
        .then(function(r) {
            if (!r.ok) throw new Error('Error en la solicitud');
            var ct = r.headers.get('Content-Type') || '';
            if (ct.indexOf('json') !== -1) {
                return r.json().then(function(d) {
                    return new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
                });
            }
            return r.blob();
        })
        .then(function(blob) {
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            window.showTacticalToast('Reporte descargado correctamente', 'success');
        })
        .catch(function(err) {
            console.error('[DOWNLOAD]', err);
            window.showTacticalToast('Error: ' + err.message, 'critical');
        });
};

window.downloadSitrep = function() {
    var ts = new Date().toISOString().slice(0, 10);
    window.downloadReport('/api/export/sitrep', 'SITREP_COBALTO_' + ts + '.json', 'Generando SitRep JSON...');
};
window.downloadSitrepDocx = function() {
    var ts = new Date().toISOString().slice(0, 10);
    window.downloadReport('/api/export/sitrep/docx', 'SITREP_COBALTO_' + ts + '.docx', 'Generando SitRep DOCX...');
};
window.downloadSitrepIA = function() {
    var ts = new Date().toISOString().slice(0, 10);
    window.downloadReport('/api/export/sitrep/generar-word', 'SITREP_COBALTO_IA_' + ts + '.docx', 'Analizando con IA...', 'POST', { max_entries: 25 });
};
window.downloadSitrepPDF = function() {
    var ts = new Date().toISOString().slice(0, 10);
    window.downloadReport('/api/export/sitrep/pdf', 'SITREP_COBALTO_' + ts + '.pdf', 'Generando SitRep PDF...');
};
window.downloadSitrepPDFIA = function() {
    var ts = new Date().toISOString().slice(0, 10);
    window.downloadReport('/api/export/sitrep/generar-pdf', 'SITREP_COBALTO_IA_' + ts + '.pdf', 'Analizando con IA y generando PDF...', 'POST', { max_entries: 25 });
};

// ── Modal de Exportación Profesional ──
var EXPORT_FORMAT = 'json';

window.showExportModal = function() {
    var overlay = document.getElementById('export-modal-overlay');
    if (overlay) overlay.classList.add('active');
};

window.closeExportModal = function() {
    var overlay = document.getElementById('export-modal-overlay');
    if (overlay) overlay.classList.remove('active');
    var progress = document.getElementById('export-progress');
    if (progress) progress.classList.remove('active');
    document.getElementById('btn-export-generate').disabled = false;
    document.getElementById('btn-export-generate').innerHTML = '⚡ GENERAR REPORTE';
};

window.selectExportFormat = function(format) {
    EXPORT_FORMAT = format;
    document.querySelectorAll('.export-modal .format-option').forEach(function(el) {
        el.classList.remove('selected');
    });
    var selected = document.querySelector('.export-modal .format-option[data-format="' + format + '"]');
    if (selected) selected.classList.add('selected');
};

window.executeExport = function() {
    var useIA = document.getElementById('export-use-ia').checked;
    var maxEntries = parseInt(document.getElementById('export-max-entries').value) || 25;
    var btn = document.getElementById('btn-export-generate');
    var progress = document.getElementById('export-progress');
    var progressText = document.getElementById('export-progress-text');
    var progressFill = document.getElementById('export-progress-fill');

    btn.disabled = true;
    progress.classList.add('active');
    progressFill.style.width = '0%';

    var ts = new Date().toISOString().slice(0, 10);
    var url, filename, toastMsg, method, body;

    if (useIA) {
        if (EXPORT_FORMAT === 'json') {
            // JSON con IA: analizar primero, luego descargar JSON
            progressText.textContent = 'Analizando entradas con IA...';
            progressFill.style.width = '30%';
            fetch('/api/export/sitrep/analizar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_entries: maxEntries })
            }).then(function(r) { return r.json(); }).then(function(data) {
                progressFill.style.width = '70%';
                progressText.textContent = 'Generando JSON...';
                var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'SITREP_COBALTO_IA_' + ts + '.json';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                progressFill.style.width = '100%';
                progressText.textContent = 'Reporte generado exitosamente';
                setTimeout(window.closeExportModal, 1000);
            }).catch(function(err) {
                window.showTacticalToast('Error: ' + err.message, 'critical');
                btn.disabled = false;
                progress.classList.remove('active');
            });
            return;
        }
        if (EXPORT_FORMAT === 'docx') {
            url = '/api/export/sitrep/generar-word';
            filename = 'SITREP_COBALTO_IA_' + ts + '.docx';
            method = 'POST';
            body = { max_entries: maxEntries };
        } else {
            url = '/api/export/sitrep/generar-pdf';
            filename = 'SITREP_COBALTO_IA_' + ts + '.pdf';
            method = 'POST';
            body = { max_entries: maxEntries };
        }
        toastMsg = 'Analizando con IA...';
    } else {
        if (EXPORT_FORMAT === 'json') {
            url = '/api/export/sitrep';
            filename = 'SITREP_COBALTO_' + ts + '.json';
            method = 'GET';
            body = null;
        } else if (EXPORT_FORMAT === 'docx') {
            url = '/api/export/sitrep/docx';
            filename = 'SITREP_COBALTO_' + ts + '.docx';
            method = 'GET';
            body = null;
        } else {
            url = '/api/export/sitrep/pdf';
            filename = 'SITREP_COBALTO_' + ts + '.pdf';
            method = 'GET';
            body = null;
        }
        toastMsg = 'Generando reporte...';
    }

    progressText.textContent = toastMsg;
    progressFill.style.width = '50%';

    window.downloadReport(url, filename, toastMsg, method, body);

    // Simular progreso y cerrar modal
    var pct = 50;
    var interval = setInterval(function() {
        pct = Math.min(pct + 10, 90);
        progressFill.style.width = pct + '%';
        if (pct >= 90) {
            clearInterval(interval);
            progressText.textContent = 'Finalizando...';
            setTimeout(function() {
                progressFill.style.width = '100%';
                progressText.textContent = 'Reporte generado exitosamente';
                setTimeout(window.closeExportModal, 800);
            }, 500);
        }
    }, 200);
};

// ── Health Dashboard de Fuentes ──
window.refreshSourceHealth = function() {
    const tbody = document.getElementById('source-health-tbody');
    const healthyEl = document.getElementById('sh-healthy');
    const degradedEl = document.getElementById('sh-degraded');
    const downEl = document.getElementById('sh-down');
    const tsEl = document.getElementById('source-health-timestamp');

    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="4" style="padding:1rem; text-align:center; color:var(--text-muted);">Actualizando...</td></tr>';

    fetch('/api/health/sources')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (healthyEl) healthyEl.textContent = data.total_healthy || 0;
            if (degradedEl) degradedEl.textContent = data.total_degraded || 0;
            if (downEl) downEl.textContent = data.total_down || 0;
            if (tsEl) tsEl.textContent = new Date().toLocaleTimeString();

            var rows = [];
            (data.degraded || []).forEach(function(f) {
                rows.push('<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">' +
                    '<td style="padding:0.4rem 0.5rem; color:#ffaa00;">⚠️ ' + f.source + '</td>' +
                    '<td style="padding:0.4rem 0.5rem; text-align:center; color:#ffaa00;">' + f.failures + '</td>' +
                    '<td style="padding:0.4rem 0.5rem; text-align:right; color:#ffaa00;">DEGRADED</td>' +
                    '<td style="padding:0.4rem 0.5rem; text-align:right; color:var(--text-muted);">' + Math.round(f.remaining_seconds / 60) + 'm</td>' +
                    '</tr>');
            });
            (data.down || []).forEach(function(f) {
                rows.push('<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">' +
                    '<td style="padding:0.4rem 0.5rem; color:#FF2D55;">🚫 ' + f.source + '</td>' +
                    '<td style="padding:0.4rem 0.5rem; text-align:center; color:#FF2D55;">' + f.failures + '</td>' +
                    '<td style="padding:0.4rem 0.5rem; text-align:right; color:#FF2D55;">DOWN</td>' +
                    '<td style="padding:0.4rem 0.5rem; text-align:right; color:var(--text-muted);">' + Math.round(f.remaining_seconds / 60) + 'm</td>' +
                    '</tr>');
            });
            if (rows.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="padding:1rem; text-align:center; color:#00ffaa;">✅ Todas las fuentes operativas</td></tr>';
            } else {
                tbody.innerHTML = rows.join('');
            }
        })
        .catch(function(err) {
            tbody.innerHTML = '<tr><td colspan="4" style="padding:1rem; text-align:center; color:#FF2D55;">Error: ' + err.message + '</td></tr>';
        });
};

// Auto-refresh health sources on analytics tab show
document.addEventListener('DOMContentLoaded', function() {
    var analyticsTab = document.getElementById('tab-analytics');
    if (analyticsTab) {
        var observer = new MutationObserver(function() {
            if (analyticsTab.classList.contains('active')) {
                window.refreshSourceHealth();
            }
        });
        observer.observe(analyticsTab, { attributes: true, attributeFilter: ['class'] });
    }
});

window.isMosaicMode = false;
window.mosaicGrid = null;

window.toggleMosaicMode = function() {
    if (window.innerWidth < 768) {
        window.showTacticalToast("El Modo Mosaico requiere una pantalla más grande.", "warning");
        return;
    }

    const mainContent = document.querySelector('main.main-content');
    const navTabs = document.querySelector('.sidebar nav');
    const tabContents = document.querySelectorAll('.tab-content');
    const toggleBtn = document.getElementById('btn-mosaic-toggle');
    
    if (!window.isMosaicMode) {
        // ACTIVAR MOSAICO
        window.isMosaicMode = true;
        if (navTabs) navTabs.style.display = 'none';
        if (toggleBtn) {
            toggleBtn.style.background = 'rgba(0, 255, 170, 0.2)';
            toggleBtn.style.color = '#fff';
            toggleBtn.innerText = '❌ CERRAR MOSAICO';
        }

        var indicator = document.getElementById('mosaic-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'mosaic-indicator';
            indicator.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9998;background:rgba(10,11,16,0.85);backdrop-filter:blur(12px);border:1px solid rgba(0,229,255,0.25);border-radius:8px;padding:6px 14px;display:flex;gap:8px;align-items:center;font-size:0.6rem;font-family:Roboto Mono,monospace;transition:opacity 0.3s;';
            mainContent.parentElement.appendChild(indicator);
        }
        var activeWidgets = [];
        tabContents.forEach(function(t) {
            if (t.id === 'tab-config' || t.id === 'tab-user-search') return;
            var name = t.id.replace('tab-', '').toUpperCase();
            activeWidgets.push('<span style="color:var(--primary);padding:2px 6px;border:1px solid rgba(0,229,255,0.15);border-radius:4px;">' + name + '</span>');
        });
        indicator.innerHTML = '<span style="color:var(--text-muted);margin-right:4px;">MOSAICO</span>' + activeWidgets.join('');
        indicator.style.opacity = '1';
        
        const gridContainer = document.createElement('div');
        gridContainer.className = 'grid-stack';
        gridContainer.id = 'c4i-grid';
        gridContainer.style.marginTop = '15px';
        
        // Insert grid in main content
        mainContent.appendChild(gridContainer);
        
        tabContents.forEach(tab => {
            if (tab.id === 'tab-config' || tab.id === 'tab-user-search') return;
            
            tab.style.display = 'block';
            tab.classList.remove('active');
            
            const widget = document.createElement('div');
            widget.className = 'grid-stack-item';
            
            // Tamaños iniciales heurísticos
            let gw = 6, gh = 5;
            if(tab.id === 'tab-news') { gw = 12; gh = 4; }
            if(tab.id === 'tab-graph' || tab.id === 'tab-map') { gw = 6; gh = 6; }
            
            widget.setAttribute('data-gs-width', gw);
            widget.setAttribute('data-gs-height', gh);
            
            const widgetContent = document.createElement('div');
            widgetContent.className = 'grid-stack-item-content';
            widgetContent.style.overflow = 'auto';
            widgetContent.style.background = 'rgba(5, 5, 10, 0.8)';
            widgetContent.style.border = '1px solid rgba(0, 229, 255, 0.2)';
            widgetContent.style.borderRadius = '8px';
            widgetContent.style.backdropFilter = 'blur(10px)';
            
            const titleBar = document.createElement('div');
            titleBar.style.padding = '8px 12px';
            titleBar.style.background = 'rgba(0, 229, 255, 0.1)';
            titleBar.style.borderBottom = '1px solid rgba(0, 229, 255, 0.2)';
            titleBar.style.fontWeight = 'bold';
            titleBar.style.color = '#00e5ff';
            titleBar.style.fontFamily = "'Roboto Mono', monospace";
            titleBar.style.cursor = 'move';
            titleBar.style.display = 'flex';
            titleBar.style.justifyContent = 'space-between';
            titleBar.className = 'grid-drag-handle';
            
            const nomenclatures = {
                'tab-news': 'MONITOR GLOBAL (SITREP)',
                'tab-intel': 'INTELIGENCIA PROCESADA',
                'tab-social': 'MONITOR DE REDES',
                'tab-alerts': 'GESTIÓN DE INCIDENTES',
                'tab-cyber': 'MONITOR DE AMENAZAS',
                'tab-realtime': 'FLUJO DE DATOS',
                'tab-narrative': 'ANÁLISIS DE NARRATIVAS',
                'tab-analytics': 'TELEMETRÍA Y MÉTRICAS',
                'tab-sentiment': 'PERFILAMIENTO CONDUCTUAL',
                'tab-timeline': 'AUDITORÍA CRONOLÓGICA',
                'tab-map': 'MONITOR GEOESPACIAL',
                'tab-graph': 'ANÁLISIS DE REDES (SNA)'
            };
            let tabName = nomenclatures[tab.id] || tab.id.replace('tab-', '').toUpperCase();
            
            titleBar.innerHTML = `<span>▤ ${tabName}</span><span style="opacity:0.5; font-size:0.8rem;">Arrastrar</span>`;
            
            widgetContent.appendChild(titleBar);
            
            const contentWrapper = document.createElement('div');
            contentWrapper.style.padding = '15px';
            contentWrapper.style.height = 'calc(100% - 35px)';
            contentWrapper.style.overflow = 'auto';
            
            // Move original children to wrapper
            const originalChildren = Array.from(tab.childNodes);
            originalChildren.forEach(child => contentWrapper.appendChild(child));
            
            widgetContent.appendChild(contentWrapper);
            widget.appendChild(widgetContent);
            gridContainer.appendChild(widget);
            
            // Store reference for teardown
            tab._originalChildren = contentWrapper;
        });
        
        window.mosaicGrid = GridStack.init({
            column: 12,
            cellHeight: '80px',
            handle: '.grid-drag-handle',
            margin: 10,
            animate: true
        }, '#c4i-grid');
        
        // UX FIX: Escuchar eventos de redimensionamiento de Mosaicos para evitar distorsiones
        window.mosaicGrid.on('resizestop', function(event, el) {
            // Refrescar Chart.js
            window.dispatchEvent(new Event('resize'));
            
            // Refrescar Leaflet Map (evitar cuadros grises al estirar)
            if(window.CobaltoMap && window.CobaltoMap.invalidateMap) {
                window.CobaltoMap.invalidateMap();
            }
            
            // Refrescar Grafo Vis.js (centrar la telaraña)
            if(typeof graphNetwork !== 'undefined' && graphNetwork) {
                setTimeout(() => { graphNetwork.fit({animation: true}); }, 100);
            }
        });
        
        // Disparar cascada de reflows al arrancar para asentar el DOM
        window.showTacticalToast("Modo Mosaico C4i ACTIVADO.", "success");
        setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
        setTimeout(() => window.dispatchEvent(new Event('resize')), 400);
        setTimeout(() => {
            if(window.CobaltoMap && window.CobaltoMap.invalidateMap) window.CobaltoMap.invalidateMap();
        }, 500);
        
    } else {
        // DESACTIVAR MOSAICO
        window.isMosaicMode = false;
        if (navTabs) navTabs.style.display = 'block';
        if (toggleBtn) {
            toggleBtn.style.background = 'transparent';
            toggleBtn.style.color = '#00ffaa';
            toggleBtn.innerText = '🧩 MODO MOSAICO (C4i)';
        }
        
        const gridContainer = document.getElementById('c4i-grid');
        if (gridContainer) {
            tabContents.forEach(tab => {
                if (tab.id === 'tab-config' || tab.id === 'tab-user-search') return;
                
                if (tab._originalChildren) {
                    const children = Array.from(tab._originalChildren.childNodes);
                    children.forEach(c => tab.appendChild(c));
                    delete tab._originalChildren;
                }
                tab.style.display = '';
            });
            gridContainer.remove();
        }
        
        if(window.CobaltoCore && window.CobaltoCore.switchTab) {
            window.CobaltoCore.switchTab('tab-news', document.querySelector('.nav-button[data-tab="tab-news"]'));
        }
        
        var indicator = document.getElementById('mosaic-indicator');
        if (indicator) { indicator.style.opacity = '0'; setTimeout(function() { if (indicator.parentElement) indicator.parentElement.removeChild(indicator); }, 300); }
        window.showTacticalToast("Modo Mosaico DESACTIVADO.", "info");
        setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    }
};

// Phase 4: Responsividad y Refinamiento (Auto-Colapso Inteligente)
window.addEventListener('resize', () => {
    if (window.isMosaicMode && window.innerWidth < 768) {
        window.showTacticalToast("Pantalla pequeña detectada. Plegando Mosaico por seguridad operativa.", "warning");
        window.toggleMosaicMode(); // Desactiva automáticamente
    }
});

if (typeof window._startCobaltoApp === 'function') {
    window._startCobaltoApp();
}

/* ── SITREP GLOBAL ACTION HELPERS ────────────────────────────────────────── */
window.sitrepFocusMap = function(countryTag, title) {
    if (window.CobaltoCore) window.CobaltoCore.switchTab('tab-map');
    setTimeout(function() {
        if (window.UnifiedMap && window.UnifiedMap.state && window.UnifiedMap.state.map) {
            var searched = false;
            if (title && typeof window.UnifiedMap.searchVector === 'function') {
                searched = window.UnifiedMap.searchVector(title);
            }
            if (!searched) {
                if (countryTag === 'COL') {
                    window.UnifiedMap.flyToTheater('COL');
                } else if (countryTag === 'VEN') {
                    window.UnifiedMap.flyToTheater('VEN');
                } else {
                    window.UnifiedMap.flyToTheater('GLOBAL');
                }
            }
        }
    }, 150);
    if (typeof window.showTacticalToast === 'function') {
        window.showTacticalToast('📍 Enfocando mapa táctico en vector ' + countryTag, 'info');
    }
};

window.sitrepInvestigateRAG = function(title) {
    if (window.CobaltoCore) window.CobaltoCore.switchTab('tab-intel');
    var input = document.getElementById('intel-query-input');
    if (input) {
        input.value = 'Investigar evento táctico: ' + title;
        input.focus();
    }
    if (typeof window.showTacticalToast === 'function') {
        window.showTacticalToast('🎯 Hipótesis transferida al Centro de Investigación IA', 'info');
    }
};

window.sitrepCopyLink = function(url) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function() {
            if (typeof window.showTacticalToast === 'function') {
                window.showTacticalToast('🔗 Enlace copiado al portapapeles', 'info');
            }
        });
    } else {
        if (typeof window.showTacticalToast === 'function') {
            window.showTacticalToast('🔗 Enlace: ' + url, 'info');
        }
    }
};

/* ── SITREP CLUSTERING & DEDUPLICATION ENGINE ───────────────────────────── */
window.clusterNewsItems = function(items) {
    if (!window._sitrepGroupDuplicates || !items || !items.length) return items;

    var stopwords = new Set(["de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "en", "para", "por", "con", "sin", "sobre", "entre", "tras", "hacia", "hasta", "contra", "y", "o", "que", "es", "son", "se", "su", "sus", "al", "lo", "como", "mas", "más", "pero", "este", "esta", "estos", "estas"]);

    function getKeywords(text) {
        if (!text) return new Set();
        var words = text.toLowerCase().match(/[a-záéíóúñ0-9]{3,}/g) || [];
        var kw = new Set();
        words.forEach(w => { if (!stopwords.has(w)) kw.add(w); });
        return kw;
    }

    var clusters = [];
    items.forEach(function(item) {
        var t = item.title || '';
        var s = item.summary || '';
        var kw = getKeywords(t + ' ' + s.slice(0, 100));

        var found = null;
        for (var i = 0; i < clusters.length; i++) {
            var exKw = clusters[i]._kw;
            if (!exKw || !kw.size) continue;

            var matchCount = 0;
            kw.forEach(w => { if (exKw.has(w)) matchCount++; });

            var unionSize = new Set([...kw, ...exKw]).size;
            var jaccard = unionSize > 0 ? (matchCount / unionSize) : 0;

            if (jaccard >= 0.38 || (matchCount >= 3 && kw.size >= 3)) {
                found = clusters[i];
                break;
            }
        }

        if (found) {
            if (!found.related_sources) found.related_sources = [];
            var srcObj = {
                source: item.source || 'OSINT',
                title: item.title || '',
                link: item.link || '#',
                published: item.published || ''
            };
            if (!found.related_sources.some(s => s.source === srcObj.source || s.link === srcObj.link)) {
                found.related_sources.push(srcObj);
            }
            found.sources_count = 1 + found.related_sources.length;
        } else {
            var itemCopy = Object.assign({}, item);
            itemCopy._kw = kw;
            itemCopy.related_sources = item.related_sources ? [...item.related_sources] : [];
            itemCopy.sources_count = item.sources_count || 1;
            clusters.push(itemCopy);
        }
    });

    clusters.forEach(c => delete c._kw);
    return clusters;
};

/* ── SITREP TACTICAL READER MODAL HANDLERS ───────────────────────────────── */
window._activeSitrepModalData = null;
window._activeSitrepModalCard = null;

window.openSitrepReader = function(card) {
    if (!card) return;
    var modal = document.getElementById('sitrep-reader-modal');
    if (!modal) return;

    var title = card.getAttribute('data-title') || card.querySelector('.news-title')?.textContent || '';
    var summary = card.getAttribute('data-summary') || card.querySelector('.news-summary')?.textContent || '';
    var countryTag = card.getAttribute('data-country') || 'GLOBAL';
    var severity = card.getAttribute('data-severity') || 'INFO';
    var source = card.querySelector('.news-source')?.textContent || 'OSINT SOURCE';
    var time = card.querySelector('.news-time')?.textContent || '';
    var img = card.querySelector('.card-image')?.src || '';
    var link = card.querySelector('.news-card-actions .news-action-btn[onclick*="sitrepCopyLink"]')?.getAttribute('onclick')?.match(/'([^']+)'/)?.[1] || card.querySelector('.news-title')?.href || '#';

    var rawRelated = card.getAttribute('data-related') || '[]';
    var relatedSources = [];
    try {
        relatedSources = JSON.parse(rawRelated);
    } catch(e) {
        relatedSources = [];
    }

    window._activeSitrepModalCard = card;
    window._activeSitrepModalData = {
        title: title,
        summary: summary,
        countryTag: countryTag,
        severity: severity,
        source: source,
        time: time,
        img: img,
        link: link,
        relatedSources: relatedSources
    };

    var titleEl = document.getElementById('sitrep-modal-title');
    if (titleEl) titleEl.textContent = card.querySelector('.news-title')?.textContent || title;

    var summaryEl = document.getElementById('sitrep-modal-summary');
    if (summaryEl) summaryEl.textContent = card.querySelector('.news-summary')?.textContent || summary;

    var sourceEl = document.getElementById('sitrep-modal-source');
    if (sourceEl) sourceEl.textContent = source.toUpperCase();

    var timeEl = document.getElementById('sitrep-modal-time');
    if (timeEl) timeEl.textContent = time;

    var linkEl = document.getElementById('sitrep-modal-link');
    if (linkEl) linkEl.href = link;

    var countryEl = document.getElementById('sitrep-modal-country');
    if (countryEl) {
        countryEl.className = 'news-country-tag ' + countryTag.toLowerCase();
        countryEl.textContent = countryTag === 'COL' ? '🇨🇴 COL' : (countryTag === 'VEN' ? '🇻🇪 VEN' : '🌐 INTL');
    }

    var sevEl = document.getElementById('sitrep-modal-severity');
    if (sevEl) {
        sevEl.className = 'news-severity-tag ' + severity.toLowerCase();
        sevEl.textContent = severity === 'CRITICAL' ? '🔴 CRÍTICO' : (severity === 'HIGH' ? '🟠 ALTO' : (severity === 'MEDIUM' ? '🟡 MEDIO' : '🔵 INFO'));
    }

    var imgWrapper = document.getElementById('sitrep-modal-img-wrapper');
    var imgEl = document.getElementById('sitrep-modal-img');
    if (img && imgWrapper && imgEl) {
        imgEl.src = img;
        imgWrapper.style.display = 'block';
    } else if (imgWrapper) {
        imgWrapper.style.display = 'none';
    }

    // Populate Multi-Source Box
    var sourcesBox = document.getElementById('sitrep-modal-sources-box');
    var sourcesList = document.getElementById('sitrep-modal-sources-list');
    var sourcesCountBadge = document.getElementById('sitrep-modal-sources-count');
    var totalSourcesCount = 1 + relatedSources.length;

    if (sourcesBox && sourcesList) {
        if (sourcesCountBadge) sourcesCountBadge.textContent = totalSourcesCount + (totalSourcesCount === 1 ? ' FUENTE' : ' FUENTES');
        
        var mainSourceHtml = `
            <div class="flex-between items-center p-1 rounded" style="background:rgba(0,229,255,0.08); border-left:3px solid var(--primary);">
                <div class="flex items-center gap-05">
                    <span class="text-primary font-bold text-xs">⭐ ${source.toUpperCase()} (Principal)</span>
                </div>
                <a href="${link}" target="_blank" rel="noopener noreferrer" class="text-xs text-primary font-mono" style="text-decoration:underline;">Abrir Noticia ↗</a>
            </div>
        `;

        var relatedHtml = relatedSources.map(s => `
            <div class="flex-between items-center p-1 rounded" style="background:rgba(255,255,255,0.03); border-left:3px solid rgba(255,255,255,0.2);">
                <div>
                    <span class="text-white font-mono text-xs font-bold">${(s.source || 'OSINT').toUpperCase()}:</span>
                    <span class="text-muted text-xs ms-1">${(s.title || '').slice(0, 70)}...</span>
                </div>
                <a href="${s.link || '#'}" target="_blank" rel="noopener noreferrer" class="text-xs text-muted font-mono" style="text-decoration:underline;">Ver ↗</a>
            </div>
        `).join('');

        sourcesList.innerHTML = mainSourceHtml + relatedHtml;
    }

    var entitiesContainer = document.getElementById('sitrep-modal-entities');
    if (entitiesContainer) {
        var textCombined = ((card.querySelector('.news-title')?.textContent || title) + ' ' + (card.querySelector('.news-summary')?.textContent || summary)).toLowerCase();
        var knownEntities = ['FANB', 'ELN', 'EMC', 'CLAN DEL GOLFO', 'PETRO', 'MADURO', 'BOGOTÁ', 'CARACAS', 'CÚCUTA', 'ARAUCA', 'APURE', 'SANCIÓN', 'PAGO', 'FRONTERA', 'DRONES'];
        var found = [];
        knownEntities.forEach(function(e) {
            if (textCombined.includes(e.toLowerCase())) found.push(e);
        });
        if (!found.length) found = ['OSINT FEED', 'COBALTO INTELLIGENCE'];

        entitiesContainer.innerHTML = found.map(function(e) {
            return `<span class="config-chip" style="font-size:0.7rem; background:rgba(0,229,255,0.08); border:1px solid rgba(0,229,255,0.2); color:var(--primary);">${e}</span>`;
        }).join('');
    }

    var aiBox = document.getElementById('sitrep-modal-ai-box');
    if (aiBox) aiBox.style.display = 'none';

    modal.style.display = 'flex';
};

window.closeSitrepReader = function() {
    var modal = document.getElementById('sitrep-reader-modal');
    if (modal) modal.style.display = 'none';
};

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') window.closeSitrepReader();
});

window.analyzeSitrepModalAI = function() {
    if (!window._activeSitrepModalData) return;
    var aiBox = document.getElementById('sitrep-modal-ai-box');
    var aiContent = document.getElementById('sitrep-modal-ai-content');
    var btn = document.getElementById('btn-sitrep-modal-ai');
    if (!aiBox || !aiContent) return;

    aiBox.style.display = 'block';
    aiContent.textContent = '⏳ Analizando contexto operacional con IA...';
    if (btn) btn.disabled = true;

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: 'Genera un desglose operacional táctico breve (1. Antecedentes, 2. Impacto Operativo en el Teatro, 3. Recomendación) para esta noticia: ' + window._activeSitrepModalData.title + ' — Resumen: ' + window._activeSitrepModalData.summary
        })
    })
    .then(r => r.json())
    .then(data => {
        aiContent.textContent = data.response || data.reply || 'Análisis completado sin observaciones adicionales.';
    })
    .catch(err => {
        aiContent.textContent = '⚠️ Error conectando con el motor IA: ' + err.message;
    })
    .finally(() => {
        if (btn) btn.disabled = false;
    });
};

/* ── TACTICAL TOAST NOTIFICATION CENTER ─────────────────────────────────── */
if (!window.showTacticalToast) {
    window.showTacticalToast = function(msg, type, title) {
        var container = document.getElementById('tactical-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'tactical-toast-container';
            container.style.cssText = 'position:fixed; bottom:20px; right:20px; z-index:99998; display:flex; flex-direction:column-reverse; gap:8px; pointer-events:none; max-width:360px;';
            document.body.appendChild(container);
        }
        type = type || 'info';
        var color = type === 'danger' || type === 'error' ? '#FF2D55' : type === 'success' ? '#00FFAA' : type === 'warning' ? '#FF9500' : '#00E5FF';
        var icon = type === 'danger' || type === 'error' ? '🚨' : type === 'success' ? '✓' : type === 'warning' ? '⚠️' : 'ℹ️';

        var toast = document.createElement('div');
        toast.style.cssText = 'pointer-events:auto; background:rgba(10,11,16,0.95); border:1px solid ' + color + '; border-left:4px solid ' + color + '; padding:10px 14px; border-radius:6px; color:#FFF; font-family:\'Roboto Mono\',monospace; font-size:0.75rem; box-shadow:0 4px 20px rgba(0,0,0,0.6), 0 0 10px ' + color + '33; backdrop-filter:blur(8px); transition:all 0.3s ease; opacity:0; transform:translateY(10px); display:flex; flex-direction:column; gap:4px;';
        
        var headerHtml = '<div style="display:flex; justify-content:space-between; align-items:center;">' +
            '<span style="font-weight:bold; color:' + color + ';">' + icon + ' ' + (title || type.toUpperCase()) + '</span>' +
            '<span style="color:#64748B; cursor:pointer; font-size:0.8rem;" onclick="this.closest(\'div\').parentElement.remove()">✕</span>' +
            '</div>';
        
        toast.innerHTML = headerHtml + '<div style="color:#CBD5E1; font-size:0.75rem; line-height:1.3;">' + msg + '</div>';
        
        container.appendChild(toast);
        setTimeout(function() {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        }, 10);
        
        setTimeout(function() {
            if (toast.parentElement) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(10px)';
                setTimeout(function() { if (toast.parentElement) toast.parentElement.removeChild(toast); }, 300);
            }
        }, 6000);
    };
}



