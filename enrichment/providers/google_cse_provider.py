"""Google Custom Search Engine — search provider for enrichment pipeline."""

import logging
from typing import List

import requests

from config import settings
from enrichment.utils import random_delay

logger = logging.getLogger(__name__)


class GoogleCSEClient:
    """Search via Google Custom Search JSON API."""

    _URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self):
        if not settings.GOOGLE_CSE_KEY or not settings.GOOGLE_CSE_CX:
            raise ValueError("GOOGLE_CSE_KEY and GOOGLE_CSE_CX are required")
        self._key = settings.GOOGLE_CSE_KEY
        self._cx = settings.GOOGLE_CSE_CX

    def search(self, query: str, count: int = 5) -> List[str]:
        try:
            resp = requests.get(
                self._URL,
                params={"key": self._key, "cx": self._cx, "q": query, "num": count},
                timeout=settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            urls = [item["link"] for item in data.get("items", [])]
            logger.debug("Google CSE: %d results for %r", len(urls), query[:60])
            random_delay()
            return urls
        except Exception as exc:
            logger.error("Google CSE search error: %s", exc)
            return []
