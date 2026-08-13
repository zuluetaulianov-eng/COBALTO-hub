import requests
import json
import uuid
import os

API_SISTEMA = "http://localhost:8100"
# Nueva API Key dedicada exclusivamente a la ingesta/mejora para no saturar las consultas
NVIDIA_API_KEY = "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"

def mejorar_y_alimentar(texto_crudo: str, nombre_referencia: str):
    """
    La IA lee el texto crudo, lo limpia, redacta un resumen semántico, 
    extrae metadatos y lo inyecta en formato impecable a la base de datos local.
    """
    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
    }
    
    prompt = f"""Eres un Agente de Ingesta y Limpieza de Datos. 
Tu trabajo es tomar el siguiente texto, corregir errores ortográficos si los hay, y estructurarlo para que sea indexado de manera óptima por un motor de búsqueda Full-Text.

Debes devolver el resultado EXACTAMENTE con esta estructura, sin agregar saludos ni comentarios:

[TÍTULO SUGERIDO]
(Escribe un título corto descriptivo)

[RESUMEN SEMÁNTICO]
(Escribe un resumen de 2 o 3 líneas del contenido)

[CONTENIDO LIMPIO]
(El texto corregido y bien formateado)

--- TEXTO DE ENTRADA ---
{texto_crudo}
------------------------"""

    payload = {
      "model": "minimaxai/minimax-m3",
      "messages": [
        {"role": "system", "content": "Eres un asistente de estructuración de datos. Respondes solo con la estructura solicitada."},
        {"role": "user", "content": prompt}
      ],
      "temperature": 0.2, # Muy analítico
      "top_p": 0.95,
      "max_tokens": 4096,
      "stream": False
    }

    print(f"\n[🧠] La IA está procesando, limpiando y estructurando '{nombre_referencia}'...")
    res = requests.post(invoke_url, headers=headers, json=payload)
    
    if res.status_code == 200:
        texto_mejorado = res.json()["choices"][0]["message"]["content"]
        
        # Ahora, inyectamos el resultado limpio a tu sistema determinista
        print("[💾] Inyectando conocimiento estructurado al Sistema Inteligente local...")
        
        doc_id = f"ia_digest_{uuid.uuid4().hex[:6]}"
        ingesta_payload = {
            "texto": texto_mejorado,
            "doc_id": doc_id
        }
        
        try:
            r_ingesta = requests.post(f"{API_SISTEMA}/api/indexar/texto", json=ingesta_payload)
            if r_ingesta.status_code == 200:
                print(f"[✅] ¡Éxito! Documento '{doc_id}' ingerido en la base de datos local.")
                print(f"El sistema ha asimilado la información y actualizado sus motores (TF-IDF y KWIC).")
            else:
                print("[ERROR] Falló la base de datos local:", r_ingesta.text)
        except Exception as e:
            print(f"[ERROR] No se pudo contactar al servidor local en {API_SISTEMA}: {e}")
    else:
        print("[ERROR] La IA falló al procesar el texto:", res.text)


if __name__ == "__main__":
    print("\n==========================================================")
    print(" 🛠️ ALIMENTADOR DE CONOCIMIENTO IA (vía NVIDIA) 🛠️")
    print("==========================================================")
    print("Este módulo usa una API Key independiente para no saturar")
    print("el agente de respuestas. Su único trabajo es digerir textos")
    print("crudos y guardarlos de forma perfecta en tu base de datos.\n")
    
    print("Opciones:")
    print("1. Escribir/pegar un texto corto directamente.")
    print("2. Leer un archivo .txt local.")
    
    opcion = input("\nElige una opción (1 o 2): ").strip()
    
    if opcion == "1":
        texto = input("\nPega tu texto aquí: ")
        if texto.strip():
            mejorar_y_alimentar(texto, "Texto Manual")
    elif opcion == "2":
        ruta = input("\nEscribe la ruta exacta del archivo .txt (ej. C:\\datos\\informe.txt): ").strip()
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                texto = f.read()
            mejorar_y_alimentar(texto, os.path.basename(ruta))
        else:
            print(f"[ERROR] No se encontró el archivo: {ruta}")
    else:
        print("Opción inválida.")
