import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
TOKEN_EXPIRY = int(os.getenv("TOKEN_EXPIRY_HOURS", "24")) * 3600

AUTH_ENABLED = bool(ADMIN_PASSWORD)

PUBLIC_PATHS = {
    "/login",
    "/api/login",
    "/api/health",
    "/api/forgot-password",
    "/static",
    "/manifest.json",
    "/service-worker.js",
    "/metrics",
    "/api/startup-progress",
    "123.png",
    "favicon.ico",
    "cortana.bmp",
}

PUBLIC_PREFIXES = {"/static/", "/api/login", "/api/forgot-password", "/noticias", "/api/vn", "/vn-login", "/vn-admin"}


def _b64_encode(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64_decode(s: str) -> dict:
    padded = s + "=" * (4 - len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def create_token(username: str) -> str:
    expiry = time.time() + TOKEN_EXPIRY
    payload = {"user": username, "exp": expiry, "jti": secrets.token_hex(8)}
    encoded = _b64_encode(payload)
    sig = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def verify_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return {}
        encoded, sig = parts
        expected = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return {}
        payload = _b64_decode(encoded)
        if payload.get("exp", 0) < time.time():
            return {}
        return payload
    except Exception:
        return {}


def get_token_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    cookie = request.cookies.get("token", "")
    if cookie:
        return cookie
    return ""


async def auth_middleware(request: Request, call_next):
    if not AUTH_ENABLED:
        return await call_next(request)
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    token = get_token_from_request(request)
    payload = verify_token(token)
    if not payload:
        if path.startswith("/api/"):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        from fastapi.responses import HTMLResponse

        return HTMLResponse(LOGIN_PAGE, status_code=401)
    request.state.user = payload.get("user", "unknown")
    return await call_next(request)


def validate_login(username: str, password: str) -> bool:
    if not AUTH_ENABLED:
        return True
    if not username or not password:
        return False
    from database import verify_user
    return verify_user(username, password)


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>COBALTO HUB - Acceso</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
@import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&display=swap');
body{
  background:#0A0B10;color:#00E5FF;
  font-family:'Roboto Mono',monospace;
  display:flex;align-items:center;justify-content:center;
  height:100vh;overflow:hidden;
  background-image:radial-gradient(circle at 50% 50%,rgba(0,229,255,0.06) 0%,transparent 60%);
}
.scanline{
  position:fixed;top:0;left:0;width:100%;height:2px;
  background:linear-gradient(90deg,transparent,rgba(0,229,255,0.25),transparent);
  animation:scan 4s linear infinite;pointer-events:none;z-index:10;
}
@keyframes scan{0%{transform:translateY(-100vh)}100%{transform:translateY(100vh)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
.container{text-align:center;animation:fadeIn 0.6s ease-out;width:340px}
.ring{
  width:40px;height:40px;margin:0 auto 1.5rem;
  border:2px solid rgba(0,229,255,0.08);
  border-top-color:#00E5FF;border-right-color:rgba(0,229,255,0.3);
  border-radius:50%;animation:spin 0.8s linear infinite;
}
.title{font-size:1.3rem;font-weight:700;letter-spacing:3px;margin-bottom:0.3rem}
.subtitle{font-size:0.65rem;color:rgba(0,229,255,0.35);letter-spacing:2px;margin-bottom:2rem}
.input-group{margin-bottom:1rem;text-align:left}
label{font-size:0.7rem;color:#94A3B8;display:block;margin-bottom:0.4rem;letter-spacing:1px}
input{
  width:100%;padding:0.7rem;background:rgba(0,229,255,0.04);
  border:1px solid rgba(0,229,255,0.15);border-radius:4px;
  color:#00E5FF;font-family:'Roboto Mono',monospace;font-size:0.8rem;
  outline:none;transition:border-color 0.3s;
}
input:focus{border-color:#00E5FF}
button{
  width:100%;padding:0.7rem;margin-top:1rem;
  background:transparent;border:1px solid #00E5FF;
  color:#00E5FF;font-family:'Roboto Mono',monospace;
  font-size:0.8rem;cursor:pointer;letter-spacing:2px;
  border-radius:4px;transition:all 0.3s;
}
button:hover{background:rgba(0,229,255,0.1)}
.error{color:#ff4444;font-size:0.7rem;margin-top:0.8rem;min-height:1.2em}
</style>
</head>
<body>
<div class="scanline"></div>
<div class="container">
  <div class="ring"></div>
  <div class="title">COBALTO HUB</div>
  <div class="subtitle">v9.0 &mdash; ACCESO RESTRINGIDO</div>
  <form id="loginForm">
    <div class="input-group" style="display: none;">
      <label>USUARIO</label>
      <input type="text" id="username" value="admin" autocomplete="username">
    </div>
    <div class="input-group">
      <label>CONTRASE&Ntilde;A DE ACCESO</label>
      <input type="password" id="password" placeholder="••••••••" autocomplete="current-password" required>
    </div>
    <button type="submit">INGRESAR</button>
    <a href="#" id="forgotPasswordBtn" style="color:rgba(0,229,255,0.45); font-size:0.7rem; text-decoration:none; display:block; margin-top:1.2rem; cursor:pointer; font-weight:500; transition:color 0.3s;" onmouseover="this.style.color='#00E5FF'" onmouseout="this.style.color='rgba(0,229,255,0.45)'">¿Olvidó su contraseña? Recupérela vía Telegram</a>
    <div class="error" id="errorMsg"></div>
  </form>
</div>
<script>
document.getElementById('loginForm').addEventListener('submit', async function(e){
  e.preventDefault();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const errEl = document.getElementById('errorMsg');
  errEl.textContent = '';
  errEl.style.color = '#ff4444';
  try {
    const resp = await fetch('/api/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username, password})
    });
    const data = await resp.json();
    if (resp.ok && data.token) {
      localStorage.setItem('token', data.token);
      document.cookie = 'token=' + data.token + '; path=/; max-age=86400';
      window.location.href = '/';
    } else {
      errEl.textContent = data.error || 'Credenciales inv&aacute;lidas';
    }
  } catch(e) {
    errEl.textContent = 'Error de conexi&oacute;n';
  }
});

document.getElementById('forgotPasswordBtn').addEventListener('click', async function(e){
  e.preventDefault();
  const errEl = document.getElementById('errorMsg');
  errEl.textContent = 'Enviando contraseña a Telegram...';
  errEl.style.color = '#00E5FF';
  try {
    const resp = await fetch('/api/forgot-password', {
      method:'POST',
      headers:{'Content-Type':'application/json'}
    });
    const data = await resp.json();
    if (resp.ok) {
      errEl.textContent = 'Clave enviada a tu chat privado con el bot.';
      errEl.style.color = '#00ffaa';
    } else {
      errEl.textContent = data.error || 'Error al enviar clave';
      errEl.style.color = '#ff4444';
    }
  } catch(e) {
    errEl.textContent = 'Error de conexión';
    errEl.style.color = '#ff4444';
  }
});
</script>
</body>
</html>"""
