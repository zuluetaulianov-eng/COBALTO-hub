import asyncio
import logging
from typing import Any, Dict

from humanization_delays import (
    human_delay_between_requests,
    simulate_human_browsing,
    simulate_human_browsing_async,
)
from humanization_proxy import get_proxies
from humanization_ratelimit import RATE_LIMITERS, wait_for_rate_limit, wait_for_rate_limit_async
from humanization_session import SESSION_MANAGER
from humanization_ua import get_headers_with_random_ua

logger = logging.getLogger(__name__)


def humanized_request(
    platform: str,
    url: str,
    method: str = "GET",
    additional_headers: Dict[str, str] = None,
    params: Dict[str, Any] = None,
    data: Dict[str, Any] = None,
    timeout: int = 15,
) -> Any:
    from osint_tls_backend import tls_manager

    wait_time = wait_for_rate_limit(platform)
    if wait_time > 0:
        logger.info(f"[RATE LIMIT] Esperando {wait_time:.2f}s para {platform}")
    delay = human_delay_between_requests(platform)
    logger.debug(f"[HUMAN DELAY] {platform}: {delay:.2f}s")
    session = SESSION_MANAGER.get_session(platform)
    headers = get_headers_with_random_ua(additional_headers)
    proxies = get_proxies(platform)
    try:
        response = tls_manager.request(
            method=method,
            url=url,
            platform=platform,
            headers=headers,
            params=params,
            data=data,
            proxies=proxies,
            timeout=timeout,
        )
        if response is None:
            raise Exception("TLS Backend falló o devolvió vacío")
        limiter = RATE_LIMITERS.get(platform, RATE_LIMITERS["default"])
        limiter.report_status(response.status_code)
        simulate_human_browsing()
        return response
    except Exception as e:
        logger.warning(f"[TLS BACKEND FAIL] Reintentando con requests estándar para {platform}: {e}")
        session = SESSION_MANAGER.get_session(platform)
        response = session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            proxies=proxies,
            timeout=timeout,
            allow_redirects=True,
        )
        return response


def safe_humanized_get(
    url: str, platform: str = "default", additional_headers: Dict[str, str] = None, timeout: int = 15
) -> Any:
    return humanized_request(
        platform=platform, url=url, method="GET", additional_headers=additional_headers, timeout=timeout
    )


async def humanized_request_async(
    platform: str,
    url: str,
    method: str = "GET",
    additional_headers: Dict[str, str] = None,
    params: Dict[str, Any] = None,
    data: Dict[str, Any] = None,
    timeout: int = 15,
) -> Any:
    from osint_tls_backend import tls_manager

    wait_time = await wait_for_rate_limit_async(platform)
    if wait_time > 0:
        logger.info(f"[RATE LIMIT] Esperando {wait_time:.2f}s para {platform}")
    delay = human_delay_between_requests(platform)
    logger.debug(f"[HUMAN DELAY] {platform}: {delay:.2f}s")
    await asyncio.sleep(delay)
    SESSION_MANAGER.get_session(platform)
    headers = get_headers_with_random_ua(additional_headers)
    proxies = get_proxies(platform)
    try:
        response = await asyncio.to_thread(
            tls_manager.request,
            method=method,
            url=url,
            platform=platform,
            headers=headers,
            params=params,
            data=data,
            proxies=proxies,
            timeout=timeout,
        )
        if response is None:
            raise Exception("TLS Backend falló o devolvió vacío")
        limiter = RATE_LIMITERS.get(platform, RATE_LIMITERS["default"])
        limiter.report_status(response.status_code)
        await simulate_human_browsing_async()
        return response
    except Exception as e:
        logger.warning(f"[TLS BACKEND FAIL] Reintentando con requests estándar para {platform}: {e}")

        def _fallback_request():
            s = SESSION_MANAGER.get_session(platform)
            return s.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                proxies=proxies,
                timeout=timeout,
                allow_redirects=True,
            )

        try:
            response = await asyncio.to_thread(_fallback_request)
            limiter = RATE_LIMITERS.get(platform, RATE_LIMITERS["default"])
            limiter.report_status(response.status_code)
            await simulate_human_browsing_async()
            return response
        except Exception as ex:
            logger.error(f"[REQUEST FAILURE] Petición fallida para {platform}: {ex}")
            raise


async def safe_humanized_get_async(
    url: str, platform: str = "default", additional_headers: Dict[str, str] = None, timeout: int = 15
) -> Any:
    return await humanized_request_async(
        platform=platform, url=url, method="GET", additional_headers=additional_headers, timeout=timeout
    )
