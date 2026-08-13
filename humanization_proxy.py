import random
import socket
from typing import Dict, Optional


def get_proxies(platform: str = "default") -> Optional[Dict[str, str]]:
    import config
    if config.RESIDENTIAL_PROXY_URL:
        session_id = random.randint(10000, 99999)
        proxy_url = config.RESIDENTIAL_PROXY_URL
        if "@" in proxy_url and ":" in proxy_url and "user" in proxy_url.lower() and "-session-" not in proxy_url:
            proxy_url = proxy_url.replace("user", f"user-session-{session_id}")
        return {"http": proxy_url, "https": proxy_url}

    if config.USE_TOR_FALLBACK:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            if sock.connect_ex(("127.0.0.1", config.TOR_SOCKS_PORT)) == 0:
                tor_proxy = f"socks5h://127.0.0.1:{config.TOR_SOCKS_PORT}"
                return {"http": tor_proxy, "https": tor_proxy}
        finally:
            sock.close()
    return None
