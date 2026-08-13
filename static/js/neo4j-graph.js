/**
 * COBALTO HUB - Neo4j Force-Graph Visor (Fase 1)
 * Modal inmersivo de pantalla completa para renderizado masivo.
 */

let neoGraph = null;

function openNeo4jGraph() {
    const modal = document.getElementById("neo4j-graph-modal");
    modal.style.display = "block";
    
    // Evitar re-renderizado si ya existe
    if (neoGraph) {
        neoGraph.resumeAnimation();
        return;
    }

    const container = document.getElementById("neo4j-graph-container");
    container.innerHTML = "<div style='color: #00e5ff; font-family: monospace; display: flex; align-items: center; justify-content: center; height: 100%;'>Conectando con Neo4j... Extraiendo topología de red...</div>";

    fetch('/api/intel/graph?limit=800')
        .then(r => r.json())
        .then(data => {
            container.innerHTML = "";
            if (!data.nodes || data.nodes.length === 0) {
                container.innerHTML = `
                    <div style='color: #ffcc00; font-family: monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; padding: 20px; background: rgba(20, 20, 20, 0.8); border-radius: 8px;'>
                        <h2 style='margin-bottom: 10px; color: #ffcc00;'>⚠️ MODO LOCAL ACTIVO (FALLBACK)</h2>
                        <p style='color: #ccc; max-width: 600px; line-height: 1.5;'>El renderizado topológico avanzado (Cibergrafo) requiere el motor de base de datos vectorial <b>Neo4j</b>.</p>
                        <p style='color: #ccc; max-width: 600px; line-height: 1.5;'>Actualmente el sistema está operando en Modo de Supervivencia sin contenedores Docker (SQLite local). Esta herramienta ha sido deshabilitada temporalmente para proteger la estabilidad de la memoria RAM.</p>
                        <button onclick="closeNeo4jGraph()" style="margin-top: 20px; padding: 10px 20px; background: #ff2d55; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">ENTENDIDO</button>
                    </div>`;
                return;
            }

            // Init Force Graph
            neoGraph = ForceGraph()(container)
                .graphData(data)
                .backgroundColor('#05050A')
                .nodeId('id')
                .nodeVal(node => Math.max(2, node.val * 3))
                .nodeLabel(node => {
                    const group = node.group || 'unknown';
                    return `<div style="background: rgba(10,11,16,0.9); padding: 5px; border: 1px solid #00e5ff; border-radius: 4px; font-family: monospace;">
                        <b style="color: #00e5ff">${node.name || node.id}</b><br/>
                        <span style="color: #888">Type: ${group}</span><br/>
                        <span style="color: #888">Degree: ${node.val}</span>
                    </div>`;
                })
                .nodeColor(node => {
                    if (node.group === "persons") return "#FF2D55";
                    if (node.group === "organizations") return "#B388FF";
                    if (node.group === "locations") return "#00E5FF";
                    return "#888888";
                })
                .linkColor(() => 'rgba(0, 229, 255, 0.2)')
                .linkWidth(link => Math.min(3, link.weight || 1))
                .linkDirectionalParticles(2)
                .linkDirectionalParticleWidth(1.5)
                .onNodeClick(node => {
                    // Center/zoom on node
                    neoGraph.centerAt(node.x, node.y, 1000);
                    neoGraph.zoom(8, 2000);
                });
        })
        .catch(err => {
            console.error("Error cargando grafo Neo4j:", err);
            container.innerHTML = `<div style='color: #FF2D55; font-family: monospace; display: flex; align-items: center; justify-content: center; height: 100%;'>Error al cargar el motor de grafos.</div>`;
        });
}

function closeNeo4jGraph() {
    const modal = document.getElementById("neo4j-graph-modal");
    modal.style.display = "none";
    if (neoGraph) neoGraph.pauseAnimation();
}

// Cerrar con tecla ESC
document.addEventListener('keydown', function(e) {
    if (e.key === "Escape") {
        const modal = document.getElementById("neo4j-graph-modal");
        if (modal && modal.style.display === "block") {
            closeNeo4jGraph();
        }
    }
});
