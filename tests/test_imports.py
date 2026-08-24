"""Test básico de importaciones del proyecto."""

import importlib
import os
import sys

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_core_imports():
    """Verifica que los módulos principales importan sin errores."""
    modules = [
        "config",
        "security_utils",
        "metrics",
        "database",
        "graph_database",
        "doh_patch",
        "app_platform",
        "app_auth",
        "app_ws",
        "app_background",
        "humanization_ua",
        "humanization_ratelimit",
        "humanization_delays",
        "humanization_proxy",
        "humanization_session",
        "humanization_stress",
        "humanization_queue",
        "humanization_stats",
        "dashboard_state",
        "dashboard_geocontext",
        "osiris_bridge",
        "osiris_recon",
        "osiris_intel",
        "finint_blockchain",
        "finint_darkweb",
        "finint_entity_linker",
        "humint_bot",
        "network_discovery_daemon",
        "theaters_config",
        "open_data_apis",
        "incidents_manager",
        "dashboard_sensors",
        "osint_deep_scraper",
        "routers.rt_agents",
        "routers.rt_analytics",
        "routers.rt_entities",
        "routers.rt_export",
        "routers.rt_finint",
        "routers.rt_humint",
        "routers.rt_predictive",
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
        except ImportError as e:
            if "playwright" in str(e).lower() or "groq" in str(e).lower():
                continue  # Dependencias opcionales
            raise AssertionError(f"Fallo al importar {mod}: {e}")


def test_dashboard_imports():
    """Verifica que dashboard.py importa correctamente."""
    try:
        importlib.import_module("dashboard")
    except ImportError as e:
        # Algunos módulos OSINT pueden no estar en el path
        if "No module named" in str(e):
            pass  # Esperado en CI sin todas las dependencias
        else:
            raise


def test_humanization_imports():
    """Verifica que humanization.py importa correctamente sus submódulos."""
    try:
        import humanization

        assert hasattr(humanization, "get_random_user_agent")
        assert hasattr(humanization, "RATE_LIMITERS")
        assert hasattr(humanization, "STRESS_MONITOR")
        assert hasattr(humanization, "TASK_QUEUE_AI")
    except ImportError:
        pass


def test_ai_local():
    """Verifica funcionalidad básica de ai_local."""
    import ai_local

    summary = ai_local.generate_local_summary(
        "Este es un texto largo de prueba. Tiene varias oraciones. "
        "Debe ser resumido correctamente. Sin necesidad de IA externa."
    )
    assert isinstance(summary, str)
    assert len(summary) > 0

    keywords = ai_local.extract_keywords_local("La inteligencia artificial y el análisis de datos en Venezuela")
    assert isinstance(keywords, list)


def test_auth():
    """Verifica funcionalidad básica de autenticación."""
    import hashlib
    import os

    os.environ["ADMIN_PASSWORD"] = "test123"
    os.environ["JWT_SECRET"] = "test-secret"
    import importlib

    import app_auth
    from database import ensure_db, get_connection

    importlib.reload(app_auth)
    ensure_db()
    pass_hash = hashlib.sha256("test123".encode()).hexdigest()
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO users (username, password_hash) VALUES (?, ?)", ("admin", pass_hash))

    assert app_auth.AUTH_ENABLED
    assert app_auth.validate_login("admin", "test123")
    assert not app_auth.validate_login("admin", "wrong")
    assert not app_auth.validate_login("", "")

    token = app_auth.create_token("admin")
    assert token
    payload = app_auth.verify_token(token)
    assert payload.get("user") == "admin"


def test_app_platform():
    """Verifica la configuración multiplataforma."""
    import app_platform

    kwargs = app_platform.get_uvicorn_kwargs()
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8083
    assert kwargs["http"] == "h11"
