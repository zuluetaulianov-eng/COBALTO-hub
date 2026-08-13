/**
 * COBALTO HUB - Palantir Global Search (Fase 2)
 * Búsqueda de alta velocidad usando Elasticsearch y atajo Ctrl+K
 */

document.addEventListener("DOMContentLoaded", () => {
    // Inyectar el HTML del modal Palantir dinámicamente si no existe
    if (!document.getElementById("palantir-modal")) {
        const modalHtml = `
            <div id="palantir-modal" style="display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(5,5,10,0.9); backdrop-filter:blur(10px); z-index:200000; align-items:flex-start; justify-content:center; padding-top:10vh;">
                <div style="width:90%; max-width:800px; background:rgba(10,11,16,0.95); border:1px solid #FF9500; border-radius:12px; box-shadow:0 0 40px rgba(255,149,0,0.15); display:flex; flex-direction:column; overflow:hidden;">
                    <div style="padding:15px 20px; border-bottom:1px solid rgba(255,149,0,0.2); display:flex; align-items:center; gap:15px;">
                        <span style="font-size:1.5rem;">👁️</span>
                        <input type="text" id="palantir-input" placeholder="Buscador Omnipotente Palantir... (Ctrl+K para cerrar)" style="flex:1; background:transparent; border:none; color:#FF9500; font-family:'Roboto Mono',monospace; font-size:1.1rem; outline:none;" autocomplete="off">
                        <span id="palantir-count" style="font-size:0.8rem; color:#888; font-family:monospace;"></span>
                    </div>
                    <div id="palantir-results" style="max-height:60vh; overflow-y:auto; padding:0;">
                        <!-- Resultados se inyectan aquí -->
                        <div style="padding:20px; color:#555; font-family:monospace; text-align:center;">
                            Busca en el historial histórico de Elasticsearch. Extrae inteligencia de millones de nodos.
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML("beforeend", modalHtml);
    }

    const modal = document.getElementById("palantir-modal");
    const input = document.getElementById("palantir-input");
    const resultsContainer = document.getElementById("palantir-results");
    const countDisplay = document.getElementById("palantir-count");
    
    let searchTimeout = null;

    // Abrir/Cerrar con Ctrl+K
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            togglePalantir();
        }
        if (e.key === "Escape" && modal.style.display === "flex") {
            togglePalantir(false);
        }
    });

    function togglePalantir(forceState = null) {
        const isCurrentlyOpen = modal.style.display === "flex";
        const willOpen = forceState !== null ? forceState : !isCurrentlyOpen;

        if (willOpen) {
            modal.style.display = "flex";
            input.focus();
            input.select();
        } else {
            modal.style.display = "none";
        }
    }

    // Lógica de Búsqueda
    input.addEventListener("input", (e) => {
        const query = e.target.value.trim();
        
        clearTimeout(searchTimeout);
        
        if (!query) {
            resultsContainer.innerHTML = `<div style="padding:20px; color:#555; font-family:monospace; text-align:center;">Ingresa un término para comenzar la extracción...</div>`;
            countDisplay.textContent = "";
            return;
        }

        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300); // 300ms de debounce
    });

    function performSearch(query) {
        resultsContainer.innerHTML = `<div style="padding:20px; color:#FF9500; font-family:monospace; text-align:center;">Consultando oráculo de Elasticsearch...</div>`;
        
        fetch(`/api/intel/search?q=${encodeURIComponent(query)}&limit=50`)
            .then(r => r.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                
                countDisplay.textContent = `${data.count} resultados`;
                
                if (data.results.length === 0) {
                    resultsContainer.innerHTML = `<div style="padding:20px; color:#FF2D55; font-family:monospace; text-align:center;">No hay coincidencias en los registros de inteligencia.</div>`;
                    return;
                }

                let html = "";
                data.results.forEach(item => {
                    const title = item.title || "Sin Título";
                    const source = item.source || "Desconocido";
                    const date = item.ingested_at ? new Date(item.ingested_at).toLocaleString() : "Sin fecha";
                    const link = item.link || "#";
                    
                    html += `
                        <div style="padding:15px 20px; border-bottom:1px solid rgba(255,255,255,0.05); transition:background 0.2s; cursor:pointer;" onmouseover="this.style.background='rgba(255,149,0,0.05)'" onmouseout="this.style.background='transparent'" onclick="window.open('${link}', '_blank')">
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:#FF9500; font-size:0.75rem; font-family:monospace; text-transform:uppercase; border:1px solid rgba(255,149,0,0.3); padding:2px 6px; border-radius:4px;">${source}</span>
                                <span style="color:#888; font-size:0.7rem; font-family:monospace;">${date}</span>
                            </div>
                            <div style="color:#fff; font-size:0.95rem; font-family:Inter, sans-serif; margin-bottom:6px; font-weight:600;">${title}</div>
                            <div style="color:#aaa; font-size:0.8rem; font-family:Inter, sans-serif; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${item.summary || ""}</div>
                        </div>
                    `;
                });
                
                resultsContainer.innerHTML = html;
            })
            .catch(err => {
                console.error("Palantir Search Error:", err);
                resultsContainer.innerHTML = `<div style="padding:20px; color:#FF2D55; font-family:monospace; text-align:center;">Error de conexión con el núcleo de búsqueda.</div>`;
            });
    }
});
