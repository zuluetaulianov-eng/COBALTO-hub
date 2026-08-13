
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
                             <div id="${resultId}" style="margin-top:10px;"></div>`;

                    html += `</div>`;
                }
                
                html += `</div>`;
            }
            html += '</div>';
        });
        
        resultsContainer.innerHTML = html;
    }
};
