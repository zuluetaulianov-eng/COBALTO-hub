/**
 * cctv_player.js — Standalone Frontend Subsystem for Video & CCTV Monitoring.
 * Orchestrates CCTV grid layouts, frame auto-refresh, modal preview, OpenCV analytics,
 * and media extractor playback.
 */
(function (window, document) {
    'use strict';

    const VideoPlayerSubsystem = {
        state: {
            cameras: [],
            selectedCamera: null,
            gridCols: 2,
            isLiveStream: true,
            refreshInterval: null,
            refreshFps: 1000, // 1 FPS refresh by default
            searchQuery: '',
            watchlist: [],
            visionCache: {}
        },

        init: function () {
            console.log('[VIDEO PLAYER] Inicializando subsistema de video...');
            this.bindEvents();
            this.fetchCameras();
            this.fetchWatchlist();
            this.fetchNewsVideos();
            this.startAutoRefresh();
        },

        bindEvents: function () {
            const searchInput = document.getElementById('cctv-search-input');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    this.state.searchQuery = e.target.value.toLowerCase();
                    this.renderGrid();
                });
            }

            const extractForm = document.getElementById('video-extract-form');
            if (extractForm) {
                extractForm.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.handleMediaExtract();
                });
            }
        },

        fetchCameras: async function () {
            try {
                const resp = await fetch('/api/cctv/cameras');
                const data = await resp.json();
                if (data && data.cameras) {
                    this.state.cameras = data.cameras;
                    this.renderGrid();
                    this.updateStats(data.collector_stats);
                }
            } catch (err) {
                console.error('[VIDEO PLAYER] Error cargando cámaras:', err);
            }
        },

        fetchWatchlist: async function () {
            try {
                const resp = await fetch('/api/cctv/watchlist');
                const data = await resp.json();
                if (data && data.watchlist) {
                    this.state.watchlist = data.watchlist;
                }
            } catch (err) {
                console.error('[VIDEO PLAYER] Error cargando watchlist:', err);
            }
        },

        setGridCols: function (cols) {
            this.state.gridCols = cols;
            const container = document.getElementById('cctv-grid');
            if (container) {
                container.className = `cctv-grid-container cctv-grid-cols-${cols}`;
            }

            // Update UI buttons
            document.querySelectorAll('.btn-layout').forEach(btn => {
                btn.classList.toggle('active', parseInt(btn.dataset.cols) === cols);
            });
        },

        toggleLiveStream: function () {
            this.state.isLiveStream = !this.state.isLiveStream;
            const btn = document.getElementById('btn-live-toggle');
            if (btn) {
                btn.textContent = this.state.isLiveStream ? '🔴 STREAM: ON' : '⏸️ STREAM: PAUSED';
                btn.style.borderColor = this.state.isLiveStream ? '#00FFAA' : '#FF4444';
            }
            if (this.state.isLiveStream) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        },

        startAutoRefresh: function () {
            this.stopAutoRefresh();
            this.state.refreshInterval = setInterval(() => {
                if (this.state.isLiveStream) {
                    this.refreshFrames();
                }
            }, this.state.refreshFps);
        },

        stopAutoRefresh: function () {
            if (this.state.refreshInterval) {
                clearInterval(this.state.refreshInterval);
                this.state.refreshInterval = null;
            }
        },

        refreshFrames: function () {
            const timestamp = new Date().getTime();
            document.querySelectorAll('.cctv-frame-img').forEach(img => {
                const camId = img.dataset.camId;
                if (camId) {
                    img.src = `/api/cctv/frame/${camId}?t=${timestamp}`;
                }
            });
        },

        renderGrid: function () {
            const container = document.getElementById('cctv-grid');
            if (!container) return;

            const filtered = this.state.cameras.filter(cam => {
                const query = this.state.searchQuery;
                return cam.name.toLowerCase().includes(query) ||
                       cam.city.toLowerCase().includes(query) ||
                       cam.source.toLowerCase().includes(query);
            });

            if (filtered.length === 0) {
                container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #64748B;">
                    No se encontraron cámaras que coincidan con la búsqueda.
                </div>`;
                return;
            }

            const ts = new Date().getTime();
            container.innerHTML = filtered.map(cam => {
                const vision = this.state.visionCache[cam.id] || null;
                const isWatch = this.state.watchlist.includes(cam.id);

                return `
                <div class="cctv-card" onclick="window.VideoPlayerSubsystem.openModal('${cam.id}')">
                    <div class="cctv-overlay-header">
                        <span class="cctv-badge">${cam.name} (${cam.city})</span>
                        <span class="cctv-status-live">● LIVE</span>
                    </div>
                    <img class="cctv-frame-img" data-cam-id="${cam.id}" src="/api/cctv/frame/${cam.id}?t=${ts}" alt="${cam.name}" />
                    <div style="position: absolute; bottom: 8px; left: 8px; right: 8px; display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.7); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 10px;">
                        <span style="color: #00E5FF;">${cam.source}</span>
                        <button onclick="event.stopPropagation(); window.VideoPlayerSubsystem.runVisionAnalysis('${cam.id}')" style="background: rgba(0,229,255,0.2); border: 1px solid #00E5FF; color: #00E5FF; padding: 2px 6px; border-radius: 3px; cursor: pointer; font-size: 9px;">
                            👁️ VISION CV
                        </button>
                    </div>
                    ${vision ? `
                        <div style="position: absolute; top: 34px; left: 8px; background: rgba(0,0,0,0.85); border: 1px solid ${vision.anomaly_detected ? '#FF4444' : '#00FFAA'}; color: #fff; padding: 3px 6px; border-radius: 4px; font-size: 9px; font-family: monospace;">
                            🚶 Peatones: ${vision.objects_detected.pedestrians} | 🚗 Vehículos: ${vision.objects_detected.vehicles} | 📊 Mov: ${vision.motion_score}%
                        </div>
                    ` : ''}
                </div>
                `;
            }).join('');
        },

        openModal: function (camId) {
            const cam = this.state.cameras.find(c => c.id === camId);
            if (!cam) return;

            this.state.selectedCamera = cam;
            const modal = document.getElementById('cctv-modal');
            const title = document.getElementById('modal-cam-title');
            const img = document.getElementById('modal-cam-img');
            const metaContainer = document.getElementById('modal-cam-meta');

            if (title) title.textContent = `${cam.name} — ${cam.city}, ${cam.country} [${cam.source}]`;
            if (img) img.src = `/api/cctv/stream/${cam.id}`;

            if (metaContainer) {
                metaContainer.innerHTML = `
                    <table class="meta-table">
                        <tr><td class="meta-label">ID Cámara:</td><td class="meta-value">${cam.id}</td></tr>
                        <tr><td class="meta-label">Fuente / NVR:</td><td class="meta-value">${cam.source}</td></tr>
                        <tr><td class="meta-label">Ubicación GPS:</td><td class="meta-value">${cam.latitude}, ${cam.longitude}</td></tr>
                        <tr><td class="meta-label">Protocolo:</td><td class="meta-value">${cam.type}</td></tr>
                        <tr><td class="meta-label">Estado:</td><td class="meta-value" style="color:#00FFAA;">ONLINE</td></tr>
                    </table>
                    <div style="margin-top: 12px; display: flex; gap: 8px;">
                        <button onclick="window.VideoPlayerSubsystem.runVisionAnalysis('${cam.id}')" class="btn-tactical" style="flex:1;">👁️ EJECUTAR VISIÓN OPENCV</button>
                        <button onclick="window.VideoPlayerSubsystem.toggleWatchlist('${cam.id}')" class="btn-tactical" style="flex:1;">
                            ${this.state.watchlist.includes(cam.id) ? '⭐ QUITAR WATCHLIST' : '☆ AÑADIR WATCHLIST'}
                        </button>
                    </div>
                `;
            }

            if (modal) modal.style.display = 'flex';
        },

        closeModal: function () {
            const modal = document.getElementById('cctv-modal');
            const img = document.getElementById('modal-cam-img');
            const embedBox = document.getElementById('modal-embed-box');
            if (img) img.style.display = 'block';
            if (embedBox) {
                embedBox.innerHTML = '';
                embedBox.style.display = 'none';
            }
            if (modal) modal.style.display = 'none';
        },

        runVisionAnalysis: async function (camId) {
            try {
                const resp = await fetch(`/api/cctv/analyze/${camId}`, { method: 'POST' });
                const data = await resp.json();
                if (data && data.analysis) {
                    this.state.visionCache[camId] = data.analysis;
                    this.renderGrid();
                    if (this.state.selectedCamera && this.state.selectedCamera.id === camId) {
                        this.openModal(camId);
                    }
                }
            } catch (err) {
                console.error('[VIDEO PLAYER] Error corriendo análisis de visión:', err);
            }
        },

        toggleWatchlist: async function (camId) {
            const isListed = this.state.watchlist.includes(camId);
            const endpoint = isListed ? '/api/cctv/watchlist/remove' : '/api/cctv/watchlist/add';
            try {
                await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_id: camId })
                });
                await this.fetchWatchlist();
                if (this.state.selectedCamera) this.openModal(camId);
            } catch (err) {
                console.error('[VIDEO PLAYER] Error actualizando watchlist:', err);
            }
        },

        handleMediaExtract: async function () {
            const input = document.getElementById('media-url-input');
            const resultBox = document.getElementById('media-player-box');
            if (!input || !resultBox || !input.value) return;

            resultBox.innerHTML = `<div style="padding:20px; color:#00E5FF;">Analizando enlace multimedia...</div>`;

            try {
                const resp = await fetch('/api/video/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: input.value })
                });
                const data = await resp.json();

                if (data && data.media) {
                    const m = data.media;
                    if (m.type === 'YOUTUBE' || m.type === 'VIMEO') {
                        resultBox.innerHTML = `<iframe src="${m.embed_url}" style="width:100%; height:400px; border:none; border-radius:8px;" allowfullscreen></iframe>`;
                    } else if (m.type === 'DIRECT_VIDEO') {
                        resultBox.innerHTML = `<video src="${m.embed_url}" controls autoplay style="width:100%; max-height:450px; border-radius:8px; border:1px solid #00E5FF;"></video>`;
                    } else {
                        resultBox.innerHTML = `
                            <div style="padding:20px; background:rgba(0,229,255,0.05); border:1px solid #00E5FF; border-radius:8px;">
                                <p style="color:#00E5FF; font-weight:bold;">Video Extraído (${m.provider})</p>
                                <p style="font-size:12px; margin-top:6px; color:#fff;">URL: ${m.url}</p>
                                <a href="${m.url}" target="_blank" class="btn-tactical" style="display:inline-block; margin-top:10px;">🔗 Abrir Reproductor Externo</a>
                            </div>
                        `;
                    }
                }
            } catch (err) {
                resultBox.innerHTML = `<div style="padding:20px; color:#FF4444;">Error al extraer video: ${err.message}</div>`;
            }
        },

        fetchNewsVideos: async function () {
            try {
                const resp = await fetch('/api/news/videos');
                const data = await resp.json();
                if (data && data.news_videos) {
                    this.state.newsVideos = data.news_videos;
                    this.renderNewsVideos();
                    const elCount = document.getElementById('stat-total-news-vid');
                    if (elCount) elCount.textContent = data.total_items || data.news_videos.length;
                }
            } catch (err) {
                console.error('[VIDEO PLAYER] Error cargando noticias con video:', err);
            }
        },

        renderNewsVideos: function () {
            const container = document.getElementById('news-videos-grid');
            if (!container) return;

            const items = this.state.newsVideos || [];
            if (items.length === 0) {
                container.innerHTML = `<div style="padding: 20px; color: #64748B; font-family: monospace;">No hay noticias con video registradas.</div>`;
                return;
            }

            container.innerHTML = items.map(item => `
                <div class="cctv-card" style="padding: 10px; background: rgba(15,23,42,0.8); display: flex; flex-direction: column; justify-content: space-between;" onclick="window.VideoPlayerSubsystem.playNewsVideo('${item.id}')">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span class="cctv-badge" style="background: rgba(255,215,0,0.15); color: #FFD700; border-color: #FFD700;">📺 ${item.source}</span>
                            <span style="font-family: monospace; font-size: 9px; color: #00FFAA;">[${item.country}]</span>
                        </div>
                        <h4 style="font-size: 11px; font-weight: bold; color: #fff; line-height: 1.3; margin-bottom: 6px;">${item.title}</h4>
                        <p style="font-size: 10px; color: var(--text-muted); line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${item.summary}</p>
                    </div>
                    <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-family: monospace; font-size: 9px; color: #00E5FF;">▶ REPRODUCIR (${item.provider})</span>
                        <span style="font-family: monospace; font-size: 9px; color: #64748B;">${item.published.substring(0, 10)}</span>
                    </div>
                </div>
            `).join('');
        },

        playNewsVideo: function (itemId) {
            const item = (this.state.newsVideos || []).find(x => x.id === itemId);
            if (!item) return;

            const modal = document.getElementById('cctv-modal');
            const title = document.getElementById('modal-cam-title');
            const img = document.getElementById('modal-cam-img');
            const metaContainer = document.getElementById('modal-cam-meta');

            if (title) title.textContent = `📰 ${item.source} — ${item.title}`;

            if (img) {
                // If iframe embed is needed, swap modal image for iframe/embed container
                img.style.display = 'none';
                let embedBox = document.getElementById('modal-embed-box');
                if (!embedBox) {
                    embedBox = document.createElement('div');
                    embedBox.id = 'modal-embed-box';
                    embedBox.style.width = '100%';
                    embedBox.style.height = '450px';
                    img.parentNode.appendChild(embedBox);
                }
                embedBox.style.display = 'block';

                if (item.provider === 'YOUTUBE' || item.provider === 'VIMEO' || item.provider === 'TIKTOK') {
                    embedBox.innerHTML = `<iframe src="${item.video_url}" style="width:100%; height:100%; border:none; border-radius:8px;" allowfullscreen></iframe>`;
                } else if (item.provider === 'MJPEG_STREAM') {
                    embedBox.innerHTML = `<img src="${item.video_url}" style="width:100%; height:100%; object-fit:contain; border-radius:8px;" />`;
                } else {
                    embedBox.innerHTML = `<video src="${item.video_url}" controls autoplay style="width:100%; height:100%; border-radius:8px; border:1px solid #00E5FF;"></video>`;
                }
            }

            if (metaContainer) {
                metaContainer.innerHTML = `
                    <div style="font-family: monospace; font-size: 11px;">
                        <h4 style="color:#FFD700; margin-bottom: 8px;">${item.title}</h4>
                        <p style="color:var(--text-muted); line-height:1.4; margin-bottom: 12px;">${item.summary}</p>
                        <table class="meta-table">
                            <tr><td class="meta-label">Fuente:</td><td class="meta-value">${item.source}</td></tr>
                            <tr><td class="meta-label">Proveedor Video:</td><td class="meta-value">${item.provider}</td></tr>
                            <tr><td class="meta-label">País:</td><td class="meta-value">${item.country}</td></tr>
                            <tr><td class="meta-label">Fecha:</td><td class="meta-value">${item.published}</td></tr>
                        </table>
                        <a href="${item.link}" target="_blank" class="btn-tactical" style="display:block; text-align:center; margin-top:12px;">
                            🔗 VER NOTICIA EN FUENTE ORIGINAL
                        </a>
                    </div>
                `;
            }

            if (modal) modal.style.display = 'flex';
        },

        updateStats: function (stats) {
            if (!stats) return;
            const elTotal = document.getElementById('stat-total-cams');
            const elSnaps = document.getElementById('stat-total-snaps');
            if (elTotal) elTotal.textContent = stats.total_cameras || this.state.cameras.length;
            if (elSnaps) elSnaps.textContent = stats.total_snapshots || 0;
        }
    };

    window.VideoPlayerSubsystem = VideoPlayerSubsystem;

    document.addEventListener('DOMContentLoaded', () => {
        VideoPlayerSubsystem.init();
    });

})(window, document);
