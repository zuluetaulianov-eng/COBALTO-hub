/**
 * Cobalto Hub - Intel Module
 * Encapsula la lógica de filtrado, ordenamiento y exportación de inteligencia.
 */

window.CobaltoIntel = {
    // --- INTEL CLASIFICADA ---
    toggleIntelFull: function(btn) {
        var card = btn.parentElement;
        var full = card.querySelector('.intel-full');
        var summary = card.querySelector('.intel-summary');
        if (!full) return;
        var hidden = full.style.display === 'none' || full.style.display === '';
        full.style.display = hidden ? 'block' : 'none';
        if (summary) summary.style.display = hidden ? 'none' : 'block';
        btn.textContent = hidden ? '\u2212 Leer menos' : '+ Leer m\u00E1s';
    },

    filterIntel: function() {
        var searchEl = document.getElementById('intel-search');
        var filterEl = document.getElementById('intel-tag-filter');
        var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
        var tag = filterEl ? filterEl.value : 'all';
        var cards = document.querySelectorAll('.intel-card');
        var visible = 0;
        cards.forEach(function(c) {
            var title = c.getAttribute('data-title') || '';
            var tags = (c.getAttribute('data-tags') || '').toLowerCase();
            var matchTag = tag === 'all' || tags.includes(tag.toLowerCase());
            var matchQ = !q || title.includes(q);
            c.style.display = matchTag && matchQ ? 'block' : 'none';
            if (matchTag && matchQ) visible++;
        });
        var totalEl = document.getElementById('intel-total-display');
        if (totalEl) totalEl.textContent = visible + '/' + cards.length;
        
        // Persistence
        this.saveFilter('intel_q', q);
    },

    filterIntelTag: function(tag) {
        var sel = document.getElementById('intel-tag-filter');
        if (sel) sel.value = tag;
        this.filterIntel();
    },

    sortIntel: function() {
        var sortEl = document.getElementById('intel-sort');
        var sort = sortEl ? sortEl.value : 'date';
        var grid = document.getElementById('intel-grid');
        if (!grid) return;
        var cards = Array.from(grid.querySelectorAll('.intel-card'));
        cards.sort(function(a, b) {
            if (sort === 'date') {
                var da = a.getAttribute('data-date') || '';
                var db = b.getAttribute('data-date') || '';
                var tsa = Date.parse(da) || 0;
                var tsb = Date.parse(db) || 0;
                if (tsa !== tsb) return tsb - tsa;
                return db.localeCompare(da);
            } else {
                var ta = a.getAttribute('data-title') || '';
                var tb = b.getAttribute('data-title') || '';
                return ta.localeCompare(tb);
            }
        });
        const frag = document.createDocumentFragment();
        cards.forEach(function(c) { frag.appendChild(c); });
        grid.appendChild(frag);
    },

    // --- RADAR SOCIAL ---
    toggleSocialGroup: function(header) {
        if (!header) return;
        var panel = header.closest('.social-group-panel') || header.parentElement;
        if (!panel) return;
        var items = panel.querySelector('.social-items');
        var toggle = header.querySelector('.social-toggle');
        if (!items) return;

        var currentDisplay = items.style.display || window.getComputedStyle(items).display;
        var isHidden = currentDisplay === 'none';

        items.style.display = isHidden ? 'grid' : 'none';
        if (toggle) {
            toggle.style.transform = isHidden ? 'rotate(90deg)' : 'rotate(0deg)';
        }
    },

    expandAllSocial: function() {
        document.querySelectorAll('.social-items').forEach(function(el) { el.style.display = 'grid'; });
        document.querySelectorAll('.social-toggle').forEach(function(el) { el.style.transform = 'rotate(90deg)'; });
    },

    collapseAllSocial: function() {
        document.querySelectorAll('.social-items').forEach(function(el) { el.style.display = 'none'; });
        document.querySelectorAll('.social-toggle').forEach(function(el) { el.style.transform = 'rotate(0deg)'; });
    },

    _socialPlatformFilter: 'ALL',
    _socialTheaterFilter: 'ALL',

    setSocialPlatformFilter: function(platform) {
        this._socialPlatformFilter = platform;
        var chips = document.querySelectorAll('#social-platform-chips .config-chip');
        chips.forEach(function(c) {
            if (c.getAttribute('data-platform') === platform) c.classList.add('active');
            else c.classList.remove('active');
        });
        this.filterSocial();
    },

    setSocialTheaterFilter: function(theater) {
        this._socialTheaterFilter = theater;
        var chips = document.querySelectorAll('#social-theater-chips .config-chip');
        chips.forEach(function(c) {
            if (c.getAttribute('data-theater') === theater) c.classList.add('active');
            else c.classList.remove('active');
        });
        this.filterSocial();
    },

    sendToRag: function(title, summary) {
        if (window.switchTab) {
            window.switchTab('intel');
        }
        const queryInput = document.getElementById('intel-query-input');
        if (queryInput) {
            queryInput.value = (title + (summary ? ': ' + summary : '')).trim();
            queryInput.focus();
            queryInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (window.CobaltoConfig && CobaltoConfig.showToast) {
            CobaltoConfig.showToast('Tema cargado en Centro de Investigación. Haz clic en Ejecutar.', 'info');
        }
    },

    sendItemToRag: function(btn) {
        if (!btn) return;
        var title = btn.getAttribute('data-title') || '';
        var summary = btn.getAttribute('data-summary') || '';
        this.sendToRag(title, summary);
    },

    filterSocial: function() {
        var searchEl = document.getElementById('social-search');
        var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
        var platform = this._socialPlatformFilter || 'ALL';
        var theater = this._socialTheaterFilter || 'ALL';
        var isFiltering = q !== '' || platform !== 'ALL' || theater !== 'ALL';

        var groups = document.querySelectorAll('.social-group');
        var totalVisible = 0;
        var srcVisible = 0;

        var self = this;
        groups.forEach(function(g) {
            var items = g.querySelectorAll('.social-item');
            var itemsContainer = g.querySelector('.social-items');
            var toggleIcon = g.querySelector('.social-toggle');
            var anyItemInGroup = false;

            items.forEach(function(it) {
                var text = (it.getAttribute('data-search-text') || '').toLowerCase();
                var srcType = (it.getAttribute('data-source-type') || 'NEWS').toUpperCase();

                // Match Keyword
                var matchQ = !q || text.includes(q);

                // Match Platform
                var matchPlat = (platform === 'ALL') ||
                    (platform === 'TELEGRAM' && srcType === 'TELEGRAM') ||
                    (platform === 'REDDIT' && srcType === 'REDDIT') ||
                    (platform === 'NEWS' && srcType === 'NEWS') ||
                    (platform === 'BLUESKY' && text.includes('bluesky')) ||
                    (platform === 'MASTODON' && text.includes('mastodon'));

                // Match Theater
                var matchTheater = (theater === 'ALL') ||
                    (theater === 'COL' && (text.includes('colombia') || text.includes('bogot') || text.includes('medellin') || text.includes('eln') || text.includes('petro'))) ||
                    (theater === 'VEN' && (text.includes('venezuela') || text.includes('caracas') || text.includes('vzla') || text.includes('maduro')));

                var show = matchQ && matchPlat && matchTheater;
                it.style.display = show ? 'flex' : 'none';
                if (show) anyItemInGroup = true;
            });

            g.style.display = anyItemInGroup ? 'block' : 'none';

            if (anyItemInGroup) {
                srcVisible++;
                if (itemsContainer && isFiltering) {
                    itemsContainer.style.display = 'grid';
                    if (toggleIcon) toggleIcon.style.transform = 'rotate(90deg)';
                }
                var visibleItems = g.querySelectorAll('.social-item[style*="display: flex"], .social-item[style*="display:block"]');
                totalVisible += visibleItems.length;
            }
        });

        var kpiTotalEl = document.getElementById('social-kpi-total');
        var srcEl = document.getElementById('social-src-display');
        if (srcEl) srcEl.textContent = srcVisible + ' grupos (' + totalVisible + ' publicaciones)';
        
        this.saveFilter('social_q', q);
    },

    filterSocialPrefix: function(prefix) {
        var q = document.getElementById('social-search');
        if (q) q.value = '';
        var groups = document.querySelectorAll('.social-group');
        if (!prefix) {
            groups.forEach(function(g) { g.style.display = 'block'; });
        } else {
            this.collapseAllSocial();
            groups.forEach(function(g) {
                var p = g.getAttribute('data-prefix') || '';
                var match = p === prefix;
                g.style.display = match ? 'block' : 'none';
                if (match) {
                    var items = g.querySelector('.social-items');
                    if (items) items.style.display = 'grid';
                    var toggle = g.querySelector('.social-toggle');
                    if (toggle) toggle.style.transform = 'rotate(90deg)';
                }
            });
        }
        var pills = document.querySelectorAll('.social-pill');
        pills.forEach(function(p) {
            var pp = p.getAttribute('data-prefix');
            if (!prefix || pp === prefix) { p.style.opacity = '1'; p.style.borderColor = ''; }
            else { p.style.opacity = '0.35'; p.style.borderColor = 'transparent'; }
        });
        this.updateSocialCounts();
    },

    updateSocialCounts: function() {
        var groups = document.querySelectorAll('.social-group');
        var total = 0;
        var srcCount = 0;
        groups.forEach(function(g) {
            if (g.style.display !== 'none') {
                var items = g.querySelectorAll('.social-item');
                var visible = 0;
                items.forEach(function(it) { if (it.style.display !== 'none') visible++; });
                total += visible;
                if (visible > 0) srcCount++;
            }
        });
        var totalEl = document.getElementById('social-total-display');
        var srcEl = document.getElementById('social-src-display');
        if (totalEl) totalEl.textContent = total;
        if (srcEl) srcEl.textContent = srcCount;
    },

    exportSocialReport: function() {
        var groups = document.querySelectorAll('.social-group');
        var report = `========================================================\n`;
        report += `COBALTO HUB - INFORME TÁCTICO DE REDES SOCIALES & OSINT\n`;
        report += `FECHA DE EXTRACCIÓN: ${new Date().toISOString()}\n`;
        report += `FILTROS ACTIVOS: Plataforma: ${this._socialPlatformFilter || 'ALL'} | Teatro: ${this._socialTheaterFilter || 'ALL'}\n`;
        report += `========================================================\n\n`;

        var totalItems = 0;
        groups.forEach(function(g, gIdx) {
            if (g.style.display === 'none') return;
            var groupName = g.getAttribute('data-group-name') || `Grupo ${gIdx + 1}`;
            var items = g.querySelectorAll('.social-item');
            var visibleItems = [];
            items.forEach(function(it) {
                if (it.style.display !== 'none') visibleItems.push(it);
            });

            if (visibleItems.length > 0) {
                report += `[${gIdx + 1}] CANAL / FUENTE: ${groupName} (${visibleItems.length} publicaciones)\n`;
                report += `--------------------------------------------------------\n`;
                visibleItems.forEach(function(it, iIdx) {
                    var titleEl = it.querySelector('a');
                    var title = titleEl ? titleEl.textContent.trim() : 'Sin título';
                    var link = titleEl ? titleEl.getAttribute('href') : '';
                    var summaryEl = it.querySelector('p');
                    var summary = summaryEl ? summaryEl.textContent.trim() : '';
                    var tagEl = it.querySelector('.social-tag');
                    var tag = tagEl ? tagEl.textContent.trim() : '';

                    report += `${iIdx + 1}. [${tag}] ${title}\n`;
                    if (summary) report += `   • Resumen: ${summary}\n`;
                    if (link) report += `   • Enlace: ${link}\n`;
                    report += `\n`;
                    totalItems++;
                });
            }
        });

        report += `========================================================\n`;
        report += `TOTAL DE PUBLICACIONES MONITOREADAS: ${totalItems}\n`;
        report += `FIN DE INFORME - COBALTO HUB RADAR SOCIAL\n`;

        var blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = `SITREP_REDES_SOCIALES_${new Date().toISOString().slice(0, 10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    refreshSocial: function() {
        if (window.CobaltoCore && window.CobaltoCore.lazyLoadTab) {
            var self = this;
            window.CobaltoCore.lazyLoadTab('tab-social', '/api/social', function(data) {
                if (window.CobaltoCore.renderSocialTab) window.CobaltoCore.renderSocialTab(data);
                self.filterSocial();
                var timeEl = document.getElementById('social-last-sync-time');
                if (timeEl) {
                    var now = new Date();
                    timeEl.textContent = 'Sincronizado: ' + now.toLocaleTimeString();
                }
            });
        }
    },

    toggleSocialAutoRefresh: function(btn) {
        if (this._socialAutoRefreshInterval) {
            clearInterval(this._socialAutoRefreshInterval);
            this._socialAutoRefreshInterval = null;
            if (btn) {
                btn.style.background = 'transparent';
                btn.style.borderColor = 'rgba(255,255,255,0.2)';
                btn.textContent = '⏱️ AUTO-REFRESCO (OFF)';
            }
        } else {
            this.refreshSocial();
            var self = this;
            this._socialAutoRefreshInterval = setInterval(function() {
                self.refreshSocial();
            }, 60000);
            if (btn) {
                btn.style.background = 'rgba(0, 229, 255, 0.15)';
                btn.style.borderColor = '#00E5FF';
                btn.textContent = '⏱️ AUTO-REFRESCO (60s ON)';
            }
        }
    },

    showOperatorGuide: function() {
        var existing = document.getElementById('modal-operator-guide');
        if (existing) { existing.style.display = 'flex'; return; }

        var modal = document.createElement('div');
        modal.id = 'modal-operator-guide';
        modal.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.85); backdrop-filter:blur(8px); z-index:99999; display:flex; align-items:center; justify-content:center; padding:20px;';
        modal.innerHTML = `
            <div style="background: linear-gradient(180deg, rgba(16,22,34,0.98) 0%, rgba(10,11,16,1) 100%); border: 1px solid #FFCC00; border-radius: 12px; max-width: 650px; width: 100%; padding: 25px; box-shadow: 0 0 35px rgba(255,204,0,0.2); font-family: 'Inter', sans-serif; color: #fff; position: relative;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,204,0,0.3); padding-bottom:12px; margin-bottom:18px;">
                    <div style="font-family:'Roboto Mono',monospace; color:#FFCC00; font-size:1.1rem; font-weight:bold;">❓ GUÍA TÁCTICA DE OPERACIONES (SOC/OSINT)</div>
                    <button onclick="document.getElementById('modal-operator-guide').style.display='none';" style="background:transparent; border:none; color:#aaa; font-size:1.4rem; cursor:pointer;">✕</button>
                </div>
                <div style="display:flex; flex-direction:column; gap:14px; font-size:0.88rem; line-height:1.6; color:#d1d5db;">
                    <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:6px; border-left:3px solid #00E5FF;">
                        <strong style="color:#00E5FF;">1. SELECCIÓN DE TEATRO & FILTRADO:</strong> Usa los chips superiores (<span style="color:#fff;">🇨🇴 COLOMBIA</span>, <span style="color:#fff;">🇻🇪 VENEZUELA</span>) o escribe una palabra clave para aislar amenazas en zonas específicas.
                    </div>
                    <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:6px; border-left:3px solid #FF2D55;">
                        <strong style="color:#FF2D55;">2. ANÁLISIS RAG E HIPÓTESIS:</strong> Haz clic en <span style="color:#00E5FF;">🎯 RAG IA</span> en cualquier publicación para enviarla a la Inteligencia Artificial Local (Ollama) e inferir repercusiones de seguridad.
                    </div>
                    <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:6px; border-left:3px solid #B388FF;">
                        <strong style="color:#B388FF;">3. MAPEO DE RELACIONES (GRAFO):</strong> Pulsa <span style="color:#B388FF;">🕸️ GRAFO DE ENTIDADES</span> para ver a los actores clave. La métrica <em>"Influencia Macro"</em> señala a los líderes de opinión y <em>"Nodo Enlace"</em> a los puentes de desinformación.
                    </div>
                    <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:6px; border-left:3px solid #FFCC00;">
                        <strong style="color:#FFCC00;">4. REPORTES EJECUTIVOS (SITREP):</strong> Exporta el resumen del turno con <span style="color:#FF2D55;">📄 EXPORTAR SITREP SOCIAL</span> o la topología completa de la red con el botón <span style="color:#fff;">💾 EXPORTAR JSON</span> en el grafo.
                    </div>
                </div>
                <div style="margin-top:20px; text-align:right;">
                    <button onclick="document.getElementById('modal-operator-guide').style.display='none';" class="btn-tactical" style="background:#FFCC00; color:#000; font-weight:bold; border:none; padding:8px 20px; cursor:pointer;">ENTENDIDO</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    },

    // --- ALERTAS ---
    filterAlerts: function() {
        var searchEl = document.getElementById('alert-search');
        var levelEl = document.getElementById('alert-level-filter');
        var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
        var rawLvl = levelEl ? levelEl.value : 'all';
        var lvl = rawLvl.replace(/[^\w\s]/g, '').trim();
        var cards = document.querySelectorAll('.alert-card');
        var pills = document.querySelectorAll('.alert-pill');
        var visible = 0;
        cards.forEach(function(c) {
            var title = c.getAttribute('data-title') || '';
            var source = c.getAttribute('data-source') || '';
            var level = (c.getAttribute('data-level') || '').replace(/[^\w\s]/g, '').trim();
            var matchLvl = lvl === 'all' || level.includes(lvl) || lvl.includes(level);
            var matchQ = !q || title.includes(q) || source.includes(q);
            var show = matchLvl && matchQ;
            c.style.display = show ? 'block' : 'none';
            if (show) visible++;
        });
        var totalEl = document.getElementById('alert-total-display');
        if (totalEl) totalEl.textContent = visible + '/' + cards.length;
        pills.forEach(function(p) {
            var pLvl = p.getAttribute('data-level');
            if (lvl === 'all' || pLvl === lvl) { p.style.opacity = '1'; p.style.borderColor = ''; }
            else { p.style.opacity = '0.4'; p.style.borderColor = 'transparent'; }
        });
        
        // Persistence
        this.saveFilter('alert_q', q);
    },

    filterAlertLevel: function(lvl) {
        var sel = document.getElementById('alert-level-filter');
        if (sel) sel.value = lvl;
        this.filterAlerts();
    },

    sortAlerts: function() {
        var sortEl = document.getElementById('alert-sort');
        var sort = sortEl ? sortEl.value : 'level';
        var list = document.getElementById('alert-list');
        if (!list) return;
        var cards = Array.from(list.querySelectorAll('.alert-card'));
        var levelWeight = { '\uD83D\uDD34 CR\u00CDTICO': 0, '\uD83D\uDFE0 URGENTE': 1, '\uD83D\uDD35 CYBER': 2, '\uD83D\uDFE1 ATENCI\u00D3N': 3 };
        cards.sort(function(a, b) {
            switch(sort) {
                case 'level':
                    var la = levelWeight[a.getAttribute('data-level')] || 4;
                    var lb = levelWeight[b.getAttribute('data-level')] || 4;
                    return la - lb;
                case 'time':
                    var ta = a.getAttribute('data-timestamp') || '';
                    var tb = b.getAttribute('data-timestamp') || '';
                    var tsa = Date.parse(ta) || 0;
                    var tsb = Date.parse(tb) || 0;
                    if (tsa !== tsb) return tsb - tsa;
                    return tb.localeCompare(ta);
                case 'source':
                    var sa = a.getAttribute('data-source') || '';
                    var sb = b.getAttribute('data-source') || '';
                    return sa.localeCompare(sb);
                default: return 0;
            }
        });
        const frag = document.createDocumentFragment();
        cards.forEach(function(c) { frag.appendChild(c); });
        list.appendChild(frag);
    },

    exportAlertsJSON: function() {
        var data = { timestamp: new Date().toISOString(), total: (window._alertData || []).length, alerts: window._alertData || [] };
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'cobalto_alertas_' + new Date().toISOString().slice(0,10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
    },

    // --- TIEMPO REAL ---
    filterRT: function() {
        var searchEl = document.getElementById('rt-search');
        var catEl = document.getElementById('rt-category');
        var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
        var cat = catEl ? catEl.value : 'all';
        var cards = document.querySelectorAll('.rt-card');
        var visible = 0;
        cards.forEach(function(c) {
            var title = c.getAttribute('data-title') || '';
            var source = c.getAttribute('data-source') || '';
            var category = c.getAttribute('data-category') || '';
            var matchCat = cat === 'all' || category === cat;
            var matchQ = !q || title.includes(q) || source.includes(q);
            var show = matchCat && matchQ;
            c.style.display = show ? 'block' : 'none';
            if (show) visible++;
        });
        var totalEl = document.getElementById('rt-total-display');
        if (totalEl) totalEl.textContent = visible + '/' + cards.length;
    },

    filterRTCategory: function(cat) {
        var sel = document.getElementById('rt-category');
        if (sel) sel.value = cat;
        this.filterRT();
    },

    sortRT: function() {
        var sortEl = document.getElementById('rt-sort');
        var sort = sortEl ? sortEl.value : 'date';
        var grid = document.getElementById('rt-grid');
        if (!grid) return;
        var cards = Array.from(grid.querySelectorAll('.rt-card'));
        cards.sort(function(a, b) {
            switch(sort) {
                case 'date':
                    var da = a.getAttribute('data-published') || '';
                    var db = b.getAttribute('data-published') || '';
                    var tsa = Date.parse(da) || 0;
                    var tsb = Date.parse(db) || 0;
                    if (tsa !== tsb) return tsb - tsa;
                    return db.localeCompare(da);
                case 'type':
                    var ta = a.getAttribute('data-type') || '';
                    var tb = b.getAttribute('data-type') || '';
                    return ta.localeCompare(tb);
                case 'source':
                    var sa = a.getAttribute('data-source') || '';
                    var sb = b.getAttribute('data-source') || '';
                    return sa.localeCompare(sb);
                default: return 0;
            }
        });
        const frag = document.createDocumentFragment();
        cards.forEach(function(c) { frag.appendChild(c); });
        grid.appendChild(frag);
    },

    // --- INTEL EXPORT ---
    exportIntelJSON: function() {
        var data = { timestamp: new Date().toISOString(), reports: window._ownPosts || [] };
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'cobalto_intel_' + new Date().toISOString().slice(0,10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
    },

    // --- Persistence ---
    saveFilter: function(key, value) {
        localStorage.setItem('cobalto_filter_' + key, value);
    },

    loadAllFilters: function() {
        var intelQ = localStorage.getItem('cobalto_filter_intel_q');
        if (intelQ) { var el = document.getElementById('intel-search'); if (el) { el.value = intelQ; this.filterIntel(); } }
        var socialQ = localStorage.getItem('cobalto_filter_social_q');
        if (socialQ) { var el = document.getElementById('social-search'); if (el) { el.value = socialQ; this.filterSocial(); } }
        var alertQ = localStorage.getItem('cobalto_filter_alert_q');
        if (alertQ) { var el = document.getElementById('alert-search'); if (el) { el.value = alertQ; this.filterAlerts(); } }
    },



    // --- CENTRO DE INVESTIGACIÓN E INFORMES DE INTELIGENCIA (IA LOCAL) ---
    currentResearchData: null,

    executeResearch: async function() {
        const queryInput = document.getElementById('intel-query-input');
        const presetSelect = document.getElementById('intel-preset-select');
        const includeRagCheck = document.getElementById('intel-include-rag');
        const btn = document.getElementById('btn-execute-research');
        const container = document.getElementById('intel-report-container');

        if (!queryInput || !queryInput.value.trim()) {
            if (window.CobaltoConfig && CobaltoConfig.showToast) {
                CobaltoConfig.showToast('Por favor introduce un tema o pregunta para la investigación', 'warning');
            } else {
                alert('Por favor introduce un tema o pregunta para la investigación');
            }
            return;
        }

        const query = queryInput.value.trim();
        const preset = presetSelect ? presetSelect.value : 'general';
        const includeRag = includeRagCheck ? includeRagCheck.checked : true;
        const useAiCheck = document.getElementById('intel-use-ai');
        const useAi = useAiCheck ? useAiCheck.checked : true;
        const originalBtnText = btn ? btn.innerHTML : '';

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = useAi ? '⏳ PENSANDO E INFERIENDO (OLLAMA)...' : '⚡ SINTETIZANDO INFORME FÁCTICO...';
            btn.style.opacity = '0.75';
        }

        // ESTADO 1: PENSANDO / BUSCANDO EN RAG
        let startTime = Date.now();
        let stepTimer;
        
        if (container) {
            container.innerHTML = `
                <div style="background: linear-gradient(180deg, rgba(16,22,34,0.95) 0%, rgba(10,11,16,0.98) 100%); border: 1px solid rgba(0,229,255,0.4); border-radius: 12px; padding: 40px 30px; text-align: center; box-shadow: 0 10px 35px rgba(0,229,255,0.12); position: relative; overflow: hidden;">
                    <style>
                        @keyframes pureSpin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                        .tactical-spinner { display: inline-block; width: 12px; height: 12px; border: 2px solid rgba(0,229,255,0.3); border-top-color: #00e5ff; border-radius: 50%; animation: pureSpin 0.75s linear infinite; vertical-align: middle; margin-right: 8px; }
                        .tactical-progress-bar { width: 0%; height: 6px; background: linear-gradient(90deg, #00e5ff, #34d399); border-radius: 3px; transition: width 0.4s ease; box-shadow: 0 0 10px rgba(0,229,255,0.5); }
                    </style>

                    <div style="display: inline-flex; align-items: center; gap: 10px; background: rgba(0,229,255,0.1); border: 1px solid rgba(0,229,255,0.3); padding: 6px 18px; border-radius: 20px; margin-bottom: 20px;">
                        <span class="ai-status-dot" style="width: 12px; height: 12px; background: #00e5ff; box-shadow: 0 0 10px #00e5ff; animation: pulse 1s infinite;"></span>
                        <span style="color: #00e5ff; font-family: 'Roboto Mono', monospace; font-size: 0.85rem; font-weight: bold; letter-spacing: 1.5px;">ESTADO: ${useAi ? 'PROCESANDO CON IA LOCAL OLLAMA' : 'SINTETIZANDO MOTOR FÁCTICO (SIN IA)'}</span>
                    </div>

                    <h3 style="color: #ffffff; font-size: 1.1rem; margin-bottom: 8px; font-weight: bold;">INVESTIGANDO: "${this.escapeHTML(query)}"</h3>
                    <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 20px;">Recuperando contexto fáctico RAG y generando informe de inteligencia...</p>
                    
                    <!-- Barra de Progreso Dinámica -->
                    <div style="max-width: 520px; margin: 0 auto 20px; background: rgba(255,255,255,0.06); border-radius: 6px; padding: 3px; border: 1px solid rgba(255,255,255,0.1);">
                        <div id="intel-bar-fill" class="tactical-progress-bar"></div>
                    </div>

                    <div id="intel-progress-steps" style="max-width: 520px; margin: 0 auto; text-align: left; background: rgba(0,0,0,0.4); padding: 18px 22px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); font-family: 'Roboto Mono', monospace; font-size: 0.82rem; line-height: 1.8;">
                        <div id="step-1" style="color: #00e5ff;"><span class="tactical-spinner"></span> 1. Consultando base de datos fáctica RAG...</div>
                        <div id="step-2" style="color: var(--text-muted);">&bull; 2. ${useAi ? 'Enviando prompt y contexto a Ollama' : 'Procesando reglas fácticas y matriz de datos'}...</div>
                        <div id="step-3" style="color: var(--text-muted);">&bull; 3. Generando matriz de amenazas e informe estructurado...</div>
                    </div>

                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 18px; font-family: 'Roboto Mono', monospace;">
                        ⏱️ Tiempo en ejecución: <span id="intel-elapsed-counter" style="color: var(--primary); font-weight: bold;">0s</span>
                    </div>
                </div>
            `;

            // Timer de segundos transcurridos y actualización progresiva
            stepTimer = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const el = document.getElementById('intel-elapsed-counter');
                const bar = document.getElementById('intel-bar-fill');
                if (el) el.innerText = elapsed + 's';
                
                let pct = Math.min(95, Math.floor((elapsed / 30) * 100));
                if (bar) bar.style.width = pct + '%';

                if (elapsed >= 1 && document.getElementById('step-2')) {
                    const s1 = document.getElementById('step-1');
                    const s2 = document.getElementById('step-2');
                    if (s1 && !s1.dataset.done) {
                        s1.dataset.done = 'true';
                        s1.style.color = '#34d399';
                        s1.innerHTML = '✓ 1. Base fáctica RAG recuperada correctamente';
                    }
                    if (s2 && !s2.dataset.active) {
                        s2.dataset.active = 'true';
                        s2.style.color = '#00e5ff';
                        s2.innerHTML = `<span class="tactical-spinner"></span> 2. ${useAi ? 'Inferencia activa en Ollama local...' : 'Generando síntesis determinística...'}`;
                    }
                }
            }, 500);
        }

        // Notificación Flotante de IA Pensando
        if (window.showAIThinkingToast) {
            window.showAIThinkingToast(useAi ? 'IA OLLAMA PENSANDO...' : 'MOTOR FÁCTICO GENERANDO...', `Procesando fuentes RAG sobre "${query.slice(0, 35)}..."`);
        }

        try {
            const resp = await fetch('/api/intel/research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, preset, include_rag: includeRag, use_ai: useAi })
            });

            if (stepTimer) clearInterval(stepTimer);

            const result = await resp.json();
            if (result.status === 'ok' && result.data) {
                // ESTADO 2: ESCRIBIENDO / RENDERIZADO COMPLETADO
                this.currentResearchData = result.data;
                this.renderResearchReport(result.data);
                this.addToResearchHistory(result.data);
                if (window.hideAIThinkingToast) {
                    window.hideAIThinkingToast(true, 'Informe de Inteligencia redactado con éxito');
                }
            } else {
                throw new Error(result.message || 'Error en la respuesta del backend');
            }
        } catch (err) {
            if (stepTimer) clearInterval(stepTimer);
            console.error('Error en investigacion:', err);
            
            if (window.hideAIThinkingToast) {
                window.hideAIThinkingToast(false, err.message || 'Fallo en la inferencia');
            }

            // ESTADO 3: ERROR CON OPCIÓN DE REINTENTO CLARA
            if (container) {
                container.innerHTML = `
                    <div style="background: rgba(255,45,85,0.08); border: 1px solid rgba(255,45,85,0.4); padding: 35px 25px; text-align: center; border-radius: 10px; box-shadow: 0 10px 30px rgba(255,45,85,0.15);">
                        <div style="font-size: 2.8rem; margin-bottom: 10px;">🚨</div>
                        <h3 style="color: #FF2D55; font-family: 'Roboto Mono', monospace; font-size: 1.1rem; letter-spacing: 1.5px; margin-bottom: 10px;">[ ERROR EN INFERENCIA / MOTOR OLLAMA ]</h3>
                        <p style="font-size: 0.9rem; color: #f87171; max-width: 550px; margin: 0 auto 18px; line-height: 1.5; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; font-family: monospace;">
                            ${this.escapeHTML(err.message || 'No se pudo obtener respuesta del modelo local Ollama.')}
                        </p>
                        <div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">
                            <button onclick="CobaltoIntel.executeResearch()" class="btn-tactical" style="background: #FF2D55; color: #fff; font-weight: bold; border: none; padding: 8px 20px; font-size: 0.85rem; border-radius: 6px; cursor: pointer;">
                                🔄 REINTENTAR INVESTIGACIÓN
                            </button>
                            <button onclick="if(window.switchTab){window.switchTab('config');setTimeout(function(){if(window.CobaltoConfig)CobaltoConfig.switchSubTab('subtab-ai');},150);}" class="btn-tactical" style="background: transparent; color: var(--primary); border: 1px solid var(--primary); padding: 8px 16px; font-size: 0.85rem; border-radius: 6px; cursor: pointer;">
                                ⚙️ VERIFICAR OLLAMA EN CONFIGURACIÓN
                            </button>
                        </div>
                    </div>
                `;
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalBtnText || '▶ EJECUTAR INVESTIGACIÓN Y GENERAR INFORME';
                btn.style.opacity = '1';
            }
        }
    },

    setQueryPreset: function(text) {
        const input = document.getElementById('intel-query-input');
        if (input) {
            input.value = text;
            input.focus();
        }
    },

    renderResearchReport: function(data) {
        const container = document.getElementById('intel-report-container');
        if (!container) return;

        const alertColor = data.nivel_alerta.includes('CRÍTICA') ? '#FF2D55' : (data.nivel_alerta.includes('ELEVADA') ? '#FF9500' : '#00E5FF');
        
        let docsHTML = '';
        if (Array.isArray(data.documentos) && data.documentos.length > 0) {
            docsHTML = `
                <div style="margin-top: 30px;">
                    <h4 style="color: var(--primary); font-family: 'Roboto Mono', monospace; font-size: 0.9rem; letter-spacing: 1px; margin-bottom: 15px; text-transform: uppercase;">📑 EVIDENCIA FÁCTICA RECUPERADA (RAG) (${data.documentos.length} FUENTES)</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
                        ${data.documentos.map(d => `
                            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-left: 3px solid var(--primary); padding: 12px; border-radius: 6px;">
                                <div style="color: #79C0FF; font-family: monospace; font-size: 0.75rem; font-weight: bold; margin-bottom: 4px;">[DOC ${d.doc_num}] ${this.escapeHTML(d.titulo)}</div>
                                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">Fuente: ${this.escapeHTML(d.fuente)} | Sentimiento: ${d.score_sentimiento}</div>
                                <div style="font-size: 0.8rem; color: #cbd5e1; line-height: 1.4; font-style: italic;">"${this.escapeHTML(d.contenido.slice(0, 140))}..."</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        container.innerHTML = `
            <div style="background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.3); border-radius: 6px; padding: 8px 14px; margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; font-size: 0.8rem; color: #34d399; font-family: 'Roboto Mono', monospace;">
                <span><i class="fas fa-check-circle"></i> ESTADO: INFORME REDACTADO Y FINALIZADO POR IA LOCAL</span>
                <span style="font-weight: bold;">[ COMPLETO ]</span>
            </div>
            <div style="background: linear-gradient(180deg, rgba(16,22,34,0.8) 0%, rgba(10,11,16,0.95) 100%); border: 1px solid rgba(0,229,255,0.25); border-radius: 10px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <!-- Header de Informe -->
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div style="color: var(--primary); font-family: 'Roboto Mono', monospace; font-size: 0.75rem; letter-spacing: 2px;">INFORME OSINT CODE: ${data.codigo}</div>
                        <h2 style="color: #fff; font-size: 1.2rem; margin: 4px 0; font-weight: bold;">${this.escapeHTML(data.tema_investigacion)}</h2>
                        <div style="color: var(--text-muted); font-size: 0.8rem;">Fecha: ${data.fecha_analisis} | Fuente: ${data.fuente_datos}</div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button onclick="CobaltoIntel.exportReport('docx')" class="btn-tactical" style="font-size: 0.8rem; padding: 6px 12px; border-color: #00E5FF; color: #00E5FF;" title="Descargar Word (.docx)"><i class="fas fa-file-word"></i> 📄 WORD (.DOCX)</button>
                        <button onclick="CobaltoIntel.exportReport('pdf')" class="btn-tactical" style="font-size: 0.8rem; padding: 6px 12px; border-color: #FF5050; color: #FF5050;" title="Descargar PDF"><i class="fas fa-file-pdf"></i> 📕 PDF</button>
                    </div>
                </div>

                <!-- Alert Level Box -->
                <div style="background: rgba(0,0,0,0.4); border-left: 4px solid ${alertColor}; padding: 12px 18px; border-radius: 4px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: ${alertColor}; font-family: 'Roboto Mono', monospace; font-weight: bold; font-size: 0.85rem; letter-spacing: 1.5px;">EVALUACIÓN DE ALERTA: ${data.nivel_alerta}</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">AUTOR: ${data.autor}</span>
                </div>

                <!-- Full AI Text -->
                <div style="color: #f1f5f9; font-size: 0.95rem; line-height: 1.7; white-space: pre-wrap; font-family: 'Inter', sans-serif; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                    ${this.formatMarkdown(data.analisis_completo)}
                </div>

                ${docsHTML}
            </div>
        `;
    },

    exportReport: async function(format) {
        if (!this.currentResearchData) return;
        const endpoint = format === 'pdf' ? '/api/intel/export_pdf' : '/api/intel/export_docx';
        try {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.currentResearchData)
            });
            if (!resp.ok) throw new Error('Error al generar el archivo');
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `informe_inteligencia_coporo_${Date.now()}.${format === 'pdf' ? 'pdf' : 'docx'}`;
            a.click();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            console.error('Error exportando informe:', e);
            alert('Error exportando el informe');
        }
    },

    addToResearchHistory: function(data) {
        const historyContainer = document.getElementById('briefing-history');
        if (!historyContainer) return;

        const empty = document.getElementById('briefing-empty');
        if (empty) empty.style.display = 'none';

        const item = document.createElement('div');
        item.style.cssText = 'background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 3px solid var(--primary); cursor: pointer; transition: background 0.2s;';
        item.innerHTML = `
            <div style="color: var(--primary); font-size: 0.8rem; margin-bottom: 4px; font-family: monospace;">${data.fecha_creacion}</div>
            <div style="font-size: 0.8rem; color: #fff; font-weight: bold; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${this.escapeHTML(data.tema_investigacion)}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">${data.nivel_alerta}</div>
        `;

        item.addEventListener('click', () => {
            this.currentResearchData = data;
            this.renderResearchReport(data);
        });

        historyContainer.insertBefore(item, historyContainer.firstChild);
    },

    formatMarkdown: function(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/### (.*?)(?:\r?\n|$)/g, '<h4 style="color: var(--primary); font-family: monospace; margin-top: 15px; margin-bottom: 8px;">$1</h4>')
            .replace(/## (.*?)(?:\r?\n|$)/g, '<h3 style="color: #00e5ff; font-family: monospace; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid rgba(0,229,255,0.2); padding-bottom: 4px;">$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #00e5ff;">$1</strong>')
            .replace(/- (.*?)(?:\r?\n|$)/g, '<li style="margin-left: 15px;">$1</li>');
    },

    escapeHTML: function(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
};

// Init on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    var first = document.querySelector('.social-items');
    if (first) first.style.display = 'grid';
    var firstToggle = document.querySelector('.social-toggle');
    if (firstToggle) firstToggle.style.transform = 'rotate(90deg)';
    window.CobaltoIntel.loadAllFilters();
});
