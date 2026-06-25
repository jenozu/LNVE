"""
core/safe_request.py — HTTP requests with rate limiting, proxy rotation,
and exponential backoff retries.

Use safe_api_call() for ALL external HTTP requests throughout LNVE.
"""

import time
import random
import logging
import requests
from typing import Optional, Dict, Any

from .rate_limit import TokenBucket
from .proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def safe_api_call(
    url: str,
    limiter: TokenBucket,
    proxy_mgr: Optional[ProxyManager] = None,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    retries: int = 3,
    min_delay: float = 0.4,
    max_delay: float = 1.2,
    timeout: int = 10,
    **kwargs: Any,
) -> requests.Response:
    """
    Make a rate-limited, proxy-rotated HTTP request with retry logic.

    Handles:
    - Token bucket rate limiting (waits before each request)
    - Random jitter delay to reduce bot detection
    - Proxy rotation via ProxyManager
    - 429 and 5xx retries with exponential backoff
    - Proxy failure reporting

    Args:
        url: Target URL.
        limiter: TokenBucket controlling request rate.
        proxy_mgr: Optional ProxyManager for IP rotation.
        method: HTTP method (GET, POST, …).
        headers: Extra HTTP headers.
        retries: Maximum retry attempts.
        min_delay: Minimum jitter delay in seconds.
        max_delay: Maximum jitter delay in seconds.
        timeout: Per-request timeout in seconds.
        **kwargs: Passed directly to requests.request().

    Returns:
        requests.Response on success.

    Raises:
        requests.RequestException if all retries are exhausted.
    """
    limiter.wait()

    proxy = proxy_mgr.get_proxy() if proxy_mgr else None
    proxies = {"http": proxy, "https": proxy} if proxy else None

    req_headers = {"User-Agent": _DEFAULT_UA}
    if headers:
        req_headers.update(headers)

    last_exc: Optional[Exception] = None

    for attempt in range(retries):
        try:
            time.sleep(random.uniform(min_delay, max_delay))
            logger.debug("%s %s (attempt %d/%d)", method, url, attempt + 1, retries)

            resp = requests.request(
                method=method,
                url=url,
                proxies=proxies,
                timeout=timeout,
                headers=req_headers,
                **kwargs,
            )

            if resp.status_code == 429:
                backoff = (2 ** attempt) + random.random()
                logger.warning("429 rate-limited. Backing off %.1fs", backoff)
                time.sleep(backoff)
                continue

            if 500 <= resp.status_code < 600:
                backoff = (2 ** attempt) + random.random()
                logger.warning("Server error %d. Backing off %.1fs", resp.status_code, backoff)
                if attempt < retries - 1:
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()

            if 400 <= resp.status_code < 500:
                logger.error("Client error %d for %s", resp.status_code, url)
                resp.raise_for_status()

            if proxy_mgr and proxy:
                proxy_mgr.report_success(proxy)

            logger.debug("Success %d for %s", resp.status_code, url)
            return resp

        except (requests.Timeout, requests.ConnectionError, requests.ProxyError) as exc:
            last_exc = exc
            if proxy_mgr and proxy:
                proxy_mgr.report_failure(proxy)
                proxy = proxy_mgr.get_proxy()
                proxies = {"http": proxy, "https": proxy} if proxy else None
            if attempt < retries - 1:
                time.sleep((2 ** attempt) + random.random())
            continue

        except requests.RequestException as exc:
            last_exc = exc
            if proxy_mgr and proxy:
                proxy_mgr.report_failure(proxy)
            if attempt < retries - 1:
                time.sleep((2 ** attempt) + random.random())
            continue

    raise requests.RetryError(
        f"All {retries} attempts failed for {url}"
    ) from last_exc


def batch_delay(min_pause: float = 1.0, max_pause: float = 3.0) -> None:
    """Sleep a random amount between processing batches."""
    pause = random.uniform(min_pause, max_pause)
    logger.debug("Batch delay: %.2fs", pause)
    time.sleep(pause)
