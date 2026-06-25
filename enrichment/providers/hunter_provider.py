"""Hunter.io — email verification and domain search provider."""

import logging
from typing import Any, Dict, List, Tuple

import requests

from config import settings
from enrichment.utils import random_delay

logger = logging.getLogger(__name__)


class HunterClient:
    """Client for the Hunter.io v2 API."""

    _BASE = "https://api.hunter.io/v2"

    def __init__(self):
        if not settings.HUNTER_API_KEY:
            raise ValueError("HUNTER_API_KEY is not configured")
        self._key = settings.HUNTER_API_KEY

    def verify_email(self, email: str) -> Tuple[bool, int]:
        """
        Verify an email address.
        Returns (is_deliverable, confidence_0_100).
        """
        try:
            resp = requests.get(
                f"{self._BASE}/email-verifier",
                params={"email": email, "api_key": self._key},
                timeout=settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            result = data.get("result", "undeliverable")
            score = int(data.get("score", 0))
            is_valid = result in ("deliverable", "risky")
            random_delay()
            return is_valid, min(100, max(0, score))
        except Exception as exc:
            logger.error("Hunter verify error (%s): %s", email, exc)
            return False, 0

    def domain_search(self, domain: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find email addresses on a domain.
        Returns list of dicts with keys: email, confidence, first_name, last_name.
        """
        try:
            resp = requests.get(
                f"{self._BASE}/domain-search",
                params={
                    "domain": domain,
                    "api_key": self._key,
                    "limit": limit,
                    "type": "personal",
                },
                timeout=settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            emails = []
            for item in resp.json().get("data", {}).get("emails", []):
                emails.append({
                    "email": item.get("value"),
                    "confidence": item.get("confidence", 50),
                    "first_name": item.get("first_name", ""),
                    "last_name": item.get("last_name", ""),
                })
            random_delay()
            return emails
        except Exception as exc:
            logger.error("Hunter domain search error (%s): %s", domain, exc)
            return []
