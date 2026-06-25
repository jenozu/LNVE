"""Bing Web Search API v7 — search provider for enrichment pipeline."""

import logging
from typing import List

import requests

from config import settings
from enrichment.utils import random_delay

logger = logging.getLogger(__name__)


class BingSearchClient:
    """Search the web via Bing Web Search API v7."""

    _URL = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self):
        if not settings.BING_V7_KEY:
            raise ValueError("BING_V7_KEY is not configured")
        self._key = settings.BING_V7_KEY

    def search(self, query: str, count: int = 5) -> List[str]:
        """Return a list of result URLs for the query."""
        try:
            resp = requests.get(
                self._URL,
                headers={"Ocp-Apim-Subscription-Key": self._key},
                params={"q": query, "count": count, "responseFilter": "Webpages"},
                timeout=settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            urls = [item["url"] for item in data.get("webPages", {}).get("value", [])]
            logger.debug("Bing: %d results for %r", len(urls), query[:60])
            random_delay()
            return urls
        except Exception as exc:
            logger.error("Bing search error: %s", exc)
            return []
