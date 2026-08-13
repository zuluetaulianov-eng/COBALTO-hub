/**
 * Cobalto Hub — Módulo de Análisis de Sentimientos (CobaltaSentiment)
 * Pipeline: Fuentes Públicas → Extracción → Preprocesamiento → NLP → Visualización/Alertas
 */

window.CobaltaSentiment = {
    charts: {},
    isLoaded: false,
    data: null,
    historyData: [],

    init: function () {
        if (!this.isLoaded) {
            this.isLoaded = true;
            this.loadHistory();
            this.refresh();
        } else {
            this.refresh(true); // background refresh
        }
    },

    refresh: function (isBackground = false) {
        if (!isBackground) {
            this.showSkeleton();
        }
        this.animatePipeline();
        fetch('/api/sentiment')
            .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
            .then(data => {
                this.data = data;
                this.render(data);
            })
            .catch(err => {
                console.error('[SENTIMENT] Error:', err);
                this.showError();
            });
    },

    // D1: Cargar historial de 7 días
    loadHistory: function () {
        fetch('/api/sentiment/history?hours=168&bucket=2')
            .then(r => r.ok ? r.json() : [])
            .then(data => {
                this.historyData = data || [];
                this.renderHistoryChart(this.historyData);
                this.renderNarrativaTimeline(this.historyData);
            })
            .catch(err => console.warn('[SENTIMENT-HIST] Error:', err));

        // También cargar stats
        fetch('/api/sentiment/stats?hours=24')
            .then(r => r.ok ? r.json() : {})
            .then(stats => this.renderStats(stats))
            .catch(() => {});
    },

    // ── Pipeline animation ──────────────────────────────────────────────────
    animatePipeline: function () {
        const steps = document.querySelectorAll('.sent-pipe-step');
        if (!steps.length) return;
        steps.forEach(s => s.classList.remove('active'));
        let i = 0;
        const interval = setInterval(() => {
            if (i > 0) steps[i - 1].classList.remove('active');
            if (i < steps.length) {
                steps[i].classList.add('active');
                i++;
            } else {
                clearInterval(interval);
            }
        }, 350);
    },

    showSkeleton: function () {
        const ids = ['sent-score-global', 'sent-total', 'sent-bot-rate', 'sent-crisis-count'];
        ids.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '…'; });
        const emptyEl = document.getElementById('sent-empty');
        if (emptyEl) emptyEl.style.display = 'none';
    },

    showError: function () {
        const emptyEl = document.getElementById('sent-empty');
        if (emptyEl) { emptyEl.style.display = 'block'; emptyEl.querySelector('p').textContent = 'Error al conectar con el motor NLP.'; }
    },

    // ── Render Principal ────────────────────────────────────────────────────
    render: function (d) {
        if (!d) return;

        // KPIs
        this._setText('sent-score-global', (d.score_global >= 0 ? '+' : '') + d.score_global.toFixed(2));
        this._setText('sent-nivel-alerta', d.nivel_alerta);
        this._setText('sent-total', d.total_analizadas.toLocaleString());
        this._setText('sent-bot-rate', d.bot_rate + '%');
        this._setText('sent-bot-count', d.bots_detectados + ' posibles bots');
        this._setText('sent-crisis-count', (d.alertas_criticas + d.alertas_atencion));

        // Color del KPI global según nivel
        const kpiScore = document.getElementById('sent-score-global');
        if (kpiScore) kpiScore.style.color = d.color_alerta;
        const nivelEl = document.getElementById('sent-nivel-alerta');
        if (nivelEl) { nivelEl.style.color = d.color_alerta; nivelEl.style.fontWeight = 'bold'; }

        // Render Cobalto PsyOps
        if (d.informe_cobalto) {
            let psy = typeof d.informe_cobalto === 'string' ? { 
                operacion_influencia: d.informe_cobalto, vector_manipulacion: "-", contramedida: "-", nivel_amenaza: "DESCONOCIDO"
            } : d.informe_cobalto;
            
            const infEl = document.getElementById('psyops-influencia');
            const vecEl = document.getElementById('psyops-vector');
            const contraEl = document.getElementById('psyops-contramedida');
            const badgeEl = document.getElementById('psyops-threat-badge');

            if (infEl) infEl.textContent = psy.operacion_influencia || 'Sin detectar';
            if (vecEl) vecEl.textContent = psy.vector_manipulacion || 'Sin detectar';
            if (contraEl) contraEl.textContent = psy.contramedida || 'Sin medidas aplicables';
            if (badgeEl) {
                const threat = (psy.nivel_amenaza || 'DESCONOCIDO').toUpperCase();
                badgeEl.textContent = 'AMENAZA: ' + threat;
                badgeEl.style.color = '#fff';
                
                if (threat.includes('VERDE')) { badgeEl.style.backgroundColor = 'rgba(0, 255, 170, 0.2)'; badgeEl.style.color = '#00ffaa'; badgeEl.style.borderColor = 'rgba(0,255,170,0.5)'; }
                else if (threat.includes('AMARILLO')) { badgeEl.style.backgroundColor = 'rgba(255, 204, 0, 0.2)'; badgeEl.style.color = '#ffcc00'; badgeEl.style.borderColor = 'rgba(255,204,0,0.5)'; }
                else if (threat.includes('NARANJA')) { badgeEl.style.backgroundColor = 'rgba(255, 136, 0, 0.2)'; badgeEl.style.color = '#ff8800'; badgeEl.style.borderColor = 'rgba(255,136,0,0.5)'; }
                else if (threat.includes('ROJO')) { badgeEl.style.backgroundColor = 'rgba(255, 68, 68, 0.2)'; badgeEl.style.color = '#ff4444'; badgeEl.style.borderColor = 'rgba(255,68,68,0.5)'; }
                else { badgeEl.style.backgroundColor = 'rgba(100,100,100,0.2)'; badgeEl.style.color = '#ccc'; badgeEl.style.borderColor = 'rgba(100,100,100,0.5)'; }
            }
        }

        // C2: Gauge animado
        this.renderGauge(d.score_global, d.color_alerta);

        // Porcentajes distribución
        const total = Math.max(1, d.distribucion.positivo + d.distribucion.neutro + d.distribucion.negativo);
        this._setText('sent-pct-pos', Math.round(d.distribucion.positivo / total * 100));
        this._setText('sent-pct-neu', Math.round(d.distribucion.neutro / total * 100));
        this._setText('sent-pct-neg', Math.round(d.distribucion.negativo / total * 100));

        // Gráficos
        this.renderDistChart(d.distribucion);
        this.renderEmocionesChart(d.emociones);
        this.renderTemporalChart(d.serie_temporal);

        // Secciones textuales
        this.renderWords(d.top_palabras_pos, 'sent-words-pos', true);
        this.renderWords(d.top_palabras_neg, 'sent-words-neg', false);
        this.renderWordCloud(d.top_palabras_pos, d.top_palabras_neg);
        this.renderNarrativas(d.narrativas_geo);
        this.renderCrisis(d.crisis_muestra);
        this.renderBots(d.bots_muestra, d.bot_rate);
        this.renderFuentes(d.por_fuente);

        // B2+E1+E2: módulos avanzados
        if (d.cib) this.renderCIB(d.cib);
        if (d.sesgo_fuentes && d.sesgo_fuentes.length) this.renderSesgoFuentes(d.sesgo_fuentes);
        if (d.overton_emergentes && d.overton_emergentes.length) this.renderOverton(d.overton_emergentes);

        // E5: preparar entradas ambiguas para análisis LLM
        if (d.entradas_muestra) this._prepararLLM(d.entradas_muestra);
    },

    // ── Gráfico: Distribución Sentimientos (Doughnut) ───────────────────────
    renderDistChart: function (dist) {
        const ctx = document.getElementById('chart-sent-dist');
        if (!ctx) return;
        if (this.charts.dist) { this.charts.dist.destroy(); }
        this.charts.dist = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Positivo', 'Neutro', 'Negativo'],
                datasets: [{
                    data: [dist.positivo, dist.neutro, dist.negativo],
                    backgroundColor: ['rgba(0,255,170,0.8)', 'rgba(68,170,238,0.7)', 'rgba(255,45,85,0.8)'],
                    borderColor: '#0a0b10',
                    borderWidth: 3,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#b0b8c8', font: { family: 'Roboto Mono', size: 10 }, padding: 12 } },
                    tooltip: { backgroundColor: 'rgba(10,11,16,0.95)', titleColor: '#00e5ff', bodyFont: { family: 'Inter' } }
                }
            }
        });
    },

    // ── Gráfico: Mapa Emocional (Polar Area) ───────────────────────────────
    renderEmocionesChart: function (em) {
        const ctx = document.getElementById('chart-sent-emociones');
        if (!ctx) return;
        if (this.charts.emociones) { this.charts.emociones.destroy(); }
        this.charts.emociones = new Chart(ctx, {
            type: 'polarArea',
            data: {
                labels: ['Ira 🔥', 'Miedo 😨', 'Esperanza 🌱', 'Neutro ⚪'],
                datasets: [{
                    data: [em.ira, em.miedo, em.esperanza, em.neutro],
                    backgroundColor: [
                        'rgba(255,45,85,0.7)',
                        'rgba(175,82,222,0.7)',
                        'rgba(0,255,170,0.7)',
                        'rgba(100,110,130,0.5)'
                    ],
                    borderColor: '#0a0b10',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { color: '#b0b8c8', font: { family: 'Roboto Mono', size: 10 }, padding: 10 } },
                    tooltip: { backgroundColor: 'rgba(10,11,16,0.95)', titleColor: '#00e5ff', bodyFont: { family: 'Inter' } }
                },
                scales: { r: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { display: false } } }
            }
        });
    },

    // ── Gráfico: Serie Temporal (Line) ──────────────────────────────────────
    renderTemporalChart: function (serie) {
        const ctx = document.getElementById('chart-sent-temporal');
        if (!ctx || !serie || !serie.length) return;
        if (this.charts.temporal) { this.charts.temporal.destroy(); }
        const labels = serie.map(s => s.hora);
        const canvas = ctx.getContext('2d');
        const gradPos = canvas.createLinearGradient(0, 0, 0, 180);
        gradPos.addColorStop(0, 'rgba(0,255,170,0.35)');
        gradPos.addColorStop(1, 'rgba(0,255,170,0.0)');
        const gradNeg = canvas.createLinearGradient(0, 0, 0, 180);
        gradNeg.addColorStop(0, 'rgba(255,45,85,0.35)');
        gradNeg.addColorStop(1, 'rgba(255,45,85,0.0)');
        this.charts.temporal = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Positivo', data: serie.map(s => s.positivo),
                        borderColor: '#00ffaa', backgroundColor: gradPos,
                        tension: 0.4, fill: true, borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#00ffaa'
                    },
                    {
                        label: 'Negativo', data: serie.map(s => s.negativo),
                        borderColor: '#FF2D55', backgroundColor: gradNeg,
                        tension: 0.4, fill: true, borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#FF2D55'
                    },
                    {
                        label: 'Score Promedio', data: serie.map(s => s.score_promedio),
                        borderColor: '#44aaee', backgroundColor: 'transparent',
                        tension: 0.4, fill: false, borderWidth: 2, borderDash: [4, 4],
                        pointRadius: 0, yAxisID: 'y2'
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#b0b8c8', font: { family: 'Roboto Mono', size: 10 } } },
                    tooltip: { backgroundColor: 'rgba(10,11,16,0.95)', titleColor: '#00e5ff', bodyFont: { family: 'Inter' } }
                },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280', font: { family: 'Roboto Mono', size: 9 } } },
                    y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280', font: { family: 'Roboto Mono', size: 9 } } },
                    y2: { position: 'right', min: -1, max: 1, grid: { display: false }, ticks: { color: '#44aaee', font: { family: 'Roboto Mono', size: 9 } } }
                }
            }
        });
    },

    // ── Palabras Clave (chips) ──────────────────────────────────────────────
    renderWords: function (words, containerId, isPos) {
        const el = document.getElementById(containerId);
        if (!el || !words || !words.length) { if (el) el.innerHTML = '<span style="color:var(--text-muted);font-size:0.75rem;">Sin datos suficientes</span>'; return; }
        const maxCount = Math.max(1, words[0].count);
        el.innerHTML = words.map(w => {
            const intensity = Math.max(0.3, w.count / maxCount);
            const color = isPos ? `rgba(0,255,170,${intensity})` : `rgba(255,45,85,${intensity})`;
            const borderColor = isPos ? `rgba(0,255,170,${intensity * 0.6})` : `rgba(255,45,85,${intensity * 0.6})`;
            const size = Math.round(10 + (w.count / maxCount) * 6);
            return `<span class="sent-word-chip" style="color:${color};border-color:${borderColor};font-size:${size}px;" title="${w.count} menciones">${w.word} <sup style="opacity:0.6;">${w.count}</sup></span>`;
        }).join('');
    },

    // ── Narrativas Geopolíticas ─────────────────────────────────────────────
    renderNarrativas: function (narrativas) {
        const el = document.getElementById('sent-narrativas');
        if (!el) return;
        if (!narrativas || !narrativas.length) {
            el.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem;">Sin narrativas detectadas.</p>';
            return;
        }
        el.innerHTML = narrativas.map(n => {
            const barWidth = Math.min(100, n.menciones * 5);
            const scoreStr = (n.score_promedio >= 0 ? '+' : '') + n.score_promedio.toFixed(2);
            return `<div style="padding:0.7rem;background:rgba(255,255,255,0.02);border-radius:8px;border-left:3px solid ${n.color};">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">
                    <span style="color:#fff;font-size:0.82rem;font-family:'Roboto Mono',monospace;">${n.nombre}</span>
                    <span style="color:${n.color};font-size:0.75rem;font-family:'Roboto Mono',monospace;">${scoreStr} · ${n.menciones} menciones</span>
                </div>
                <div class="sent-bar-mini"><div class="sent-bar-fill" style="width:${barWidth}%;background:${n.color};"></div></div>
                ${n.polarizacion_negativa > 50 ? `<div style="font-size:0.65rem;color:#FF9500;margin-top:0.3rem;">⚠ ${n.polarizacion_negativa}% de cobertura negativa</div>` : ''}
                <div style="font-size:0.68rem;color:var(--text-muted);margin-top:0.2rem;font-style:italic;">${n.muestra}</div>
            </div>`;
        }).join('');
    },

    // ── Early Warning Crisis ────────────────────────────────────────────────
    renderCrisis: function (lista) {
        const el = document.getElementById('sent-crisis-list');
        if (!el) return;
        if (!lista || !lista.length) {
            el.innerHTML = '<div style="text-align:center;padding:1.5rem;color:#00ffaa;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">✅ SIN ALERTAS ACTIVAS</div>';
            return;
        }
        const colorMap = { 'CRÍTICO': '#FF2D55', 'ALERTA': '#FF9500', 'ATENCIÓN': '#FFD700' };
        el.innerHTML = lista.map(c => {
            const color = colorMap[c.nivel] || '#44aaee';
            return `<div class="sent-crisis-card" style="border-color:${color};background:rgba(${color === '#FF2D55' ? '255,45,85' : color === '#FF9500' ? '255,149,0' : '255,215,0'},0.04);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">
                    <span style="color:${color};font-size:0.7rem;font-family:'Roboto Mono',monospace;font-weight:bold;">${c.nivel}</span>
                    <span style="color:var(--text-muted);font-size:0.65rem;">${c.source}</span>
                </div>
                <div style="color:#fff;font-size:0.78rem;margin-bottom:0.3rem;">${c.title}</div>
                <div style="color:var(--text-muted);font-size:0.68rem;">${c.descripcion}</div>
            </div>`;
        }).join('');
    },

    // ── Detección de Bots ────────────────────────────────────────────────────
    renderBots: function (lista, rate) {
        const badge = document.getElementById('sent-bot-badge');
        if (badge) {
            if (rate > 30) badge.textContent = '🚨 TORMENTA DE BOTS DETECTADA';
            else if (rate > 15) badge.textContent = `⚠ ${rate}% actividad sospechosa`;
            else badge.textContent = `✅ ${rate}% — Bajo riesgo`;
        }
        const el = document.getElementById('sent-bot-list');
        if (!el) return;
        if (!lista || !lista.length) {
            el.innerHTML = '<div style="padding:1.5rem;text-align:center;color:#00ffaa;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;">✅ SIN SEÑALES DE BOTS DETECTADAS</div>';
            return;
        }
        el.innerHTML = lista.map(b => {
            const intensity = Math.min(100, b.score_bot);
            const barColor = intensity > 60 ? '#FF2D55' : intensity > 35 ? '#FF9500' : '#FFD700';
            return `<div class="sent-bot-card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                    <span style="color:#FF2D55;font-size:0.65rem;font-family:'Roboto Mono',monospace;font-weight:bold;">🤖 SCORE: ${b.score_bot}%</span>
                    <span style="color:var(--text-muted);font-size:0.65rem;">${b.source}</span>
                </div>
                <div style="color:#f0f0f0;font-size:0.78rem;margin-bottom:0.5rem;">${b.title}</div>
                <div style="font-size:0.65rem;color:#FF9500;margin-bottom:0.4rem;">${(b.signals || []).join(' · ')}</div>
                <div class="sent-bar-mini"><div class="sent-bar-fill" style="width:${intensity}%;background:${barColor};"></div></div>
            </div>`;
        }).join('');
    },

    // ── Tabla Fuentes ────────────────────────────────────────────────────────
    renderFuentes: function (fuentes) {
        const tbody = document.getElementById('sent-tbody-fuentes');
        if (!tbody || !fuentes || !fuentes.length) return;
        tbody.innerHTML = fuentes.map(f => {
            const score = f.score_promedio;
            const color = score >= 0.15 ? '#00ffaa' : score <= -0.15 ? '#FF2D55' : '#44aaee';
            const barWidth = Math.min(100, Math.abs(score) * 100);
            const barLeft = score < 0 ? `${50 - barWidth / 2}%` : '50%';
            const barW = barWidth / 2;
            const scoreStr = (score >= 0 ? '+' : '') + score.toFixed(2);
            return `<tr>
                <td style="color:#f0f0f0;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${f.fuente}</td>
                <td style="text-align:center;color:var(--text-muted);">${f.total}</td>
                <td style="text-align:center;color:${color};font-weight:bold;">${scoreStr}</td>
                <td style="text-align:center;color:#00ffaa;">${f.positivo}</td>
                <td style="text-align:center;color:#FF2D55;">${f.negativo}</td>
                <td style="text-align:center;color:${f.bots_detectados > 0 ? '#FF9500' : 'var(--text-muted)'};">${f.bots_detectados > 0 ? '🤖 ' + f.bots_detectados : '—'}</td>
                <td style="min-width:120px;">
                    <div style="position:relative;height:6px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden;">
                        <div style="position:absolute;left:50%;height:100%;width:1px;background:rgba(255,255,255,0.1);"></div>
                        <div style="position:absolute;left:${score >= 0 ? '50%' : (50 - barW) + '%'};width:${barW}%;height:100%;background:${color};border-radius:3px;transition:width 0.6s ease;"></div>
                    </div>
                </td>
            </tr>`;
        }).join('');
    },

    _setText: function (id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    },

    // C3: Word Cloud dinámico usando canvas
    renderWordCloud: function (posWords, negWords) {
        const el = document.getElementById('sent-wordcloud');
        if (!el) return;
        const all = [
            ...(posWords || []).map(w => ({ ...w, type: 'pos' })),
            ...(negWords || []).map(w => ({ ...w, type: 'neg' })),
        ].sort(() => Math.random() - 0.5);
        if (!all.length) { el.innerHTML = '<span style="color:var(--text-muted);font-size:0.8rem;">Sin datos</span>'; return; }
        const maxCount = Math.max(1, ...all.map(w => w.count));
        el.innerHTML = all.map(w => {
            const size = Math.round(10 + (w.count / maxCount) * 22);
            const opacity = 0.5 + (w.count / maxCount) * 0.5;
            const color = w.type === 'pos'
                ? `rgba(0,255,170,${opacity})`
                : `rgba(255,45,85,${opacity})`;
            const rotate = (Math.random() > 0.7) ? 'rotate(-15deg)' : 'none';
            return `<span style="
                font-size:${size}px;
                color:${color};
                font-family:'Roboto Mono',monospace;
                font-weight:bold;
                display:inline-block;
                margin:4px 6px;
                transform:${rotate};
                transition:all 0.3s;
                cursor:default;
                text-shadow:0 0 ${Math.round(size/3)}px ${color};
            " title="${w.count} menciones">${w.word}</span>`;
        }).join('');
    },

    // B2: Panel CIB (Coordinated Inauthentic Behavior)
    renderCIB: function (cib) {
        const el = document.getElementById('sent-cib-panel');
        if (!el) return;
        if (!cib.disponible) {
            el.innerHTML = '<div style="color:var(--text-muted);font-size:0.75rem;text-align:center;padding:1rem;">Módulo ML no disponible</div>';
            return;
        }
        if (!cib.alerta_cib) {
            el.innerHTML = '<div style="color:#00ffaa;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;text-align:center;padding:1rem;">\u2705 SIN EVIDENCIA DE COORDINACIÓN</div>';
            return;
        }
        const nivelColor = { 'CRÍTICO': '#FF2D55', 'ALERTA': '#FF9500', 'NORMAL': '#00ffaa' }[cib.nivel] || '#FFD700';
        el.innerHTML = `
            <div style="padding:0.6rem;background:rgba(255,45,85,0.06);border-radius:6px;border-left:3px solid ${nivelColor};margin-bottom:1rem;">
                <div style="color:${nivelColor};font-family:'Roboto Mono',monospace;font-size:0.75rem;font-weight:bold;">🚨 ${cib.nivel} — ${cib.mensaje}</div>
                <div style="color:var(--text-muted);font-size:0.65rem;margin-top:0.3rem;">${cib.total_sospechosas} entradas en ${cib.clusters.length} cluster(s) coordinados</div>
            </div>
            ${cib.clusters.slice(0, 4).map(c => `
                <div style="padding:0.6rem;border:1px solid rgba(255,255,255,0.06);border-radius:6px;margin-bottom:0.5rem;">
                    <div style="display:flex;justify-content:space-between;font-family:'Roboto Mono',monospace;font-size:0.68rem;">
                        <span style="color:#FF9500;">🤖 Cluster de ${c.tamaño} entradas · sim. ${(c.similitud_promedio*100).toFixed(0)}%</span>
                        <span style="color:${c.multi_fuente ? '#FF2D55' : '#44aaee'}">${c.multi_fuente ? '⚠ MULTI-FUENTE' : 'Misma fuente'}</span>
                    </div>
                    <div style="font-size:0.65rem;color:var(--text-muted);margin:0.3rem 0;">Fuentes: ${c.fuentes.join(', ')}</div>
                    ${c.narrativa ? `<div style="font-size:0.6rem;color:#FFD700;font-family:'Roboto Mono',monospace;">Firma: ${c.narrativa}</div>` : ''}
                    ${c.muestra.slice(0,2).map(s => `<div style="font-size:0.7rem;color:#c0c8d4;margin-top:0.3rem;border-left:2px solid rgba(255,255,255,0.1);padding-left:0.4rem;">${s.title}</div>`).join('')}
                </div>
            `).join('')}
        `;
    },

    // E1: Tabla de sesgo editorial por fuente
    renderSesgoFuentes: function (sesgoList) {
        const el = document.getElementById('sent-sesgo-fuentes');
        if (!el || !sesgoList.length) return;
        const sesgoColors = { 'PRO-NEGATIVO': '#FF2D55', 'NEUTRAL': '#44aaee', 'PRO-POSITIVO': '#00ffaa' };
        const confColors = { 'ALTA': '#00ffaa', 'MEDIA': '#FFD700', 'BAJA': '#FF2D55' };
        el.innerHTML = `
            <table style="width:100%;border-collapse:collapse;font-size:0.72rem;font-family:'Roboto Mono',monospace;">
                <thead>
                    <tr style="color:var(--text-muted);border-bottom:1px solid rgba(255,255,255,0.08);">
                        <th style="text-align:left;padding:0.4rem;">Fuente</th>
                        <th style="text-align:center;">Score</th>
                        <th style="text-align:center;">Sesgo</th>
                        <th style="text-align:center;">Confiab.</th>
                        <th style="text-align:center;">Bots</th>
                    </tr>
                </thead>
                <tbody>
                    ${sesgoList.map(s => `
                        <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                            <td style="padding:0.3rem;color:#f0f0f0;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${s.fuente}">${s.fuente}</td>
                            <td style="text-align:center;color:${s.score_promedio < -0.15 ? '#FF2D55' : s.score_promedio > 0.15 ? '#00ffaa' : '#44aaee'};font-weight:bold;">${s.score_promedio >= 0 ? '+' : ''}${s.score_promedio.toFixed(2)}</td>
                            <td style="text-align:center;color:${sesgoColors[s.sesgo_editorial] || '#fff'};">${s.sesgo_editorial}</td>
                            <td style="text-align:center;color:${confColors[s.confiabilidad] || '#fff'};">${s.confiabilidad}</td>
                            <td style="text-align:center;color:${s.bots_detectados > 0 ? '#FF9500' : 'var(--text-muted)'}">${s.bots_detectados > 0 ? '🤖' + s.bots_detectados : '—'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    // E2: Panel Ventana de Overton
    renderOverton: function (emergentes) {
        const el = document.getElementById('sent-overton-panel');
        if (!el || !emergentes.length) return;
        const max_ratio = Math.max(...emergentes.map(e => e.ratio_cambio));
        el.innerHTML = emergentes.map(e => {
            const width = Math.min(100, (e.ratio_cambio / max_ratio) * 100);
            const color = e.ratio_cambio > 10 ? '#FF2D55' : e.ratio_cambio > 5 ? '#FF9500' : '#FFD700';
            return `<div style="margin-bottom:0.5rem;">
                <div style="display:flex;justify-content:space-between;font-family:'Roboto Mono',monospace;font-size:0.7rem;margin-bottom:0.15rem;">
                    <span style="color:#f0f0f0;">${e.termino}</span>
                    <span style="color:${color};">+${e.ratio_cambio}x ↑</span>
                </div>
                <div style="height:4px;background:rgba(255,255,255,0.05);border-radius:2px;overflow:hidden;">
                    <div style="width:${width}%;height:100%;background:${color};border-radius:2px;transition:width 0.8s ease;"></div>
                </div>
            </div>`;
        }).join('');
    },

    // C6: Exportar CSV
    exportCSV: function (hours = 24) {
        const a = document.createElement('a');
        a.href = `/api/sentiment/export?hours=${hours}`;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    },

    // E5: Disparar análisis LLM para entradas ambiguas
    _prepararLLM: function (entradas) {
        // Filtrar entradas con score en zona ambigua (-0.1 a +0.1)
        const ambiguas = entradas.filter(e => e.score >= -0.1 && e.score <= 0.1);
        const btn = document.getElementById('sent-btn-llm');
        if (btn) {
            if (ambiguas.length > 0) {
                btn.textContent = `🧠 Analizar ${Math.min(10, ambiguas.length)} entradas con LLM`;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.onclick = () => this.triggerLLM(ambiguas.slice(0, 10));
            } else {
                btn.textContent = '🧠 Sin entradas ambiguas';
                btn.style.opacity = '0.4';
            }
        }
    },

    triggerLLM: async function (entradas) {
        const panel = document.getElementById('sent-llm-result');
        if (panel) panel.innerHTML = '<div style="color:#44aaee;font-size:0.75rem;">\u231b Consultando LLM...</div>';
        try {
            const res = await fetch('/api/sentiment/llm-analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ entries: entradas }),
            });
            const data = await res.json();
            if (!panel) return;
            if (data.error) {
                panel.innerHTML = `<div style="color:#FF2D55;font-size:0.75rem;">❌ ${data.error}</div>`;
                return;
            }
            const resultados = data.resultados || [];
            const etqColors = { 'POSITIVO': '#00ffaa', 'NEGATIVO': '#FF2D55', 'NEUTRO': '#44aaee' };
            panel.innerHTML = `
                <div style="font-size:0.65rem;color:var(--text-muted);margin-bottom:0.5rem;font-family:'Roboto Mono',monospace;">Modelo: ${data.modelo || 'LLM'} · ${resultados.length} clasificaciones</div>
                ${resultados.map(r => `
                    <div style="padding:0.4rem;border-left:2px solid ${etqColors[r.etiqueta]||'#44aaee'};margin-bottom:0.4rem;background:rgba(255,255,255,0.02);border-radius:4px;">
                        <span style="color:${etqColors[r.etiqueta]||'#44aaee'};font-size:0.65rem;font-family:'Roboto Mono',monospace;font-weight:bold;">${r.etiqueta}</span>
                        ${r.razon ? `<div style="font-size:0.68rem;color:var(--text-muted);margin-top:0.2rem;">${r.razon}</div>` : ''}
                    </div>
                `).join('')}
            `;
        } catch (err) {
            if (panel) panel.innerHTML = `<div style="color:#FF2D55;font-size:0.75rem;">❌ Error: ${err.message}</div>`;
        }
    },

    // C2: Gauge animado tipo velocímetro (-1 → +1) usando SVG + canvas arc
    renderGauge: function (score, color) {
        const el = document.getElementById('sent-gauge-canvas');
        if (!el) return;
        const size = el.offsetWidth || 200;
        el.width = size;
        el.height = size * 0.6;
        const ctx = el.getContext('2d');
        const cx = size / 2, cy = size * 0.58;
        const r = size * 0.42;
        ctx.clearRect(0, 0, el.width, el.height);

        // Fondo arco completo
        const startAngle = Math.PI, endAngle = 2 * Math.PI;
        ctx.beginPath();
        ctx.arc(cx, cy, r, startAngle, endAngle);
        ctx.lineWidth = size * 0.08;
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.stroke();

        // Arco de valor (score -1→1 mapeado a 0→PI)
        const clamp = Math.max(-1, Math.min(1, score));
        const sweepAngle = (clamp + 1) / 2 * Math.PI; // 0→PI
        const grad = ctx.createLinearGradient(cx - r, cy, cx + r, cy);
        grad.addColorStop(0, '#FF2D55');
        grad.addColorStop(0.5, '#FFD700');
        grad.addColorStop(1, '#00ffaa');
        ctx.beginPath();
        ctx.arc(cx, cy, r, Math.PI, Math.PI + sweepAngle);
        ctx.lineWidth = size * 0.08;
        ctx.strokeStyle = color;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Aguja
        const needleAngle = Math.PI + sweepAngle;
        const nx = cx + (r * 0.82) * Math.cos(needleAngle);
        const ny = cy + (r * 0.82) * Math.sin(needleAngle);
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(nx, ny);
        ctx.lineWidth = size * 0.025;
        ctx.strokeStyle = '#ffffff';
        ctx.lineCap = 'round';
        ctx.stroke();

        // Centro
        ctx.beginPath();
        ctx.arc(cx, cy, size * 0.035, 0, 2 * Math.PI);
        ctx.fillStyle = '#ffffff';
        ctx.fill();

        // Labels
        ctx.font = `bold ${Math.round(size * 0.07)}px 'Roboto Mono'`;
        ctx.fillStyle = color;
        ctx.textAlign = 'center';
        ctx.fillText((score >= 0 ? '+' : '') + score.toFixed(2), cx, cy - r * 0.35);

        ctx.font = `${Math.round(size * 0.055)}px 'Roboto Mono'`;
        ctx.fillStyle = 'rgba(255,255,255,0.35)';
        ctx.fillText('-1', cx - r * 0.9, cy + size * 0.04);
        ctx.fillText('+1', cx + r * 0.9, cy + size * 0.04);
    },

    // D1: Gráfico histórico de 7 días (score_global + bot_rate)
    renderHistoryChart: function (series) {
        const ctx = document.getElementById('chart-sent-history');
        if (!ctx || !series || !series.length) return;
        if (this.charts.history) { this.charts.history.destroy(); }

        const labels = series.map(s => {
            const d = new Date(s.ts);
            return d.toLocaleDateString('es', { weekday: 'short', hour: '2-digit' }) + 'h';
        });
        const canvasCtx = ctx.getContext('2d');
        const gradScore = canvasCtx.createLinearGradient(0, 0, 0, 200);
        gradScore.addColorStop(0, 'rgba(0,229,255,0.35)');
        gradScore.addColorStop(1, 'rgba(0,229,255,0.0)');

        this.charts.history = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Score Global',
                        data: series.map(s => s.score_global),
                        borderColor: '#00e5ff', backgroundColor: gradScore,
                        tension: 0.4, fill: true, borderWidth: 2,
                        pointRadius: 2, yAxisID: 'y'
                    },
                    {
                        label: 'Tasa Bots (%)',
                        data: series.map(s => s.bot_rate),
                        borderColor: '#FF9500', backgroundColor: 'transparent',
                        tension: 0.3, fill: false, borderWidth: 1.5,
                        borderDash: [5, 3], pointRadius: 0, yAxisID: 'y2'
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#b0b8c8', font: { family: 'Roboto Mono', size: 9 } } },
                    tooltip: {
                        backgroundColor: 'rgba(10,11,16,0.95)', titleColor: '#00e5ff',
                        callbacks: {
                            afterLabel: (item) => {
                                const s = series[item.dataIndex];
                                if (!s) return '';
                                const nivel = s.nivel_alerta || 'NORMAL';
                                const nivelColors = { 'NORMAL': '✅', 'ALERTA': '⚠', 'CRÍTICO': '🚨', 'BOT-STORM': '🤖' };
                                return `${nivelColors[nivel] || '•'} ${nivel}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#555', font: { family: 'Roboto Mono', size: 8 }, maxRotation: 45 } },
                    y: { min: -1, max: 1, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#00e5ff', font: { family: 'Roboto Mono', size: 9 } } },
                    y2: { position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { color: '#FF9500', font: { family: 'Roboto Mono', size: 9 }, callback: v => v + '%' } }
                }
            }
        });
    },

    // C4: Timeline de narrativas como barras apiladas horizontales por ciclo
    renderNarrativaTimeline: function (series) {
        const ctx = document.getElementById('chart-sent-narrativa-timeline');
        if (!ctx || !series || !series.length) return;
        if (this.charts.narrativaTL) { this.charts.narrativaTL.destroy(); }

        const labels = series.slice(-24).map(s => {
            const d = new Date(s.ts);
            return d.getHours() + 'h';
        });
        const slice = series.slice(-24);

        this.charts.narrativaTL = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: '+ Positivo',
                        data: slice.map(s => s.dist_positivo || 0),
                        backgroundColor: 'rgba(0,255,170,0.7)', borderWidth: 0
                    },
                    {
                        label: '◐ Neutro',
                        data: slice.map(s => s.dist_neutro || 0),
                        backgroundColor: 'rgba(68,170,238,0.5)', borderWidth: 0
                    },
                    {
                        label: '- Negativo',
                        data: slice.map(s => s.dist_negativo || 0),
                        backgroundColor: 'rgba(255,45,85,0.7)', borderWidth: 0
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#b0b8c8', font: { family: 'Roboto Mono', size: 9 }, padding: 8 } },
                    tooltip: { backgroundColor: 'rgba(10,11,16,0.95)', titleColor: '#00e5ff' }
                },
                scales: {
                    x: { stacked: true, grid: { display: false }, ticks: { color: '#555', font: { family: 'Roboto Mono', size: 8 } } },
                    y: { stacked: true, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#6b7280', font: { family: 'Roboto Mono', size: 8 } } }
                }
            }
        });
    },

    // D1: Render de estadísticas de período (24h summary)
    renderStats: function (stats) {
        if (!stats || stats.sin_datos) return;
        this._setText('sent-hist-ciclos', stats.ciclos || 0);
        this._setText('sent-hist-score-min', stats.score_min !== undefined ? stats.score_min.toFixed(2) : '—');
        this._setText('sent-hist-score-max', stats.score_max !== undefined ? stats.score_max.toFixed(2) : '—');
        this._setText('sent-hist-bot-max', stats.bot_rate_max !== undefined ? stats.bot_rate_max + '%' : '—');
        this._setText('sent-hist-nivel-pico', stats.nivel_pico || '—');
        const nivelEl = document.getElementById('sent-hist-nivel-pico');
        if (nivelEl && stats.nivel_pico) {
            const colors = { 'CRÍTICO': '#FF2D55', 'BOT-STORM': '#FF9500', 'ALERTA': '#FFD700', 'NORMAL': '#00ffaa' };
            nivelEl.style.color = colors[stats.nivel_pico] || '#44aaee';
        }
    }
};

// Auto-resolución de bandera pendiente: si switchTab() fue llamado antes
// de que este script defer cargara, lo inicializamos ahora.
(function() {
    var tab = document.getElementById('tab-sentiment');
    if (window._pendingSentimentInit || (tab && tab.classList.contains('active'))) {
        window._pendingSentimentInit = false;
        window.CobaltaSentiment.init();
    }
})();
