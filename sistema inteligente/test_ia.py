import os
import requests

# 1. Configuración
API_SISTEMA = "http://localhost:8100"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

def buscar_contexto(pregunta: str) -> str:
    """Consulta el Sistema Inteligente (Capa 1: Determinista)."""
    try:
        # Hacemos la consulta al motor FTS5 local
        res = requests.get(f"{API_SISTEMA}/api/buscar", params={"q": pregunta, "limite": 3})
        datos = res.json()
        
        if not datos.get("resultados"):
            return "No se encontró información en la base de datos local."
        
        # Unimos los fragmentos encontrados
        contexto = []
        for doc in datos["resultados"]:
            # Limpiamos los corchetes que usa FTS5 para resaltar palabras
            frag = doc["fragmento"].replace("[", "").replace("]", "") 
            contexto.append(f"Documento [{doc['nombre']}]: {frag}")
        
        return "\n".join(contexto)
    except Exception as e:
        return f"Error conectando al índice local (¿está corriendo el servidor?): {e}"


def consultar_ia(pregunta: str, contexto: str):
    """Consulta a NVIDIA AI usando el contexto (Capa 2: Generativa)."""
    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
    }
    
    # El "Prompt de Sistema" obliga a la IA a comportarse de forma segura
    prompt_sistema = f"""Eres un analista experto del sistema COPORO/COBALTO. 
Tu tarea es responder a la pregunta del usuario utilizando ÚNICAMENTE la siguiente información oficial extraída del motor determinista. 
Si la información proporcionada no contiene la respuesta, debes decir "No tengo datos suficientes en mi base de datos para responder a esto".
¡BAJO NINGÚN CONCEPTO DEBES ALUCINAR O INVENTAR INFORMACIÓN!

--- INFORMACIÓN OFICIAL ---
{contexto}
---------------------------"""

    payload = {
      "model": "minimaxai/minimax-m3",
      "messages": [
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": pregunta}
      ],
      "temperature": 0.2, # Baja temperatura para que sea analítica y exacta
      "top_p": 0.95,
      "max_tokens": 1024,
      "stream": False
    }

    response = requests.post(invoke_url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error de la IA: {response.text}"


if __name__ == "__main__":
    print("\n=======================================================")
    print(" 🤖 SISTEMA HÍBRIDO (RAG): MOTOR FTS5 + NVIDIA AI 🤖")
    print("=======================================================")
    
    pregunta = input("\nHaz una pregunta sobre tus documentos: ")
    
    print("\n[1/2] 🔍 Buscando datos exactos en el Sistema Inteligente local...")
    contexto = buscar_contexto(pregunta)
    print(f"\n--- LO QUE ENCONTRÓ EL SISTEMA LOCAL ---\n{contexto}\n----------------------------------------")
    
    print("\n[2/2] 🧠 Enviando datos a NVIDIA AI (modelo: minimax-m3) para su análisis...")
    respuesta = consultar_ia(pregunta, contexto)
    
    print("\n================ RESPUESTA FINAL ================")
    print(respuesta)
    print("=================================================\n")
