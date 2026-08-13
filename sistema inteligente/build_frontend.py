"""Genera el dashboard frontend en frontend/index.html"""
import os
os.makedirs("frontend", exist_ok=True)

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Sistema Inteligente - Pipeline</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
body { font-family: Inter, sans-serif; background: #0b1120; color: #cbd5e1; min-height: 100vh; margin: 0; padding: 2rem; }
.pipeline { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 2rem; }
.organ { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 14px; padding: 1.5rem; position: relative; }
.organ::before { content: ''; position: absolute; top: -2rem; left: 50%; width: 2px; height: 2rem; background: #38bdf8; opacity: 0.3; }
.organ:first-child::before { display: none; }
.organ h2 { font-size: 1.2rem; color: #38bdf8; margin-top: 0; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
.organ h2 span { background: rgba(56,189,248,.1); padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem; color: #38bdf8; border: 1px solid rgba(56,189,248,.3); }
.row { display: flex; gap: 1rem; margin-bottom: 1rem; }
.inp { background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.08); border-radius: 9px; padding: 0.75rem 1rem; color: #e2e8f0; font-family: Inter, sans-serif; flex: 1; outline: none; }
.inp:focus { border-color: #38bdf8; }
.btn { background: linear-gradient(135deg, #38bdf8, #818cf8); border: none; border-radius: 9px; padding: 0.75rem 1.5rem; color: #0b1120; font-weight: bold; cursor: pointer; white-space: nowrap; }
.btn:hover { opacity: 0.9; }
.result-card { background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,.05); border-radius: 8px; padding: 1rem; margin-top: 1rem; cursor: pointer; transition: border 0.2s; }
.result-card:hover { border-color: rgba(56,189,248,.3); }
.doc-title { font-weight: 600; color: #fff; margin-bottom: 0.5rem; }
.doc-snippet { font-size: 0.85rem; color: #94a3b8; }
.doc-snippet b { color: #fbbf24; }
.analysis-panel { display: none; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.08); }
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin: 0.2rem; background: rgba(56,189,248,.1); color: #38bdf8; border: 1px solid rgba(56,189,248,.2); }
.badge-org { background: rgba(251,191,36,.1); color: #fbbf24; border-color: rgba(251,191,36,.2); }
.badge-loc { background: rgba(34,197,94,.1); color: #4ade80; border-color: rgba(34,197,94,.2); }
.badge-per { background: rgba(129,140,248,.1); color: #818cf8; border-color: rgba(129,140,248,.2); }
.empty { text-align: center; color: #475569; padding: 1rem; font-size: 0.9rem; }
.spin{display:inline-block;width:16px;height:16px;border:2px solid rgba(56,189,248,.3);border-top-color:#38bdf8;border-radius:50%;animation:sp .7s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes sp{to{transform:rotate(360deg)}}
.flex-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.section-title { font-size: 0.85rem; text-transform: uppercase; color: #64748b; font-weight: 700; margin-bottom: 0.5rem; letter-spacing: 0.05em; }
.organ-ia { background: rgba(129,140,248,.04); border: 1px solid rgba(129,140,248,.2); border-radius: 14px; padding: 1.5rem; position: relative; box-shadow: 0 0 40px rgba(129,140,248,.06); }
.organ-ia::before { content: ''; position: absolute; top: -2rem; left: 50%; width: 2px; height: 2rem; background: #818cf8; opacity: 0.4; }
.organ-ia h2 { font-size: 1.2rem; color: #a78bfa; margin-top: 0; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
.organ-ia h2 span { background: rgba(167,139,250,.12); padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem; color: #a78bfa; border: 1px solid rgba(167,139,250,.3); }
.btn-ia { background: linear-gradient(135deg, #a78bfa, #f59e0b); border: none; border-radius: 9px; padding: 0.75rem 1.5rem; color: #0b1120; font-weight: bold; cursor: pointer; white-space: nowrap; }
.btn-ia:hover { opacity: 0.9; }
.ia-ctx { background: rgba(15,23,42,.7); border: 1px solid rgba(255,255,255,.05); border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.8rem; font-size: 0.8rem; color: #64748b; }
.ia-ctx b { color: #94a3b8; }
.ia-response { background: rgba(129,140,248,.06); border: 1px solid rgba(129,140,248,.2); border-radius: 10px; padding: 1.2rem 1.4rem; font-size: 0.92rem; color: #e2e8f0; line-height: 1.7; white-space: pre-wrap; }
.ia-badge { display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(167,139,250,.1); color: #a78bfa; border: 1px solid rgba(167,139,250,.2); border-radius: 20px; padding: 0.2rem 0.7rem; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.8rem; }
</style>
</head>
<body>
<div class="pipeline">
  <div style="text-align:center; margin-bottom: 1rem;">
    <h1 style="color:#fff; font-size:1.5rem; margin:0;">Sistema <span style="color:#38bdf8">Inteligente</span></h1>
    <div style="color:#64748b; font-size:0.9rem; margin-top:0.5rem;">Pipeline Automático de Análisis de Texto</div>
  </div>

  <div class="organ" id="o-ingesta">
    <h2><span>Fase 1</span> Ingesta de Conocimiento (Boca)</h2>
    <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem;">Sube documentos. El sistema los indexará en SQLite, extraerá su texto y actualizará la IA (TF-IDF y Concordancia) de forma automática.</p>
    <div class="row">
      <input type="file" id="fi" class="inp" accept=".txt,.pdf,.docx,.md">
      <button class="btn" onclick="subir()">Digerir Documento</button>
    </div>
    <div id="ru"></div>
  </div>

  <div class="organ" id="o-busqueda">
    <h2><span>Fase 2</span> Búsqueda y Análisis Profundo (Estómago / Intestinos)</h2>
    <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem;">Busca cualquier término. <b>Haz clic en un resultado</b> y el sistema procesará automáticamente ese documento pasando el texto por NLP (extracción de entidades) y TF-IDF (matemática de palabras clave).</p>
    <div class="row">
      <input id="q" class="inp" placeholder='Término o frase (ej. "inteligencia")' onkeypress="if(event.key==='Enter')buscar()">
      <button class="btn" onclick="buscar()">Buscar en el Corpus</button>
    </div>
    <div id="rb"><div class="empty">Esperando consulta...</div></div>
  </div>

  <div class="organ" id="o-kwic">
    <h2><span>Fase 3</span> Análisis de Patrones Globales (KWIC)</h2>
    <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem;">Visualiza cómo se usa una palabra exacta en todo el corpus para entender su contexto transversal.</p>
    <div class="row">
      <input id="kt" class="inp" placeholder="Término a analizar..." onkeypress="if(event.key==='Enter')kwic()">
      <input id="kv" class="inp" type="number" value="5" style="width:70px;flex:none" title="Ventana (palabras)" placeholder="Vent.">
      <button class="btn" onclick="kwic()">Analizar Contexto</button>
    </div>
    <div id="rk"><div class="empty">Esperando consulta...</div></div>
  </div>

  <div class="organ-ia" id="o-ia">
    <h2><span>Fase 4</span> 🧠 Consulta a la IA (RAG)</h2>
    <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem;">
      Haz una pregunta en lenguaje natural. El sistema buscará contexto exacto en el índice FTS5 (Capa 1) y se lo enviará a <b style="color:#a78bfa">NVIDIA AI / minimax-m3</b> para que genere una respuesta fundamentada (Capa 2). La IA <u>no inventa</u> — solo analiza los documentos indexados.
    </p>
    <div class="row">
      <input id="ia-q" class="inp" placeholder='Ej: ¿Cuál es el RIF de la empresa Corporación Matrix?' onkeypress="if(event.key==='Enter')consultar_ia()" style="border-color:rgba(129,140,248,.3);">
      <button class="btn-ia" onclick="consultar_ia()">Consultar IA</button>
    </div>
    <div id="ria"><div class="empty">Esperando pregunta... La IA responderá basándose en los documentos del índice local.</div></div>
  </div>

</div>
<script>
const API='';

async function subir(){
  const f=document.getElementById('fi').files[0];if(!f)return;
  const fd=new FormData();fd.append('file',f);
  document.getElementById('ru').innerHTML='<span class="spin"></span>Ingiriendo documento...';
  try{
    const res=await fetch(API+'/api/indexar/archivo',{method:'POST',body:fd});
    const d=await res.json();
    const msg=d.status === 'ok' ? 'Ingerido correctamente' : d.mensaje;
    document.getElementById('ru').innerHTML=`<div class="result-card" style="cursor:default;"><div style="color:#4ade80">✓ ${msg}</div><div class="doc-snippet">Archivo: ${d.archivo||'--'} | ID Interno: ${d.doc_id||'--'}</div><div id="sync-status" style="font-size:0.8rem;color:#64748b;margin-top:0.5rem"><span class="spin"></span> Sincronizando motores...</div></div>`;
    document.getElementById('fi').value = '';
    if(d.status === 'ok'){
      let intentos=0;
      const check=setInterval(async()=>{
        try{
          const s=await fetch(API+'/api/estado').then(r=>r.json());
          const el=document.getElementById('sync-status');
          if(!el){clearInterval(check);return;}
          if(s.concordancia_docs>0||++intentos>=5){
            clearInterval(check);
            el.innerHTML=`⚡ Motores sincronizados — ${s.concordancia_docs} doc(s) en KWIC · Clasificador: ${s.clasificador_entrenado?'✓ activo':'esperando ≥2 docs'}`;
            el.style.color='#4ade80';
          }
        }catch{clearInterval(check);}
      },1500);
    }
  }catch(e){document.getElementById('ru').innerHTML=`<div style="color:#f87171">${e.message}</div>`;}
}

async function buscar(){
  const q=document.getElementById('q').value.trim();if(!q)return;
  document.getElementById('rb').innerHTML='<span class="spin"></span>Buscando...';
  try{
    const res=await fetch(API+'/api/buscar?q='+encodeURIComponent(q)+'&limite=15');
    const d=await res.json();
    if(!d.resultados.length){document.getElementById('rb').innerHTML='<div class="empty">No se encontró información en el sistema.</div>';return;}
    
    let html = '';
    d.resultados.forEach(x => {
      html += `
      <div class="result-card" onclick="analizarDoc(${x.id}, this)">
        <div class="doc-title">[ID: ${x.id}] ${x.nombre}</div>
        <div class="doc-snippet">${(x.fragmento||'').replace(/\[/g,'<b>').replace(/\]/g,'</b>')}</div>
        <div class="analysis-panel" id="analysis-${x.id}"></div>
      </div>`;
    });
    document.getElementById('rb').innerHTML = html;
  }catch(e){document.getElementById('rb').innerHTML=`<div style="color:#f87171">${e.message}</div>`;}
}

async function analizarDoc(docId, cardEl){
  const panel = cardEl.querySelector('.analysis-panel');
  if(panel.style.display === 'block'){ panel.style.display = 'none'; return; }
  
  document.querySelectorAll('.analysis-panel').forEach(p => p.style.display = 'none');
  panel.style.display = 'block';
  panel.innerHTML = '<span class="spin"></span>Digeriendo documento (Extrayendo NLP y calculando TF-IDF)...';
  
  try {
    const [nlpRes, tfidfRes] = await Promise.all([
      fetch(API+'/api/extraer/'+docId).then(r=>r.json()),
      fetch(API+'/api/tfidf/keywords/'+docId+'?top_n=8').then(r=>r.json())
    ]);
    
    let nlpHTML = '<div class="section-title">Entidades Detectadas (NLP)</div>';
    if(nlpRes.entidades && Object.keys(nlpRes.entidades).length > 0){
       Object.keys(nlpRes.entidades).forEach(k => {
         let cls = 'badge';
         if(k==='ORG'||k.includes('rif')) cls='badge badge-org';
         if(k==='LOC'||k==='coordenadas') cls='badge badge-loc';
         if(k==='PER'||k.includes('cedula')||k.includes('email')) cls='badge badge-per';
         
         nlpHTML += `<div style="margin-bottom:0.3rem"><span style="font-size:0.7rem;color:#94a3b8;display:inline-block;width:80px;vertical-align:top;margin-top:0.3rem">${k}</span> <div style="display:inline-block;width:calc(100% - 90px)">`;
         nlpRes.entidades[k].forEach(v => { nlpHTML += `<span class="${cls}">${v}</span>`; });
         nlpHTML += '</div></div>';
       });
    } else {
       nlpHTML += '<div class="empty" style="padding:0;text-align:left">Ninguna entidad relevante</div>';
    }
    
    let tfidfHTML = '<div class="section-title">Conceptos Clave (TF-IDF)</div>';
    if(tfidfRes.keywords && tfidfRes.keywords.length > 0){
       tfidfRes.keywords.forEach(k => {
         tfidfHTML += `<span class="badge" style="background:rgba(255,255,255,0.05);color:#cbd5e1;border-color:rgba(255,255,255,0.1)">${k.palabra}</span>`;
       });
    } else {
       tfidfHTML += '<div class="empty" style="padding:0;text-align:left">No hay suficientes datos matemáticos</div>';
    }
    
    panel.innerHTML = `
      <div class="flex-grid">
        <div>${nlpHTML}</div>
        <div>${tfidfHTML}</div>
      </div>
    `;
  } catch(e) {
    panel.innerHTML = `<div style="color:#f87171">Error al analizar: ${e.message}</div>`;
  }
}

async function kwic(){
  const term=document.getElementById('kt').value.trim(),v=parseInt(document.getElementById('kv').value)||5;if(!term)return;
  document.getElementById('rk').innerHTML='<span class="spin"></span>Analizando corpus global...';
  try{
    const res=await fetch(API+'/api/concordancia/buscar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({termino:term,ventana:v})});
    const d=await res.json();
    if(!d.lineas || !d.lineas.length){document.getElementById('rk').innerHTML='<div class="empty">No encontrado en el corpus global</div>';return;}
    let h=`<div style="margin-bottom:1rem;font-size:0.85rem;color:#38bdf8">${d.total_ocurrencias} ocurrencias encontradas</div>`;
    d.lineas.forEach(l=>{
      h+=`<div class="result-card" style="margin-top:0.5rem;font-size:0.85rem;cursor:default;">
        <span style="color:#64748b">[Doc ${l.doc}]</span> 
        <span style="color:#94a3b8">${l.izquierda}</span> 
        <b style="color:#fbbf24">${l.termino}</b> 
        <span style="color:#94a3b8">${l.derecha}</span>
      </div>`;
    });
    document.getElementById('rk').innerHTML=h;
  }catch(e){document.getElementById('rk').innerHTML=`<div style="color:#f87171">${e.message}</div>`;}
}

async function consultar_ia(){
  const p=document.getElementById('ia-q').value.trim();if(!p)return;
  const out=document.getElementById('ria');
  out.innerHTML='<span class="spin"></span><span style="color:#a78bfa">Buscando contexto en el índice local y consultando NVIDIA AI...</span>';
  try{
    const res=await fetch(API+'/api/ia/consultar',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({pregunta:p,limite_contexto:3})
    });
    if(res.status===429){out.innerHTML='<div style="color:#f87171">⚠️ Límite de solicitudes NVIDIA alcanzado. Espera unos segundos e intenta nuevamente.</div>';return;}
    if(res.status===502||res.status===504){const e=await res.json();out.innerHTML=`<div style="color:#f87171">⚠️ ${e.detail}</div>`;return;}
    const d=await res.json();
    
    // Construir panel de contexto
    let ctxHTML='';
    if(d.contexto_local.encontrado && d.contexto_local.fragmentos.length){
      ctxHTML='<div class="ia-ctx"><b>🔍 Contexto extraído del índice local (' + d.contexto_local.documentos + ' doc(s)):</b><br>';
      d.contexto_local.fragmentos.forEach(f=>{
        ctxHTML+=`<div style="margin-top:0.4rem"><span style="color:#38bdf8">[${f.nombre}]</span> ${f.fragmento.replace(/\[/g,'<b>').replace(/\]/g,'</b>')}</div>`;
      });
      ctxHTML+='</div>';
    } else {
      ctxHTML='<div class="ia-ctx" style="color:#f59e0b">⚠️ No se encontró contexto específico en el índice. La IA responderá que no tiene datos suficientes.</div>';
    }
    
    out.innerHTML=`
      <div style="margin-bottom:0.6rem">
        <span class="ia-badge">🧠 ${d.modelo} • NVIDIA AI</span>
      </div>
      ${ctxHTML}
      <div class="section-title" style="margin-top:0.5rem">Respuesta de la IA</div>
      <div class="ia-response">${d.respuesta_ia.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
    `;
  }catch(e){out.innerHTML=`<div style="color:#f87171">${e.message}</div>`;}
}
</script>
</body>
</html>"""

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)
print("frontend/index.html generado OK")
