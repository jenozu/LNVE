"""
core/proxy_manager.py — Proxy rotation with failure tracking.

Maintains a pool of proxies. When a proxy fails repeatedly it is
temporarily banned and automatically recovers after a cooldown.
"""

import random
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProxyManager:
    """
    Manages a pool of HTTP proxies with automatic rotation and banning.

    Example:
        mgr = ProxyManager(["http://user:pass@proxy1:8080"])
        proxy = mgr.get_proxy()
        try:
            resp = requests.get(url, proxies={"http": proxy, "https": proxy})
            mgr.report_success(proxy)
        except Exception:
            mgr.report_failure(proxy)
    """

    def __init__(
        self,
        proxies: list,
        fail_threshold: int = 3,
        cooldown: int = 300,
    ):
        self._pool = {
            p: {"fails": 0, "banned_until": 0.0, "total": 0, "errors": 0}
            for p in proxies
            if p
        }
        self._lock = threading.Lock()
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        logger.info("ProxyManager: %d proxies loaded", len(self._pool))

    # ── Public API ────────────────────────────────────────────

    def get_proxy(self) -> Optional[str]:
        """Return a random available proxy, or None if all are banned."""
        now = time.time()
        with self._lock:
            available = [p for p, s in self._pool.items() if s["banned_until"] <= now]
            if not available:
                logger.warning("All proxies are currently banned")
                return None
            chosen = random.choice(available)
            self._pool[chosen]["total"] += 1
            return chosen

    def report_success(self, proxy: Optional[str]) -> None:
        if not proxy or proxy not in self._pool:
            return
        with self._lock:
            self._pool[proxy]["fails"] = 0

    def report_failure(self, proxy: Optional[str]) -> None:
        if not proxy or proxy not in self._pool:
            return
        with self._lock:
            info = self._pool[proxy]
            info["fails"] += 1
            info["errors"] += 1
            if info["fails"] >= self.fail_threshold:
                info["banned_until"] = time.time() + self.cooldown
                logger.warning(
                    "Proxy banned for %ds after %d failures: %s",
                    self.cooldown,
                    info["fails"],
                    self._mask(proxy),
                )

    def stats(self) -> dict:
        now = time.time()
        with self._lock:
            return {
                "total": len(self._pool),
                "available": sum(1 for s in self._pool.values() if s["banned_until"] <= now),
                "banned": sum(1 for s in self._pool.values() if s["banned_until"] > now),
            }

    # ── Internal ──────────────────────────────────────────────

    @staticmethod
    def _mask(url: str) -> str:
        """Hide password in proxy URL for safe logging."""
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                auth, host = rest.rsplit("@", 1)
                user = auth.split(":")[0]
                return f"{scheme}://{user}:****@{host}"
        return url
