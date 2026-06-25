"""Snov.io — email finder provider (optional)."""

import logging
from typing import List

import requests

from config import settings
from enrichment.utils import random_delay

logger = logging.getLogger(__name__)


class SnovClient:
    """Client for the Snov.io API."""

    _TOKEN_URL = "https://api.snov.io/v1/oauth/access_token"
    _SEARCH_URL = "https://api.snov.io/v2/domain-emails-with-info"

    def __init__(self):
        if not settings.SNOV_API_KEY:
            raise ValueError("SNOV_API_KEY is not configured")
        self._key = settings.SNOV_API_KEY
        self._token: str = ""

    def _get_token(self) -> str:
        resp = requests.post(
            self._TOKEN_URL,
            data={"grant_type": "client_credentials", "client_id": self._key,
                  "client_secret": self._key},
            timeout=settings.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        self._token = resp.json().get("access_token", "")
        return self._token

    def search(self, domain: str, limit: int = 5) -> List[str]:
        """Return email addresses found on the domain."""
        try:
            if not self._token:
                self._get_token()
            resp = requests.get(
                self._SEARCH_URL,
                params={"domain": domain, "limit": limit, "lastId": 0, "type": "all"},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            emails = [
                item["email"]
                for item in resp.json().get("emails", [])
                if item.get("email")
            ]
            random_delay()
            return emails
        except Exception as exc:
            logger.error("Snov search error (%s): %s", domain, exc)
            return []
