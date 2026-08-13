# ==========================================
#  COBALTO HUB v9.0 - DOCKERFILE MULTIPROPÓSITO
# ==========================================
# Imagen base oficial ligera con Python 3.11
FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc y forzar salida en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema requeridas para psutil, playwright y DoH
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    procps \
    build-essential \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de dependencias e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright directamente en el build layer
RUN python -m playwright install chromium

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto del servidor web FastAPI
EXPOSE 8083

# Por defecto, el contenedor puede ser sobreescrito para correr el servidor o el worker
CMD ["python", "app.py"]
