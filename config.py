"""
config.py — Settings used by the lean LNVE MVP.

The MVP intentionally requires only a Google Maps/Places API key plus a Flask
secret. Advanced enrichment, proxy, scraping, and AI configuration from the
older application is preserved on the `pre-mvp-refactor` branch.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-change-in-production")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "0") == "1"

    GOOGLE_MAPS_KEY: str = os.getenv("GOOGLE_MAPS_KEY", "")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "leads.db")

    @classmethod
    def has_google_maps(cls) -> bool:
        return bool(cls.GOOGLE_MAPS_KEY)

    @classmethod
    def validate(cls) -> None:
        if not cls.GOOGLE_MAPS_KEY:
            raise ValueError(
                "GOOGLE_MAPS_KEY is not set. Copy .env.example to .env and add your key."
            )
        logger.info("Configuration validated OK")
        logger.info("  Google Maps/Places: ✓")
        logger.info("  Database: %s", cls.DATABASE_PATH)


settings = Settings()
