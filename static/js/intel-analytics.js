/**
 * Cobalto Hub - Tactical Analytics Controller
 * Handles Chart.js initialization, live data polling, and beautiful dark-mode renderings.
 */

window.CobaltoAnalytics = {
    charts: {},
    isInitialized: false,
    activeEntries: [], // Guarda una referencia a las entradas de auditoría forense del rango actual

    init: function() {
        if (this.isInitialized) {
            this.refreshData();
            return;
        }
        this.isInitialized = true;
        this.refreshData();
    },

    refreshData: function() {
        if (this._loading) return;
        this._loading = true;
        const refreshBtn = document.querySelector("#tab-analytics .btn-tactical");
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerText = "⚡ CARGANDO...";
        }

        const rangeSelector = document.getElementById("analytics-timerange");
        const range = rangeSelector ? rangeSelector.value : "24h";

        fetch(`/api/analytics-data?range=${range}`)
            .then(response => {
                if (!response.ok) throw new Error("API HTTP Error: " + response.status);
                return response.json();
            })
            .then(data => {
                this.activeEntries = data.all_entries || [];
                this.renderCharts(data);
                if (refreshBtn) {
                    refreshBtn.disabled = false;
                    refreshBtn.innerText = "🔄 REFRESCAR MÉTRICAS";
                }
                this._loading = false;
            })
            .catch(err => {
                console.error("[ERROR] CobaltoAnalytics: Falló la recarga de métricas:", err);
                if (refreshBtn) {
                    refreshBtn.disabled = false;
                    refreshBtn.innerText = "⚠️ REINTENTAR";
                }
                this._loading = false;
            });
    },

    renderCharts: function(data) {
        // Asegurar la existencia de todas las propiedades para evitar TypeErrors
        data = data || {};
        data.severity = data.severity || {};
        data.threats = data.threats || {};
        data.sentiment = data.sentiment || {};
        data.latency = data.latency || {};
        data.latency.Patria = data.latency.Patria || [];
        data.latency.BCV = data.latency.BCV || [];
        data.latency.CANTV = data.latency.CANTV || [];
        data.sigint = data.sigint || {};
        data.darkweb = data.darkweb || {};
        data.misinfo = data.misinfo || {};
        data.geointel = data.geointel || {};

        // ACTUALIZAR KPI METRICS DINÁMICAMENTE
        const critical = data.severity["CRÍTICO"] || 0;
        const alta = data.severity["ALTA"] || 0;
        const media = data.severity["MEDIA"] || 0;
        
        const criticalIncidents = critical + alta;
        const kpiCritical = document.getElementById('kpi-critical-incidents');
        if (kpiCritical) kpiCritical.innerText = criticalIncidents;

        // Calcular Threat Level dinámicamente
        const threatLevel = Math.min(100, Math.max(10, (critical * 18 + alta * 10 + media * 3)));
        const kpiThreat = document.getElementById('kpi-threat-level');
        const kpiThreatStatus = document.getElementById('kpi-threat-status');
        if (kpiThreat) kpiThreat.innerText = threatLevel + "%";
        if (kpiThreatStatus) {
            if (threatLevel >= 75) {
                kpiThreatStatus.innerText = "(CRÍTICO)";
                kpiThreatStatus.style.color = "#ff4444";
                kpiThreat.style.color = "#ff4444";
            } else if (threatLevel >= 40) {
                kpiThreatStatus.innerText = "(MEDIO)";
                kpiThreatStatus.style.color = "#ffaa00";
                kpiThreat.style.color = "#ffaa00";
            } else {
                kpiThreatStatus.innerText = "(BAJO)";
                kpiThreatStatus.style.color = "#00ffaa";
                kpiThreat.style.color = "#00ffaa";
            }
        }


        // --- BLUF IA Y GENERACIÓN DE RECOMENDACIONES ---
        const blufText = document.getElementById('analytics-ai-bluf');
        const actionList = document.getElementById('analytics-action-list');
        
        if (blufText && actionList) {
            let summary = "";
            let actions = [];
            
            // Lógica heurística de MINERVA para el BLUF
            if (threatLevel >= 75) {
                summary = `ALERTA CRÍTICA: Se detecta una crisis sistémica. Severidad extremadamente alta cruzada con un ${data.misinfo?.activas > 0 ? 'pico de operaciones inauténticas' : 'alta negatividad orgánica'}. Prioridad de defensa en sector ${Object.keys(data.threats).sort((a,b) => data.threats[b] - data.threats[a])[0] || 'Desconocido'}.`;
                actions = [
                    "Activar Bloqueo Preventivo: Restringir IPs anónimas y redes Tor.",
                    "Escalar nivel de alerta en anillos de seguridad físicos (Instalaciones Estratégicas).",
                    "Desplegar contramedida comunicacional en redes oficiales para desmentir narrativas."
                ];
            } else if (threatLevel >= 40) {
                summary = `ADVERTENCIA TÁCTICA: Aumento de fricción en la red. Existe una correlación entre ataques de botnets de intensidad media y focos de calor geopolítico. Monitoreo elevado recomendado.`;
                actions = [
                    "Aumentar frecuencia de polling del Mando Central (cada 3 minutos).",
                    "Preparar análisis de grafo social para identificar Nodos Cero (paciente cero) de los bulos.",
                    "Revisar logs de latencia (CANTV/Patria) en busca de micro-cortes por DDoS."
                ];
            } else {
                summary = `OPERACIÓN ESTABLE: Todos los nodos de inteligencia reportan parámetros dentro del umbral nominal. El tráfico inauténtico es filtrado exitosamente por la barrera pasiva.`;
                actions = [
                    "Mantener estado de vigilancia rutinario.",
                    "Ejecutar purga de la base de datos histórica programada (si > 30 días).",
                    "Continuar generación de mapas de calor pasivos."
                ];
            }
            
            blufText.innerHTML = `<strong>Análisis de Patrones:</strong> ${summary}`;
            actionList.innerHTML = actions.map(a => `<li>${a}</li>`).join('');
        }
        
        // Estilos y Paleta de Colores Tácticos (Cyber-SIEM Neon Glow)

        const colors = {
            primary: 'rgba(0, 229, 255, 0.85)',       // Cian Neón
            primaryGlow: 'rgba(0, 229, 255, 0.2)',
            accent: 'rgba(175, 82, 222, 0.85)',        // Púrpura Imperial
            accentGlow: 'rgba(175, 82, 222, 0.2)',
            red: 'rgba(255, 59, 48, 0.85)',            // Rojo Crítico
            redGlow: 'rgba(255, 59, 48, 0.2)',
            orange: 'rgba(255, 149, 0, 0.85)',         // Naranja Botnet/Alto
            orangeGlow: 'rgba(255, 149, 0, 0.2)',
            yellow: 'rgba(255, 204, 0, 0.85)',         // Amarillo Atención
            green: 'rgba(52, 199, 89, 0.85)',          // Verde Operacional
            greenGlow: 'rgba(52, 199, 89, 0.2)',
            text: '#8E8E93',
            gridLines: 'rgba(255, 255, 255, 0.05)',
            cardBg: 'rgba(10, 11, 16, 0.85)'
        };

        const globalOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#f0f0f0',
                        font: { family: 'Roboto Mono, monospace', size: 10 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(10, 11, 16, 0.95)',
                    titleColor: '#00e5ff',
                    titleFont: { family: 'Roboto Mono', weight: 'bold' },
                    bodyFont: { family: 'Inter' },
                    borderColor: 'rgba(0, 229, 255, 0.3)',
                    borderWidth: 1
                }
            }
        };

        // 1. GRAVEDAD DE INCIDENTES (Doughnut - Drill down compatible)
        try {
            this.destroyChart('chart-severity');
            const ctxSeverity = document.getElementById('chart-severity');
            if (ctxSeverity) {
                this.charts['chart-severity'] = new Chart(ctxSeverity, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(data.severity),
                        datasets: [{
                            data: Object.values(data.severity),
                            backgroundColor: [colors.red, colors.orange, colors.yellow, colors.primary],
                            borderColor: '#12131a',
                            borderWidth: 2,
                            hoverOffset: 6
                        }]
                    },
                    options: Object.assign({}, globalOptions, {
                        onClick: function(event, elements) {
                            if (elements.length > 0) {
                                const index = elements[0].index;
                                const label = this.data.labels[index];
                                window.CobaltoAnalytics.handleForensicDrilldown('severity', label);
                            }
                        },
                        plugins: Object.assign({}, globalOptions.plugins, {
                            legend: {
                                position: 'right',
                                labels: { color: '#f0f0f0', font: { family: 'Roboto Mono', size: 11 } }
                            }
                        })
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-severity:", e);
        }

        // 2. VECTORES DE AMENAZAS (Horizontal Bar - Drill down compatible)
        try {
            this.destroyChart('chart-threats');
            const ctxThreats = document.getElementById('chart-threats');
            if (ctxThreats) {
                this.charts['chart-threats'] = new Chart(ctxThreats, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(data.threats),
                        datasets: [{
                            label: 'Número de Incidentes',
                            data: Object.values(data.threats),
                            backgroundColor: [
                                colors.red,
                                colors.orange,
                                colors.accent,
                                colors.primary,
                                colors.yellow,
                                '#8e8e93'
                            ],
                            borderWidth: 0,
                            borderRadius: 4
                        }]
                    },
                    options: Object.assign({}, globalOptions, {
                        indexAxis: 'y',
                        onClick: function(event, elements) {
                            if (elements.length > 0) {
                                const index = elements[0].index;
                                const label = this.data.labels[index];
                                window.CobaltoAnalytics.handleForensicDrilldown('threats', label);
                            }
                        },
                        plugins: Object.assign({}, globalOptions.plugins, {
                            legend: { display: false }
                        }),
                        scales: {
                            x: {
                                grid: { color: colors.gridLines },
                                ticks: { color: colors.text, font: { family: 'Roboto Mono' } }
                            },
                            y: {
                                grid: { display: false },
                                ticks: { color: '#f0f0f0', font: { family: 'Roboto Mono', size: 10 } }
                            }
                        }
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-threats:", e);
        }

        // 3. LATENCIA DE RED E INFRAESTRUCTURA CRÍTICA (Line Chart con Degradados de Neón)
        try {
            this.destroyChart('chart-latency');
            const ctxLatency = document.getElementById('chart-latency');
            if (ctxLatency) {
                const ctx = ctxLatency.getContext('2d');
                const hours = data.hours || ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00", "00:00", "02:00", "04:00", "06:00", "08:00", "10:00"];
                
                // Degradado 1 (Cian)
                const gradPrimary = ctx.createLinearGradient(0, 0, 0, 200);
                gradPrimary.addColorStop(0, 'rgba(0, 229, 255, 0.45)');
                gradPrimary.addColorStop(1, 'rgba(0, 229, 255, 0.0)');
                
                // Degradado 2 (Púrpura)
                const gradAccent = ctx.createLinearGradient(0, 0, 0, 200);
                gradAccent.addColorStop(0, 'rgba(175, 82, 222, 0.45)');
                gradAccent.addColorStop(1, 'rgba(175, 82, 222, 0.0)');
                
                // Degradado 3 (Naranja)
                const gradOrange = ctx.createLinearGradient(0, 0, 0, 200);
                gradOrange.addColorStop(0, 'rgba(255, 149, 0, 0.45)');
                gradOrange.addColorStop(1, 'rgba(255, 149, 0, 0.0)');

                this.charts['chart-latency'] = new Chart(ctxLatency, {
                    type: 'line',
                    data: {
                        labels: hours,
                        datasets: [
                            {
                                label: 'Patria.org.ve (ms)',
                                data: data.latency.Patria,
                                borderColor: colors.primary,
                                backgroundColor: gradPrimary,
                                tension: 0.4,
                                fill: true,
                                borderWidth: 2
                            },
                            {
                                label: 'BCV Finanzas (ms)',
                                data: data.latency.BCV,
                                borderColor: colors.accent,
                                backgroundColor: gradAccent,
                                tension: 0.4,
                                fill: true,
                                borderWidth: 2
                            },
                            {
                                label: 'Gateway CANTV (ms)',
                                data: data.latency.CANTV,
                                borderColor: colors.orange,
                                backgroundColor: gradOrange,
                                tension: 0.4,
                                fill: true,
                                borderWidth: 2
                            }
                        ]
                    },
                    options: Object.assign({}, globalOptions, {
                        scales: {
                            x: {
                                grid: { color: colors.gridLines },
                                ticks: { color: colors.text, font: { family: 'Roboto Mono' } }
                            },
                            y: {
                                grid: { color: colors.gridLines },
                                ticks: { color: colors.text, font: { family: 'Roboto Mono' } }
                            }
                        }
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-latency:", e);
        }

        // 4. POLARIZACIÓN Y SENTIMIENTO DE RED (Polar Area Chart)
        try {
            this.destroyChart('chart-sentiment');
            const ctxSentiment = document.getElementById('chart-sentiment');
            if (ctxSentiment) {
                const translatedLabels = {
                    "positive": "Positivo / Orgánico",
                    "negative": "Hostil / Coordinado",
                    "neutral": "Neutro / Informativo"
                };
                this.charts['chart-sentiment'] = new Chart(ctxSentiment, {
                    type: 'polarArea',
                    data: {
                        labels: Object.keys(data.sentiment).map(k => translatedLabels[k] || k),
                        datasets: [{
                            data: Object.values(data.sentiment),
                            backgroundColor: [colors.green, colors.red, '#8e8e93'],
                            borderColor: '#12131a',
                            borderWidth: 2
                        }]
                    },
                    options: Object.assign({}, globalOptions, {
                        scales: {
                            r: {
                                grid: { color: 'rgba(255,255,255,0.06)' },
                                angleLines: { color: 'rgba(255,255,255,0.08)' },
                                ticks: { display: false }
                            }
                        }
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-sentiment:", e);
        }

        // 5. ANOMALÍAS Y SOBREVUELOS SIGINT (Vertical Bar)
        try {
            this.destroyChart('chart-sigint');
            const ctxSigint = document.getElementById('chart-sigint');
            if (ctxSigint) {
                this.charts['chart-sigint'] = new Chart(ctxSigint, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(data.sigint),
                        datasets: [{
                            label: 'Vectores Detectados',
                            data: Object.values(data.sigint),
                            backgroundColor: colors.accent,
                            borderColor: colors.accent,
                            borderWidth: 1,
                            borderRadius: 5,
                            barThickness: 32
                        }]
                    },
                    options: Object.assign({}, globalOptions, {
                        plugins: Object.assign({}, globalOptions.plugins, {
                            legend: { display: false }
                        }),
                        scales: {
                            x: {
                                grid: { display: false },
                                ticks: { color: '#f0f0f0', font: { family: 'Roboto Mono', size: 10 } }
                            },
                            y: {
                                grid: { color: colors.gridLines },
                                ticks: { color: colors.text, font: { family: 'Roboto Mono' }, stepSize: 1 }
                            }
                        }
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-sigint:", e);
        }

        // 6. DARK WEB & RANSOMWARE (Radar Chart - Drill down compatible)
        try {
            this.destroyChart('chart-darkweb');
            const ctxDarkweb = document.getElementById('chart-darkweb');
            if (ctxDarkweb) {
                const dw = data.darkweb || { Finanzas: 5, Energía: 3, Telecom: 8, Gubernamental: 12, Industrial: 4 };
                this.charts['chart-darkweb'] = new Chart(ctxDarkweb, {
                    type: 'radar',
                    data: {
                        labels: ['Finanzas', 'Energía', 'Telecom', 'Gubernamental', 'Industrial'],
                        datasets: [{
                            label: 'Menciones / Filtraciones',
                            data: [
                                dw.Finanzas || 0,
                                dw.Energía || 0,
                                dw.Telecom || 0,
                                dw.Gubernamental || 0,
                                dw.Industrial || 0
                            ],
                            backgroundColor: colors.accentGlow,
                            borderColor: colors.accent,
                            pointBackgroundColor: colors.primary,
                            pointBorderColor: '#fff',
                            borderWidth: 2
                        }]
                    },
                    options: Object.assign({}, globalOptions, {
                        onClick: function(event, elements) {
                            if (elements.length > 0) {
                                const index = elements[0].index;
                                const label = this.data.labels[index];
                                window.CobaltoAnalytics.handleForensicDrilldown('darkweb', label);
                            }
                        },
                        scales: {
                            r: {
                                grid: { color: 'rgba(255, 255, 255, 0.06)' },
                                angleLines: { color: 'rgba(255, 255, 255, 0.08)' },
                                pointLabels: { color: '#f0f0f0', font: { family: 'Roboto Mono', size: 10 } },
                                ticks: { display: false }
                            }
                        }
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-darkweb:", e);
        }

        // 7. DESINFORMACIÓN Y FAKE NEWS (Half-Doughnut Gauge)
        try {
            this.destroyChart('chart-misinfo');
            const ctxMisinfo = document.getElementById('chart-misinfo');
            if (ctxMisinfo) {
                const mis = data.misinfo || { activas: 6, analizadas: 24 };
                const activas = mis.activas || 0;
                const analizadas = mis.analizadas || 0;
                const normalBase = Math.max(10, analizadas - activas);
                this.charts['chart-misinfo'] = new Chart(ctxMisinfo, {
                    type: 'doughnut',
                    data: {
                        labels: ['Campañas Detectadas', 'Espectro Neutro'],
                        datasets: [{
                            data: [activas, normalBase],
                            backgroundColor: [colors.orange, 'rgba(255, 255, 255, 0.04)'],
                            borderColor: '#12131a',
                            borderWidth: 2
                        }]
                    },
                    options: Object.assign({}, globalOptions, {
                        circumference: 180,
                        rotation: -90,
                        plugins: Object.assign({}, globalOptions.plugins, {
                            legend: {
                                position: 'bottom',
                                labels: { color: '#f0f0f0', font: { family: 'Roboto Mono', size: 10 } }
                            }
                        })
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-misinfo:", e);
        }

        // 8. GEOINTEL: SATÉLITES Y AIS DARK (Grouped Vertical Bar Chart)
        try {
            this.destroyChart('chart-geointel');
            const ctxGeointel = document.getElementById('chart-geointel');
            if (ctxGeointel) {
                const geo = data.geointel || {
                    regiones: ["Occidente", "Centro", "Oriente", "Guayana"],
                    anomalias_satelitales: [4, 2, 7, 3],
                    vessels_dark: [3, 1, 5, 2]
                };
                this.charts['chart-geointel'] = new Chart(ctxGeointel, {
                    type: 'bar',
                    data: {
                        labels: geo.regiones || ["Occidente", "Centro", "Oriente", "Guayana"],
                        datasets: [
                            {
                                label: 'Focos de Calor Satelital (NASA)',
                                data: geo.anomalias_satelitales || [0, 0, 0, 0],
                                backgroundColor: colors.orange,
                                borderColor: colors.orange,
                                borderWidth: 1,
                                borderRadius: 4,
                                barPercentage: 0.7,
                                categoryPercentage: 0.6
                            },
                            {
                                label: 'Buques en Modo Dark (AIS Off)',
                                data: geo.vessels_dark || [0, 0, 0, 0],
                                backgroundColor: colors.primary,
                                borderColor: colors.primary,
                                borderWidth: 1,
                                borderRadius: 4,
                                barPercentage: 0.7,
                                categoryPercentage: 0.6
                            }
                        ]
                    },
                    options: Object.assign({}, globalOptions, {
                        scales: {
                            x: {
                                grid: { display: false },
                                ticks: { color: '#f0f0f0', font: { family: 'Roboto Mono', size: 10 } }
                            },
                            y: {
                                grid: { color: colors.gridLines },
                                ticks: { color: colors.text, font: { family: 'Roboto Mono' }, stepSize: 1 }
                            }
                        }
                    })
                });
            }
        } catch (e) {
            console.error("[ERROR] CobaltoAnalytics: Falló inicialización de chart-geointel:", e);
        }
    },

    destroyChart: function(id) {
        if (this.charts[id]) {
            this.charts[id].destroy();
            delete this.charts[id];
        }
    },

    exportChart: function(chartId, filename) {
        const chart = this.charts[chartId];
        if (chart) {
            const url = chart.toBase64Image();
            const a = document.createElement('a');
            a.href = url;
            a.download = filename + '_' + new Date().toISOString().slice(0,10) + '.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    },


    // ==========================================
    // 🖨️ GENERACIÓN DE SITREP EJECUTIVO (PDF/TXT)
    // ==========================================
    
    generateSITREP: function() {
        const bluf = document.getElementById('analytics-ai-bluf')?.innerText || 'Sin BLUF disponible.';
        const threatLvl = document.getElementById('kpi-threat-level')?.innerText || 'N/A';
        const actionsNodes = document.getElementById('analytics-action-list')?.querySelectorAll('li');
        const actions = Array.from(actionsNodes || []).map(li => "- " + li.innerText).join('\n');
        
        const timestamp = new Date().toISOString();
        
        const sitrep = `
=====================================================
    MINISTERIO DEL PODER POPULAR PARA LA DEFENSA
    SITREP EJECUTIVO - INTELIGENCIA TÁCTICA Y REDES
=====================================================
FECHA Y HORA (UTC): ${timestamp}
NIVEL DE AMENAZA:   ${threatLvl}
AGENTE ANALISTA:    Cobalto HUB (ARES Protocol)

-----------------------------------------------------
[ 1. SÍNTESIS EJECUTIVA - BLUF ]
-----------------------------------------------------
${bluf}

-----------------------------------------------------
[ 2. PROTOCOLOS OPERACIONALES RECOMENDADOS ]
-----------------------------------------------------
${actions}

-----------------------------------------------------
[ 3. VECTORES DE INFECCIÓN Y DISTRIBUCIÓN ]
-----------------------------------------------------
> Revise los gráficos en el panel de control del COBALTO HUB para un desglose geolocalizado de las amenazas y los nodos CIB.

[FIN DEL REPORTE]
=====================================================
        `;
        
        // Descargar como archivo de texto plano
        const blob = new Blob([sitrep.trim()], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `SITREP_COBALTO_${timestamp.slice(0,10)}.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        console.log("[SITREP] Reporte exportado exitosamente.");
    },

    // ==========================================
    // 🛡️ CONSOLA DE AUDITORÍA FORENSE & DRILL-DOWN
    // ==========================================


    handleForensicDrilldown: function(chartType, label) {
        console.log(`[DRILLDOWN] Tipo: ${chartType}, Filtro: ${label}`);
        let filtered = [];

        if (chartType === 'severity') {
            // Label: "CRÍTICO", "ALTA", "MEDIA", "BAJA"
            filtered = this.activeEntries.filter(entry => {
                const sev = String(entry.severity || '').toUpperCase();
                if (label === 'CRÍTICO') return sev.includes('CRIT') || sev.includes('CRTICO');
                if (label === 'ALTA') return sev.includes('ALT');
                if (label === 'MEDIA') return sev.includes('MED');
                if (label === 'BAJA') return sev.includes('BAJ');
                return false;
            });
        } else if (chartType === 'threats') {
            // Label: Categorías de amenazas
            filtered = this.activeEntries.filter(entry => {
                const source = String(entry.source || '').toLowerCase();
                const stype = String(entry.summary || '').toLowerCase() + " " + String(entry.title || '').toLowerCase();
                if (label === 'Resiliencia de Red') return source.includes('resiliencia') || stype.includes('apag') || stype.includes('fall');
                if (label === 'Anomalías SIGINT') return source.includes('sigint') || source.includes('vuelo') || source.includes('vessel');
                if (label === 'Detector de Botnets') return source.includes('botnet') || stype.includes('astroturfing') || stype.includes('bot');
                if (label === 'Monitoreo Satelital') return source.includes('satelital') || source.includes('firms') || stype.includes('calor') || stype.includes('incendio');
                if (label === 'Guerra Económica (FININT)') return source.includes('finint') || source.includes('divisa') || source.includes('bcv');
                if (label === 'Ciberseguridad (VenCERT/Cyber)') return ["vencert", "cyber", "ransomware", "pastebin"].some(kw => source.includes(kw));
                return false;
            });
        } else if (chartType === 'darkweb') {
            // Label: Finanzas, Energía, Telecom, Gubernamental, Industrial
            filtered = this.activeEntries.filter(entry => {
                const source = String(entry.source || '').toLowerCase();
                const text = (String(entry.title || '') + " " + String(entry.summary || '')).toLowerCase();
                const isDark = ["onion", "ransomware", "leak"].some(kw => source.includes(kw) || text.includes(kw));
                if (!isDark) return false;
                if (label === 'Finanzas') return text.includes('banc') || text.includes('finan');
                if (label === 'Energía') return ["elect", "energ", "petrol", "pdvsa"].some(kw => text.includes(kw));
                if (label === 'Telecom') return ["cantv", "telecom", "inter"].some(kw => text.includes(kw));
                if (label === 'Gubernamental') return ["gob", "patria", "ministerio"].some(kw => text.includes(kw));
                if (label === 'Industrial') return !["banc", "finan", "elect", "energ", "petrol", "pdvsa", "cantv", "telecom", "inter", "gob", "patria", "ministerio"].some(kw => text.includes(kw));
                return false;
            });
        }

        this.showForensicModal(`${chartType.toUpperCase()} - ${label}`, filtered);
    },

    showForensicModal: function(title, entries) {
        let modal = document.getElementById('forensic-audit-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'forensic-audit-modal';
            modal.style.position = 'fixed';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.width = '100vw';
            modal.style.height = '100vh';
            modal.style.backgroundColor = 'rgba(5, 6, 10, 0.85)';
            modal.style.backdropFilter = 'blur(12px)';
            modal.style.zIndex = '999999';
            modal.style.display = 'flex';
            modal.style.alignItems = 'center';
            modal.style.justifyContent = 'center';
            modal.style.opacity = '0';
            modal.style.transition = 'opacity 0.3s ease';
            document.body.appendChild(modal);
        }

        // Generar contenido interno interactivo premium
        modal.innerHTML = `
            <div style="width:90%; max-width:750px; height:80%; max-height:600px; background:#0d0e15; border:1px solid rgba(0,229,255,0.25); border-radius:12px; box-shadow:0 0 30px rgba(0,229,255,0.15); display:flex; flex-direction:column; overflow:hidden; font-family:'Inter', sans-serif; box-sizing:border-box;">
                <!-- Header -->
                <div style="padding:1.2rem; background:rgba(0,229,255,0.04); border-bottom:1px solid rgba(0,229,255,0.15); display:flex; justify-content:space-between; align-items:center; box-sizing:border-box;">
                    <div style="display:flex; align-items:center; gap:0.6rem;">
                        <span style="font-size:1.2rem;">🔎</span>
                        <div>
                            <h2 style="color:#00e5ff; font-family:'Roboto Mono',monospace; font-size:1rem; margin:0; font-weight:normal; letter-spacing:1px; text-transform:uppercase;">Auditoría Forense e Integridad</h2>
                            <p style="margin:0; font-size:0.7rem; color:#8E8E93;">Procedencia y trazabilidad de datos para: <strong style="color:#fff;">${title}</strong></p>
                        </div>
                    </div>
                    <button onclick="document.getElementById('forensic-audit-modal').style.opacity='0'; setTimeout(()=> { document.getElementById('forensic-audit-modal').style.display='none'; }, 300)" style="background:transparent; border:none; color:#ff4444; font-size:1.5rem; cursor:pointer; font-family:'Roboto Mono',monospace; transition:color 0.2s;" onmouseover="this.style.color='#ff8888'" onmouseout="this.style.color='#ff4444'">×</button>
                </div>
                <!-- Body -->
                <div style="flex:1; overflow-y:auto; padding:1.5rem; display:flex; flex-direction:column; gap:1.2rem; background:#0a0b10; box-sizing:border-box;">
                    ${entries.length === 0 ? `
                        <div style="text-align:center; padding:3rem; color:#8E8E93; font-family:'Roboto Mono',monospace; font-size:0.85rem;">
                            ⚠️ NO HAY REGISTROS QUE COINCIDAN EN ESTE SEGMENTO TEMPORAL
                        </div>
                    ` : entries.map((entry, index) => {
                        const hashBase = entry.title + entry.timestamp;
                        let hashVal = 0;
                        for (let i = 0; i < hashBase.length; i++) {
                            hashVal = (hashVal << 5) - hashVal + hashBase.charCodeAt(i);
                            hashVal |= 0;
                        }
                        const forensicId = Math.abs(hashVal).toString(16).toUpperCase().padStart(8, '0');
                        
                        let statusColor = "#00ffaa";
                        let statusText = "VERIFICADO";
                        if (entry.severity === "CRÍTICO" || entry.severity === "ALTA") {
                            statusColor = "#ffaa00";
                            statusText = "ALERTA SOC";
                        }
                        return `
                            <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:8px; padding:1rem; display:flex; flex-direction:column; gap:0.6rem; transition:border-color 0.2s; box-sizing:border-box;" onmouseover="this.style.borderColor='rgba(0,229,255,0.2)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.05)'">
                                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; font-family:'Roboto Mono',monospace; font-size:0.75rem;">
                                    <span style="color:#00e5ff; background:rgba(0,229,255,0.08); padding:2px 8px; border-radius:4px; border:1px solid rgba(0,229,255,0.15);">🆔 HASH FORENSE: ${forensicId}</span>
                                    <span style="color:${statusColor}; background:rgba(${statusColor === '#00ffaa' ? '0,255,170' : '255,170,0'}, 0.08); padding:2px 8px; border-radius:4px; border:1px solid ${statusColor}44;">🛡️ ${statusText}</span>
                                </div>
                                <h3 style="margin:0; font-size:0.9rem; color:#fff; font-weight:normal; line-height:1.4;">${entry.title}</h3>
                                <p style="margin:0; font-size:0.8rem; color:#8E8E93; line-height:1.4;">${entry.summary || 'Sin resumen disponible.'}</p>
                                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-top:0.4rem; padding-top:0.4rem; border-top:1px solid rgba(255,255,255,0.03); font-family:'Roboto Mono',monospace; font-size:0.7rem; color:#8E8E93;">
                                    <span>🛰️ ORIGEN: <strong style="color:#f0f0f0;">${entry.source || 'Intel Hub'}</strong></span>
                                    <span>⏱️ TIEMPO: <strong style="color:#f0f0f0;">${new Date(entry.timestamp).toLocaleString()}</strong></span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
                <!-- Footer -->
                <div style="padding:0.8rem 1.2rem; background:rgba(255,255,255,0.02); border-top:1px solid rgba(255,255,255,0.04); display:flex; justify-content:space-between; align-items:center; font-family:'Roboto Mono',monospace; font-size:0.7rem; color:#8E8E93; box-sizing:border-box;">
                    <span>🛡️ CONSOLA DE AUDITORÍA FORENSE v9.2</span>
                    <span>TOTAL: ${entries.length} REGISTROS</span>
                </div>
            </div>
        `;

        modal.style.display = 'flex';
        // Forzar reflow
        modal.offsetHeight;
        modal.style.opacity = '1';
    }
};

// Auto-inicializar si la pestaña de analíticas ya está activa al cargar el script o si hay una inicialización pendiente
if ((document.getElementById('tab-analytics') && document.getElementById('tab-analytics').classList.contains('active')) || window._pendingAnalyticsInit) {
    window._pendingAnalyticsInit = false;
    window.CobaltoAnalytics.init();
}
