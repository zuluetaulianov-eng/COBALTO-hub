"""
Script de Verificacion de Integracion de IA
Verifica: Servidor local FastAPI + API NVIDIA + Flujo RAG completo
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests
import json
import sys

BASE = "http://localhost:8100"

# Claves extraídas de los archivos del proyecto
NVIDIA_KEY_TEST    = "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"  # test_ia.py
NVIDIA_KEY_FEEDER  = "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"  # alimentador_ia.py

resultados = {}

# ─────────────────────────────────────────────────────────────────
# 1. Servidor Local (FastAPI en puerto 8100)
# ─────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print(" [1] VERIFICANDO SERVIDOR LOCAL (FastAPI :8100)")
print("="*55)
try:
    r = requests.get(f"{BASE}/api/estado", timeout=5)
    if r.status_code == 200:
        d = r.json()
        print(f"  [OK] Servidor activo | version={d.get('version')}")
        print(f"  Corpus stats        : {d.get('corpus')}")
        print(f"  spaCy activo        : {d.get('spacy_activo')} | modelo: {d.get('spacy_modelo')}")
        print(f"  Clasificador TF-IDF : {'ENTRENADO' if d.get('clasificador_entrenado') else 'sin entrenar'}")
        print(f"  KWIC/Concordancia   : {d.get('concordancia_docs')} docs cargados")
        resultados["servidor_local"] = "OK"
    else:
        print(f"  [FALLO] HTTP {r.status_code}")
        resultados["servidor_local"] = f"HTTP {r.status_code}"
except Exception as e:
    print(f"  [FALLO] No responde: {e}")
    resultados["servidor_local"] = f"ERROR: {e}"

# ─────────────────────────────────────────────────────────────────
# 2. API NVIDIA — Key de test_ia.py (RAG)
# ─────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print(" [2] VERIFICANDO API NVIDIA (key: test_ia.py)")
print("="*55)
try:
    res = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {NVIDIA_KEY_TEST}", "Accept": "application/json"},
        json={
            "model": "minimaxai/minimax-m3",
            "messages": [{"role": "user", "content": "Responde solo con: OK"}],
            "temperature": 0.1,
            "max_tokens": 10,
            "stream": False
        },
        timeout=20
    )
    if res.status_code == 200:
        resp = res.json()["choices"][0]["message"]["content"].strip()
        print(f"  [OK] NVIDIA responde: \"{resp}\"")
        resultados["nvidia_key_rag"] = "OK"
    else:
        print(f"  [FALLO] HTTP {res.status_code}: {res.text[:300]}")
        resultados["nvidia_key_rag"] = f"HTTP {res.status_code}"
except Exception as e:
    print(f"  [FALLO] {e}")
    resultados["nvidia_key_rag"] = f"ERROR: {e}"

# ─────────────────────────────────────────────────────────────────
# 3. API NVIDIA — Key de alimentador_ia.py (Ingesta)
# ─────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print(" [3] VERIFICANDO API NVIDIA (key: alimentador_ia.py)")
print("="*55)
try:
    res2 = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {NVIDIA_KEY_FEEDER}", "Accept": "application/json"},
        json={
            "model": "minimaxai/minimax-m3",
            "messages": [{"role": "user", "content": "Responde solo con: ACTIVO"}],
            "temperature": 0.1,
            "max_tokens": 10,
            "stream": False
        },
        timeout=20
    )
    if res2.status_code == 200:
        resp2 = res2.json()["choices"][0]["message"]["content"].strip()
        print(f"  [OK] NVIDIA responde: \"{resp2}\"")
        resultados["nvidia_key_feeder"] = "OK"
    else:
        print(f"  [FALLO] HTTP {res2.status_code}: {res2.text[:300]}")
        resultados["nvidia_key_feeder"] = f"HTTP {res2.status_code}"
except Exception as e:
    print(f"  [FALLO] {e}")
    resultados["nvidia_key_feeder"] = f"ERROR: {e}"

# ─────────────────────────────────────────────────────────────────
# 4. Flujo RAG completo (si el servidor local está OK)
# ─────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print(" [4] VERIFICANDO FLUJO RAG COMPLETO (FTS5 -> NVIDIA)")
print("="*55)
if resultados.get("servidor_local") == "OK" and resultados.get("nvidia_key_rag") == "OK":
    try:
        # Buscar contexto local
        r_ctx = requests.get(f"{BASE}/api/buscar", params={"q": "sistema", "limite": 2}, timeout=5)
        datos = r_ctx.json()
        n_resultados = datos.get("total", 0)
        contexto = "Sin documentos en corpus aún."
        if n_resultados > 0:
            frags = []
            for doc in datos["resultados"]:
                frag = doc["fragmento"].replace("[","").replace("]","")
                frags.append(f"Doc [{doc['nombre']}]: {frag}")
            contexto = "\n".join(frags)

        print(f"  FTS5 encontró {n_resultados} resultado(s) para 'sistema'")

        # Enviar a NVIDIA con contexto
        r_ai = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_KEY_TEST}", "Accept": "application/json"},
            json={
                "model": "minimaxai/minimax-m3",
                "messages": [
                    {"role": "system", "content": f"Contexto del índice local:\n{contexto}\nResponde basándote SOLO en este contexto."},
                    {"role": "user", "content": "¿De qué trata la información en la base de datos?"}
                ],
                "temperature": 0.2,
                "max_tokens": 150,
                "stream": False
            },
            timeout=20
        )
        if r_ai.status_code == 200:
            respuesta = r_ai.json()["choices"][0]["message"]["content"].strip()
            print(f"  [OK] Respuesta RAG (primeros 200 chars):")
            print(f"  > {respuesta[:200]}")
            resultados["flujo_rag"] = "OK"
        else:
            print(f"  [FALLO] NVIDIA en flujo RAG: HTTP {r_ai.status_code}")
            resultados["flujo_rag"] = f"HTTP {r_ai.status_code}"
    except Exception as e:
        print(f"  [FALLO] {e}")
        resultados["flujo_rag"] = f"ERROR: {e}"
else:
    print("  [OMITIDO] Requiere servidor local y API NVIDIA activos.")
    resultados["flujo_rag"] = "OMITIDO"

# ─────────────────────────────────────────────────────────────────
# RESUMEN FINAL
# ─────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print(" RESUMEN DE INTEGRACIÓN DE IA")
print("="*55)
todos_ok = True
for k, v in resultados.items():
    icono = "[OK]   " if v == "OK" else "[FALLO]" if "OK" not in v else "[SKIP] "
    if v != "OK":
        todos_ok = False
    print(f"  {icono} {k:30s}: {v}")

print()
if todos_ok:
    print("  ✅ INTEGRACIÓN COMPLETA — El sistema IA está 100% operativo.")
else:
    print("  ⚠️  INTEGRACIÓN PARCIAL — Revisa los módulos marcados como FALLO.")
print()
