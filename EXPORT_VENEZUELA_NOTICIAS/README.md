# 🇻🇪 Venezuela Noticias — Portal Informativo & CMS Autónomo

**Venezuela Noticias** es una plataforma web independiente, moderna y ligera para la publicación, curaduría y distribución de información en tiempo real sobre Venezuela y la región.

Diseñado con arquitectura desacoplada y alta estética visual ciberpunk-táctica, incluye un **portal público responsivo**, un **sistema CMS de administración con control de acceso basado en roles (RBAC)**, distribución vía **Feed RSS 2.0 XML** y una **API REST de ingesta remota**.

---

## 🌟 Características Principales

- **Portal Público (`/noticias`)**: Interfaz táctica con ticker de última hora, hero de noticia destacada, reproducción de video embebido (YouTube, Vimeo, TikTok, MP4), buscador dinámico y filtrado instantáneo por categorías.
- **Lectura de Artículo (`/noticias/articulo/{slug}`)**: Vista de lectura limpia con slugs semánticos amigables con SEO, metadatos de autoría y botones de interacción social (WhatsApp, Telegram, Copiar Enlace).
- **Feed RSS 2.0 (`/noticias/rss.xml`)**: Generación dinámica en estándar XML para distribución automática a bots de Telegram, agregadores o lectores RSS.
- **Sistema CMS de Administración (`/vn-admin`)**: Panel con métricas KPI, bandeja de ingesta de noticias sugeridas y creador/editor de artículos.
- **Control de Acceso basado en Roles (RBAC) y Moderación por Autoría**:
  - 👑 **Superadministrador / Administradores**: Acceso total al sistema, aprobación/descarte exclusivo de noticias de la bandeja de entrada (Visto Bueno), gestión de usuarios y moderación/edición/borrado de cualquier noticia.
  - ✍️ **Reporteros**: Creación de noticias propias y permiso de edición/eliminación **únicamente sobre sus propios artículos**. Intento de modificación sobre contenido ajeno es rechazado con `403 Forbidden`.
- **Gestión de Usuarios y Credenciales**: Panel para registrar reporteros y administradores, con cambio de roles y autenticación JWT segura.
- **Ingesta Remota REST API (`POST /api/vn/inbox/push`)**: Endpoint para recibir sugerencias de noticias desde COBALTO HUB u otros agentes externos vía HTTP JSON en segundo plano.

---

## 📁 Estructura del Proyecto

```
EXPORT_VENEZUELA_NOTICIAS/
├── venezuela_noticias.py       # Aplicación FastAPI + orquestador independiente
├── router.py                  # Router de endpoints API REST & vistas Jinja2
├── data/
│   └── venezuela_noticias.db   # Base de datos SQLite persistente (Artículos, Inbox, Usuarios)
├── static/
│   ├── css/
│   │   └── dashboard.css       # Estilos globales y temas tácticos
│   └── img/
│       └── vn_logo.png         # Logo oficial de Venezuela Noticias
├── templates/
│   └── venezuela_noticias/
│       ├── index.html          # Portal público principal
│       ├── single.html         # Vista de noticia individual
│       ├── admin.html          # Dashboard CMS con RBAC
│       └── login.html          # Pantalla de inicio de sesión
├── tests/
│   └── test_venezuela_noticias.py # Suite de pruebas automatizadas con pytest
├── iniciar_venezuela_noticias.bat # Lanzador 1-Clic para Windows
├── requirements.txt           # Dependencias Python (FastAPI, Uvicorn, PyJWT, Passlib, etc.)
└── README.md                  # Documentación oficial del proyecto
```

---

## 🚀 Instalación y Ejecución Rápida

### 1. Requisitos Previos
- Python 3.11 o superior.

### 2. Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 3. Iniciar el Servidor (Windows 1-Clic)
Simplemente haz doble clic en el archivo `iniciar_venezuela_noticias.bat` o ejecútalo desde la consola CMD/PowerShell:
```cmd
iniciar_venezuela_noticias.bat
```

### 4. Iniciar mediante Línea de Comandos
```bash
python venezuela_noticias.py --port 8000
```

Navega a:
- 🌐 **Portal Público**: `http://localhost:8000/noticias`
- ⚙️ **CMS Admin**: `http://localhost:8000/vn-admin`
- 🔐 **Inicio de Sesión**: `http://localhost:8000/vn-login`
- 📡 **Feed RSS XML**: `http://localhost:8000/noticias/rss.xml`

*Credencial Administrador Inicial:*
- **Usuario:** `admin`
- **Contraseña:** `admin` (o la credencial principal configurada).

---

## 🔌 Ingesta Remota desde COBALTO HUB

Venezuela Noticias funciona **100% de forma autónoma sin depender de COBALTO HUB**. Sin embargo, cuando COBALTO HUB está encendido, puede enviar sugerencias de noticias directamente a la bandeja de entrada de curaduría enviando un `POST` JSON a `/api/vn/inbox/push`:

```bash
curl -X POST http://localhost:8000/api/vn/inbox/push \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Avances en la infraestructura nacional",
    "summary": "Resumen ejecutivo del informe recibido...",
    "link": "https://fuente.com/noticia",
    "source": "COBALTO OSINT Agent"
  }'
```

*(Las noticias enviadas desde COBALTO permanecen en la bandeja en estado `pending` a la espera del visto bueno del Superadministrador).*

---

## 🧪 Pruebas Unitarias & Cobertura

Para ejecutar la suite de pruebas unitarias automatizadas:

```bash
python -m pytest tests/test_venezuela_noticias.py -v
```

Las pruebas validan la inicialización del esquema SQLite, operaciones CRUD de artículos, ingesta remota, autenticación JWT, flujo RBAC (autoría y roles) y renderizado de endpoints FastAPI.

---

## 📄 Licencia

Licencia MIT — Desarrollado para difusión informativa libre e independiente.
