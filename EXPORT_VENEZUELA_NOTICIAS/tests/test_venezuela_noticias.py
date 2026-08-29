# tests/test_venezuela_noticias.py - Suite de pruebas para Venezuela Noticias Standalone

import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from main import app  # noqa: E402

import venezuela_noticias as vn  # noqa: E402

client = TestClient(app)


def test_vn_database_initialization():
    vn.init_vn_db()
    assert os.path.exists(vn.VN_DB_PATH)


def test_article_crud_flow():
    article = vn.create_article(
        title="Noticia de Prueba Standalone",
        summary="Resumen de prueba",
        content="Contenido extenso",
        category="Economía",
        is_featured=True
    )
    assert article["id"] > 0
    assert "slug" in article

    fetched = vn.get_article_by_slug(article["slug"])
    assert fetched is not None
    assert fetched["title"] == "Noticia de Prueba Standalone"

    published = vn.get_published_articles(category="Economía")
    assert len(published) >= 1
    deleted = vn.delete_article(article["id"])
    assert deleted is True


def test_remote_push_and_inbox():
    unique_link = f"https://example.com/noticia-{int(time.time() * 1000)}"
    push_data = [
        {
            "title": "Noticia enviada desde COBALTO via HTTP REST API",
            "summary": "Resumen transmitido remotamente",
            "link": unique_link,
            "image": "https://example.com/img.jpg",
            "source": "COBALTO HUB"
        }
    ]
    res_push = client.post("/api/vn/inbox/push", json=push_data)
    assert res_push.status_code == 200
    assert res_push.json().get("imported") == 1

    inbox = vn.get_cobalto_inbox(status="pending")
    assert len(inbox) >= 1

    inbox_id = inbox[0]["id"]
    approved = vn.approve_inbox_item(inbox_id, custom_category="Nacional")
    assert approved is not None


def test_admin_auth_and_login_flow():
    # 1. Sin autenticación -> redirección en HTML a /vn-login
    res_admin_unauth = client.get("/vn-admin", follow_redirects=False)
    assert res_admin_unauth.status_code == 303
    assert "/vn-login" in res_admin_unauth.headers.get("location", "")

    # 2. Login con credenciales inválidas -> 401
    res_bad_login = client.post("/api/vn-admin/login", json={"username": "admin", "password": "wrongpassword"})
    assert res_bad_login.status_code == 401

    # 3. Login con credenciales válidas -> 200 + token + cookie
    res_login = client.post("/api/vn-admin/login", json={"username": "admin", "password": "admin"})
    assert res_login.status_code == 200
    token = res_login.json().get("token")
    assert token is not None

    # 4. Acceso con token a /vn-admin -> 200 OK
    client.cookies.set("vn_token", token)
    res_admin_auth = client.get("/vn-admin")
    assert res_admin_auth.status_code == 200
    assert "CMS ADMIN" in res_admin_auth.text


def test_user_management_and_rbac_flow():
    # Login como Admin principal
    res_login = client.post("/api/vn-admin/login", json={"username": "admin", "password": "admin"})
    admin_token = res_login.json()["token"]
    client.cookies.set("vn_token", admin_token)

    # 1. Crear nuevo usuario Reportero
    uname = f"reporter_{int(time.time())}"
    res_create = client.post("/api/vn-admin/users", json={
        "username": uname,
        "full_name": "Reportero Test",
        "password": "reporterpass123",
        "role": "reporter"
    })
    assert res_create.status_code == 200
    new_user = res_create.json()["user"]
    assert new_user["role"] == "reporter"

    # 2. Login como el nuevo Reportero
    res_rep_login = client.post("/api/vn-admin/login", json={"username": uname, "password": "reporterpass123"})
    assert res_rep_login.status_code == 200
    rep_token = res_rep_login.json()["token"]
    assert res_rep_login.json()["role"] == "reporter"

    # 3. Reportero intenta acceder a API de gestión de usuarios -> 403 Forbidden
    client.cookies.set("vn_token", rep_token)
    res_forbidden = client.get("/api/vn-admin/users")
    assert res_forbidden.status_code == 403

    # 4. Admin crea una noticia A_Admin
    client.cookies.set("vn_token", admin_token)
    art_admin_res = client.post("/api/vn-admin/articles", json={"title": "Noticia de Admin"})
    art_admin = art_admin_res.json()["article"]

    # Reportero crea una noticia A_Reporter
    client.cookies.set("vn_token", rep_token)
    art_rep_res = client.post("/api/vn-admin/articles", json={"title": "Noticia de Reportero"})
    art_rep = art_rep_res.json()["article"]

    # 4b. Reportero intenta editar y borrar noticia de Admin -> 403 Forbidden
    res_edit_forbidden = client.put(f"/api/vn-admin/articles/{art_admin['id']}", json={"title": "Hack Titulo"})
    assert res_edit_forbidden.status_code == 403

    res_del_forbidden = client.delete(f"/api/vn-admin/articles/{art_admin['id']}")
    assert res_del_forbidden.status_code == 403

    # 4c. Reportero edita y borra su propia noticia -> 200 OK
    res_edit_own = client.put(f"/api/vn-admin/articles/{art_rep['id']}", json={"title": "Noticia de Reportero Editada"})
    assert res_edit_own.status_code == 200
    assert res_edit_own.json()["article"]["title"] == "Noticia de Reportero Editada"

    res_del_own = client.delete(f"/api/vn-admin/articles/{art_rep['id']}")
    assert res_del_own.status_code == 200

    # 4d. Reportero intenta dar visto bueno a la bandeja de entrada -> 403 Forbidden (Reservado Superadmin)
    res_app_forbidden = client.post("/api/vn-admin/inbox/approve/999")
    assert res_app_forbidden.status_code == 403

    # 5. Volver a Admin y cambiar rol a admin
    client.cookies.set("vn_token", admin_token)
    res_role = client.put(f"/api/vn-admin/users/{new_user['id']}/role", json={"role": "admin"})
    assert res_role.status_code == 200

    # 6. Eliminar noticia de Admin y usuario
    client.delete(f"/api/vn-admin/articles/{art_admin['id']}")
    res_del = client.delete(f"/api/vn-admin/users/{new_user['id']}")
    assert res_del.status_code == 200


def test_fastapi_endpoints():
    res_news = client.get("/noticias")
    assert res_news.status_code == 200
    assert "VENEZUELA NOTICIAS" in res_news.text

    res_login_page = client.get("/vn-login")
    assert res_login_page.status_code == 200
    assert "Acceso Panel de Administración" in res_login_page.text

    res_rss = client.get("/noticias/rss.xml")
    assert res_rss.status_code == 200
    assert "application/xml" in res_rss.headers.get("content-type", "")
