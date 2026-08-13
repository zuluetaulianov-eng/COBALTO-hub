from unittest.mock import MagicMock, patch

import pytest
from backend.services.groq_service import obtener_analisis_ia


@pytest.mark.asyncio
async def test_obtener_analisis_exitoso():
    mock_choice = MagicMock()
    mock_choice.message.content = "Análisis simulado"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("backend.services.groq_service.groq_client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response
        resultado = await obtener_analisis_ia("17JUN", "Texto de prueba.", [])
        assert resultado["analisis"] == "Análisis simulado"


@pytest.mark.asyncio
async def test_obtener_analisis_contenido():
    mock_choice = MagicMock()
    mock_choice.message.content = '{"actores": [], "amenaza": "bajo", "analisis": "Texto"}'

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("backend.services.groq_service.groq_client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response
        resultado = await obtener_analisis_ia("17JUN", "Novedad de prueba para contenido.", [])
        assert resultado["amenaza"] == "bajo"
