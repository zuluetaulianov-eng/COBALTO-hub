import asyncio
import logging
import random
from urllib.parse import urlparse

from playwright.async_api import async_playwright

# ── Browser Pool: Reutiliza instancias Chrome entre llamadas ──
_browser_instance = None
_playwright_instance = None
_browser_lock = asyncio.Lock()
_playwright_semaphore = asyncio.Semaphore(2)  # Evita saturar RAM de 8GB limitando a 2 pestañas simultáneas


async def _get_playwright():
    global _playwright_instance
    if _playwright_instance is None:
        _playwright_instance = await async_playwright().start()
    return _playwright_instance


async def _get_browser():
    global _browser_instance
    async with _browser_lock:
        if _browser_instance is None or not _browser_instance.is_connected():
            p = await _get_playwright()
            _browser_instance = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-gpu",  # Apaga procesamiento gráfico innecesario
                    "--disable-dev-shm-usage",  # Previene agotamiento de memoria compartida
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-http2",  # Evita ERR_HTTP2_PROTOCOL_ERROR en sitios protegidos como Banca y Negocios
                ],
            )
        return _browser_instance


async def simulate_human_interaction(page):
    """Simula movimientos de mouse, scroll y pausas de lectura."""
    try:
        # 1. Movimientos de mouse aleatorios
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y, steps=random.randint(10, 20))
            await asyncio.sleep(random.uniform(0.1, 0.5))

        # 2. Scrolls aleatorios (lectura)
        for _ in range(random.randint(1, 3)):
            scroll_amount = random.randint(200, 600)
            await page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(1.0, 3.0))  # Pausa de lectura

    except Exception as e:
        logging.debug(f"[HUMAN-SIM] Error menor: {e}")


async def fetch_rss_with_browser(url: str, timeout: int = 30000) -> bytes:
    """
    Usa un navegador Chrome automatizado (headless) para descargar el RSS.
    Reusa la instancia de browser del pool para evitar overhead.
    Retorna los bytes crudos de la página.
    """
    async with _playwright_semaphore:
        browser = await _get_browser()
        p = await _get_playwright()
        device = p.devices.get("Pixel 6") or {
            "viewport": {"width": 412, "height": 915},
            "user_agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36",
        }
        try:
            context = await browser.new_context(
                **device,
                locale="es-VE",
                timezone_id="America/Caracas",
                geolocation={"latitude": 10.4806, "longitude": -66.9036},
                permissions=["geolocation"],
                color_scheme="dark",
                ignore_https_errors=True,
            )
        except Exception as e:
            logging.warning(f"[PLAYWRIGHT] Fallo al crear contexto ({e}). Recreando browser...")
            global _browser_instance
            async with _browser_lock:
                try:
                    await _browser_instance.close()
                except Exception:
                    pass
                _browser_instance = None
            browser = await _get_browser()
            context = await browser.new_context(
                **device,
                locale="es-VE",
                timezone_id="America/Caracas",
                geolocation={"latitude": 10.4806, "longitude": -66.9036},
                permissions=["geolocation"],
                color_scheme="dark",
                ignore_https_errors=True,
            )

        # Hardening de Élite: WebGL, Fonts y Canvas
        await context.add_init_script("""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris Xe Graphics';
                return getParameter(parameter);
            };
            const origFonts = document.fonts.check;
            document.fonts.check = function(font) {
                const common = ['Arial', 'Times', 'Roboto', 'Inter'];
                if (common.some(f => font.includes(f))) return true;
                return origFonts(font);
            };
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete window.RTCPeerConnection;
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(...args) {
                const imageData = originalGetImageData.apply(this, args);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += Math.random() > 0.5 ? 1 : -1;
                }
                return imageData;
            };
        """)

        page = await context.new_page()

        # Optimización i3-N305: Bloquear descarga de imágenes, multimedia y fuentes externas
        await page.route(
            "**/*",
            lambda route: (
                route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
            ),
        )

        captured_content = {"data": None}

        async def handle_response(response):
            if urlparse(response.url).path == urlparse(url).path and response.status == 200:
                try:
                    ctype = response.headers.get("content-type", "").lower()
                    if "xml" in ctype or "rss" in ctype or "atom" in ctype or "text/plain" in ctype:
                        captured_content["data"] = await response.body()
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            logging.info(f"[PLAYWRIGHT] Desplegando bot encubierto en {url}")
            await page.goto(url, wait_until="commit", timeout=timeout)

            for i in range(5):
                content = await page.content()
                if "<rss" in content or "<feed" in content or "<?xml" in content:
                    logging.info(f"[PLAYWRIGHT] Feed detectado visualmente en el DOM ({url})")
                    break
                await page.wait_for_timeout(2000)
                try:
                    verify_btn = page.get_by_text("Verify you are human").first
                    if await verify_btn.is_visible():
                        await verify_btn.click()
                except Exception:
                    pass

            await simulate_human_interaction(page)

            if "twitter" in url or "x.com" in url or "social" in url:
                logging.info(f"[PLAYWRIGHT] Iniciando scroll infinito para {url}...")
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)

            if captured_content["data"]:
                return captured_content["data"]

            html = await page.content()
            if "<rss" in html or "<feed" in html:
                return html.encode("utf-8")

            return b""

        except Exception as e:
            logging.error(f"[PLAYWRIGHT-FAIL] {url}: {str(e)}")
            return b""
        finally:
            await context.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://ipysvenezuela.org/feed/"

    async def main():
        print(f"Iniciando infiltracion con Chrome a {test_url} ...")
        res = await fetch_rss_with_browser(test_url)
        texto = res.decode("utf-8", errors="ignore")
        print("\nResultado (primeros 500 chars):")
        print(texto[:500])
        if "Aporrea" in texto or "<rss" in texto:
            print("\n[EXITO] Evasion de Cloudflare completada.")
        else:
            print("\n[FALLO] No se encontro RSS valido.")

    asyncio.run(main())
