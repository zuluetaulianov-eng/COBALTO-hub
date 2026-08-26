"""
EJEMPLO DE USO (Módulo de IA Exportado)
=======================================
Ejecuta este archivo para comprobar la generación de reportes y debate con CometAPI.
"""

import asyncio
import json

from ai_engine import ask_ai
from report_generator import generar_debate_multiagente, generar_informe_masivo, generar_informe_sitrep


async def main():
    print("=== 1. Prueba de Inferencia Básica (CometAPI) ===")
    respuesta = await ask_ai("Responde con una frase de bienvenida militar.", json_mode=False)
    print(f"Respuesta IA: {respuesta}\n")

    print("=== 2. Generación de Informe SITREP Estructurado ===")
    informe = await generar_informe_sitrep(
        titulo="Movilización de patrullas fluviales en la frontera",
        contenido="Se reporta un incremento del 20% en patrullajes fluviales por unidades combinadas en el sector fronterizo.",
        fuente="Monitoreo C4I",
    )
    print("Informe JSON Generado:")
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    print("\n")

    print("=== 3. Prueba de Debate Multi-Agente ===")
    noticias_prueba = [
        {"titulo": "Reportan interrupción de servicios de energía", "contenido": "Caída del servicio eléctrico afectando telecomunicaciones en 3 municipios."},
        {"titulo": "Reunión binacional de seguridad", "contenido": "Autoridades sostienen reunión táctica para coordinar respuesta de emergencia."},
    ]
    debate = await generar_debate_multiagente(noticias_prueba)
    print("Resultado del Debate Multi-Agente:")
    print(json.dumps(debate, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
