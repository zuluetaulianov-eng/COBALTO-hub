/**
 * Cobalto System Configuration Manager
 * Breathtaking premium administrative console interface controller
 */

window.CobaltoConfig = {
    state: {
        config: null,
        activeSubTab: 'subtab-rss',
        keywords: [],
        targetUsers: [],
        rssFeeds: {},
        telegramSources: [],
        priorityFeeds: [],
        trackingAircraft: {},
        trackingVessels: {}
    },

    init: function() {
        console.log('[COBALTO] Config Manager Initialized');
        this.applySavedTheme();
    },

    applySavedTheme: function() {
        const savedTheme = localStorage.getItem('cobalto-ui-theme') || 'cyber';
        this.setThemeClass(savedTheme);
        const selector = document.getElementById('config-ui-theme');
        if (selector) selector.value = savedTheme;
    },

    changeTheme: function(themeName) {
        localStorage.setItem('cobalto-ui-theme', themeName);
        this.setThemeClass(themeName);
        this.showToast('Tema visual actualizado', 'success');
    },

    setThemeClass: function(themeName) {
        document.body.classList.remove('theme-amoled', 'theme-light', 'theme-amoled-plus');
        if (themeName === 'amoled') {
            document.body.classList.add('theme-amoled');
        } else if (themeName === 'amoled-plus') {
            document.body.classList.add('theme-amoled-plus');
        } else if (themeName === 'light') {
            document.body.classList.add('theme-light');
        }
    },

    loadConfig: async function() {
        const container = document.getElementById('tab-config');
        if (!container) return;

        // Show loading spinner
        this.showLoadingState(true);

        try {
            const [response, envResponse] = await Promise.all([
                fetch('/api/config'),
                fetch('/api/env')
            ]);
            
            if (response.status === 401 || envResponse.status === 401) {
                this.showAuthError();
                return;
            }
            if (!response.ok) throw new Error('Failed to load settings');

            const data = await response.json();
            this.state.config = data;
            this.state.keywords = [...(data.KEYWORDS || [])];
            this.state.targetUsers = [...(data.TARGET_USERS || [])];
            this.state.rssFeeds = Object.assign({}, data.RSS_FEEDS || {});
            this.state.telegramSources = Object.assign({}, data.TELEGRAM_SOURCES || {});
            this.state.priorityFeeds = [...(data.PRIORITY_FEEDS || [])];
            this.state.trackingAircraft = Object.assign({}, data.TRACKING_AIRCRAFT || {});
            this.state.trackingVessels = Object.assign({}, data.TRACKING_VESSELS || {});

            this.populateFields();
            this.detectOllamaModels(true);
            this.renderRSSList();
            this.renderTelegramList();
            this.renderKeywords();
            this.renderTargetUsers();
            this.renderAircraftList();
            this.renderVesselList();

            if (envResponse.ok) {
                const envData = await envResponse.json();
                this.populateEnvFields(envData);
            }

            this.showLoadingState(false);
        } catch (error) {
            console.error('Error loading config:', error);
            this.showToast('Error al cargar la configuración', 'error');
            this.showLoadingState(false);
        }
    },

    showLoadingState: function(show) {
        const loader = document.getElementById('config-loader');
        const form = document.getElementById('config-form-container');
        if (loader && form) {
            loader.style.display = show ? 'flex' : 'none';
            form.style.opacity = show ? '0.3' : '1';
            form.style.pointerEvents = show ? 'none' : 'auto';
        }
    },

    showAuthError: function() {
        const container = document.getElementById('tab-config');
        if (container) {
            container.innerHTML = `
                <div class="empty-state" style="margin-top: 5rem;">
                    <div class="empty-icon" style="color: var(--threat-red);">🔒</div>
                    <p style="color: var(--threat-red); font-size: 1.2rem; font-weight: bold; letter-spacing: 2px;">ACCESO RESTRINGIDO</p>
                    <p style="max-width: 450px; margin: 0.5rem auto; font-size: 0.85rem; color: var(--text-muted);">
                        Requiere autenticación de administrador. Inicie sesión en la pantalla del sistema central.
                    </p>
                    <a href="/login" class="btn-tactical" style="margin-top: 1.5rem; display: inline-flex;">IR A INICIAR SESIÓN</a>
                </div>
            `;
        }
    },

    populateFields: function() {
        const cfg = this.state.config;
        if (!cfg) return;

        // Numeric fields
        document.getElementById('cfg-cache-max-age').value = cfg.CACHE_MAX_AGE_MINUTES || 15;
        document.getElementById('cfg-entry-max-age').value = cfg.ENTRY_MAX_AGE_HOURS || 48;
        document.getElementById('cfg-cycle-interval').value = cfg.CYCLE_INTERVAL_MINUTES || 30;
        document.getElementById('cfg-tor-socks-port').value = cfg.TOR_SOCKS_PORT || 9150;

        // String fields
        document.getElementById('cfg-proxy-url').value = cfg.RESIDENTIAL_PROXY_URL || '';


        // Booleans
        document.getElementById('cfg-ssl-verify').checked = !!cfg.SSL_VERIFY;
        document.getElementById('cfg-use-tor').checked = !!cfg.USE_TOR_FALLBACK;


        // C4I Settings
        document.getElementById('cfg-defcon-level').value = cfg.DEFCON_LEVEL || 3;
        document.getElementById('cfg-data-retention').value = cfg.DATA_RETENTION_DAYS || 15;
        document.getElementById('cfg-similarity').value = cfg.SIMILARITY_THRESHOLD !== undefined ? cfg.SIMILARITY_THRESHOLD : 0.85;
        document.getElementById('cfg-module-osint').checked = cfg.MODULE_OSINT_ACTIVE !== false;
        document.getElementById('cfg-module-social').checked = cfg.MODULE_SOCIAL_ACTIVE !== false;
        document.getElementById('cfg-module-nlp').checked = cfg.MODULE_NLP_ACTIVE !== false;
        document.getElementById('cfg-social-batch-size').value = cfg.SOCIAL_FETCH_BATCH_SIZE || 4;
        document.getElementById('cfg-seismic-enabled').checked = cfg.SEISMIC_MONITOR_ENABLED !== false;
        document.getElementById('cfg-seismic-lat').value = cfg.SEISMIC_TARGET_LAT || 10.4806;
        document.getElementById('cfg-seismic-lon').value = cfg.SEISMIC_TARGET_LON || -66.9036;
        document.getElementById('cfg-seismic-max-dist').value = cfg.SEISMIC_MAX_DISTANCE_KM || 400;
        document.getElementById('cfg-seismic-min-mag').value = cfg.SEISMIC_MIN_MAGNITUDE || 3.5;
        document.getElementById('cfg-gdacs-enabled').checked = cfg.GDACS_MONITOR_ENABLED !== false;
        document.getElementById('cfg-gdacs-max-dist').value = cfg.GDACS_MAX_DISTANCE_KM || 800;
        document.getElementById('cfg-gdacs-days').value = cfg.GDACS_EVENT_DAYS || 2;
        document.getElementById('cfg-asn-enabled').checked = cfg.ASN_MONITOR_ENABLED !== false;
        document.getElementById('cfg-asn-threshold').value = cfg.ASN_DROP_THRESHOLD || 30;
        const simValDisplay = document.getElementById('sim-val-display');
        if (simValDisplay) {
            simValDisplay.textContent = parseFloat(cfg.SIMILARITY_THRESHOLD !== undefined ? cfg.SIMILARITY_THRESHOLD : 0.85).toFixed(2);
        }

        // ── OSIRIS Engine toggles ──
        document.getElementById('cfg-osiris-recon').checked = cfg.OSIRIS_RECON_ENABLED !== false;
        document.getElementById('cfg-osiris-intel').checked = cfg.OSIRIS_INTEL_ENABLED !== false;
        document.getElementById('cfg-osiris-map').checked = cfg.OSIRIS_MAP_ENABLED !== false;
        document.getElementById('cfg-osiris-cctv').checked = cfg.OSIRIS_CCTV_ENABLED !== false;
        document.getElementById('cfg-osiris-feed').checked = cfg.OSIRIS_FEED_ENABLED !== false;

        // ── OSIRIS intervals ──
        document.getElementById('cfg-osiris-feed-interval').value = cfg.OSIRIS_FEED_INTERVAL_SEC || 120;
        document.getElementById('cfg-osiris-cctv-interval').value = cfg.OSIRIS_CCTV_INTERVAL_SEC || 300;
        document.getElementById('cfg-osiris-markets-interval').value = cfg.OSIRIS_MARKETS_INTERVAL_SEC || 600;
        document.getElementById('cfg-osiris-cyber-interval').value = cfg.OSIRIS_CYBER_INTERVAL_SEC || 300;
        document.getElementById('cfg-osiris-aerospace-interval').value = cfg.OSIRIS_AEROSPACE_INTERVAL_SEC || 120;
        document.getElementById('cfg-osiris-disasters-interval').value = cfg.OSIRIS_DISASTERS_INTERVAL_SEC || 300;

        // ── OSIRIS Map layer intervals ──
        document.getElementById('cfg-osiris-map-flights').value = cfg.OSIRIS_MAP_FLIGHTS_INTERVAL_SEC || 60;
        document.getElementById('cfg-osiris-map-satellites').value = cfg.OSIRIS_MAP_SATELLITES_INTERVAL_SEC || 120;
        document.getElementById('cfg-osiris-map-earthquakes').value = cfg.OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC || 120;
        document.getElementById('cfg-osiris-map-fires').value = cfg.OSIRIS_MAP_FIRES_INTERVAL_SEC || 120;
        document.getElementById('cfg-osiris-map-weather').value = cfg.OSIRIS_MAP_WEATHER_INTERVAL_SEC || 300;
        document.getElementById('cfg-osiris-map-cctv').value = cfg.OSIRIS_MAP_CCTV_INTERVAL_SEC || 300;

        // ── OSIRIS Sanctions ──
        document.getElementById('cfg-osiris-sanctions-refresh').value = cfg.OSIRIS_SANCTIONS_REFRESH_HOURS || 24;

        // Branding & Metadata
        document.getElementById('cfg-page-title').value = cfg.PAGE_TITLE || '';
        document.getElementById('cfg-page-description').value = cfg.PAGE_DESCRIPTION || '';
        document.getElementById('cfg-site-url').value = cfg.SITE_URL || '';
        document.getElementById('cfg-logo-path').value = cfg.LOGO_PATH || '';
        document.getElementById('cfg-logo-fallback').value = cfg.LOGO_FALLBACK || '';
        document.getElementById('cfg-about-us').value = cfg.ABOUT_US_CONTENT || '';

        // Advanced AI Settings
        document.getElementById('cfg-ollama-enabled').checked = cfg.OLLAMA_ENABLED !== false;
        document.getElementById('cfg-ollama-host').value = cfg.OLLAMA_HOST || '192.168.1.213';
        document.getElementById('cfg-ollama-port').value = cfg.OLLAMA_PORT || 11434;
        const keyEl = document.getElementById('cfg-ollama-api-key');
        if (keyEl) keyEl.value = cfg.OLLAMA_API_KEY || '';
        document.getElementById('cfg-ollama-model').value = cfg.OLLAMA_MODEL || 'llama3.2';
        document.getElementById('cfg-ollama-timeout').value = cfg.OLLAMA_TIMEOUT || 180;

        document.getElementById('cfg-ai-model').value = cfg.AI_MODEL || 'meta/llama-3.3-70b-instruct';
        document.getElementById('cfg-ai-temperature').value = cfg.AI_TEMPERATURE !== undefined ? cfg.AI_TEMPERATURE : 0.55;
        const tempValDisplay = document.getElementById('temp-val-display');
        if (tempValDisplay) {
            tempValDisplay.textContent = parseFloat(cfg.AI_TEMPERATURE !== undefined ? cfg.AI_TEMPERATURE : 0.55).toFixed(2);
        }
        document.getElementById('cfg-ai-max-tokens').value = cfg.AI_MAX_TOKENS || 800;
        document.getElementById('cfg-prompt-ares').value = cfg.AI_SYSTEM_PROMPT_ARES || '';
        document.getElementById('cfg-prompt-minerva').value = cfg.AI_SYSTEM_PROMPT_MINERVA || '';
        document.getElementById('cfg-prompt-nexus').value = cfg.AI_SYSTEM_PROMPT_NEXUS || '';

        // Advanced Alert Settings
        document.getElementById('cfg-telegram-push-chat-id').value = cfg.TELEGRAM_PUSH_CHAT_ID || '';
        document.getElementById('cfg-alert-critical').value = (cfg.ALERT_CRITICAL_KEYWORDS || []).join(', ');
        document.getElementById('cfg-alert-urgent').value = (cfg.ALERT_URGENT_KEYWORDS || []).join(', ');

        // Sentiment NLP Settings
        const s = cfg.SENTIMIENTO || {};
        const thrPos = s.THRESHOLD_POSITIVO !== undefined ? s.THRESHOLD_POSITIVO : 0.15;
        const thrNeg = s.THRESHOLD_NEGATIVO !== undefined ? s.THRESHOLD_NEGATIVO : -0.15;
        const thrCrit = s.CRISIS_SCORE_THRESHOLD !== undefined ? s.CRISIS_SCORE_THRESHOLD : -0.5;
        const thrAlert = s.ALERTA_SCORE_THRESHOLD !== undefined ? s.ALERTA_SCORE_THRESHOLD : -0.3;

        document.getElementById('cfg-sent-threshold-positivo').value = thrPos;
        document.getElementById('sent-thr-pos-display').textContent = parseFloat(thrPos).toFixed(2);
        document.getElementById('cfg-sent-threshold-negativo').value = thrNeg;
        document.getElementById('sent-thr-neg-display').textContent = parseFloat(thrNeg).toFixed(2);
        document.getElementById('cfg-sent-max-muestras').value = s.MAX_MUESTRAS !== undefined ? s.MAX_MUESTRAS : 300;
        document.getElementById('cfg-sent-bot-score').value = s.BOT_SCORE_THRESHOLD !== undefined ? s.BOT_SCORE_THRESHOLD : 40;
        document.getElementById('cfg-sent-bot-storm').value = s.BOT_STORM_RATE !== undefined ? s.BOT_STORM_RATE : 25;
        document.getElementById('cfg-sent-serie-horas').value = s.SERIE_TEMPORAL_HORAS !== undefined ? s.SERIE_TEMPORAL_HORAS : 12;
        document.getElementById('cfg-sent-crisis-score').value = thrCrit;
        document.getElementById('sent-thr-crit-display').textContent = parseFloat(thrCrit).toFixed(2);
        document.getElementById('cfg-sent-alerta-score').value = thrAlert;
        document.getElementById('sent-thr-alert-display').textContent = parseFloat(thrAlert).toFixed(2);
        document.getElementById('cfg-sent-crisis-kw-min').value = s.CRISIS_KEYWORDS_MIN !== undefined ? s.CRISIS_KEYWORDS_MIN : 2;
        document.getElementById('cfg-sent-lexico-pos').value = JSON.stringify(s.LEXICO_POSITIVO || {}, null, 2);
        document.getElementById('cfg-sent-lexico-neg').value = JSON.stringify(s.LEXICO_NEGATIVO || {}, null, 2);
        document.getElementById('cfg-sent-keywords-crisis').value = (s.KEYWORDS_CRISIS || []).join(', ');
        document.getElementById('cfg-sent-keywords-bot').value = (s.KEYWORDS_BOT || []).join(', ');

        // Advanced sentiment
        document.getElementById('cfg-sent-lexico-ira').value = JSON.stringify(s.LEXICO_IRA || [], null, 2);
        document.getElementById('cfg-sent-lexico-miedo').value = JSON.stringify(s.LEXICO_MIEDO || [], null, 2);
        document.getElementById('cfg-sent-lexico-esperanza').value = JSON.stringify(s.LEXICO_ESPERANZA || [], null, 2);
        document.getElementById('cfg-sent-top-palabras').value = s.TOP_PALABRAS_LIMIT !== undefined ? s.TOP_PALABRAS_LIMIT : 12;
        document.getElementById('cfg-sent-bots-muestra').value = s.BOTS_MUESTRA_LIMIT !== undefined ? s.BOTS_MUESTRA_LIMIT : 8;
        document.getElementById('cfg-sent-crisis-muestra').value = s.CRISIS_MUESTRA_LIMIT !== undefined ? s.CRISIS_MUESTRA_LIMIT : 10;
        document.getElementById('cfg-sent-entradas-muestra').value = s.ENTRADAS_MUESTRA_LIMIT !== undefined ? s.ENTRADAS_MUESTRA_LIMIT : 20;
        const thrAten = s.ATENCION_SCORE_THRESHOLD !== undefined ? s.ATENCION_SCORE_THRESHOLD : -0.15;
        document.getElementById('cfg-sent-atencion-score').value = thrAten;
        const dispAten = document.getElementById('sent-thr-atencion-display');
        if (dispAten) dispAten.textContent = parseFloat(thrAten).toFixed(2);
        const normDenom = s.NORMALIZACION_DENOM !== undefined ? s.NORMALIZACION_DENOM : 0.5;
        document.getElementById('cfg-sent-norm-denom').value = normDenom;
        const dispNorm = document.getElementById('sent-norm-denom-display');
        if (dispNorm) dispNorm.textContent = parseFloat(normDenom).toFixed(2);
    },

    populateEnvFields: function(envData) {
        if (!envData) return;
        const SENSITIVE_KEYS = new Set([
            "ADMIN_PASSWORD", "TELEGRAM_TOKEN",
            "GROQ_API_KEY", "GROQ_API_KEY_COORD", "GROQ_API_KEY_ARES", "GROQ_API_KEY_NEXUS", "GROQ_API_KEY_MINERVA",
            "GEMINI_API_KEY", "GEMINI_API_KEY_2", "FIRMS_API_KEY", "GITHUB_TOKEN", "SHODAN_API_KEY"
        ]);
        const keys = [
            "ADMIN_USERNAME", "ADMIN_PASSWORD",
            "TELEGRAM_TOKEN", "TELEGRAM_CHANNEL", "TELEGRAM_ADMIN_CHAT_ID",
            "GROQ_API_KEY", "GROQ_API_KEY_COORD", "GROQ_API_KEY_ARES", "GROQ_API_KEY_NEXUS", "GROQ_API_KEY_MINERVA",
            "GEMINI_API_KEY", "GEMINI_API_KEY_2", "FIRMS_API_KEY", "OPENWEATHER_API_KEY", "GITHUB_TOKEN", "SHODAN_API_KEY"
        ];
        keys.forEach(k => {
            const el = document.getElementById(`env-${k}`);
            if (!el) return;
            const val = envData[k] || '';
            // No cargar valores redactados (contienen ****) para no reenviarlos al guardar
            if (SENSITIVE_KEYS.has(k) && val.includes('****')) {
                el.value = '';
                el.placeholder = '•••••••• (valor existente no mostrado)';
                return;
            }
            el.value = val;
        });
    },

    switchSubTab: function(subTabId, btnElement) {
        document.querySelectorAll('.config-subtab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.config-subtab-btn').forEach(el => el.classList.remove('active'));

        const target = document.getElementById(subTabId);
        if (target) target.classList.add('active');
        if (btnElement) btnElement.classList.add('active');

        this.state.activeSubTab = subTabId;
    },

    /* --- RSS FEEDS LOGIC --- */
    renderRSSList: function() {
        const tbody = document.getElementById('rss-feeds-table-body');
        if (!tbody) return;

        let html = '';
        const sortedKeys = Object.keys(this.state.rssFeeds).sort();

        if (sortedKeys.length === 0) {
            html = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 20px;">No hay fuentes RSS configuradas.</td></tr>`;
        } else {
            sortedKeys.forEach(name => {
                const url = this.state.rssFeeds[name];
                const isPriority = this.state.priorityFeeds.includes(name);
                const starIcon = isPriority ? '★' : '☆';
                const starColor = isPriority ? 'var(--primary)' : 'var(--text-muted)';
                const starTitle = isPriority ? 'Prioridad alta activa' : 'Hacer prioridad alta';

                html += `
                    <tr class="rss-row" data-name="${name}">
                        <td style="font-family:'Roboto Mono',monospace; font-size:0.8rem; color:#fff;">${name}</td>
                        <td style="font-family:'Roboto Mono',monospace; font-size:0.75rem; color:var(--text-muted); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${url}</td>
                        <td style="text-align: right; white-space: nowrap;">
                            <button onclick="CobaltoConfig.togglePriority('${name}')" class="btn-icon" style="color:${starColor}; font-size: 1rem; margin-right: 8px;" title="${starTitle}">${starIcon}</button>
                            <button onclick="CobaltoConfig.editRSSFeed('${name}')" class="btn-icon" style="color:var(--primary); margin-right: 8px;" title="Editar">✏️</button>
                            <button onclick="CobaltoConfig.deleteRSSFeed('${name}')" class="btn-icon" style="color:var(--threat-red);" title="Eliminar">🗑️</button>
                        </td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = html;
    },

    addRSSFeed: function() {
        const nameInput = document.getElementById('new-rss-name');
        const urlInput = document.getElementById('new-rss-url');
        if (!nameInput || !urlInput) return;

        const name = nameInput.value.trim();
        const url = urlInput.value.trim();

        if (!name || !url) {
            this.showToast('Ambos campos son obligatorios', 'error');
            return;
        }

        try {
            new URL(url); // basic client side validation
        } catch (_) {
            this.showToast('Ingrese una URL válida', 'error');
            return;
        }

        this.state.rssFeeds[name] = url;
        nameInput.value = '';
        urlInput.value = '';
        this.renderRSSList();
        this.showToast('Fuente RSS agregada localmente', 'info');
    },

    editRSSFeed: function(oldName) {
        const oldUrl = this.state.rssFeeds[oldName];
        const newName = prompt('Nombre de la fuente RSS:', oldName);
        if (newName === null) return;
        const newUrl = prompt('URL de la fuente RSS:', oldUrl);
        if (newUrl === null) return;

        const trimmedName = newName.trim();
        const trimmedUrl = newUrl.trim();

        if (!trimmedName || !trimmedUrl) {
            this.showToast('Datos inválidos', 'error');
            return;
        }

        delete this.state.rssFeeds[oldName];
        this.state.rssFeeds[trimmedName] = trimmedUrl;

        // Update priority list mapping as well if name changed
        const priIdx = this.state.priorityFeeds.indexOf(oldName);
        if (priIdx !== -1) {
            this.state.priorityFeeds[priIdx] = trimmedName;
        }

        this.renderRSSList();
        this.showToast('Fuente RSS modificada', 'info');
    },

    deleteRSSFeed: function(name) {
        if (!confirm(`¿Eliminar la fuente RSS "${name}"?`)) return;

        delete this.state.rssFeeds[name];
        this.state.priorityFeeds = this.state.priorityFeeds.filter(n => n !== name);
        this.renderRSSList();
        this.showToast('Fuente RSS eliminada localmente', 'info');
    },

    togglePriority: function(name) {
        if (this.state.priorityFeeds.includes(name)) {
            this.state.priorityFeeds = this.state.priorityFeeds.filter(n => n !== name);
            this.showToast(`Eliminado de prioridad: ${name}`, 'info');
        } else {
            this.state.priorityFeeds.push(name);
            this.showToast(`Agregado a prioridad: ${name}`, 'info');
        }
        this.renderRSSList();
    },

    /* --- TELEGRAM LOGIC --- */
    renderTelegramList: function() {
        const tbody = document.getElementById('telegram-sources-table-body');
        if (!tbody) return;

        let html = '';
        const keys = Object.keys(this.state.telegramSources).sort();

        if (keys.length === 0) {
            html = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 20px;">No hay canales de Telegram configurados.</td></tr>`;
        } else {
            keys.forEach(name => {
                const url = this.state.telegramSources[name];
                html += `
                    <tr class="rss-row" data-name="${name}">
                        <td style="font-family:'Roboto Mono',monospace; font-size:0.8rem; color:#fff;">${name}</td>
                        <td style="font-family:'Roboto Mono',monospace; font-size:0.75rem; color:var(--text-muted);">${url}</td>
                        <td style="text-align: right; white-space: nowrap;">
                            <button onclick="CobaltoConfig.editTelegramSource('${name}')" class="btn-icon" style="color:var(--primary); margin-right: 8px;" title="Editar">✏️</button>
                            <button onclick="CobaltoConfig.deleteTelegramSource('${name}')" class="btn-icon" style="color:var(--threat-red);" title="Eliminar">🗑️</button>
                        </td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = html;
    },

    addTelegramSource: function() {
        const nameInput = document.getElementById('new-tg-name');
        const urlInput = document.getElementById('new-tg-url');
        if (!nameInput || !urlInput) return;

        const name = nameInput.value.trim();
        const url = urlInput.value.trim();

        if (!name || !url) {
            this.showToast('Ambos campos son obligatorios', 'error');
            return;
        }

        this.state.telegramSources[name] = url;
        nameInput.value = '';
        urlInput.value = '';
        this.renderTelegramList();
        this.showToast('Canal Telegram agregado localmente', 'info');
    },

    editTelegramSource: function(oldName) {
        const oldUrl = this.state.telegramSources[oldName];
        const newName = prompt('Nombre del canal:', oldName);
        if (newName === null) return;
        const newUrl = prompt('URL del canal:', oldUrl);
        if (newUrl === null) return;

        const trimmedName = newName.trim();
        const trimmedUrl = newUrl.trim();

        if (!trimmedName || !trimmedUrl) {
            this.showToast('Datos inválidos', 'error');
            return;
        }

        delete this.state.telegramSources[oldName];
        this.state.telegramSources[trimmedName] = trimmedUrl;
        this.renderTelegramList();
        this.showToast('Canal de Telegram modificado', 'info');
    },

    deleteTelegramSource: function(name) {
        if (!confirm(`¿Eliminar canal "${name}"?`)) return;

        delete this.state.telegramSources[name];
        this.renderTelegramList();
        this.showToast('Canal eliminado localmente', 'info');
    },

    /* --- AIRCRAFT TRACKING --- */
    renderAircraftList: function() {
        const tbody = document.getElementById('aircraft-table-body');
        if (!tbody) return;
        const ac = this.state.trackingAircraft || {};
        const keys = Object.keys(ac).sort();
        let html = '';
        if (keys.length === 0) {
            html = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:20px;">No hay aeronaves configuradas.</td></tr>';
        } else {
            keys.forEach(icao => {
                html += `<tr><td style="font-family:monospace;font-size:0.8rem;color:#fff;">${icao}</td>
                    <td style="font-family:monospace;font-size:0.75rem;color:var(--text-muted);">${ac[icao]}</td>
                    <td style="text-align:right;"><button onclick="CobaltoConfig.deleteAircraft('${icao}')" class="btn-icon" style="color:var(--threat-red);" title="Eliminar">🗑️</button></td></tr>`;
            });
        }
        tbody.innerHTML = html;
    },

    addAircraft: function() {
        const icaoInput = document.getElementById('new-ac-icao');
        const tailInput = document.getElementById('new-ac-tail');
        if (!icaoInput || !tailInput) return;
        const icao = icaoInput.value.trim().toUpperCase();
        const tail = tailInput.value.trim();
        if (!icao || !tail) { this.showToast('Ambos campos son obligatorios', 'error'); return; }
        this.state.trackingAircraft = this.state.trackingAircraft || {};
        this.state.trackingAircraft[icao] = tail;
        icaoInput.value = ''; tailInput.value = '';
        this.renderAircraftList();
        this.showToast('Aeronave agregada', 'info');
    },

    deleteAircraft: function(icao) {
        if (!confirm(`¿Eliminar aeronave "${icao}"?`)) return;
        if (this.state.trackingAircraft) delete this.state.trackingAircraft[icao];
        this.renderAircraftList();
        this.showToast('Aeronave eliminada', 'info');
    },

    /* --- VESSEL TRACKING --- */
    renderVesselList: function() {
        const tbody = document.getElementById('vessels-table-body');
        if (!tbody) return;
        const ves = this.state.trackingVessels || {};
        const keys = Object.keys(ves).sort();
        let html = '';
        if (keys.length === 0) {
            html = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:20px;">No hay buques configurados.</td></tr>';
        } else {
            keys.forEach(mmsi => {
                html += `<tr><td style="font-family:monospace;font-size:0.8rem;color:#fff;">${mmsi}</td>
                    <td style="font-family:monospace;font-size:0.75rem;color:var(--text-muted);">${ves[mmsi]}</td>
                    <td style="text-align:right;"><button onclick="CobaltoConfig.deleteVessel('${mmsi}')" class="btn-icon" style="color:var(--threat-red);" title="Eliminar">🗑️</button></td></tr>`;
            });
        }
        tbody.innerHTML = html;
    },

    addVessel: function() {
        const mmsiInput = document.getElementById('new-vessel-mmsi');
        const nameInput = document.getElementById('new-vessel-name');
        if (!mmsiInput || !nameInput) return;
        const mmsi = mmsiInput.value.trim();
        const name = nameInput.value.trim();
        if (!mmsi || !name) { this.showToast('Ambos campos son obligatorios', 'error'); return; }
        this.state.trackingVessels = this.state.trackingVessels || {};
        this.state.trackingVessels[mmsi] = name;
        mmsiInput.value = ''; nameInput.value = '';
        this.renderVesselList();
        this.showToast('Buque agregado', 'info');
    },

    deleteVessel: function(mmsi) {
        if (!confirm(`¿Eliminar buque "${mmsi}"?`)) return;
        if (this.state.trackingVessels) delete this.state.trackingVessels[mmsi];
        this.renderVesselList();
        this.showToast('Buque eliminado', 'info');
    },

    /* --- CHIPS / TAGS FOR KEYWORDS & TARGET USERS --- */
    renderKeywords: function() {
        const container = document.getElementById('keywords-chips-container');
        if (!container) return;

        let html = '';
        this.state.keywords.sort().forEach(word => {
            html += `
                <div class="config-chip">
                    <span>${this.escapeHTML(word)}</span>
                    <span onclick="CobaltoConfig.removeKeyword('${this.escapeHTML(word)}')" class="config-chip-close">×</span>
                </div>
            `;
        });

        container.innerHTML = html;
        const countDisplay = document.getElementById('keywords-count');
        if (countDisplay) countDisplay.textContent = this.state.keywords.length;
    },

    addKeywordFromInput: function(event) {
        if (event && event.key !== 'Enter') return;
        const input = document.getElementById('new-keyword-input');
        if (!input) return;

        const word = input.value.trim().toLowerCase();
        if (!word) return;

        if (this.state.keywords.includes(word)) {
            this.showToast('La palabra clave ya existe', 'warning');
            input.value = '';
            return;
        }

        this.state.keywords.push(word);
        input.value = '';
        this.renderKeywords();
    },

    removeKeyword: function(word) {
        this.state.keywords = this.state.keywords.filter(w => w !== word);
        this.renderKeywords();
    },

    renderTargetUsers: function() {
        const container = document.getElementById('targets-chips-container');
        if (!container) return;

        let html = '';
        this.state.targetUsers.sort().forEach(user => {
            html += `
                <div class="config-chip border-accent">
                    <span>@${this.escapeHTML(user)}</span>
                    <span onclick="CobaltoConfig.removeTargetUser('${this.escapeHTML(user)}')" class="config-chip-close">×</span>
                </div>
            `;
        });

        container.innerHTML = html;
        const countDisplay = document.getElementById('targets-count');
        if (countDisplay) countDisplay.textContent = this.state.targetUsers.length;
    },

    addTargetUserFromInput: function(event) {
        if (event && event.key !== 'Enter') return;
        const input = document.getElementById('new-target-input');
        if (!input) return;

        let user = input.value.trim();
        if (!user) return;

        // Clean user handle if they typed '@'
        if (user.startsWith('@')) user = user.substring(1);

        if (this.state.targetUsers.includes(user)) {
            this.showToast('El usuario ya está en la lista', 'warning');
            input.value = '';
            return;
        }

        this.state.targetUsers.push(user);
        input.value = '';
        this.renderTargetUsers();
    },

    removeTargetUser: function(user) {
        this.state.targetUsers = this.state.targetUsers.filter(u => u !== user);
        this.renderTargetUsers();
    },

    /* --- PERSISTENCE & ACTIONS --- */
    saveConfig: async function() {
        this.showLoadingState(true);

        const data = {
            RSS_FEEDS: this.state.rssFeeds,
            TELEGRAM_SOURCES: this.state.telegramSources,
            PRIORITY_FEEDS: this.state.priorityFeeds,
            TRACKING_AIRCRAFT: Object.assign({}, this.state.trackingAircraft),
            TRACKING_VESSELS: Object.assign({}, this.state.trackingVessels),
            CACHE_MAX_AGE_MINUTES: parseInt(document.getElementById('cfg-cache-max-age').value) || 15,
            ENTRY_MAX_AGE_HOURS: parseInt(document.getElementById('cfg-entry-max-age').value) || 48,
            CYCLE_INTERVAL_MINUTES: parseInt(document.getElementById('cfg-cycle-interval').value) || 30,
            SSL_VERIFY: document.getElementById('cfg-ssl-verify').checked,
            RESIDENTIAL_PROXY_URL: document.getElementById('cfg-proxy-url').value.trim() || null,
            USE_TOR_FALLBACK: document.getElementById('cfg-use-tor').checked,
            TOR_SOCKS_PORT: parseInt(document.getElementById('cfg-tor-socks-port').value) || 9150,
            DEFCON_LEVEL: parseInt(document.getElementById('cfg-defcon-level').value) || 3,
            DATA_RETENTION_DAYS: parseInt(document.getElementById('cfg-data-retention').value) || 15,
            SIMILARITY_THRESHOLD: parseFloat(document.getElementById('cfg-similarity').value) || 0.85,
            MODULE_OSINT_ACTIVE: document.getElementById('cfg-module-osint').checked,
            MODULE_SOCIAL_ACTIVE: document.getElementById('cfg-module-social').checked,
            MODULE_NLP_ACTIVE: document.getElementById('cfg-module-nlp').checked,
            SOCIAL_FETCH_BATCH_SIZE: parseInt(document.getElementById('cfg-social-batch-size').value) || 4,
            SEISMIC_MONITOR_ENABLED: document.getElementById('cfg-seismic-enabled').checked,
            SEISMIC_TARGET_LAT: parseFloat(document.getElementById('cfg-seismic-lat').value) || 10.4806,
            SEISMIC_TARGET_LON: parseFloat(document.getElementById('cfg-seismic-lon').value) || -66.9036,
            SEISMIC_MAX_DISTANCE_KM: parseFloat(document.getElementById('cfg-seismic-max-dist').value) || 400,
            SEISMIC_MIN_MAGNITUDE: parseFloat(document.getElementById('cfg-seismic-min-mag').value) || 3.5,
            GDACS_MONITOR_ENABLED: document.getElementById('cfg-gdacs-enabled').checked,
            GDACS_MAX_DISTANCE_KM: parseFloat(document.getElementById('cfg-gdacs-max-dist').value) || 800,
            GDACS_EVENT_DAYS: parseInt(document.getElementById('cfg-gdacs-days').value) || 2,
            ASN_MONITOR_ENABLED: document.getElementById('cfg-asn-enabled').checked,
            ASN_DROP_THRESHOLD: parseFloat(document.getElementById('cfg-asn-threshold').value) || 30,

            // Branding
            PAGE_TITLE: document.getElementById('cfg-page-title').value.trim() || null,
            PAGE_DESCRIPTION: document.getElementById('cfg-page-description').value.trim() || null,
            SITE_URL: document.getElementById('cfg-site-url').value.trim() || null,
            LOGO_PATH: document.getElementById('cfg-logo-path').value.trim() || null,
            LOGO_FALLBACK: document.getElementById('cfg-logo-fallback').value.trim() || null,
            ABOUT_US_CONTENT: document.getElementById('cfg-about-us').value,

            TARGET_USERS: this.state.targetUsers,
            KEYWORDS: this.state.keywords,

            OLLAMA_ENABLED: document.getElementById('cfg-ollama-enabled').checked,
            OLLAMA_HOST: document.getElementById('cfg-ollama-host').value.trim() || '192.168.1.213',
            OLLAMA_PORT: parseInt(document.getElementById('cfg-ollama-port').value) || 11434,
            OLLAMA_API_KEY: (document.getElementById('cfg-ollama-api-key') ? document.getElementById('cfg-ollama-api-key').value.trim() : ''),
            OLLAMA_MODEL: document.getElementById('cfg-ollama-model').value.trim() || 'llama3.2',
            OLLAMA_TIMEOUT: parseFloat(document.getElementById('cfg-ollama-timeout').value) || 180,

            AI_MODEL: document.getElementById('cfg-ai-model').value,
            AI_TEMPERATURE: parseFloat(document.getElementById('cfg-ai-temperature').value) || 0.55,
            AI_MAX_TOKENS: parseInt(document.getElementById('cfg-ai-max-tokens').value) || 800,
            AI_SYSTEM_PROMPT_ARES: document.getElementById('cfg-prompt-ares').value,
            AI_SYSTEM_PROMPT_MINERVA: document.getElementById('cfg-prompt-minerva').value,
            AI_SYSTEM_PROMPT_NEXUS: document.getElementById('cfg-prompt-nexus').value,
            TELEGRAM_PUSH_CHAT_ID: document.getElementById('cfg-telegram-push-chat-id').value.trim(),
            ALERT_CRITICAL_KEYWORDS: document.getElementById('cfg-alert-critical').value.split(',').map(s => s.trim()).filter(Boolean),
            ALERT_URGENT_KEYWORDS: document.getElementById('cfg-alert-urgent').value.split(',').map(s => s.trim()).filter(Boolean),
            SENTIMIENTO: this._buildSentimientoPayload(),

            // ── OSIRIS Engine ──
            OSIRIS_RECON_ENABLED: document.getElementById('cfg-osiris-recon').checked,
            OSIRIS_INTEL_ENABLED: document.getElementById('cfg-osiris-intel').checked,
            OSIRIS_MAP_ENABLED: document.getElementById('cfg-osiris-map').checked,
            OSIRIS_CCTV_ENABLED: document.getElementById('cfg-osiris-cctv').checked,
            OSIRIS_FEED_ENABLED: document.getElementById('cfg-osiris-feed').checked,
            OSIRIS_SANCTIONS_REFRESH_HOURS: parseInt(document.getElementById('cfg-osiris-sanctions-refresh').value) || 24,
            OSIRIS_FEED_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-feed-interval').value) || 120,
            OSIRIS_CCTV_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-cctv-interval').value) || 300,
            OSIRIS_MARKETS_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-markets-interval').value) || 600,
            OSIRIS_CYBER_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-cyber-interval').value) || 300,
            OSIRIS_AEROSPACE_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-aerospace-interval').value) || 120,
            OSIRIS_DISASTERS_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-disasters-interval').value) || 300,
            OSIRIS_MAP_FLIGHTS_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-map-flights').value) || 60,
            OSIRIS_MAP_SATELLITES_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-map-satellites').value) || 120,
            OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-map-earthquakes').value) || 120,
            OSIRIS_MAP_FIRES_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-map-fires').value) || 120,
            OSIRIS_MAP_WEATHER_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-map-weather').value) || 300,
            OSIRIS_MAP_CCTV_INTERVAL_SEC: parseInt(document.getElementById('cfg-osiris-map-cctv').value) || 300,
        };

        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to save settings');
            }

            const resData = await response.json();
            this.showToast('¡Configuración guardada y aplicada con éxito!', 'success');
            
            if (data.PAGE_TITLE) document.title = data.PAGE_TITLE;
            const descEl = document.querySelector('.logo-area img');
            if (descEl && data.LOGO_PATH) {
                descEl.src = data.LOGO_PATH;
            }

            this.showLoadingState(false);
        } catch (error) {
            console.error('Error saving config:', error);
            this.showToast(error.message || 'Error al guardar la configuración', 'error');
            this.showLoadingState(false);
        }
    },

    saveEnvConfig: async function() {
        this.showLoadingState(true);
        const keys = [
            "ADMIN_USERNAME", "ADMIN_PASSWORD",
            "TELEGRAM_TOKEN", "TELEGRAM_CHANNEL", "TELEGRAM_ADMIN_CHAT_ID",
            "GROQ_API_KEY", "GROQ_API_KEY_COORD", "GROQ_API_KEY_ARES", "GROQ_API_KEY_NEXUS", "GROQ_API_KEY_MINERVA",
            "GEMINI_API_KEY", "GEMINI_API_KEY_2", "FIRMS_API_KEY", "OPENWEATHER_API_KEY", "GITHUB_TOKEN", "SHODAN_API_KEY"
        ];
        
        const data = {};
        const SENSITIVE_KEYS = new Set([
            "ADMIN_PASSWORD", "TELEGRAM_TOKEN",
            "GROQ_API_KEY", "GROQ_API_KEY_COORD", "GROQ_API_KEY_ARES", "GROQ_API_KEY_NEXUS", "GROQ_API_KEY_MINERVA",
            "GEMINI_API_KEY", "GEMINI_API_KEY_2", "FIRMS_API_KEY", "GITHUB_TOKEN", "SHODAN_API_KEY"
        ]);
        keys.forEach(k => {
            const el = document.getElementById(`env-${k}`);
            if (!el) return;
            const val = el.value.trim();
            if (SENSITIVE_KEYS.has(k) && val.includes('****')) return;
            data[k] = val;
        });

        try {
            const response = await fetch('/api/env', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Error al guardar variables de entorno');
            }

            this.showToast('¡Variables de entorno guardadas (.env)! Algunas requieren reiniciar el sistema.', 'success');
            this.showLoadingState(false);
        } catch (error) {
            console.error('Error saving env:', error);
            this.showToast(error.message || 'Error al guardar variables de entorno', 'error');
            this.showLoadingState(false);
        }
    },

    resetConfig: async function() {
        if (!confirm("⚠️ ¿ADVERTENCIA EXTREMA?\nEsto borrará TODA la configuración actual, los léxicos, palabras clave y fuentes, restaurando los valores originales de fábrica. ¿Estás seguro?")) return;

        this.showLoadingState(true);
        try {
            const response = await fetch('/api/config/reset', { method: 'DELETE' });
            if (!response.ok) throw new Error('Error al restaurar configuración');
            this.showToast('Configuración restaurada a valores de fábrica', 'success');
            setTimeout(() => location.reload(), 1500);
        } catch (error) {
            console.error('Error resetting config:', error);
            this.showToast('Error al restaurar configuración de fábrica', 'error');
            this.showLoadingState(false);
        }
    },

    exportEvidence: function() {
        this.showToast('Generando CSV de evidencia... Esto puede tardar unos segundos.', 'info');
        window.location.href = '/api/intel/export_csv';
    },

    purgeDatabase: async function() {
        const days = document.getElementById('cfg-data-retention').value || 15;
        if (!confirm(`⚠️ ¿Estás seguro de que deseas purgar permanentemente TODA la inteligencia anterior a ${days} días? Esta acción no se puede deshacer.`)) return;

        this.showLoadingState(true);
        try {
            const response = await fetch('/api/intel/purge_db', { method: 'POST' });
            if (!response.ok) throw new Error('Error al purgar base de datos');
            const data = await response.json();
            this.showToast(data.message || 'Base de datos purgada exitosamente', 'success');
            this.showLoadingState(false);
        } catch (error) {
            console.error('Error purging DB:', error);
            this.showToast('Falló el purgado táctico', 'error');
            this.showLoadingState(false);
        }
    },

    _buildSentimientoPayload: function() {
        const parseJSON = (id, fallback) => {
            try { return JSON.parse(document.getElementById(id).value || '{}'); }
            catch(e) { this.showToast(`JSON inválido en ${id}`, 'warning'); return fallback; }
        };
        const parseJSONArray = (id, fallback) => {
            try { const v = JSON.parse(document.getElementById(id).value || '[]'); return Array.isArray(v) ? v : fallback; }
            catch(e) { this.showToast(`JSON inválido en ${id}`, 'warning'); return fallback; }
        };
        const parseCsv = id => document.getElementById(id).value.split(',').map(s => s.trim()).filter(Boolean);
        const existing = (this.state.config && this.state.config.SENTIMIENTO) ? this.state.config.SENTIMIENTO : {};
        return {
            ...existing,
            THRESHOLD_POSITIVO: parseFloat(document.getElementById('cfg-sent-threshold-positivo').value) || 0.15,
            THRESHOLD_NEGATIVO: parseFloat(document.getElementById('cfg-sent-threshold-negativo').value) || -0.15,
            MAX_MUESTRAS: parseInt(document.getElementById('cfg-sent-max-muestras').value) || 300,
            BOT_SCORE_THRESHOLD: parseInt(document.getElementById('cfg-sent-bot-score').value) || 40,
            BOT_STORM_RATE: parseFloat(document.getElementById('cfg-sent-bot-storm').value) || 25,
            SERIE_TEMPORAL_HORAS: parseInt(document.getElementById('cfg-sent-serie-horas').value) || 12,
            CRISIS_SCORE_THRESHOLD: parseFloat(document.getElementById('cfg-sent-crisis-score').value) || -0.5,
            ALERTA_SCORE_THRESHOLD: parseFloat(document.getElementById('cfg-sent-alerta-score').value) || -0.3,
            CRISIS_KEYWORDS_MIN: parseInt(document.getElementById('cfg-sent-crisis-kw-min').value) || 2,
            LEXICO_POSITIVO: parseJSON('cfg-sent-lexico-pos', existing.LEXICO_POSITIVO || {}),
            LEXICO_NEGATIVO: parseJSON('cfg-sent-lexico-neg', existing.LEXICO_NEGATIVO || {}),
            LEXICO_IRA: parseJSONArray('cfg-sent-lexico-ira', existing.LEXICO_IRA || []),
            LEXICO_MIEDO: parseJSONArray('cfg-sent-lexico-miedo', existing.LEXICO_MIEDO || []),
            LEXICO_ESPERANZA: parseJSONArray('cfg-sent-lexico-esperanza', existing.LEXICO_ESPERANZA || []),
            TOP_PALABRAS_LIMIT: parseInt(document.getElementById('cfg-sent-top-palabras').value) || 12,
            BOTS_MUESTRA_LIMIT: parseInt(document.getElementById('cfg-sent-bots-muestra').value) || 8,
            CRISIS_MUESTRA_LIMIT: parseInt(document.getElementById('cfg-sent-crisis-muestra').value) || 10,
            ENTRADAS_MUESTRA_LIMIT: parseInt(document.getElementById('cfg-sent-entradas-muestra').value) || 20,
            ATENCION_SCORE_THRESHOLD: parseFloat(document.getElementById('cfg-sent-atencion-score').value) || -0.15,
            NORMALIZACION_DENOM: parseFloat(document.getElementById('cfg-sent-norm-denom').value) || 0.5,
            KEYWORDS_CRISIS: parseCsv('cfg-sent-keywords-crisis'),
            KEYWORDS_BOT: parseCsv('cfg-sent-keywords-bot'),
        };
    },

    forceRefresh: async function() {
        const btn = document.getElementById('btn-force-refresh');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span class="config-spinner"></span> RASTREANDO...`;
        }

        try {
            const response = await fetch('/api/refresh', { method: 'POST' });
            if (!response.ok) throw new Error('Refresh failed');
            this.showToast('Rastreo en segundo plano forzado e iniciado con éxito', 'success');
        } catch (error) {
            console.error('Error refreshing sensors:', error);
            this.showToast('Error al forzar rastreo de sensores', 'error');
        } finally {
            setTimeout(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `⚡ FORZAR RASTREO`;
                }
            }, 3000);
        }
    },

    /* --- TOAST NOTIFICATIONS --- */
    showToast: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `config-toast ${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '❌';
        if (type === 'warning') icon = '⚠️';

        toast.innerHTML = `
            <div style="font-size: 1.1rem; margin-right: 10px;">${icon}</div>
            <div style="font-family: 'Roboto Mono', monospace; font-size: 0.8rem; font-weight: 500;">${message}</div>
        `;

        // Check if there is already a toast container
        let container = document.getElementById('config-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'config-toast-container';
            container.style.position = 'fixed';
            container.style.bottom = '20px';
            container.style.right = '20px';
            container.style.zIndex = '99999';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '10px';
            document.body.appendChild(container);
        }

        container.appendChild(toast);

        // Slide-in and fade-out animation
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        }, 10);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    },

    detectOllamaModels: async function(silent = false) {
        const btn = document.getElementById('btn-detect-ollama-models');
        const icon = document.getElementById('icon-detect-ollama');
        const hostInput = document.getElementById('cfg-ollama-host');
        const portInput = document.getElementById('cfg-ollama-port');
        const modelSelect = document.getElementById('cfg-ollama-model');

        const statusBadge = document.getElementById('local-ai-status-badge');
        const engineTitle = document.getElementById('local-ai-engine-title');
        const engineDesc = document.getElementById('local-ai-engine-desc');
        const vramTag = document.getElementById('local-ai-vram-tag');

        if (!modelSelect) return;

        const host = hostInput ? hostInput.value.trim() : 'localhost';
        const port = portInput ? portInput.value.trim() : '11434';

        if (icon) icon.classList.add('fa-spin');
        if (btn) btn.disabled = true;

        try {
            const resp = await fetch(`/api/local-ai/detect?host=${encodeURIComponent(host)}&port=${encodeURIComponent(port)}`);
            const data = await resp.json();

            if (data.status === 'ok') {
                if (hostInput && data.host && data.host !== hostInput.value) {
                    hostInput.value = data.host;
                }
                if (portInput && data.port && parseInt(data.port) !== parseInt(portInput.value)) {
                    portInput.value = data.port;
                }

                const models = data.models || [];
                const runningModel = data.running_model || '';
                const currentVal = modelSelect.value || (this.state.config && this.state.config.OLLAMA_MODEL) || runningModel;

                modelSelect.innerHTML = '';

                if (models.length > 0) {
                    models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        let label = m;
                        if (m === runningModel) {
                            label += ' 🔥 (ACTIVO EN VRAM)';
                        } else if (m.includes('llama3.2') || m.includes('mistral')) {
                            label += ' (Recomendado)';
                        }
                        opt.textContent = label;
                        if (m === runningModel || (!runningModel && m === currentVal)) {
                            opt.selected = true;
                        }
                        modelSelect.appendChild(opt);
                    });
                } else if (runningModel) {
                    const opt = document.createElement('option');
                    opt.value = runningModel;
                    opt.textContent = runningModel + ' 🔥 (ACTIVO EN VRAM)';
                    opt.selected = true;
                    modelSelect.appendChild(opt);
                }

                if (!models.includes(currentVal) && currentVal && currentVal !== runningModel) {
                    const opt = document.createElement('option');
                    opt.value = currentVal;
                    opt.textContent = currentVal + ' (Guardado)';
                    modelSelect.appendChild(opt);
                }

                if (statusBadge) {
                    statusBadge.style.background = '#00ffaa';
                    statusBadge.style.boxShadow = '0 0 10px #00ffaa';
                }
                if (engineTitle) {
                    engineTitle.textContent = `🟢 ${data.engine_name.toUpperCase()} CONECTADO (${data.host}:${data.port})`;
                }
                if (engineDesc) {
                    engineDesc.textContent = runningModel
                        ? `Modelo activo en memoria: ${runningModel}`
                        : `${data.count} modelo(s) disponibles instalados`;
                }
                if (vramTag) {
                    vramTag.style.display = runningModel ? 'inline-block' : 'none';
                    vramTag.textContent = runningModel ? `🔥 MEMORIA: ${runningModel}` : '';
                }

                if (!silent) {
                    const engineMsg = data.engine_name || 'Motor Local';
                    this.showToast(`✅ [${engineMsg}] Detectado en ${data.host}:${data.port}. Modelo en uso: ${runningModel || 'Listo'}`, 'success');
                }
            } else {
                if (statusBadge) {
                    statusBadge.style.background = '#ff2d55';
                    statusBadge.style.boxShadow = '0 0 10px #ff2d55';
                }
                if (engineTitle) {
                    engineTitle.textContent = '🔴 NINGÚN MOTOR LOCAL DETECTADO';
                }
                if (engineDesc) {
                    engineDesc.textContent = 'No se encontró Ollama (11434), KoboldCPP (5001) ni LM Studio (1234) en ejecución.';
                }
                if (vramTag) {
                    vramTag.style.display = 'none';
                }

                if (!silent) {
                    this.showToast(data.message || 'No se encontró ningún motor de IA local activo.', 'warning');
                }
            }
        } catch (err) {
            console.error('Error detectando motor de IA local:', err);
            if (statusBadge) {
                statusBadge.style.background = '#ff2d55';
                statusBadge.style.boxShadow = '0 0 10px #ff2d55';
            }
            if (engineTitle) {
                engineTitle.textContent = '🔴 ERROR DE CONEXIÓN A MOTOR LOCAL';
            }
            if (engineDesc) {
                engineDesc.textContent = 'Asegúrate de que Ollama, KoboldCPP o LM Studio estén iniciados en tu PC.';
            }
            if (vramTag) {
                vramTag.style.display = 'none';
            }
            if (!silent) {
                this.showToast(`No se pudo verificar la conexión local con el servidor de IA.`, 'error');
            }
        } finally {
            if (icon) icon.classList.remove('fa-spin');
            if (btn) btn.disabled = false;
        }
    },

    applyPreset: async function(presetName) {
        if (!confirm(`¿Aplicar el perfil de misión "${presetName}"?`)) return;
        this.showLoadingState(true);
        try {
            const resp = await fetch(`/api/config/preset/${presetName}`, { method: 'POST' });
            const data = await resp.json();
            if (resp.ok) {
                this.showToast(data.message || `Perfil ${presetName} aplicado correctamente.`, 'success');
                await this.loadConfig();
            } else {
                this.showToast(data.detail || 'Error aplicando perfil', 'error');
            }
        } catch (e) {
            this.showToast('Error de red al aplicar perfil', 'error');
        } finally {
            this.showLoadingState(false);
        }
    },

    testTokenConnection: async function(serviceName, inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        const keyVal = input.value.trim();
        if (!keyVal || keyVal.includes('****')) {
            this.showToast('Introduzca una clave válida para probar la conexión.', 'warning');
            return;
        }
        this.showToast(`Probando conexión con ${serviceName}...`, 'info');
        try {
            const resp = await fetch('/api/config/test_token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: serviceName, api_key: keyVal })
            });
            const data = await resp.json();
            if (resp.ok && data.status === 'ok') {
                this.showToast(`✅ ${data.service}: ${data.message}`, 'success');
            } else {
                this.showToast(`🚨 ${serviceName}: ${data.message || 'Error en prueba'}`, 'error');
            }
        } catch (e) {
            this.showToast(`Error probando servicio ${serviceName}`, 'error');
        }
    },

    escapeHTML: function(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
};


document.addEventListener('DOMContentLoaded', () => {
    CobaltoConfig.init();
});

// ----------------------------------------------------
// C4I DASHBOARD (FASE 3)
// ----------------------------------------------------
window.refreshC4iDashboard = function() {
    const redisStatus = document.getElementById("c4i-redis-status");
    const postgresStatus = document.getElementById("c4i-postgres-status");
    const queueAi = document.getElementById("c4i-queue-ai");
    const queueOsint = document.getElementById("c4i-queue-osint");
    const cpuVal = document.getElementById("c4i-cpu");
    const ramVal = document.getElementById("c4i-ram");

    if(!redisStatus) return;

    // Mostrar estado de carga
    redisStatus.textContent = "CONSULTANDO...";
    redisStatus.style.color = "#FF9500";
    postgresStatus.textContent = "CONSULTANDO...";
    postgresStatus.style.color = "#FF9500";

    fetch("/api/intel/system_status")
        .then(res => res.json())
        .then(data => {
            // Update Redis Status
            if (data.redis_connected) {
                redisStatus.textContent = "CONECTADO Y OPERACIONAL";
                redisStatus.style.color = "#00e5ff";
            } else {
                redisStatus.textContent = "DESCONECTADO (FALLBACK LOCAL MEMORIA)";
                redisStatus.style.color = "#FF2D55";
            }

            // Update Postgres Status
            if (data.postgres_connected) {
                postgresStatus.textContent = "POSTGRESQL (OPERACIONAL DISTRIBUIDO)";
                postgresStatus.style.color = "#b388ff";
            } else {
                postgresStatus.textContent = "SQLITE (FALLBACK LOCAL MONOUSUARIO)";
                postgresStatus.style.color = "#FF9500";
            }

            // Update Queues
            if (data.queues) {
                queueAi.textContent = data.queues.ai_tasks || 0;
                queueOsint.textContent = data.queues.osint_tasks || 0;
            }

            // Update CPU & RAM
            cpuVal.textContent = data.cpu_percent ? data.cpu_percent.toFixed(1) + "%" : "0%";
            ramVal.textContent = data.mem_percent ? data.mem_percent.toFixed(1) + "%" : "0%";
            
            // Add slight color code to CPU
            if (data.cpu_percent > 80) cpuVal.style.color = "#FF2D55";
            else if (data.cpu_percent > 50) cpuVal.style.color = "#FF9500";
            else cpuVal.style.color = "#00ffaa";
            
            // Add slight color code to RAM
            if (data.mem_percent > 85) ramVal.style.color = "#FF2D55";
            else if (data.mem_percent > 60) ramVal.style.color = "#FF9500";
            else ramVal.style.color = "#00ffaa";
        })
        .catch(err => {
            console.error("C4i Refresh Error:", err);
            redisStatus.textContent = "ERROR AL COMUNICAR CON NÚCLEO";
            redisStatus.style.color = "#FF2D55";
        });
};

// Hook automatic refresh when C4i tab is opened
document.addEventListener("DOMContentLoaded", () => {
    const c4iBtn = document.getElementById("btn-c4i-tab");
    if (c4iBtn) {
        c4iBtn.addEventListener("click", () => {
            refreshC4iDashboard();
            // Auto refresh every 5 seconds while looking at it
            if (window.c4iInterval) clearInterval(window.c4iInterval);
            window.c4iInterval = setInterval(() => {
                const c4iTab = document.getElementById("subtab-c4i");
                if (c4iTab && c4iTab.classList.contains("active")) {
                    refreshC4iDashboard();
                } else {
                    clearInterval(window.c4iInterval);
                }
            }, 5000);
        });
    }
});
