/**
 * Cobalto Hub - Intel Graph Module
 * Grafo Social con vis-network. Cargado bajo demanda.
 */
var graphNetwork = null;
var graphAllNodes = null;
var graphAllEdges = null;
var graphRawData = null;
var graphFiltersActive = { type: {}, sentiment: {}, community: {} };
var graphSearchTerm = '';
var graphTimelineData = [];
var graphTimelineIdx = -1;
var graphColorByCommunity = false;
var graphCurrentSolver = 'forceAtlas2Based';

var ENTITY_ALIASES = {
    'eln': 'ELN (Ejército de Liberación Nacional)',
    'ejército de liberación nacional': 'ELN (Ejército de Liberación Nacional)',
    'ejercito de liberacion nacional': 'ELN (Ejército de Liberación Nacional)',
    'mindefensa': 'Ministerio de Defensa',
    'ministerio de defensa': 'Ministerio de Defensa',
    'ffmm colombia': 'Fuerzas Militares de Colombia',
    'fuerzasmilcol': 'Fuerzas Militares de Colombia',
    'ejército nacional': 'Ejército Nacional de Colombia',
    'ejercito_col': 'Ejército Nacional de Colombia',
    'fanb': 'FANB (Fuerza Armada Nacional Bolivariana)',
    'padrino lópez': 'Vladimir Padrino López',
    'padrino lopez': 'Vladimir Padrino López'
};

function resetGraphView() { if (graphNetwork) graphNetwork.fit({ animation: true }); }

function graphRefreshFromEmpty() {
    var btn = document.getElementById('graph-refresh-btn');
    var statusEl = document.getElementById('graph-empty-status');
    if (btn) { btn.disabled = true; btn.textContent = '\u23F3 Consultando...'; }
    if (statusEl) statusEl.textContent = 'Solicitando datos frescos al servidor...';
    fetch('/api/graph-data').then(function(r) { return r.json(); }).then(function(data) {
        if (data && data.nodes && data.nodes.length) {
            window._socialGraph = data;
            if (statusEl) statusEl.style.color = '#00ffaa';
            if (statusEl) statusEl.textContent = '\u2705 ' + data.nodes.length + ' nodos encontrados. Construyendo grafo...';
            setTimeout(function() { initSocialGraph(); }, 400);
        } else {
            if (btn) { btn.disabled = false; btn.innerHTML = '\uD83D\uDD04 Reintentar'; }
            if (statusEl) { statusEl.style.color = '#FF9500'; statusEl.textContent = '\u26A0\uFE0F Sin nodos a\u00FAn. El worker sigue procesando datos del pipeline OSINT.'; }
            var tsEl = document.getElementById('graph-empty-ts');
            if (tsEl) tsEl.textContent = new Date().toLocaleString('es-VE') + ' (sin datos)';
        }
    }).catch(function(e) {
        if (btn) { btn.disabled = false; btn.innerHTML = '\uD83D\uDD04 Reintentar'; }
        if (statusEl) { statusEl.style.color = '#FF2D55'; statusEl.textContent = '\u274C Error de conexi\u00F3n al servidor.'; }
    });
}

function exportGraphImage() {
    var container = document.getElementById('social-graph-container');
    if (!container || typeof html2canvas === 'undefined') return;
    html2canvas(container, { backgroundColor: '#0A0B10', scale: 2 }).then(function(canvas) {
        var link = document.createElement('a');
        link.download = 'cobalto_grafo_' + new Date().toISOString().slice(0, 10) + '.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
    });
}

function exportGraphJSON() {
    if (!graphRawData && (!graphAllNodes || !graphAllEdges)) return;
    var dataToExport = {
        timestamp: new Date().toISOString(),
        nodes: graphAllNodes ? graphAllNodes.get() : [],
        edges: graphAllEdges ? graphAllEdges.get() : []
    };
    var blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'cobalto_topologia_grafo_' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function graphTooltipHTML(n) {
    var sent = n.sentiment || 'neutral';
    var sentColor = sent === 'positive' ? '#00FF88' : sent === 'negative' ? '#FF2D55' : '#FFCC00';
    var catColor = n.group === 'persons' ? '#FF2D55' : n.group === 'organizations' ? '#B388FF' : '#00E5FF';
    
    var botnetBadge = n.is_botnet ? 
        '<div style="background:#FF9500;color:#000;font-weight:bold;font-size:9px;padding:2px 4px;border-radius:3px;margin-bottom:4px;text-align:center;font-family:Inter,sans-serif;">⚠️ BOTNET / ASTROTURFING</div>' : '';

    var ofacBadge = n.ofac_match ? 
        '<span style="background:#FF2D5544;color:#FF2D55;border:1px solid #FF2D5566;padding:1px 6px;border-radius:4px;font-size:8px;font-weight:bold;margin-right:4px;">🔴 OFAC</span>' : '';
    var wikiBadge = n.wikidata_qid ? 
        '<span style="background:#3291FF44;color:#3291FF;border:1px solid #3291FF66;padding:1px 6px;border-radius:4px;font-size:8px;font-weight:bold;margin-right:4px;">🟦 Wikidata</span>' : '';

    return '<div style="font-family:Inter,sans-serif;">' + botnetBadge + 
        '<b style="color:' + catColor + ';">' + (n.label || n.id) + '</b><br/>' +
        '<div style="margin:4px 0;">' + ofacBadge + wikiBadge + '</div>' +
        'Tipo: ' + (n.group || '?') + '<br/>' +
        'Sentimiento: <span style="color:' + sentColor + ';">' + sent + ' (' + (n.sentiment_score || 0).toFixed(2) + ')</span><br/>' +
        'Comunidad: ' + (n.community !== undefined ? n.community : '?') + '<br/>' +
        'Menciones: ' + (n.mention_frequency || 0) + '<br/>' +
        'PageRank: ' + (n.pagerank || 0).toFixed(3) + '<br/>' +
        'Betweenness: ' + (n.betweenness_centrality || 0).toFixed(3) + '<br/>' +
        'Degree: ' + (n.degree_centrality || 0).toFixed(3) + '</div>';
}

function getGraphOptions() {
    return {
        physics: {
            solver: graphCurrentSolver,
            forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 120, springConstant: 0.02 },
            barnesHut: { gravitationalConstant: -3000, centralGravity: 0.3, springLength: 95, springConstant: 0.04 },
            repulsion: { nodeDistance: 120, centralGravity: 0.2, springLength: 200, springConstant: 0.01 },
            hierarchicalRepulsion: { nodeDistance: 120, centralGravity: 0.0, springLength: 100, springConstant: 0.01 }
        },
        edges: { smooth: { type: 'continuous' } },
        interaction: { hover: true, tooltipDelay: 150, navigationButtons: true, keyboard: true },
        nodes: { borderWidth: 1, shadow: { enabled: true, color: 'rgba(0,0,0,0.3)', size: 4 } }
    };
}

function visNodeFromRaw(n) {
    var catColor = n.group === 'persons' ? '#FF2D55' : n.group === 'organizations' ? '#B388FF' : n.group === 'locations' ? '#00E5FF' : '#888888';
    var isBot = !!n.is_botnet;
    var nodeColor = isBot ? '#FF9500' : (n.community_color || catColor);
    // OFAC/Wikidata badges from entity registry
    var ofacBadge = n.ofac_match ? '<span class="badge-critical" style="font-size:8px;">🔴</span>' : '';
    var wikiBadge = n.wikidata_qid ? '<span class="badge-info" style="font-size:8px;">🟦</span>' : '';
    var labelSuffix = (ofacBadge || wikiBadge) ? ' ' + ofacBadge + wikiBadge : '';
    var ofacBorder = n.ofac_match ? '#FF2D55' : null;

    var rawText = (n.label || n.id || '').toLowerCase().trim();
    var canonicalName = ENTITY_ALIASES[rawText] || n.label || n.id;
    return {
        id: n.id, label: canonicalName + labelSuffix, title: graphTooltipHTML(n),
        size: isBot ? Math.max(16, ((n.pagerank || 0.01) * 22 + 10)) : Math.max(6, Math.min(28, ((n.pagerank || 0.01) * 22 + 6))),
        color: { background: nodeColor, border: ofacBorder || (isBot ? '#FF3B30' : nodeColor), highlight: { background: '#fff', border: isBot ? '#FF9500' : (ofacBorder || catColor) } },
        borderWidth: isBot ? 3 : (n.ofac_match ? 2 : 1),
        font: { color: '#E2E8F0', size: 10, strokeWidth: 2, strokeColor: '#0A0B10' },
        group: n.group || 'unknown', sentiment: n.sentiment || 'neutral', sentiment_score: n.sentiment_score || 0,
        community: n.community !== undefined ? n.community : 0, community_color: n.community_color || catColor,
        mention_frequency: n.mention_frequency || 0, degree_centrality: n.degree_centrality || 0,
        betweenness_centrality: n.betweenness_centrality || 0, closeness_centrality: n.closeness_centrality || 0,
        eigenvector_centrality: n.eigenvector_centrality || 0, pagerank: n.pagerank || 0,
        is_botnet: isBot, ofac_match: n.ofac_match || false, wikidata_qid: n.wikidata_qid || ''
    };
}

function visEdgeFromRaw(e) {
    return {
        from: e.from || e.source, to: e.to || e.target, width: e.width || 1, title: e.title || '',
        color: { color: e.color || '#888888', opacity: 0.35, highlight: '#fff' },
        dashes: (e.type === 'co-occurrence'), edgeType: e.type || 'co-occurrence'
    };
}

function initSocialGraph() {
    var container = document.getElementById('social-graph-container');
    if (!container) return;
    var raw = window._socialGraph;
    var nodesList = raw && raw.nodes ? raw.nodes : (raw && raw.graph && raw.graph.nodes ? raw.graph.nodes : []);
    if (!nodesList || !nodesList.length) {
        var ts = window._socialGraphTimestamp ? new Date(window._socialGraphTimestamp).toLocaleString('es-VE') : 'Sin sincronizar';
        container.innerHTML =
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:3rem;text-align:center;">' +
                '<div style="font-size:3rem;margin-bottom:1.5rem;opacity:0.4;">&#x1F578;</div>' +
                '<div style="font-family:\'Roboto Mono\',monospace;color:var(--primary);font-size:0.85rem;letter-spacing:2px;margin-bottom:0.8rem;text-transform:uppercase;">GRAFO SOCIAL &mdash; EN ESPERA DE DATOS</div>' +
                '<p style="color:var(--text-muted);font-size:0.85rem;max-width:480px;line-height:1.6;margin-bottom:1.5rem;">El grafo de entidades sociales se genera durante el ciclo completo del worker OSINT. Requiere un m&iacute;nimo de noticias extra&iacute;das para construir las relaciones entre personas, organizaciones y ubicaciones.</p>' +
                '<div style="display:flex;gap:1rem;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:1.5rem;">' +
                    '<div style="background:rgba(0,229,255,0.05);border:1px solid rgba(0,229,255,0.15);border-radius:8px;padding:0.6rem 1.2rem;font-family:\'Roboto Mono\',monospace;font-size:0.7rem;">' +
                        '<div style="color:var(--text-muted);margin-bottom:0.2rem;">�LTIMO SNAPSHOT</div>' +
                        '<div style="color:var(--primary);" id="graph-empty-ts">' + ts + '</div>' +
                    '</div>' +
                    '<div style="background:rgba(255,45,85,0.05);border:1px solid rgba(255,45,85,0.15);border-radius:8px;padding:0.6rem 1.2rem;font-family:\'Roboto Mono\',monospace;font-size:0.7rem;">' +
                        '<div style="color:var(--text-muted);margin-bottom:0.2rem;">NODOS DETECTADOS</div>' +
                        '<div style="color:#FF2D55;">0 nodos</div>' +
                    '</div>' +
                '</div>' +
                '<button id="graph-refresh-btn" onclick="graphRefreshFromEmpty()" style="' +
                    'padding:0.6rem 1.5rem;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.35);' +
                    'color:var(--primary);border-radius:8px;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;' +
                    'cursor:pointer;letter-spacing:1px;transition:all 0.3s;" ' +
                    'onmouseover="this.style.background=\'rgba(0,229,255,0.2)\'" onmouseout="this.style.background=\'rgba(0,229,255,0.1)\'"' +
                '">&#x1F504; Consultar Datos Frescos</button>' +
                '<div id="graph-empty-status" style="color:var(--text-muted);font-size:0.7rem;margin-top:0.8rem;font-family:\'Roboto Mono\',monospace;min-height:1.2rem;"></div>' +
                '<p style="color:var(--text-muted);font-size:0.7rem;margin-top:0.5rem;font-family:\'Roboto Mono\',monospace;">' +
                    'Aseg&uacute;rate de que <span style="color:var(--primary);">cobalto_worker.py</span> est&eacute; ejecut&aacute;ndose.' +
                '</p>' +
            '</div>';
        return;
    }
    graphRawData = (raw && raw.graph) || raw || {};
    var edgesList = raw && raw.edges ? raw.edges : (raw && raw.graph && raw.graph.edges ? raw.graph.edges : []);
    container.innerHTML = '';
    var uniqTypes = {}, uniqSent = {}, uniqComm = {};
    nodesList.forEach(function(n) {
        var g = n.group || 'unknown'; uniqTypes[g] = (uniqTypes[g] || 0) + 1;
        var s = n.sentiment || 'neutral'; uniqSent[s] = (uniqSent[s] || 0) + 1;
        var c = n.community !== undefined ? n.community : 0; uniqComm[c] = (uniqComm[c] || 0) + 1;
    });
    Object.keys(uniqTypes).forEach(function(k) { graphFiltersActive.type[k] = true; });
    Object.keys(uniqSent).forEach(function(k) { graphFiltersActive.sentiment[k] = true; });
    Object.keys(uniqComm).forEach(function(k) { graphFiltersActive.community[k] = true; });
    graphAllNodes = new vis.DataSet(nodesList.map(function(n) { return visNodeFromRaw(n); }));
    graphAllEdges = new vis.DataSet(edgesList.map(function(e) { return visEdgeFromRaw(e); }));
    var toolbar = document.getElementById('graph-toolbar');
    if (toolbar) {
        toolbar.innerHTML = '<div class="graph-stats" id="graph-stats"></div>' +
            '<div class="graph-search-group"><input type="text" id="graph-search-input" placeholder="Buscar entidad..." class="graph-search-input" />' +
            '<button id="graph-search-btn" class="graph-search-btn">\uD83D\uDD0D</button></div>' +
            '<div class="graph-actions">' +
            '<button onclick="graphColorToggle()" id="graph-color-btn" class="graph-action-btn" title="Color por comunidad">\uD83C\uDFA8</button>' +
            '<button onclick="exportGraphImage()" class="graph-action-btn" title="Exportar PNG">\uD83D\uDCF7</button>' +
            '<button onclick="exportGraphJSON()" class="graph-action-btn" title="Exportar JSON (Gephi/Maltego)">💾</button>' +
            '<button onclick="resetGraphView()" class="graph-action-btn" title="Reiniciar vista">\u27F2</button></div>';
    }
    buildGraphFilters(uniqTypes, uniqSent, uniqComm);
    var visContainer = document.createElement('div');
    visContainer.style.cssText = 'width:100%;height:100%;';
    container.appendChild(visContainer);
    var filtered = applyGraphFilters();
    graphNetwork = new vis.Network(visContainer, filtered, getGraphOptions());
    graphNetwork.on('click', function(params) { 
        if (params.nodes && params.nodes.length) {
            showGraphNodeDetail(params.nodes[0]); 
            applyTargetLock(params.nodes[0]);
        } else {
            hideGraphDetail(); 
            clearTargetLock();
        }
    });
    graphNetwork.on('doubleClick', function() { graphNetwork.fit({ animation: true }); });
    graphNetwork.on('hoverNode', function() { visContainer.style.cursor = 'pointer'; });
    graphNetwork.on('blurNode', function() { visContainer.style.cursor = 'default'; });
    var searchInput = document.getElementById('graph-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            graphSearchTerm = this.value;
            clearTimeout(window._graphSearchDebounce);
            window._graphSearchDebounce = setTimeout(doGraphSearch, 300);
        });
    }
    var searchBtn = document.getElementById('graph-search-btn');
    if (searchBtn) { searchBtn.addEventListener('click', function() { graphSearchTerm = document.getElementById('graph-search-input').value; doGraphSearch(); }); }
    updateGraphStats();
    buildGraphLegend();
    updateKillChain();
    loadGraphTimeline();
    window.refreshGraphData = refreshGraphData;
}

function buildGraphFilters(uniqTypes, uniqSent, uniqComm) {
    var el = document.getElementById('graph-filters');
    if (!el) return;
    var html = '';
    html += '<div class="graph-filter-group">Tipo:';
    Object.keys(uniqTypes).forEach(function(t) {
        var cls = t === 'persons' ? 'btn-red' : t === 'organizations' ? 'btn-purple' : 'btn-cyan';
        html += '<button class="graph-filter-btn active ' + cls + '" data-filter="type" data-value="' + t + '" onclick="toggleGraphFilter(\'type\',\'' + t + '\')">' + t + '</button>';
    });
    html += '</div><div class="graph-filter-group">Sentimiento:';
    Object.keys(uniqSent).forEach(function(s) {
        var cls = s === 'positive' ? 'btn-green' : s === 'negative' ? 'btn-red' : 'btn-orange';
        html += '<button class="graph-filter-btn active ' + cls + '" data-filter="sentiment" data-value="' + s + '" onclick="toggleGraphFilter(\'sentiment\',\'' + s + '\')">' + s + '</button>';
    });
    html += '</div>';
    var commKeys = Object.keys(uniqComm);
    if (commKeys.length > 1) {
        html += '<div class="graph-filter-group">Comunidad:';
        commKeys.forEach(function(c) { html += '<button class="graph-filter-btn active btn-community" data-filter="community" data-value="' + c + '" onclick="toggleGraphFilter(\'community\',\'' + c + '\')">C' + c + '</button>'; });
        html += '</div>';
    }
    
    html += '<div class="graph-filter-group" style="margin-left:auto;">';
    html += '<button id="btn-solo-botnet" class="graph-filter-btn btn-orange" onclick="toggleSoloBotnet()" style="font-weight:bold; border:1px solid #FF9500;"><span style="font-size:1.1rem;">⚠️</span> MODO: SOLO BOTNET</button>';
    html += '</div>';

    var layouts = ['forceAtlas2Based', 'barnesHut', 'repulsion', 'hierarchicalRepulsion'];

    var layoutLabels = ['Fuerza', 'Barnes-Hut', 'Repulsi\u00F3n', 'Jer\u00E1rquico'];
    html += '<div class="graph-filter-group">Layout:';
    for (var li = 0; li < layouts.length; li++) {
        var act = layouts[li] === graphCurrentSolver ? ' active' : '';
        html += '<button class="graph-filter-btn' + act + '" onclick="switchGraphLayout(\'' + layouts[li] + '\')">' + layoutLabels[li] + '</button>';
    }
    html += '</div>';
    el.innerHTML = html;
}

function toggleGraphFilter(category, value) {
    graphFiltersActive[category][value] = !graphFiltersActive[category][value];
    var btn = document.querySelector('[data-filter="' + category + '"][data-value="' + value + '"]');
    if (btn) btn.classList.toggle('active');
    reapplyGraph();
}

function applyGraphFilters() {
    var visibleIds = {};
    var nodesArr = graphAllNodes.get();
    nodesArr.forEach(function(n) {
        if (graphFiltersActive.type[n.group] !== false && graphFiltersActive.sentiment[n.sentiment] !== false && graphFiltersActive.community[n.community] !== false) {
                if (window.graphSoloBotnet && !n.is_botnet) {
                    return; // Ignorar nodos humanos en modo Botnet
                }
            visibleIds[n.id] = true;
        }
    });
    var filteredNodesArr = nodesArr.filter(function(n) { return visibleIds[n.id]; }).map(function(n) { return Object.assign({}, n); });
    var allEdges = graphAllEdges.get();
    var filteredEdgesArr = allEdges.filter(function(e) { return visibleIds[e.from] && visibleIds[e.to]; });
    if (graphSearchTerm) {
        var term = graphSearchTerm.toLowerCase();
        filteredNodesArr.forEach(function(n) {
            var match = (n.label || '').toLowerCase().indexOf(term) !== -1 || (n.id || '').toLowerCase().indexOf(term) !== -1;
            if (match) {
                n.color = { background: '#FF2D55', border: '#FF2D55', highlight: { background: '#fff', border: '#FF2D55' } };
                n.size = Math.max(n.size || 10, 16);
            } else {
                var catColor = n.group === 'persons' ? '#FF2D55' : n.group === 'organizations' ? '#B388FF' : n.group === 'locations' ? '#00E5FF' : '#888888';
                var cc = graphColorByCommunity ? (n.community_color || catColor) : catColor;
                n.color = { background: cc, border: cc, highlight: { background: '#fff', border: cc } };
                n.size = Math.max(6, Math.min(28, ((n.pagerank || 0.01) * 22 + 6)));
            }
        });
    } else if (graphColorByCommunity) {
        filteredNodesArr.forEach(function(n) { var cc = n.community_color || '#888888'; n.color = { background: cc, border: cc, highlight: { background: '#fff', border: cc } }; });
    }
    return { nodes: new vis.DataSet(filteredNodesArr), edges: new vis.DataSet(filteredEdgesArr) };
}

function reapplyGraph() { if (!graphNetwork) return; graphNetwork.setData(applyGraphFilters()); updateGraphStats(); }

function doGraphSearch() {
    var input = document.getElementById('graph-search-input');
    if (input) graphSearchTerm = input.value;
    reapplyGraph();
    if (graphSearchTerm && graphNetwork) {
        var nodes = graphAllNodes.get({ filter: function(n) { return (n.label || '').toLowerCase().indexOf(graphSearchTerm.toLowerCase()) !== -1; } });
        if (nodes && nodes.length && nodes[0].id) graphNetwork.focus(nodes[0].id, { scale: 1.5, animation: true });
    }
}

function switchGraphLayout(solver) {
    graphCurrentSolver = solver;
    if (!graphNetwork) return;
    graphNetwork.setOptions({ physics: { solver: solver } });
    var btns = document.querySelectorAll('#graph-filters .graph-filter-btn');
    btns.forEach(function(b) { if (b.textContent.trim() === 'Fuerza' || b.textContent.trim() === 'Barnes-Hut' || b.textContent.trim() === 'Repulsi\u00F3n' || b.textContent.trim() === 'Jer\u00E1rquico') b.classList.remove('active'); });
    btns.forEach(function(b) {
        var idx = -1;
        if (solver === 'forceAtlas2Based' && b.textContent.trim() === 'Fuerza') idx = 0;
        else if (solver === 'barnesHut' && b.textContent.trim() === 'Barnes-Hut') idx = 1;
        else if (solver === 'repulsion' && b.textContent.trim() === 'Repulsi\u00F3n') idx = 2;
        else if (solver === 'hierarchicalRepulsion' && b.textContent.trim() === 'Jer\u00E1rquico') idx = 3;
        if (idx !== -1) b.classList.add('active');
    });
}

function graphColorToggle() {
    graphColorByCommunity = !graphColorByCommunity;
    var btn = document.getElementById('graph-color-btn');
    if (btn) btn.style.borderColor = graphColorByCommunity ? '#00E5FF' : 'rgba(255,255,255,0.06)';
    reapplyGraph();
}

function showGraphNodeDetail(nodeId) {
    var node = graphAllNodes.get(nodeId);
    if (!node) return;
    var panel = document.getElementById('graph-detail-panel');
    if (!panel) return;
    var sent = node.sentiment || 'neutral';
    var sentColor = sent === 'positive' ? '#00FF88' : sent === 'negative' ? '#FF2D55' : '#FFCC00';
    var catColor = node.group === 'persons' ? '#FF2D55' : node.group === 'organizations' ? '#B388FF' : node.group === 'locations' ? '#00E5FF' : '#888888';
    panel.innerHTML = '<div class="gdetail-header" style="border-left:4px solid ' + catColor + ';">' +
        '<span class="gdetail-title" style="color:' + catColor + ';">' + (node.label || node.id) + '</span>' +
        '<button onclick="hideGraphDetail()" class="gdetail-close">\u2715</button></div>' +
        '<div class="gdetail-body">' +
        '<div class="gdetail-section"><div class="gdetail-sectitle">Clasificaci\u00F3n</div>' +
        '<div class="gdetail-row"><span class="gdetail-label">Tipo</span><span class="gdetail-value">' + (node.group || '?') + '</span></div>' +
        '<div class="gdetail-row"><span class="gdetail-label">Comunidad</span><span class="gdetail-value">' + (node.community !== undefined ? node.community : '?') + '</span></div>' +
        '<div class="gdetail-row"><span class="gdetail-label">Sentimiento</span><span class="gdetail-value ' + sent + '">' + sent + ' (' + (node.sentiment_score || 0).toFixed(2) + ')</span></div></div>' +
        '<div class="gdetail-section"><div class="gdetail-sectitle">Métricas de Influencia & Enlace</div>' +
        '<div class="gdetail-row" title="Importancia macro en la red social"><span class="gdetail-label">👑 Influencia Macro</span><span class="gdetail-value">' + (node.pagerank || 0).toFixed(4) + '</span></div>' +
        '<div class="gdetail-row" title="Capacidad de conectar comunidades distintas"><span class="gdetail-label">🌉 Nodo Enlace / Puente</span><span class="gdetail-value">' + (node.betweenness_centrality || 0).toFixed(4) + '</span></div>' +
        '<div class="gdetail-row" title="Número de conexiones directas"><span class="gdetail-label">🔌 Conexiones Directas</span><span class="gdetail-value">' + (node.degree_centrality || 0).toFixed(4) + '</span></div>' +
        '<div class="gdetail-row" title="Cercanía promedio a todos los nodos"><span class="gdetail-label">🎯 Velocidad de Difusión</span><span class="gdetail-value">' + (node.closeness_centrality || 0).toFixed(4) + '</span></div>' +
        '<div class="gdetail-row" title="Conexiones con otros nodos clave"><span class="gdetail-label">⚡ Red de Influencia</span><span class="gdetail-value">' + (node.eigenvector_centrality || 0).toFixed(4) + '</span></div></div>' +
        '<div class="gdetail-section"><div class="gdetail-sectitle">Actividad</div>' +
        '<div class="gdetail-row"><span class="gdetail-label">Menciones</span><span class="gdetail-value">' + (node.mention_frequency || 0) + '</span></div>' +
        '<div class="gdetail-row"><span class="gdetail-label">Tama\u00F1o</span><span class="gdetail-value">' + (node.size || 0) + '</span></div></div></div>' +
        '<div style="margin-top:15px;"><button class="btn-cyan" style="width:100%; padding:10px; font-family:\'Roboto Mono\',monospace; border-radius:6px; font-weight:bold; cursor:pointer;" onclick="requestCobaltoProfile(\'' + node.id + '\', \'' + (node.label || node.id).replace(/'/g, "\\'") + '\', \'' + node.is_botnet + '\')">🤖 SOLICITAR PERFIL (COBALTO)</button></div>' +
        '<div id="cobalto-profile-result" style="min-height:50px; margin-top:10px;"></div>';

    panel.classList.add('visible');
}

function hideGraphDetail() { var panel = document.getElementById('graph-detail-panel'); if (panel) panel.classList.remove('visible'); }

function updateGraphStats() {
    var el = document.getElementById('graph-stats');
    if (!el || !graphNetwork) return;
    var allNodes = graphAllNodes.get();
    var allEdges = graphAllEdges.get();
    var visibleEdges = graphNetwork.body.data.edges.get();
    var visibleNodes = graphNetwork.body.data.nodes.get();
    var typeCounts = { persons: 0, organizations: 0, locations: 0 };
    allNodes.forEach(function(n) { var g = n.group || 'unknown'; if (typeCounts[g] !== undefined) typeCounts[g]++; });
    el.innerHTML = '<span class="graph-stat-item"><span class="stat-num">' + visibleNodes.length + '</span>/' + allNodes.length + ' nodos</span>' +
        '<span class="graph-stat-item"><span class="stat-num">' + visibleEdges.length + '</span>/' + allEdges.length + ' aristas</span>' +
        (typeCounts.persons ? '<span class="graph-stat-item stat-persons"><span class="stat-num">' + typeCounts.persons + '</span> personas</span>' : '') +
        (typeCounts.organizations ? '<span class="graph-stat-item stat-orgs"><span class="stat-num">' + typeCounts.organizations + '</span> orgs</span>' : '') +
        (typeCounts.locations ? '<span class="graph-stat-item stat-locations"><span class="stat-num">' + typeCounts.locations + '</span> ubic.</span>' : '');
}

function buildGraphLegend() {
    var el = document.getElementById('graph-legend');
    if (!el) return;
    el.innerHTML = '<div class="glegend-title">Leyenda</div>' +
        '<div class="glegend-item"><span class="glegend-dot" style="background:#FF2D55;box-shadow:0 0 4px #FF2D55;"></span>Personas</div>' +
        '<div class="glegend-item"><span class="glegend-dot" style="background:#B388FF;box-shadow:0 0 4px #B388FF;"></span>Organizaciones</div>' +
        '<div class="glegend-item"><span class="glegend-dot" style="background:#00E5FF;box-shadow:0 0 4px #00E5FF;"></span>Ubicaciones</div>' +
        '<div style="margin-top:0.3rem;border-top:1px solid rgba(255,255,255,0.04);padding-top:0.25rem;">' +
        '<div class="glegend-item"><span class="glegend-line" style="background:#FF2D55;"></span>Conflicto</div>' +
        '<div class="glegend-item"><span class="glegend-line" style="background:#00FF88;"></span>Alianza</div>' +
        '<div class="glegend-item"><span class="glegend-line" style="background:#00E5FF;"></span>Ubicaci\u00F3n</div>' +
        '<div class="glegend-item"><span class="glegend-line" style="background:#888888;border:1px dashed rgba(255,255,255,0.15);"></span>Co-ocurrencia</div></div>';

}

function loadGraphTimeline() {
    var toolbar = document.getElementById('graph-toolbar');
    if (!toolbar) return;
    var mainArea = document.querySelector('#tab-graph .graph-main-area');
    if (!mainArea) return;
    var existing = document.getElementById('graph-timeline');
    if (existing) existing.remove();
    var timelineDiv = document.createElement('div');
    timelineDiv.className = 'graph-timeline';
    timelineDiv.id = 'graph-timeline';
    timelineDiv.innerHTML = 'Cargando historial...';
    toolbar.parentNode.insertBefore(timelineDiv, mainArea);
    graphTimelineData = []; graphTimelineIdx = -1;
    fetch('/api/graph-timeline').then(function(r) { return r.json(); }).then(function(data) {
        if (data && data.length > 1) { graphTimelineData = data; graphTimelineIdx = data.length - 1; renderTimeline(); }
        else { timelineDiv.innerHTML = '<span style="color:#64748B;">Snapshot actual: ' + (window._socialGraphTimestamp ? new Date(window._socialGraphTimestamp).toLocaleString() : 'ahora') + '</span>'; }
    }).catch(function() { timelineDiv.innerHTML = '<span style="color:#64748B;">Snapshot actual: ' + (window._socialGraphTimestamp ? new Date(window._socialGraphTimestamp).toLocaleString() : 'ahora') + '</span>'; });
}

function renderTimeline() {
    var el = document.getElementById('graph-timeline');
    if (!el || !graphTimelineData.length) return;
    var snap = graphTimelineData[graphTimelineIdx];
    el.innerHTML = '<button class="graph-timeline-btn" onclick="timelinePrev()" ' + (graphTimelineIdx <= 0 ? 'disabled' : '') + '>\u25C0 Anterior</button>' +
        '<span>Snapshot ' + (graphTimelineIdx + 1) + '/' + graphTimelineData.length + ' - ' + new Date(snap.timestamp).toLocaleString() + '</span>' +
        '<button class="graph-timeline-btn" onclick="timelineNext()" ' + (graphTimelineIdx >= graphTimelineData.length - 1 ? 'disabled' : '') + '>Siguiente \u25B6</button>';
    if (snap && snap.graph_data) {
        graphAllNodes = new vis.DataSet((snap.graph_data.nodes || []).map(function(n) { return visNodeFromRaw(n); }));
        graphAllEdges = new vis.DataSet((snap.graph_data.edges || []).map(function(e) { return visEdgeFromRaw(e); }));
        reapplyGraph();
    }
}
function timelinePrev() { if (graphTimelineIdx > 0) { graphTimelineIdx--; renderTimeline(); } }
function timelineNext() { if (graphTimelineIdx < graphTimelineData.length - 1) { graphTimelineIdx++; renderTimeline(); } }

function refreshGraphData() {
    var tab = document.getElementById('tab-graph');
    if (!tab) return;
    fetch('/api/graph-data').then(function(r) { return r.json(); }).then(function(data) {
        if (data && data.nodes && data.nodes.length) {
            if (!graphNetwork) {
                var container = document.getElementById('social-graph-container');
                if (container) {
                    container.innerHTML = '';
                    window._socialGraph = data;
                    initSocialGraph();
                }
                return;
            }
            graphRawData = data;
            graphAllNodes = new vis.DataSet((data.nodes || []).map(function(n) { return visNodeFromRaw(n); }));
            graphAllEdges = new vis.DataSet((data.edges || []).map(function(e) { return visEdgeFromRaw(e); }));
            if (graphNetwork) {
                reapplyGraph();
                var hud = document.getElementById('hud-update');
                if (hud && tab.classList.contains('active')) { hud.innerText = 'Grafo actualizado.'; hud.style.display = 'block'; setTimeout(function() { hud.style.display = 'none'; }, 3000); }
            }
            loadGraphTimeline();
        }
    }).catch(function() {});
}


window.graphSoloBotnet = false;
function toggleSoloBotnet() {
    window.graphSoloBotnet = !window.graphSoloBotnet;
    var btn = document.getElementById('btn-solo-botnet');
    if(window.graphSoloBotnet) {
        btn.style.background = '#FF9500';
        btn.style.color = '#000';
        btn.style.boxShadow = '0 0 15px #FF9500';
    } else {
        btn.style.background = 'transparent';
        btn.style.color = '#FF9500';
        btn.style.boxShadow = 'none';
    }
    reapplyGraph();
}

function updateKillChain() {
    var panel = document.getElementById('kill-chain-panel');
    var list = document.getElementById('kill-chain-list');
    if(!panel || !list || !graphAllNodes) return;
    
    var nodes = graphAllNodes.get();
    if(nodes.length === 0) {
        panel.style.display = 'none';
        return;
    }
    
    // Algoritmo de Score de Amenaza Táctica Compuesta (OFAC + Botnet + Betweenness + PageRank)
    nodes.forEach(n => {
        var score = 0;
        if (n.ofac_match) score += 100;
        if (n.is_botnet) score += 50;
        score += (n.betweenness_centrality || 0) * 40;
        score += (n.pagerank || 0) * 30;
        n._threatScore = score;
    });
    nodes.sort((a,b) => (b._threatScore || 0) - (a._threatScore || 0));
    var top5 = nodes.slice(0, 5);
    
    var html = '';
    top5.forEach((n, i) => {
        var ofacBadge = n.ofac_match ? '<span style="color:#FF2D55;font-weight:bold;font-size:0.65rem;margin-left:4px;">[OFAC]</span>' : '';
        var botBadge = n.is_botnet ? '<span style="color:#FF9500;font-weight:bold;font-size:0.65rem;margin-left:4px;">[BOTNET]</span>' : '';
        var bridgeBadge = (n.betweenness_centrality || 0) > 0.1 ? '<span style="color:#B388FF;font-weight:bold;font-size:0.65rem;margin-left:4px;">[PUENTE]</span>' : '';
        
        html += `<div style="background:rgba(255,255,255,0.05); padding:8px; border-radius:6px; font-family:'Inter',sans-serif; font-size:0.75rem; cursor:pointer; border-left:3px solid #FF2D55; margin-bottom:4px;" 
                    onclick="focusOnNode('${n.id}')"
                    onmouseover="this.style.background='rgba(255,45,85,0.2)'" onmouseout="this.style.background='rgba(255,255,255,0.05)'">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#64748B;">#${i+1}</span>
                <b style="color:#E2E8F0; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${n.label || n.id}</b>
                <div>${ofacBadge}${botBadge}${bridgeBadge}</div>
            </div>
            <div style="color:#94A3B8; font-size:0.65rem; margin-top:4px; display:flex; justify-content:space-between;">
                <span>Score Amenaza: <b style="color:#FF2D55;">${(n._threatScore || 0).toFixed(1)} pts</b></span>
                <span>Puente: ${(n.betweenness_centrality || 0).toFixed(3)}</span>
            </div>
        </div>`;
    });
    list.innerHTML = html;
    panel.style.display = 'block';
}

function focusOnNode(nodeId) {
    if(!graphNetwork) return;
    graphNetwork.focus(nodeId, { scale: 1.2, animation: true });
    graphNetwork.setSelection({ nodes: [nodeId] });
    showGraphNodeDetail(nodeId);
    applyTargetLock(nodeId);
}

function applyTargetLock(nodeId) {
    if(!graphNetwork) return;
    var allNodes = graphNetwork.body.data.nodes.get();
    var connectedEdges = graphNetwork.getConnectedEdges(nodeId);
    var connectedNodes = graphNetwork.getConnectedNodes(nodeId);
    
    var updates = [];
    allNodes.forEach(n => {
        if(n.id === nodeId) {
            // Target locked (brillante)
            updates.push({ id: n.id, color: { border: '#00FF00', background: n.color.background }, opacity: 1.0, shadow: {color: '#00FF00', size: 20} });
        } else if (connectedNodes.includes(n.id)) {
            // Conectados (semi brillantes)
            updates.push({ id: n.id, opacity: 0.8 });
        } else {
            // Resto oscurecido
            updates.push({ id: n.id, opacity: 0.1 });
        }
    });
    
    graphNetwork.body.data.nodes.update(updates);
}

function clearTargetLock() {
    if(!graphNetwork) return;
    var allNodes = graphNetwork.body.data.nodes.get();
    var updates = [];
    allNodes.forEach(n => {
        updates.push({ id: n.id, opacity: 1.0, shadow: {color: 'rgba(0,0,0,0.3)', size: 4} });
    });
    graphNetwork.body.data.nodes.update(updates);
}

window.requestCobaltoProfile = function(nodeId, nodeLabel, isBot) {
    var cont = document.getElementById('cobalto-profile-result');
    if(!cont) return;
    cont.innerHTML = '<div style="color:#00E5FF; font-family:\\\'Roboto Mono\\\'; font-size:0.75rem;">⏳ [COBALTO] Estableciendo conexión neuronal... analizando telemetría...</div>';
    
    setTimeout(() => {
        var profile = "";
        if(isBot === 'true') {
            profile = "⚠️ ALERTA DE PSYOPS: Este nodo presenta un patrón de Entropía Mecánica (Botnet). Genera ruido artificial para inflar métricas. Recomendación: AISLAR INMEDIATAMENTE y bloquear subred.";
        } else {
            profile = "ℹ️ EVALUACIÓN TÁCTICA: Actor orgánico detectado. Actúa como difusor ideológico. Revisar 'Betweenness' para verificar si es un puente de infiltración.";
        }
        
        cont.innerHTML = `<div style="background:rgba(0, 229, 255, 0.1); border-left:3px solid #00E5FF; padding:8px; font-family:'Inter',sans-serif; font-size:0.75rem; color:#E2E8F0; margin-top:10px;">
            <b style="color:#00E5FF;">REPORTE COBALTO (PSY-OPS)</b><br/>
            ${profile}
        </div>`;
    }, 1500);
}
