"""
config.py — Single source of truth for all LNVE settings.

Every module imports from here. Nothing reads os.getenv() directly
except this file. Call config.validate() at startup to catch missing
required keys early.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    # ── Flask ─────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-change-in-production")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "0") == "1"

    # ── Google Maps ───────────────────────────────────────────
    GOOGLE_MAPS_KEY: str = os.getenv("GOOGLE_MAPS_KEY", "")

    # ── OpenAI ────────────────────────────────────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── Enrichment: Search APIs ───────────────────────────────
    BING_V7_KEY: str = os.getenv("BING_V7_KEY", "")
    GOOGLE_CSE_KEY: str = os.getenv("GOOGLE_CSE_KEY", "")
    GOOGLE_CSE_CX: str = os.getenv("GOOGLE_CSE_CX", "")

    # ── Enrichment: Optional Verifiers ────────────────────────
    HUNTER_API_KEY: str = os.getenv("HUNTER_API_KEY", "")
    SNOV_API_KEY: str = os.getenv("SNOV_API_KEY", "")

    # ── Proxies ───────────────────────────────────────────────
    _raw_proxies: str = os.getenv("PROXIES", "")
    PROXY_LIST: list = [p.strip() for p in _raw_proxies.split(",") if p.strip()]
    PROXY_FAIL_THRESHOLD: int = int(os.getenv("PROXY_FAIL_THRESHOLD", "3"))
    PROXY_COOLDOWN: int = int(os.getenv("PROXY_COOLDOWN", "300"))

    # ── Rate limiting ─────────────────────────────────────────
    RATE_GOOGLE: float = float(os.getenv("RATE_GOOGLE", "2"))
    RATE_YELLOWPAGES: float = float(os.getenv("RATE_YELLOWPAGES", "1"))
    RATE_BING: float = float(os.getenv("RATE_BING", "2"))
    MIN_DELAY: float = float(os.getenv("MIN_DELAY", "0.4"))
    MAX_DELAY: float = float(os.getenv("MAX_DELAY", "1.2"))
    RETRY_MAX: int = int(os.getenv("RETRY_MAX", "3"))
    LEAD_PAUSE_MIN: float = float(os.getenv("LEAD_PAUSE_MIN", "1.0"))
    LEAD_PAUSE_MAX: float = float(os.getenv("LEAD_PAUSE_MAX", "3.0"))

    # ── Enrichment behaviour ──────────────────────────────────
    RESULTS_PER_LEAD: int = int(os.getenv("RESULTS_PER_LEAD", "5"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "12"))

    # ── Database ──────────────────────────────────────────────
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "leads.db")

    # ── Helpers ───────────────────────────────────────────────
    @classmethod
    def has_google_maps(cls) -> bool:
        return bool(cls.GOOGLE_MAPS_KEY)

    @classmethod
    def has_openai(cls) -> bool:
        return bool(cls.OPENAI_API_KEY)

    @classmethod
    def has_bing(cls) -> bool:
        return bool(cls.BING_V7_KEY)

    @classmethod
    def has_google_cse(cls) -> bool:
        return bool(cls.GOOGLE_CSE_KEY and cls.GOOGLE_CSE_CX)

    @classmethod
    def has_hunter(cls) -> bool:
        return bool(cls.HUNTER_API_KEY)

    @classmethod
    def has_snov(cls) -> bool:
        return bool(cls.SNOV_API_KEY)

    @classmethod
    def has_enrichment_search(cls) -> bool:
        """At least one search provider is configured."""
        return cls.has_bing() or cls.has_google_cse()

    @classmethod
    def get_proxy_dict(cls) -> dict:
        """Single-proxy dict for requests library (uses first available)."""
        if cls.PROXY_LIST:
            return {"http": cls.PROXY_LIST[0], "https": cls.PROXY_LIST[0]}
        return {}

    @classmethod
    def validate(cls) -> None:
        """Call at startup. Raises ValueError for missing required keys."""
        if not cls.GOOGLE_MAPS_KEY:
            raise ValueError(
                "GOOGLE_MAPS_KEY is not set. Add it to your .env file."
            )
        logger.info("Configuration validated OK")
        logger.info("  Google Maps: ✓")
        logger.info("  OpenAI: %s", "✓" if cls.has_openai() else "✗ (analysis disabled)")
        logger.info("  Bing search: %s", "✓" if cls.has_bing() else "✗")
        logger.info("  Google CSE: %s", "✓" if cls.has_google_cse() else "✗")
        logger.info("  Hunter.io: %s", "✓" if cls.has_hunter() else "✗")
        logger.info("  Proxies: %d configured", len(cls.PROXY_LIST))


# Global singleton — import this everywhere
settings = Settings()
