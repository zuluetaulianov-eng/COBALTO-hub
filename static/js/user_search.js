
document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('user-search-input');
    if(input) {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if(window.CobaltoSearch) CobaltoSearch.searchUser();
            }
        });
    }
});
/**
 * Cobalto Hub - User Search Module
 * Manejo de búsqueda de perfiles en múltiples plataformas.
 */

window.CobaltoSearch = {
    
    clearSearch: function() {
        document.getElementById('user-search-input').value = '';
        document.getElementById('user-search-results').innerHTML = '';
        var searchBtn = document.querySelector('#tab-user-search .btn-tactical');
        if (searchBtn) { searchBtn.disabled = false; searchBtn.textContent = 'INVESTIGAR'; }
    },
    searchUser: function() {
        if (this._searching) return;
        const username = document.getElementById('user-search-input').value.trim();
        const platform = document.getElementById('platform-select').value;
        const resultsContainer = document.getElementById('user-search-results');
        const searchBtn = document.querySelector('#tab-user-search .btn-tactical');
        
        if (!username) {
            resultsContainer.innerHTML = '<div style="text-align:center;padding:3rem;color:var(--text-muted);"><p>Ingrese un nombre de usuario</p></div>';
            return;
        }
        
        resultsContainer.innerHTML = `
            <div style="padding:2rem; font-family:'Roboto Mono',monospace; color:#00E5FF; background:rgba(10,11,16,0.8); border:1px solid #00E5FF; border-radius:8px;">
                <div style="margin-bottom:8px;">> INICIANDO MOTOR OSINT...</div>
                <div style="margin-bottom:8px;">> ESCANEANDO PLATAFORMA: ${platform.toUpperCase()}</div>
                <div style="margin-bottom:8px;">> EXTRAYENDO HUELLA DIGITAL PARA: @${username}</div>
                <div class="blinking-cursor" style="display:inline-block; width:10px; height:15px; background:#00E5FF; animation:blink 1s step-end infinite;"></div>
            </div>`;

        if (searchBtn) { searchBtn.disabled = true; searchBtn.textContent = '🔍 BUSCANDO...'; }
        this._searching = true;

        var controller = new AbortController();
        var timeout = setTimeout(function() { controller.abort(); }, 30000);

        fetch('/api/search-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username, platform: platform }),
            signal: controller.signal
        })
        .then(response => response.json())
        .then(data => {
            clearTimeout(timeout);
            this.displayUserResults(data);
        })
        .catch(error => {
            clearTimeout(timeout);
            console.error('Error:', error);
            resultsContainer.innerHTML = '<div style="text-align:center;padding:3rem;color:#FF2D55;"><p>Error al buscar usuario</p></div>';
        })
        .finally(function() {
            if (searchBtn) { searchBtn.disabled = false; searchBtn.textContent = 'INVESTIGAR'; }
            this._searching = false;
        }.bind(this));
    },

    
    analyzeWithCobalto: function(name, bio, platform, containerId) {
        var container = document.getElementById(containerId);
        if(!container) return;
        
        container.innerHTML = '<div style="color:#00E5FF; font-family:\'Roboto Mono\'; font-size:0.75rem;">⏳ [COBALTO] Analizando perfil lingüístico y biometría de red...</div>';
        
        setTimeout(() => {
            var isSuspicious = bio.toLowerCase().includes('bot') || bio.toLowerCase().includes('backup') || bio === 'Sin biografía' || bio.length < 10;
            var report = "";
            
            if(isSuspicious) {
                report = "⚠️ <b>NIVEL DE AMENAZA: ALTO.</b> El perfil carece de profundidad orgánica. La biografía es genérica o ausente, típico comportamiento de cuentas " + 
                         "desechables o nodos de Astroturfing. Se recomienda monitorizar interacciones para mapear granja de bots.";
            } else {
                report = "ℹ️ <b>NIVEL DE AMENAZA: BAJO/MODERADO.</b> El usuario presenta huella digital orgánica. Biografía estructurada (" + platform + "). " +
                         "Probable actor humano real. Proceder con análisis de sentimiento en sus publicaciones si es un objetivo de interés.";
            }
            
            container.innerHTML = `
                <div style="background:rgba(0,229,255,0.1); border-left:4px solid #00E5FF; padding:10px; font-family:'Inter',sans-serif; font-size:0.8rem; color:#E2E8F0; border-radius:0 4px 4px 0;">
                    <div style="color:#00E5FF; font-weight:bold; font-family:'Roboto Mono'; margin-bottom:5px;">REPORTE TÁCTICO DE COBALTO</div>
                    ${report}
                </div>`;
        }, 2000);
    },
    displayUserResults: function(data) {
        const resultsContainer = document.getElementById('user-search-results');
        const escapeFn = (window.CobaltoCore && window.CobaltoCore.utils.escapeHTML) || 
            (s => String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[m])));
        
        if (!data || Object.keys(data).length === 0) {
            resultsContainer.innerHTML = '<div style="text-align:center;padding:3rem;color:var(--text-muted);"><p>No se encontraron resultados</p></div>';
            return;
        }

        if (data.error) {
            resultsContainer.innerHTML = `<div style="text-align:center;padding:3rem;color:#FF2D55;">
                <p>⚠️ Error del motor OSINT: ${escapeFn(data.error)}</p>
            </div>`;
            return;
        }

        // Normalize: handle both single-user {platforms:{}} and multi-user extraction {type:"username_extraction", results:[...]}
        var platformSets = [];
        if (data.type === 'username_extraction' && data.results) {
            data.results.forEach(function(r) {
                if (r.platforms) platformSets.push({username: r.username, platforms: r.platforms});
            });
        } else if (data.platforms) {
            platformSets.push({username: data.username, platforms: data.platforms});
        }

        if (!platformSets.length) {
            resultsContainer.innerHTML = '<div style="text-align:center;padding:3rem;color:var(--text-muted);"><p>No se encontraron resultados</p></div>';
            return;
        }

        var html = '';
        platformSets.forEach(function(ps) {
            if (platformSets.length > 1 && ps.username) {
                html += '<h4 style="color:#E2E8F0;margin:0.5rem 0 0.3rem 0;font-size:0.95rem;">@' + escapeFn(ps.username) + '</h4>';
            }
            html += '<div style="display:flex;flex-direction:column;gap:1rem;">';
            for (const platform in ps.platforms) {
                const result = ps.platforms[platform];
                const statusColor = result.found ? '#4CD964' : '#FF2D55';
                const statusText = result.found ? '✓ Encontrado' : '✗ No encontrado';
                
                html += `<div class="panel-glass" style="padding:1.2rem; margin-bottom:1rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem;">
                        <span style="font-weight:700;color:#fff;font-size:1rem;">${escapeFn(result.platform)}</span>
                        <span style="color:${statusColor};font-size:0.85rem;font-weight:600;">${escapeFn(statusText)}</span>
                    </div>`;
                
                if (result.found) {
                    html += `<div style="display:flex;flex-direction:column;gap:0.5rem;">`;
                    if (result.name) html += `<div style="color:#E2E8F0;font-size:0.9rem;"><strong>Nombre:</strong> ${escapeFn(result.name)}</div>`;
                    if (result.bio) html += `<div style="color:#94A3B8;font-size:0.85rem;"><strong>Bio:</strong> ${escapeFn(result.bio)}</div>`;
                    if (result.followers) html += `<div style="color:#94A3B8;font-size:0.85rem;"><strong>Seguidores:</strong> ${escapeFn(result.followers)}</div>`;
                    
                    if (result.matches && result.matches.length > 0) {
                        html += `<div style="margin-top:0.5rem; padding:0.8rem; background:rgba(0,229,255,0.05); border:1px solid rgba(0,229,255,0.1); border-radius:8px;">
                            <div style="color:var(--primary); font-size:0.7rem; font-family:'Roboto Mono',monospace; margin-bottom:0.4rem; font-weight:bold;">📍 HALLAZGOS TÁCTICOS (KEYWORDS)</div>`;
                        result.matches.forEach(m => {
                            html += `<div style="color:#E2E8F0; font-size:0.75rem; margin-bottom:0.4rem; border-left:2px solid var(--primary); padding-left:8px; line-height:1.4;">${escapeFn(m)}</div>`;
                        });
                        html += `</div>`;
                    }
                    
                    if (result.url) html += `<a href="${escapeFn(result.url)}" target="_blank" style="color:#00E5FF;text-decoration:none;font-size:0.85rem;margin-top:0.5rem;display:inline-block;">Ver perfil →</a>`;
                    
                    var safeBio = escapeFn(result.bio || 'Sin biografía').replace(/'/g, "\'");
                    var safeName = escapeFn(result.name || username).replace(/'/g, "\'");
                    var resultId = 'cobalto-eval-' + Math.random().toString(36).substr(2, 9);
                    
                    html += `<button class="btn-cyan" style="margin-top:15px; padding:10px; width:100%; border-radius:6px; font-weight:bold; font-family:'Roboto Mono';" onclick="if(window.CobaltoSearch)CobaltoSearch.analyzeWithCobalto('${safeName}', '${safeBio}', '${escapeFn(result.platform)}', '${resultId}')">🤖 EVALUAR AMENAZA (COBALTO)</button>
                             <button class="btn-tactical" style="margin-top:8px; padding:10px; width:100%; border-radius:6px; font-weight:bold; font-family:'Roboto Mono'; border-color:#00E5FF; color:#00E5FF;" onclick="if(window.CobaltoSearch)CobaltoSearch.loadDossier('${safeName}')">📜 VER DOSSIER TÁCTICO 360°</button>
                             <div id="${resultId}" style="margin-top:10px;"></div>`;

                    html += `</div>`;
                }
                
                html += `</div>`;
            }
            html += '</div>';
        });
        
        resultsContainer.innerHTML = html;
    },

    loadDossier: function(targetName) {
        const resultsContainer = document.getElementById('user-search-results');
        const escapeFn = (window.CobaltoCore && window.CobaltoCore.utils.escapeHTML) || (s => String(s));
        
        resultsContainer.innerHTML = `
            <div style="padding:2rem; font-family:'Roboto Mono',monospace; color:#00E5FF; background:rgba(10,11,16,0.9); border:1px solid #00E5FF; border-radius:8px;">
                <div>> CONSULTANDO HISTÓRICO Y FININT...</div>
                <div>> GENERANDO EXPEDIENTE TÁCTICO 360° PARA: ${escapeFn(targetName)}</div>
                <div class="blinking-cursor" style="display:inline-block; width:10px; height:15px; background:#00E5FF; margin-top:10px;"></div>
            </div>`;

        fetch('/api/dossier?target=' + encodeURIComponent(targetName))
            .then(res => res.json())
            .then(d => {
                if (d.error) {
                    resultsContainer.innerHTML = '<div style="color:#FF2D55; padding:2rem;">⚠️ ' + escapeFn(d.error) + '</div>';
                    return;
                }
                this.displayDossier(d);
            })
            .catch(err => {
                console.error(err);
                resultsContainer.innerHTML = '<div style="color:#FF2D55; padding:2rem;">⚠️ Error cargando expediente táctico</div>';
            });
    },

    displayDossier: function(d) {
        this.currentDossierData = d;
        const resultsContainer = document.getElementById('user-search-results');
        const escapeFn = (window.CobaltoCore && window.CobaltoCore.utils.escapeHTML) || (s => String(s));
        const prof = d.profile || {};
        const met = d.metrics || {};
        
        let riskColor = '#3291FF';
        if (prof.risk_level === 'CRÍTICO') riskColor = '#FF2D55';
        else if (prof.risk_level === 'ALERTA') riskColor = '#FF9500';
        else if (prof.risk_level === 'ELEVADO') riskColor = '#FFCC00';

        let html = `
            <div class="panel-glass" style="padding:1.5rem; border-top:4px solid ${riskColor}; margin-bottom:1.5rem;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem; flex-wrap:wrap; gap:1rem;">
                    <div>
                        <div style="font-size:0.75rem; color:#94A3B8; font-family:'Roboto Mono';">EXPEDIENTE TÁCTICO 360°</div>
                        <h2 style="margin:0.2rem 0; color:#FFF; font-size:1.5rem;">${escapeFn(prof.name)}</h2>
                        <div style="font-size:0.8rem; color:#00E5FF;">TIPO: ${escapeFn(prof.entity_type)} | TEATRO: ${(prof.country_tags||[]).join(', ')}</div>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.4rem;">
                        <div style="background:${riskColor}; color:#000; padding:4px 12px; border-radius:4px; font-weight:bold; font-size:0.85rem; font-family:'Roboto Mono';">
                            RIESGO ${escapeFn(prof.risk_level)} (${prof.risk_score}/10)
                        </div>
                        ${prof.ofac_flag ? '<div style="background:#FF2D55; color:#FFF; padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:bold;">🚨 SANCIÓN OFAC SDN</div>' : ''}
                        <div style="display:flex; gap:0.4rem; margin-top:0.4rem;">
                            <button onclick="CobaltoSearch.exportDossierJSON()" class="btn-tactical" style="font-size:0.7rem; padding:3px 8px; border-color:#00E5FF; color:#00E5FF;">
                                📥 EXPORTAR JSON
                            </button>
                            <button onclick="CobaltoSearch.printDossierPDF()" class="btn-tactical" style="font-size:0.7rem; padding:3px 8px; border-color:#00FFAA; color:#00FFAA;">
                                🖨️ IMPRIMIR / PDF
                            </button>
                        </div>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:1rem; margin-bottom:1.5rem; background:rgba(0,0,0,0.3); padding:1rem; border-radius:8px;">
                    <div>
                        <div style="font-size:0.7rem; color:#94A3B8;">MENCIONES TOTALES</div>
                        <div style="font-size:1.2rem; color:#FFF; font-weight:bold;">${met.total_mentions}</div>
                    </div>
                    <div>
                        <div style="font-size:0.7rem; color:#94A3B8;">ACTIVIDAD 24H</div>
                        <div style="font-size:1.2rem; color:#00E5FF; font-weight:bold;">${met.recent_24h_mentions}</div>
                    </div>
                    <div>
                        <div style="font-size:0.7rem; color:#94A3B8;">PRESIÓN MEDIÁTICA</div>
                        <div style="font-size:1.2rem; color:#FFF; font-weight:bold;">${met.media_pressure}</div>
                    </div>
                    <div>
                        <div style="font-size:0.7rem; color:#94A3B8;">REPORTES HUMINT</div>
                        <div style="font-size:1.2rem; color:#FFF; font-weight:bold;">${met.humint_reports_count}</div>
                    </div>
                </div>

                <h3 style="color:#00E5FF; font-size:1rem; margin-bottom:0.8rem; font-family:'Roboto Mono';">📅 LÍNEA DE TIEMPO Y SUCESOS RECIENTES</h3>
                <div style="display:flex; flex-direction:column; gap:0.6rem; margin-bottom:1.5rem;">`;

        if (d.timeline && d.timeline.length) {
            d.timeline.forEach(t => {
                html += `
                    <div style="background:rgba(255,255,255,0.03); border-left:3px solid #00E5FF; padding:0.8rem; border-radius:0 6px 6px 0;">
                        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94A3B8; margin-bottom:4px;">
                            <span>${escapeFn(t.source)}</span>
                            <span>${escapeFn(t.timestamp)}</span>
                        </div>
                        <div style="color:#FFF; font-size:0.85rem; font-weight:600; margin-bottom:4px;">${escapeFn(t.title)}</div>
                        <div style="color:#CBD5E1; font-size:0.78rem;">${escapeFn(t.summary)}</div>
                    </div>`;
            });
        } else {
            html += `<div style="color:#94A3B8; font-size:0.85rem;">No hay sucesos registrados en la línea de tiempo.</div>`;
        }

        html += `</div>
                <button class="btn-tactical" style="width:100%; border-color:#666; color:#AAA;" onclick="if(window.CobaltoSearch)CobaltoSearch.clearSearch()">← VOLVER A BÚSQUEDA</button>
            </div>`;

        resultsContainer.innerHTML = html;
    },

    exportDossierJSON: function() {
        if (!this.currentDossierData) return;
        var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(this.currentDossierData, null, 2));
        var downloadAnchor = document.createElement('a');
        var name = (this.currentDossierData.profile && this.currentDossierData.profile.name) ? this.currentDossierData.profile.name : 'dossier';
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", `dossier_tactico_${name.replace(/\s+/g, '_').toLowerCase()}.json`);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
    },

    printDossierPDF: function() {
        window.print();
    }
};


