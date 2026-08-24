/**
 * COBALTO HUB - Slash Commands / Búsqueda Paramétrica
 * Sistema de comandos slash para búsqueda paramétrica tipo Discord/Slack.
 * Atajo: teclear "/" en la barra de búsqueda.
 */

window.CobaltoSlash = (function() {
    var CMD_CHAR = '/';

    var commands = [];
    var isActive = false;
    var selectedIdx = -1;
    var searchInput = null;
    var dropdownEl = null;
    var resultsEl = null;
    var commandHistory = [];
    var historyIdx = -1;

    function escHtml(str) {
        if (str == null) return '';
        return String(str).replace(/[&<>"']/g, function(m) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[m];
        });
    }

    function injectUI() {
        if (document.getElementById('slash-dropdown')) return;

        var container = document.createElement('div');
        container.id = 'slash-container';
        container.style.cssText = 'position:relative;display:flex;flex-direction:column;flex:1;min-width:200px;';

        var dropdown = document.createElement('div');
        dropdown.id = 'slash-dropdown';
        dropdown.style.cssText = 'display:none;position:absolute;top:100%;left:0;right:0;z-index:200000;background:rgba(10,11,16,0.98);border:1px solid #00E5FF;border-radius:0 0 12px 12px;box-shadow:0 10px 40px rgba(0,0,0,0.8),0 0 30px rgba(0,229,255,0.1);margin-top:2px;overflow:hidden;backdrop-filter:blur(16px);';
        dropdownEl = dropdown;

        var resultsPanel = document.createElement('div');
        resultsPanel.id = 'slash-results';
        resultsPanel.style.cssText = 'display:none;position:absolute;top:100%;left:0;right:0;z-index:199999;background:rgba(10,11,16,0.98);border:1px solid rgba(0,229,255,0.3);border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.8);margin-top:4px;overflow:hidden;max-height:400px;overflow-y:auto;backdrop-filter:blur(16px);';
        resultsEl = resultsPanel;

        container.appendChild(dropdown);
        container.appendChild(resultsPanel);

        var input = document.getElementById('search-input');
        if (input) {
            var parent = input.parentNode;
            parent.insertBefore(container, input);
            container.appendChild(input);
            searchInput = input;
            input.style.width = '100%';
            input.style.boxSizing = 'border-box';
        }

        document.addEventListener('click', function(e) {
            if (!e.target.closest('#slash-container') && !e.target.closest('#slash-results')) {
                hideDropdown();
                hideResults();
            }
        });
    }

    function register(cmd) {
        if (!cmd.name || !cmd.handler) return;
        commands.push({
            name: cmd.name.toLowerCase(),
            display: cmd.name,
            description: cmd.description || '',
            usage: cmd.usage || '/' + cmd.name + ' <param>',
            category: cmd.category || 'General',
            color: cmd.color || '#00E5FF',
            handler: cmd.handler,
            paramLabel: cmd.paramLabel || 'parámetro'
        });
    }

    function getSuggestions(partial) {
        if (!partial) return commands.slice(0, 8);
        var p = partial.toLowerCase();
        var exact = [];
        var fuzzy = [];
        commands.forEach(function(c) {
            if (c.name === p) exact.push(c);
            else if (c.name.indexOf(p) !== -1) fuzzy.push(c);
        });
        var merged = exact.concat(fuzzy);
        return merged.slice(0, 10);
    }

    function showSuggestions(input) {
        var partial = input.slice(1).trim();
        var suggestions = getSuggestions(partial);

        if (!suggestions.length) {
            dropdownEl.innerHTML = '<div style="padding:12px 16px;color:#888;font-family:\'Roboto Mono\',monospace;font-size:0.75rem;">Ningún comando coincide</div>';
            dropdownEl.style.display = 'block';
            resultsEl.style.display = 'none';
            return;
        }

        var html = '';
        html += '<div style="padding:8px 16px;border-bottom:1px solid rgba(255,255,255,0.05);color:#666;font-family:\'Roboto Mono\',monospace;font-size:0.65rem;letter-spacing:1px;text-transform:uppercase;">Comandos disponibles (' + suggestions.length + ')</div>';

        suggestions.forEach(function(cmd, i) {
            var isSelected = i === selectedIdx;
            var bg = isSelected ? 'rgba(0,229,255,0.12)' : 'transparent';
            html += '<div class="slash-cmd-item" data-index="' + i + '" style="display:flex;align-items:center;padding:10px 16px;cursor:pointer;transition:background 0.15s;background:' + bg + ';border-left:3px solid ' + cmd.color + ';">';
            html += '<div style="flex:1;">';
            html += '<div style="display:flex;align-items:center;gap:8px;">';
            html += '<span style="color:' + cmd.color + ';font-weight:bold;font-family:\'Roboto Mono\',monospace;font-size:0.85rem;">/' + escHtml(cmd.display) + '</span>';
            html += '<span style="color:#aaa;font-size:0.7rem;font-family:Inter,sans-serif;">' + escHtml(cmd.description) + '</span>';
            html += '</div>';
            html += '<div style="color:#666;font-size:0.65rem;font-family:\'Roboto Mono\',monospace;margin-top:2px;">' + escHtml(cmd.usage) + '</div>';
            html += '</div>';
            html += '<span style="color:' + cmd.color + ';font-size:0.6rem;font-family:\'Roboto Mono\',monospace;opacity:0.6;white-space:nowrap;margin-left:8px;">' + escHtml(cmd.category) + '</span>';
            html += '</div>';
        });

        dropdownEl.innerHTML = html;
        dropdownEl.style.display = 'block';
        resultsEl.style.display = 'none';

        dropdownEl.querySelectorAll('.slash-cmd-item').forEach(function(el) {
            el.addEventListener('click', function() {
                var idx = parseInt(el.getAttribute('data-index'), 10);
                if (!isNaN(idx) && suggestions[idx]) {
                    selectCommand(suggestions[idx]);
                }
            });
            el.addEventListener('mouseenter', function() {
                var idx = parseInt(el.getAttribute('data-index'), 10);
                if (!isNaN(idx)) {
                    selectedIdx = idx;
                    highlightItem();
                }
            });
        });
    }

    function highlightItem() {
        dropdownEl.querySelectorAll('.slash-cmd-item').forEach(function(el) {
            var idx = parseInt(el.getAttribute('data-index'), 10);
            el.style.background = idx === selectedIdx ? 'rgba(0,229,255,0.12)' : 'transparent';
        });
    }

    function hideDropdown() {
        if (dropdownEl) dropdownEl.style.display = 'none';
        selectedIdx = -1;
    }

    function hideResults() {
        if (resultsEl) {
            resultsEl.style.display = 'none';
            resultsEl.innerHTML = '';
        }
    }

    function selectCommand(cmd) {
        if (cmd.requiresParam) {
            searchInput.value = '/' + cmd.name + ' ';
            searchInput.focus();
            hideDropdown();
            return;
        }
        cmd.handler('');
        searchInput.value = '';
        hideDropdown();
        hideResults();
    }

    function parseInput(val) {
        if (!val || !val.startsWith(CMD_CHAR)) return null;
        var trimmed = val.slice(1).trim();
        var parts = trimmed.split(/\s+/);
        var cmdName = parts[0].toLowerCase();
        var args = parts.slice(1).join(' ');

        for (var i = 0; i < commands.length; i++) {
            if (commands[i].name === cmdName) {
                return { command: commands[i], args: args };
            }
        }
        return null;
    }

    function showLoading(container) {
        container.innerHTML = '<div style="padding:20px;text-align:center;font-family:\'Roboto Mono\',monospace;color:#00E5FF;">' +
            '<div style="margin-bottom:8px;">> PROCESANDO COMANDO...</div>' +
            '<div style="display:inline-block;width:10px;height:15px;background:#00E5FF;animation:blink 1s step-end infinite;"></div>' +
            '</div>';
        container.style.display = 'block';
    }

    function showError(container, msg) {
        container.innerHTML = '<div style="padding:20px;text-align:center;font-family:\'Roboto Mono\',monospace;color:#FF2D55;">' +
            '<div style="font-size:1.2rem;margin-bottom:6px;">⚠</div>' +
            '<div>' + escHtml(msg) + '</div></div>';
        container.style.display = 'block';
    }

    function showResults(title, contentHtml) {
        resultsEl.innerHTML = '';
        var header = document.createElement('div');
        header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid rgba(0,229,255,0.1);';
        header.innerHTML = '<span style="color:#00E5FF;font-weight:bold;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">' + escHtml(title) + '</span>' +
            '<span style="color:#888;font-size:0.7rem;font-family:monospace;cursor:pointer;" id="slash-results-close">✕ CERRAR</span>';

        var body = document.createElement('div');
        body.style.cssText = 'padding:8px 0;';
        body.innerHTML = contentHtml;

        resultsEl.appendChild(header);
        resultsEl.appendChild(body);
        resultsEl.style.display = 'block';
        dropdownEl.style.display = 'none';

        var closeBtn = resultsEl.querySelector('#slash-results-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() { hideResults(); });
        }
    }

    function executeParsed(parsed) {
        if (!parsed) return;
        var cmd = parsed.command;
        var args = parsed.args;

        if (cmd.requiresParam && !args) {
            showResults('/' + cmd.name, '<div style="padding:16px;color:#aaa;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;text-align:center;">Uso: <span style="color:#00E5FF;">' + escHtml(cmd.usage) + '</span></div>');
            return;
        }

        cmd.handler(args);
    }

    function addToHistory(cmdLine) {
        commandHistory.push(cmdLine);
        if (commandHistory.length > 50) commandHistory.shift();
        historyIdx = commandHistory.length;
    }

    function onInput(e) {
        var val = e.target.value;

        if (val.startsWith(CMD_CHAR)) {
            isActive = true;
            if (val.length === 1) {
                selectedIdx = -1;
            }

            var parsed = parseInput(val);

            // Si ya es un comando completo con argumentos, ocultar dropdown de sugerencias
            if (parsed && parsed.args) {
                hideDropdown();
                searchInput.placeholder = '/' + parsed.command.name + ' — ' + parsed.command.description.toLowerCase() + '...';
                return;
            }

            // Si es un comando completo seguido exactamente de un espacio, esperando argumentos
            if (parsed && val.endsWith(' ') && !parsed.args) {
                hideDropdown();
                searchInput.placeholder = '/' + parsed.command.name + ' — ingresa ' + parsed.command.paramLabel + '...';
                return;
            }

            showSuggestions(val);
        } else {
            if (isActive) {
                isActive = false;
                hideDropdown();
                hideResults();
                searchInput.placeholder = 'Filtrar datos tácticos...';
            }
        }
    }

    function onKeyDown(e) {
        if (!isActive) return;

        var val = searchInput.value;
        var parsed = parseInput(val);
        var dropdownVisible = dropdownEl.style.display === 'block';
        var items = dropdownVisible ? dropdownEl.querySelectorAll('.slash-cmd-item') : [];
        var hasItems = items.length > 0;

        switch (e.key) {
            case 'ArrowDown':
                if (!dropdownVisible || !hasItems) return;
                e.preventDefault();
                selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
                highlightItem();
                items[selectedIdx].scrollIntoView({ block: 'nearest' });
                break;
            case 'ArrowUp':
                if (!dropdownVisible || !hasItems) return;
                e.preventDefault();
                selectedIdx = Math.max(selectedIdx - 1, 0);
                highlightItem();
                items[selectedIdx].scrollIntoView({ block: 'nearest' });
                break;
            case 'Enter':
                e.preventDefault();
                if (dropdownVisible && selectedIdx >= 0 && selectedIdx < items.length) {
                    var partial = val.slice(1).trim();
                    var suggestions = getSuggestions(partial);
                    if (suggestions[selectedIdx]) {
                        selectCommand(suggestions[selectedIdx]);
                    }
                    return;
                }
                if (parsed) {
                    executeParsed(parsed);
                    searchInput.value = '';
                    searchInput.placeholder = 'Filtrar datos tácticos...';
                }
                break;
            case 'Tab':
                if (!dropdownVisible || !hasItems) return;
                if (selectedIdx >= 0) {
                    e.preventDefault();
                    var partial = searchInput.value.slice(1).trim();
                    var suggestions = getSuggestions(partial);
                    if (suggestions[selectedIdx]) {
                        selectCommand(suggestions[selectedIdx]);
                    }
                }
                break;
            case 'Escape':
                e.preventDefault();
                hideDropdown();
                hideResults();
                isActive = false;
                searchInput.value = '';
                searchInput.placeholder = 'Filtrar datos tácticos...';
                searchInput.blur();
                break;
        }
    }

    function switchTab(tabId) {
        var btn = document.querySelector('.nav-button[data-tab="' + tabId + '"]');
        if (btn) {
            btn.click();
            return true;
        }
        return false;
    }

    function filterTab(searchId, query) {
        var input = document.getElementById(searchId);
        if (input) {
            input.value = query;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            return true;
        }
        return false;
    }

    function getPlatformColor(platform) {
        var colors = {
            twitter: '#1DA1F2',
            instagram: '#E4405F',
            tiktok: '#000000',
            telegram: '#0088CC',
            youtube: '#FF0000',
            all: '#00E5FF'
        };
        return colors[platform] || '#00E5FF';
    }

    function init() {
        injectUI();

        register({
            name: 'help',
            description: 'Muestra todos los comandos disponibles',
            usage: '/help',
            category: 'Sistema',
            color: '#B388FF',
            paramLabel: '',
            requiresParam: false,
            handler: function() {
                var html = '<div style="padding:8px 16px;">';
                commands.forEach(function(cmd) {
                    if (cmd.name === 'help') return;
                    html += '<div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03);">';
                    html += '<span style="color:' + cmd.color + ';font-weight:bold;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;width:140px;">/' + escHtml(cmd.display) + '</span>';
                    html += '<span style="color:#aaa;font-size:0.75rem;flex:1;">' + escHtml(cmd.description) + '</span>';
                    html += '<span style="color:#666;font-size:0.65rem;font-family:\'Roboto Mono\',monospace;">' + escHtml(cmd.category) + '</span>';
                    html += '</div>';
                });
                html += '</div>';
                showResults('COMANDOS SLASH (' + commands.length + ')', html);
            }
        });

        register({
            name: 'search',
            description: 'Búsqueda global en inteligencia (Elasticsearch)',
            usage: '/search <término>',
            category: 'Inteligencia',
            color: '#FF9500',
            paramLabel: 'término de búsqueda',
            requiresParam: true,
            handler: function(args) {
                showLoading(resultsEl);
                resultsEl.style.display = 'block';
                dropdownEl.style.display = 'none';

                fetch('/api/intel/search?q=' + encodeURIComponent(args) + '&limit=50')
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.error) throw new Error(data.error);
                        if (!data.results || !data.results.length) {
                            showResults('BÚSQUEDA: ' + escHtml(args), '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">Sin resultados</div>');
                            return;
                        }
                        var html = '';
                        data.results.slice(0, 20).forEach(function(item) {
                            var title = item.title || 'Sin Título';
                            var source = item.source || 'Desconocido';
                            var date = item.ingested_at ? new Date(item.ingested_at).toLocaleString() : '';
                            var link = item.link || '#';
                            html += '<div style="padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.04);cursor:pointer;transition:background 0.15s;" onmouseover="this.style.background=\'rgba(255,149,0,0.05)\'" onmouseout="this.style.background=\'transparent\'" onclick="window.open(\'' + escHtml(link) + '\',\'_blank\')">';
                            html += '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">';
                            html += '<span style="color:#FF9500;font-size:0.65rem;font-family:\'Roboto Mono\',monospace;border:1px solid rgba(255,149,0,0.3);padding:1px 6px;border-radius:3px;">' + escHtml(source) + '</span>';
                            html += '<span style="color:#888;font-size:0.65rem;font-family:monospace;">' + escHtml(date) + '</span>';
                            html += '</div>';
                            html += '<div style="color:#fff;font-size:0.85rem;font-weight:600;">' + escHtml(title) + '</div>';
                            if (item.summary) html += '<div style="color:#aaa;font-size:0.75rem;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + escHtml(item.summary) + '</div>';
                            html += '</div>';
                        });
                        if (data.results.length > 20) {
                            html += '<div style="padding:12px;text-align:center;color:#888;font-size:0.75rem;font-family:monospace;">+' + (data.results.length - 20) + ' resultados más</div>';
                        }
                        showResults('BÚSQUEDA: ' + escHtml(args) + ' (' + data.count + ' resultados)', html);
                    })
                    .catch(function(err) {
                        showError(resultsEl, 'Error en búsqueda: ' + err.message);
                    });
            }
        });

        register({
            name: 'osint',
            description: 'Búsqueda OSINT completa en todas las plataformas',
            usage: '/osint <username>',
            category: 'OSINT',
            color: '#00ffaa',
            paramLabel: 'nombre de usuario',
            requiresParam: true,
            handler: function(args) {
                showLoading(resultsEl);
                resultsEl.style.display = 'block';
                dropdownEl.style.display = 'none';

                fetch('/api/search-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: args, platform: 'all' })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) throw new Error(data.error);
                    if (!data.platforms || !Object.keys(data.platforms).length) {
                        showResults('OSINT: @' + escHtml(args), '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se encontraron perfiles para @' + escHtml(args) + '</div>');
                        return;
                    }
                    var html = '';
                    var foundCount = 0;
                    for (var p in data.platforms) {
                        if (!data.platforms.hasOwnProperty(p)) continue;
                        var r = data.platforms[p];
                        if (!r.found) continue;
                        foundCount++;
                        html += '<div style="padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.04);">';
                        html += '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">';
                        html += '<span style="color:' + getPlatformColor(p) + ';font-weight:bold;font-size:0.8rem;font-family:\'Roboto Mono\',monospace;">' + escHtml(p.toUpperCase()) + '</span>';
                        html += '<span style="color:#4CD964;font-size:0.7rem;">✓ ENCONTRADO</span>';
                        html += '</div>';
                        if (r.name) html += '<div style="color:#fff;font-size:0.85rem;">' + escHtml(r.name) + '</div>';
                        if (r.bio) html += '<div style="color:#94A3B8;font-size:0.75rem;margin-top:2px;">' + escHtml(r.bio) + '</div>';
                        if (r.followers) html += '<div style="color:#94A3B8;font-size:0.7rem;">Seguidores: ' + escHtml(r.followers) + '</div>';
                        if (r.url) html += '<a href="' + escHtml(r.url) + '" target="_blank" style="color:#00E5FF;font-size:0.75rem;text-decoration:none;display:inline-block;margin-top:4px;">Ver perfil →</a>';
                        html += '</div>';
                    }
                    if (!foundCount) {
                        html = '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se encontraron perfiles para @' + escHtml(args) + '</div>';
                    }
                    showResults('OSINT: @' + escHtml(args), html);
                })
                .catch(function(err) {
                    showError(resultsEl, 'Error en OSINT: ' + err.message);
                });
            }
        });

        register({
            name: 'twitter',
            description: 'Busca perfil en X (Twitter)',
            usage: '/twitter <username>',
            category: 'Social',
            color: '#1DA1F2',
            paramLabel: 'usuario de Twitter',
            requiresParam: true,
            handler: function(args) {
                showLoading(resultsEl);
                resultsEl.style.display = 'block';
                dropdownEl.style.display = 'none';
                fetch('/api/search-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: args, platform: 'twitter' })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) throw new Error(data.error);
                    var html = '';
                    if (data.platforms && data.platforms.twitter && data.platforms.twitter.found) {
                        var r = data.platforms.twitter;
                        html += '<div style="padding:16px;">';
                        if (r.name) html += '<div style="color:#fff;font-size:0.95rem;font-weight:600;">' + escHtml(r.name) + '</div>';
                        if (r.bio) html += '<div style="color:#94A3B8;font-size:0.8rem;margin-top:4px;">' + escHtml(r.bio) + '</div>';
                        if (r.followers) html += '<div style="color:#888;font-size:0.75rem;margin-top:4px;">👥 ' + escHtml(r.followers) + '</div>';
                        if (r.url) html += '<a href="' + escHtml(r.url) + '" target="_blank" style="color:#1DA1F2;font-size:0.8rem;text-decoration:none;display:inline-block;margin-top:8px;">Ver perfil →</a>';
                        html += '</div>';
                    } else {
                        html = '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se encontró perfil de Twitter para @' + escHtml(args) + '</div>';
                    }
                    showResults('TWITTER: @' + escHtml(args), html);
                })
                .catch(function(err) {
                    showError(resultsEl, 'Error: ' + err.message);
                });
            }
        });

        register({
            name: 'instagram',
            description: 'Busca perfil en Instagram',
            usage: '/instagram <username>',
            category: 'Social',
            color: '#E4405F',
            paramLabel: 'usuario de Instagram',
            requiresParam: true,
            handler: function(args) {
                showLoading(resultsEl);
                resultsEl.style.display = 'block';
                dropdownEl.style.display = 'none';
                fetch('/api/search-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: args, platform: 'instagram' })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) throw new Error(data.error);
                    var html = '';
                    if (data.platforms && data.platforms.instagram && data.platforms.instagram.found) {
                        var r = data.platforms.instagram;
                        html += '<div style="padding:16px;">';
                        if (r.name) html += '<div style="color:#fff;font-size:0.95rem;font-weight:600;">' + escHtml(r.name) + '</div>';
                        if (r.bio) html += '<div style="color:#94A3B8;font-size:0.8rem;margin-top:4px;">' + escHtml(r.bio) + '</div>';
                        if (r.followers) html += '<div style="color:#888;font-size:0.75rem;margin-top:4px;">👥 ' + escHtml(r.followers) + '</div>';
                        if (r.url) html += '<a href="' + escHtml(r.url) + '" target="_blank" style="color:#E4405F;font-size:0.8rem;text-decoration:none;display:inline-block;margin-top:8px;">Ver perfil →</a>';
                        html += '</div>';
                    } else {
                        html = '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se encontró perfil de Instagram para @' + escHtml(args) + '</div>';
                    }
                    showResults('INSTAGRAM: @' + escHtml(args), html);
                })
                .catch(function(err) {
                    showError(resultsEl, 'Error: ' + err.message);
                });
            }
        });

        register({
            name: 'telegram',
            description: 'Busca perfil en Telegram',
            usage: '/telegram <username>',
            category: 'Social',
            color: '#0088CC',
            paramLabel: 'usuario de Telegram',
            requiresParam: true,
            handler: function(args) {
                showLoading(resultsEl);
                resultsEl.style.display = 'block';
                dropdownEl.style.display = 'none';
                fetch('/api/search-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: args, platform: 'telegram' })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) throw new Error(data.error);
                    var html = '';
                    if (data.platforms && data.platforms.telegram && data.platforms.telegram.found) {
                        var r = data.platforms.telegram;
                        html += '<div style="padding:16px;">';
                        if (r.name) html += '<div style="color:#fff;font-size:0.95rem;font-weight:600;">' + escHtml(r.name) + '</div>';
                        if (r.bio) html += '<div style="color:#94A3B8;font-size:0.8rem;margin-top:4px;">' + escHtml(r.bio) + '</div>';
                        if (r.followers) html += '<div style="color:#888;font-size:0.75rem;margin-top:4px;">👥 ' + escHtml(r.followers) + '</div>';
                        if (r.url) html += '<a href="' + escHtml(r.url) + '" target="_blank" style="color:#0088CC;font-size:0.8rem;text-decoration:none;display:inline-block;margin-top:8px;">Ver perfil →</a>';
                        html += '</div>';
                    } else {
                        html = '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se encontró perfil de Telegram para @' + escHtml(args) + '</div>';
                    }
                    showResults('TELEGRAM: @' + escHtml(args), html);
                })
                .catch(function(err) {
                    showError(resultsEl, 'Error: ' + err.message);
                });
            }
        });

        register({
            name: 'tiktok',
            description: 'Busca perfil en TikTok',
            usage: '/tiktok <username>',
            category: 'Social',
            color: '#000000',
            paramLabel: 'usuario de TikTok',
            requiresParam: true,
            handler: function(args) {
                showLoading(resultsEl);
                resultsEl.style.display = 'block';
                dropdownEl.style.display = 'none';
                fetch('/api/search-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: args, platform: 'tiktok' })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) throw new Error(data.error);
                    var html = '';
                    if (data.platforms && data.platforms.tiktok && data.platforms.tiktok.found) {
                        var r = data.platforms.tiktok;
                        html += '<div style="padding:16px;">';
                        if (r.name) html += '<div style="color:#fff;font-size:0.95rem;font-weight:600;">' + escHtml(r.name) + '</div>';
                        if (r.bio) html += '<div style="color:#94A3B8;font-size:0.8rem;margin-top:4px;">' + escHtml(r.bio) + '</div>';
                        if (r.followers) html += '<div style="color:#888;font-size:0.75rem;margin-top:4px;">👥 ' + escHtml(r.followers) + '</div>';
                        if (r.url) html += '<a href="' + escHtml(r.url) + '" target="_blank" style="color:#fff;font-size:0.8rem;text-decoration:none;display:inline-block;margin-top:8px;">Ver perfil →</a>';
                        html += '</div>';
                    } else {
                        html = '<div style="padding:20px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se encontró perfil de TikTok para @' + escHtml(args) + '</div>';
                    }
                    showResults('TIKTOK: @' + escHtml(args), html);
                })
                .catch(function(err) {
                    showError(resultsEl, 'Error: ' + err.message);
                });
            }
        });

        register({
            name: 'news',
            description: 'Filtra noticias por palabra clave en el tab actual',
            usage: '/news <palabra clave>',
            category: 'Navegación',
            color: '#44aaee',
            paramLabel: 'palabra clave',
            requiresParam: true,
            handler: function(args) {
                switchTab('news');
                setTimeout(function() { filterTab('search-input', args); }, 100);
                hideResults();
                hideDropdown();
                searchInput.value = '';
                searchInput.placeholder = 'Filtrar datos tácticos...';
            }
        });

        register({
            name: 'sentiment',
            description: 'Navega al análisis de sentimiento',
            usage: '/sentiment <término>',
            category: 'Navegación',
            color: '#ffd700',
            paramLabel: 'término',
            requiresParam: false,
            handler: function(args) {
                switchTab('sentiment');
                if (args) {
                    setTimeout(function() { filterTab('sentiment-search', args); }, 100);
                }
                hideResults();
                hideDropdown();
                searchInput.value = '';
                searchInput.placeholder = 'Filtrar datos tácticos...';
            }
        });

        register({
            name: 'tab',
            description: 'Cambia al tab especificado',
            usage: '/tab <news|intel|social|map|...>',
            category: 'Navegación',
            color: '#00E5FF',
            paramLabel: 'nombre del tab',
            requiresParam: true,
            handler: function(args) {
                var tabMap = {
                    'news': 'news',
                    'noticias': 'news',
                    'intel': 'intel',
                    'social': 'social',
                    'map': 'map',
                    'mapa': 'map',
                    'actors': 'user-search',
                    'actores': 'user-search',
                    'analytics': 'analytics',
                    'analitica': 'analytics',
                    'cyber': 'cyber',
                    'alerts': 'alerts',
                    'alertas': 'alerts',
                    'realtime': 'realtime',
                    'narratives': 'narrative',
                    'narrativas': 'narrative',
                    'graph': 'graph',
                    'grafo': 'graph',
                    'config': 'config',
                    'configuracion': 'config',
                    'sentiment': 'sentiment',
                    'timeline': 'timeline'
                };
                var tabId = tabMap[args.toLowerCase().trim()];
                if (!tabId) {
                    showResults('TAB', '<div style="padding:16px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">Tab desconocido: "' + escHtml(args) + '". Usa /help para ver tabs disponibles.</div>');
                    return;
                }
                var switched = switchTab(tabId);
                if (!switched) {
                    showResults('TAB', '<div style="padding:16px;color:#FF2D55;text-align:center;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">No se pudo cambiar al tab "' + escHtml(tabId) + '"</div>');
                    return;
                }
                hideResults();
                hideDropdown();
                searchInput.value = '';
                searchInput.placeholder = 'Filtrar datos tácticos...';
            }
        });

        register({
            name: 'clear',
            description: 'Limpia filtros y resultados',
            usage: '/clear',
            category: 'Sistema',
            color: '#FF2D55',
            paramLabel: '',
            requiresParam: false,
            handler: function() {
                var clearBtn = document.getElementById('btn-clear-filters');
                if (clearBtn) clearBtn.click();
                hideResults();
                hideDropdown();
                searchInput.value = '';
                searchInput.placeholder = 'Filtrar datos tácticos...';
                if (window.CobaltoSearch) CobaltoSearch.clearSearch();
            }
        });

        register({
            name: 'cctv',
            description: 'Abre el visor global de cámaras CCTV',
            usage: '/cctv',
            category: 'OSIRIS',
            color: '#FFD700',
            paramLabel: '',
            requiresParam: false,
            handler: function() {
                if (window.CobaltoCore && window.CobaltoCore.switchTab) {
                    window.CobaltoCore.switchTab('tab-osiris-global');
                }
                hideResults();
                hideDropdown();
            }
        });

        register({
            name: 'recon',
            description: 'Ejecuta consulta en OSIRIS RECON Toolkit',
            usage: '/recon <tool> <target>',
            category: 'OSIRIS',
            color: '#00FFAA',
            paramLabel: 'objetivo',
            requiresParam: true,
            handler: function(args) {
                if (window.CobaltoCore && window.CobaltoCore.switchTab) {
                    window.CobaltoCore.switchTab('tab-osiris-recon');
                }
                var reconInput = document.getElementById('or-query');
                if (reconInput) {
                    reconInput.value = args;
                    reconInput.focus();
                }
                hideResults();
                hideDropdown();
            }
        });

        register({
            name: 'dossier',
            description: 'Abre el perfilador táctico de actores (Dossier 360°)',
            usage: '/dossier <nombre>',
            category: 'Inteligencia',
            color: '#B388FF',
            paramLabel: 'actor',
            requiresParam: true,
            handler: function(args) {
                if (window.CobaltoCore && window.CobaltoCore.switchTab) {
                    window.CobaltoCore.switchTab('tab-user-search');
                }
                var searchInput = document.getElementById('user-search-input');
                if (searchInput) {
                    searchInput.value = args;
                    var btn = document.getElementById('user-search-btn');
                    if (btn) btn.click();
                }
                hideResults();
                hideDropdown();
            }
        });

        if (searchInput) {
            searchInput.addEventListener('input', onInput);
            searchInput.addEventListener('keydown', onKeyDown);
        }

        // Global Ctrl+K / Cmd+K listener for Omnibox activation
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                var sInput = document.getElementById('search-input');
                if (sInput) {
                    sInput.focus();
                    if (!sInput.value.startsWith('/')) {
                        sInput.value = '/';
                    }
                    var evt = new Event('input', { bubbles: true });
                    sInput.dispatchEvent(evt);
                    if (typeof window.showTacticalToast === 'function') {
                        window.showTacticalToast('⚡ Omnibox Táctico Activado (Comandos Slash)', 'info');
                    }
                }
            }
        });

        console.log('[SLASH] Sistema de comandos slash inicializado. ' + commands.length + ' comandos registrados.');
    }

    return {
        init: init,
        register: register,
        commands: commands,
        showResults: showResults,
        hideResults: hideResults
    };
})();

document.addEventListener('DOMContentLoaded', function() {
    if (window.CobaltoSlash) {
        window.CobaltoSlash.init();
    }
});

