/**
 * COBALTO HUB - MESA DE TRABAJO & DOSSIER DE INTELIGENCIA
 * Permite seleccionar noticias en SitRep/Noticias/Redes, curar la lista y procesarla con IA.
 */
window.IntelDossier = {
    STORAGE_KEY: 'cobalto_intel_dossier',
    items: [],

    init: function() {
        this.load();
        this.updateBadges();
        this.renderDossierList();
    },

    load: function() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEY);
            this.items = raw ? JSON.parse(raw) : [];
        } catch (e) {
            console.error('Error cargando dossier:', e);
            this.items = [];
        }
    },

    save: function() {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.items));
        } catch (e) {
            console.error('Error guardando dossier:', e);
        }
    },

    getItems: function() {
        return this.items || [];
    },

    has: function(idOrLink) {
        if (!idOrLink) return false;
        return this.items.some(it => it.id === idOrLink || it.link === idOrLink || it.title === idOrLink);
    },

    add: function(item) {
        if (!item || !item.title) return;
        const key = item.link || item.id || item.title;
        if (this.has(key)) {
            if (window.CobaltoConfig && window.CobaltoConfig.showToast) {
                window.CobaltoConfig.showToast('⚠️ Esta noticia ya está en tu dossier.', 'warning');
            }
            return;
        }
        const dossierItem = {
            id: key,
            title: item.title,
            summary: item.summary || '',
            source: item.source || 'Prensa / Redes',
            date: item.date || item.published || new Date().toISOString(),
            link: item.link || '#',
            severity: item.severity || 'info'
        };
        this.items.push(dossierItem);
        this.save();
        this.updateBadges();
        this.renderDossierList();
        this.updateCardButtons();

        if (window.CobaltoConfig && window.CobaltoConfig.showToast) {
            window.CobaltoConfig.showToast(`📌 Noticia agregada al dossier (${this.items.length} total)`, 'success');
        }
    },

    remove: function(idOrKey) {
        this.items = this.items.filter(it => it.id !== idOrKey && it.link !== idOrKey && it.title !== idOrKey);
        this.save();
        this.updateBadges();
        this.renderDossierList();
        this.updateCardButtons();
        if (window.CobaltoConfig && window.CobaltoConfig.showToast) {
            window.CobaltoConfig.showToast('🗑️ Noticia eliminada del dossier', 'info');
        }
    },

    clear: function() {
        if (this.items.length === 0) return;
        if (!confirm('¿Deseas limpiar todas las noticias del dossier?')) return;
        this.items = [];
        this.save();
        this.updateBadges();
        this.renderDossierList();
        this.updateCardButtons();
        if (window.CobaltoConfig && window.CobaltoConfig.showToast) {
            window.CobaltoConfig.showToast('🧹 Dossier vaciado', 'info');
        }
    },

    toggleFromCard: function(cardEl) {
        if (!cardEl) return;
        const title = cardEl.getAttribute('data-title') || cardEl.querySelector('.news-title, .rt-title, a')?.textContent?.trim() || '';
        const summary = cardEl.getAttribute('data-summary') || cardEl.querySelector('.news-summary, p')?.textContent?.trim() || '';
        const link = cardEl.getAttribute('data-link') || cardEl.querySelector('a')?.href || '';
        const source = cardEl.getAttribute('data-source') || cardEl.querySelector('.news-source, .rt-source')?.textContent?.trim() || 'OSINT';
        
        const key = link || title;
        if (!title) return;

        if (this.has(key)) {
            this.remove(key);
        } else {
            this.add({ id: key, title, summary, link, source });
        }
    },

    updateBadges: function() {
        const count = this.items.length;
        const badges = document.querySelectorAll('#dossier-count-badge, .dossier-counter-badge');
        badges.forEach(b => {
            b.textContent = `${count} NOTICIA${count === 1 ? '' : 'S'}`;
        });
    },

    updateCardButtons: function() {
        document.querySelectorAll('.news-card, .social-item, .rt-card, .panel-glass').forEach(card => {
            const title = card.getAttribute('data-title') || card.querySelector('.news-title, .rt-title, a')?.textContent?.trim() || '';
            const link = card.getAttribute('data-link') || card.querySelector('a')?.href || '';
            const key = link || title;
            const btn = card.querySelector('.btn-dossier-toggle');
            if (btn && key) {
                if (this.has(key)) {
                    btn.classList.add('in-dossier');
                    btn.style.background = 'rgba(0, 229, 255, 0.2)';
                    btn.style.color = '#00E5FF';
                    btn.style.borderColor = '#00E5FF';
                    btn.innerHTML = '📌 En Dossier';
                } else {
                    btn.classList.remove('in-dossier');
                    btn.style.background = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                    btn.innerHTML = '📌 +Dossier';
                }
            }
        });
    },

    renderDossierList: function() {
        const container = document.getElementById('intel-dossier-items-container');
        if (!container) return;

        if (this.items.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 1.5rem; color: var(--text-muted); background: rgba(0,0,0,0.2); border-radius: 6px; border: 1px dashed rgba(255,255,255,0.08);">
                    <div style="font-size: 1.5rem; margin-bottom: 0.4rem; opacity: 0.6;">📌</div>
                    <div style="font-size: 0.82rem; font-family: monospace; color: #fff; margin-bottom: 0.3rem;">EL DOSSIER ESTÁ VACÍO</div>
                    <div style="font-size: 0.72rem;">Navega por las pestañas <strong>Noticias (SitRep)</strong> o <strong>Redes Sociales</strong> y haz clic en <strong>📌 +Dossier</strong> en las noticias que deseas analizar conjuntamente.</div>
                </div>
            `;
            return;
        }

        let html = '';
        this.items.forEach((item, idx) => {
            const escTitle = (item.title || '').replace(/"/g, '&quot;');
            const escSummary = (item.summary || '').substring(0, 140) + ((item.summary || '').length > 140 ? '...' : '');
            const escSource = item.source || 'OSINT';
            const escKey = item.id.replace(/'/g, "\\'");

            html += `
                <div class="panel-glass" style="padding: 0.8rem; border-left: 3px solid var(--primary); background: rgba(15, 23, 42, 0.7); display: flex; flex-direction: column; justify-content: space-between; position: relative;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                            <span style="font-size: 0.65rem; background: rgba(0,229,255,0.1); color: var(--primary); padding: 1px 5px; border-radius: 3px; font-family: monospace;">${idx + 1}. ${escSource}</span>
                            <button type="button" onclick="IntelDossier.remove('${escKey}')" style="background: transparent; border: none; color: #ff2d55; cursor: pointer; font-size: 0.8rem;" title="Eliminar noticia del dossier">🗑️</button>
                        </div>
                        <div style="font-weight: 600; font-size: 0.82rem; color: #f1f5f9; margin-bottom: 0.3rem; line-height: 1.25;">${escTitle}</div>
                        <p style="margin: 0; font-size: 0.72rem; color: var(--text-muted); line-height: 1.3;">${escSummary}</p>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    },

    analyzeSelection: async function() {
        if (this.items.length === 0) {
            if (window.CobaltoConfig && window.CobaltoConfig.showToast) {
                window.CobaltoConfig.showToast('⚠️ Añade al menos una noticia al dossier antes de analizar.', 'warning');
            } else {
                alert('Añade al menos una noticia al dossier antes de analizar.');
            }
            return;
        }

        const btn = document.getElementById('btn-analyze-dossier');
        const container = document.getElementById('intel-report-container');
        const presetSelect = document.getElementById('dossier-preset-select');
        const preset = presetSelect ? presetSelect.value : 'general';

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PROCESANDO DOSSIER CON IA...';
        }

        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
                    <div style="font-size: 2rem; margin-bottom: 10px;" class="fa-spin">⚙️</div>
                    <h3 style="color: var(--primary); font-family: monospace; font-size: 0.95rem; margin-bottom: 6px;">ANALIZANDO ${this.items.length} NOTICIAS CON MOTOR IA LOCAL...</h3>
                    <p style="font-size: 0.8rem;">Sintetizando correlaciones, nivel de impacto y conclusiones de inteligencia...</p>
                </div>
            `;
        }

        try {
            const resp = await fetch('/api/intel/analyze-dossier', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    items: this.items,
                    preset: preset
                })
            });
            const data = await resp.json();

            if (data.status === 'ok' && data.report) {
                const formattedData = {
                    codigo: `DOSSIER-${Date.now().toString().slice(-4)}`,
                    tema_investigacion: `Análisis Táctico de Dossier (${this.items.length} Noticias)`,
                    fecha_creacion: new Date().toLocaleString(),
                    fecha_analisis: new Date().toLocaleDateString(),
                    fuente_datos: `Dossier Operativo (${this.items.length} Fuentes)`,
                    autor: 'Analista C4I / COBALTO Hub',
                    nivel_alerta: data.report.includes('CRÍTICA') ? 'ALERTA CRÍTICA' : (data.report.includes('ELEVAD') ? 'ALERTA ELEVADA' : 'EVALUACIÓN DE DOSSIER'),
                    resumen_ejecutivo: data.report.slice(0, 300) + '...',
                    analisis_completo: data.report,
                    documentos: this.items.map((it, idx) => ({
                        doc_num: String(idx + 1),
                        titulo: it.title,
                        fuente: it.source || 'OSINT',
                        score_sentimiento: 0.0,
                        contenido: it.summary || '',
                        url: it.link || '#'
                    }))
                };

                if (window.CobaltoIntel && typeof window.CobaltoIntel.renderResearchReport === 'function') {
                    window.CobaltoIntel.currentResearchData = formattedData;
                    window.CobaltoIntel.renderResearchReport(formattedData);
                    if (typeof window.CobaltoIntel.addToResearchHistory === 'function') {
                        window.CobaltoIntel.addToResearchHistory(formattedData);
                    }
                } else if (container) {
                    const formattedHtml = window.CobaltoIntel && window.CobaltoIntel.formatMarkdown ? 
                        window.CobaltoIntel.formatMarkdown(data.report) : 
                        data.report.replace(/\n\n/g, '<br/><br/>').replace(/\n/g, '<br/>');
                    container.innerHTML = `<div class="intel-report-body" style="padding: 1.5rem; background: rgba(13, 17, 23, 0.9); border-radius: 8px; border: 1px solid var(--border-color); color: #f0f6fc; line-height: 1.6;">${formattedHtml}</div>`;
                }

                if (window.CobaltoConfig && window.CobaltoConfig.showToast) {
                    window.CobaltoConfig.showToast(`✅ Informe redactado sobre ${this.items.length} noticias.`, 'success');
                }
            } else {
                throw new Error(data.message || 'Error procesando el dossier');
            }
        } catch (err) {
            console.error('Error analizando dossier:', err);
            if (container) {
                container.innerHTML = `<div style="padding: 1rem; color: #ff2d55; background: rgba(255, 45, 85, 0.1); border-radius: 6px;">❌ Error generando el informe: ${err.message}</div>`;
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🤖 ANALIZAR NOTICIAS SELECCIONADAS CON IA';
            }
        }
    }
};

document.addEventListener('DOMContentLoaded', function() {
    window.IntelDossier.init();
});
