# router.py - FastAPI Router para Venezuela Noticias (Repositorio Independiente)

import logging
import os
import secrets
import time
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.responses import Response as FastAPIResponse
from fastapi.templating import Jinja2Templates

import venezuela_noticias as vn

router = APIRouter(tags=["Venezuela Noticias"])
logger = logging.getLogger("router")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "vn")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_token_from_request(request: Request) -> str:
    """Extrae el token de autenticación desde cookies o cabeceras."""
    token = request.cookies.get("vn_token") or request.cookies.get("token", "")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
    return token


def require_admin_auth(request: Request, required_role: str = "reporter") -> dict:
    """Verifica autenticación y permisos de rol (admin vs reporter)."""
    token = get_token_from_request(request)
    auth_data = vn.verify_admin_token(token)
    if not auth_data:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=401, detail="No autorizado. Inicie sesión en /vn-login")
        raise HTTPException(status_code=401, detail="Sesión expirada o no autorizada")

    user_role = auth_data.get("role", "reporter")
    if required_role == "admin" and user_role != "admin":
        raise HTTPException(status_code=403, detail="Permiso denegado. Función reservada exclusivamente para Administradores.")

    return auth_data


# ── PORTAL PÚBLICO (HTML, API & RSS) ───────────────────────────

@router.get("/noticias", response_class=HTMLResponse)
async def public_news_home(request: Request):
    """Página principal del portal público de Venezuela Noticias."""
    templates: Jinja2Templates = request.app.state.templates if hasattr(request.app.state, "templates") else Jinja2Templates(directory="templates")
    articles = vn.get_published_articles(limit=25)
    featured = vn.get_featured_article()
    return templates.TemplateResponse(
        "venezuela_noticias/index.html",
        {
            "request": request,
            "articles": articles,
            "featured": featured,
            "active_category": "ALL"
        }
    )


@router.get("/noticias/articulo/{slug}", response_class=HTMLResponse)
async def public_news_single(request: Request, slug: str):
    """Vista ampliada de un artículo de noticias específico."""
    templates: Jinja2Templates = request.app.state.templates if hasattr(request.app.state, "templates") else Jinja2Templates(directory="templates")
    article = vn.get_article_by_slug(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    related = vn.get_published_articles(category=article.get("category"), limit=4)
    related = [a for a in related if a["slug"] != slug]
    return templates.TemplateResponse(
        "venezuela_noticias/single.html",
        {
            "request": request,
            "article": article,
            "related": related
        }
    )


@router.get("/api/vn/articles")
async def api_get_published_articles(
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """API JSON pública para consultar noticias publicadas."""
    articles = vn.get_published_articles(category=category, query=q, limit=limit, offset=offset)
    return JSONResponse({"status": "ok", "count": len(articles), "articles": articles})


@router.get("/api/vn/featured")
async def api_get_featured_article():
    """API JSON para consultar la noticia destacada principal."""
    featured = vn.get_featured_article()
    return JSONResponse({"status": "ok", "featured": featured})


@router.get("/noticias/rss.xml", response_class=FastAPIResponse)
async def public_news_rss():
    """Feed RSS 2.0 en XML del portal público de Venezuela Noticias."""
    articles = vn.get_published_articles(limit=30)
    items_xml = []
    for a in articles:
        pub_date = a.get("published_at", "")
        link = f"/noticias/articulo/{a.get('slug')}"
        summary_clean = (a.get("summary") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        title_clean = (a.get("title") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        items_xml.append(
            f"<item><title>{title_clean}</title><link>{link}</link><guid>{link}</guid>"
            f"<description>{summary_clean}</description><pubDate>{pub_date}</pubDate>"
            f"<category>{a.get('category', 'Nacional')}</category></item>"
        )

    items_str = "\n".join(items_xml)
    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        '<rss version="2.0">\n'
        '<channel>\n'
        '    <title>Venezuela Noticias — Feed Oficial</title>\n'
        '    <link>/noticias</link>\n'
        '    <description>Portal Informativo Autónomo Multicanal</description>\n'
        '    <language>es</language>\n'
        f'    {items_str}\n'
        '</channel>\n'
        '</rss>'
    )
    return FastAPIResponse(content=rss_xml, media_type="application/xml")


@router.post("/api/vn/inbox/push")
async def api_push_remote_entries(request: Request):
    """Endpoint REST API para recibir noticias enviadas remotamente por HTTP."""
    api_key_env = os.getenv("VN_API_KEY", "")
    if api_key_env:
        sent_key = request.headers.get("X-VN-API-Key") or request.query_params.get("api_key", "")
        if sent_key != api_key_env:
            raise HTTPException(status_code=401, detail="API Key inválida para Venezuela Noticias")
    try:
        data = await request.json()
        entries = data if isinstance(data, list) else [data]
        imported = vn.sync_cobalto_entries_to_inbox(entries)
        return JSONResponse({"status": "ok", "imported": imported, "received": len(entries)})
    except Exception as e:
        logger.exception(f"Error en /api/vn/inbox/push: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ── LOGIN & AUTENTICACIÓN ADMIN ─────────────────────────────

@router.get("/vn-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Página de inicio de sesión para administradores y reporteros."""
    templates: Jinja2Templates = request.app.state.templates if hasattr(request.app.state, "templates") else Jinja2Templates(directory="templates")
    return templates.TemplateResponse("venezuela_noticias/login.html", {"request": request})


@router.post("/api/vn-admin/login")
async def api_admin_login(request: Request, response: Response):
    """Procesa las credenciales de inicio de sesión."""
    try:
        data = await request.json()
        username = data.get("username", "")
        password = data.get("password", "")

        user_info = vn.verify_admin_credentials(username, password)
        if not user_info:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        token = vn.create_admin_token(user_info["username"], role=user_info["role"])
        res = JSONResponse({
            "status": "ok",
            "token": token,
            "username": user_info["username"],
            "role": user_info["role"]
        })
        res.set_cookie(key="vn_token", value=token, max_age=86400, httponly=True, samesite="lax")
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error en login: {e}")
        raise HTTPException(status_code=400, detail="Petición de inicio de sesión inválida")


@router.post("/api/vn-admin/logout")
async def api_admin_logout(response: Response):
    """Cierra la sesión del administrador descartando la cookie."""
    res = JSONResponse({"status": "ok", "logout": True})
    res.delete_cookie(key="vn_token")
    return res


# ── GESTIÓN DE USUARIOS Y CONFIGURACIÓN (RESERVADO ADMIN) ────

@router.get("/api/vn-admin/users")
async def api_get_users(request: Request):
    """Obtiene la lista de usuarios del sistema (Requiere rol Admin)."""
    require_admin_auth(request, required_role="admin")
    users = vn.get_all_users()
    return JSONResponse({"status": "ok", "users": users})


@router.post("/api/vn-admin/users")
async def api_create_user(request: Request):
    """Crea un nuevo usuario Administrador o Reportero (Requiere rol Admin)."""
    require_admin_auth(request, required_role="admin")
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    full_name = data.get("full_name", "")
    role = data.get("role", "reporter")

    try:
        new_user = vn.create_user(username=username, password=password, full_name=full_name, role=role)
        return JSONResponse({"status": "ok", "user": new_user})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/vn-admin/users/{user_id}")
async def api_delete_user(user_id: int, request: Request):
    """Elimina un usuario del sistema (Requiere rol Admin)."""
    require_admin_auth(request, required_role="admin")
    try:
        deleted = vn.delete_user(user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return JSONResponse({"status": "ok", "deleted": True})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/vn-admin/users/{user_id}/role")
async def api_update_user_role(user_id: int, request: Request):
    """Actualiza el rol de un usuario (Requiere rol Admin)."""
    require_admin_auth(request, required_role="admin")
    data = await request.json()
    new_role = data.get("role", "reporter")
    updated = vn.update_user_role(user_id, new_role)
    if not updated:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o rol inválido")
    return JSONResponse({"status": "ok", "updated": True})


# ── PANEL DE ADMINISTRACIÓN CMS (PROTEGIDO POR ROLES) ─────────

@router.get("/vn-admin", response_class=HTMLResponse)
async def admin_cms_home(request: Request):
    """Panel de Control CMS para Venezuela Noticias."""
    token = get_token_from_request(request)
    auth_data = vn.verify_admin_token(token)
    if not auth_data:
        return RedirectResponse(url="/vn-login", status_code=303)

    templates: Jinja2Templates = request.app.state.templates if hasattr(request.app.state, "templates") else Jinja2Templates(directory="templates")
    inbox = vn.get_cobalto_inbox(status="pending", limit=50)
    published = vn.get_published_articles(limit=50)
    users = vn.get_all_users() if auth_data.get("role") == "admin" else []

    return templates.TemplateResponse(
        "venezuela_noticias/admin.html",
        {
            "request": request,
            "inbox": inbox,
            "published": published,
            "users": users,
            "current_user": auth_data
        }
    )


@router.get("/api/vn-admin/inbox")
async def api_get_inbox(request: Request):
    """API JSON para consultar la bandeja de entrada pendiente (Admin / Reportero)."""
    require_admin_auth(request, required_role="reporter")
    inbox = vn.get_cobalto_inbox(status="pending", limit=100)
    return JSONResponse({"status": "ok", "count": len(inbox), "inbox": inbox})


@router.get("/api/vn-admin/inbox/inspect/{inbox_id}")
async def api_inspect_inbox(inbox_id: int, request: Request):
    """Inspecciona una noticia del inbox antes de aprobar, intentando extracción profunda si aplica."""
    require_admin_auth(request, required_role="reporter")
    conn = vn.get_vn_db_connection()
    try:
        row = conn.execute("SELECT * FROM vn_cobalto_inbox WHERE id = ?", (inbox_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Elemento no encontrado")
        item = dict(row)
        item["suggested_category"] = vn.auto_detect_category(item.get("title", ""), item.get("summary", ""))
        return JSONResponse({"status": "ok", "item": item})
    finally:
        conn.close()


@router.post("/api/vn-admin/inbox/approve/{inbox_id}")
async def api_approve_inbox(inbox_id: int, request: Request):
    """Aprobar un elemento de la bandeja e ingresarlo como noticia publicada (Exclusivo Superadmin)."""
    auth_data = require_admin_auth(request, required_role="admin")
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    
    category = body.get("category")
    custom_title = body.get("title")
    custom_summary = body.get("summary")
    custom_content = body.get("content")
    custom_image_url = body.get("image_url")
    custom_video_url = body.get("video_url")

    article = vn.approve_inbox_item(
        inbox_id=inbox_id,
        custom_category=category,
        custom_title=custom_title,
        custom_summary=custom_summary,
        custom_content=custom_content,
        custom_image_url=custom_image_url,
        custom_video_url=custom_video_url,
        author_name=auth_data.get("username", "Redacción VN")
    )
    if not article:
        raise HTTPException(status_code=404, detail="Elemento no encontrado en bandeja de entrada")
    return JSONResponse({"status": "ok", "article": article})


@router.post("/api/vn-admin/inbox/reject/{inbox_id}")
async def api_reject_inbox(inbox_id: int, request: Request):
    """Rechazar y descartar un elemento de la bandeja (Exclusivo Superadmin)."""
    require_admin_auth(request, required_role="admin")
    success = vn.reject_inbox_item(inbox_id)
    if not success:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    return JSONResponse({"status": "ok", "rejected": True})


@router.post("/api/vn-admin/articles")
async def api_create_article(request: Request):
    """Creación manual de un nuevo artículo desde el panel CMS Admin (Admin / Reportero)."""
    auth_data = require_admin_auth(request, required_role="reporter")
    data = await request.json()
    title = data.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="El título es obligatorio")

    article = vn.create_article(
        title=title,
        summary=data.get("summary", ""),
        content=data.get("content", ""),
        category=data.get("category", "Nacional"),
        image_url=data.get("image_url", ""),
        video_url=data.get("video_url", ""),
        source_name=data.get("source_name", "Redacción VN"),
        canonical_url=data.get("canonical_url", ""),
        is_featured=bool(data.get("is_featured", False)),
        status="published",
        author_name=auth_data.get("username", "Redacción VN")
    )
    return JSONResponse({"status": "ok", "article": article})


@router.put("/api/vn-admin/articles/{article_id}")
async def api_update_article(article_id: int, request: Request):
    """Edita un artículo existente (Administradores o Autor Reportero propietario)."""
    auth_data = require_admin_auth(request, required_role="reporter")
    existing = vn.get_article_by_id(article_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    if auth_data.get("role") != "admin" and existing.get("author_name") != auth_data.get("username"):
        raise HTTPException(status_code=403, detail="Permiso denegado. Los reporteros solo pueden editar sus propias noticias.")

    data = await request.json()
    title = data.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="El título es obligatorio")

    updated = vn.update_article(
        article_id=article_id,
        title=title,
        summary=data.get("summary", ""),
        content=data.get("content", ""),
        category=data.get("category", "Nacional"),
        image_url=data.get("image_url", ""),
        video_url=data.get("video_url", "")
    )
    return JSONResponse({"status": "ok", "article": updated})


@router.delete("/api/vn-admin/articles/{article_id}")
async def api_delete_article(article_id: int, request: Request):
    """Eliminar un artículo publicado (Administradores o Autor Reportero propietario)."""
    auth_data = require_admin_auth(request, required_role="reporter")
    existing = vn.get_article_by_id(article_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    if auth_data.get("role") != "admin" and existing.get("author_name") != auth_data.get("username"):
        raise HTTPException(status_code=403, detail="Permiso denegado. Los reporteros solo pueden eliminar sus propias noticias.")

    success = vn.delete_article(article_id)
    return JSONResponse({"status": "ok", "deleted": success})


@router.post("/api/vn-admin/upload")
async def api_upload_media(request: Request, file: UploadFile = File(...)):
    """Subida directa de imágenes y videos locales para artículos redactados por reporteros/usuarios."""
    require_admin_auth(request, required_role="reporter")
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Formato no permitido. Extensiones soportadas: {', '.join(allowed_exts)}")

    filename = f"vn_{int(time.time())}_{secrets.token_hex(4)}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    try:
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        url = f"/static/uploads/vn/{filename}"
        return JSONResponse({"status": "ok", "url": url, "filename": filename})
    except Exception as e:
        logger.exception(f"Error subiendo archivo multimedia: {e}")
        raise HTTPException(status_code=500, detail="Error guardando archivo multimedia")
