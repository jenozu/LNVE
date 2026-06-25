"""
enrichment/utils.py — Shared utilities for the enrichment pipeline.
"""

import logging
import random
import re
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
import tldextract

from config import settings

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
    "Gecko/20100101 Firefox/119.0",
]

# Generic / no-reply email patterns to deprioritise
_GENERIC_PREFIXES = {
    "info", "contact", "hello", "admin", "support", "noreply",
    "no-reply", "mail", "office", "enquiries", "general",
}

# Patterns that indicate owner/manager names in text
_CONTACT_PATTERNS = [
    r"(?:owner|manager|president|director|ceo|founder)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    r"(?:contact|speak with|ask for)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),?\s+(?:owner|manager|president|director)",
]
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)


def random_delay(min_s: float = None, max_s: float = None) -> None:
    """Sleep for a random interval."""
    lo = min_s if min_s is not None else settings.MIN_DELAY
    hi = max_s if max_s is not None else settings.MAX_DELAY
    time.sleep(random.uniform(lo, hi))


def get_random_ua() -> str:
    return random.choice(_USER_AGENTS)


def fetch_with_retry(url: str, max_retries: int = None) -> Optional[requests.Response]:
    """GET a URL with retry logic and rotating user agents."""
    retries = max_retries if max_retries is not None else settings.RETRY_MAX
    proxies = settings.get_proxy_dict()

    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": get_random_ua(),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=settings.REQUEST_TIMEOUT,
                proxies=proxies or None,
            )
            if resp.status_code == 429:
                wait = 10 * (2 ** attempt)
                logger.warning("429 for %s — waiting %ds", url, wait)
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as exc:
            logger.warning("Fetch attempt %d/%d failed for %s: %s",
                           attempt + 1, retries + 1, url, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)

    logger.error("All retries exhausted for %s", url)
    return None


def build_search_query(name: str, address: str = None, phone: str = None) -> str:
    """Build a web search query for a business."""
    parts = [f'"{name}"']
    if address:
        city = address.split(",")[1].strip() if "," in address else address
        parts.append(city)
    if phone and phone != "N/A":
        parts.append(phone)
    parts.append("email contact")
    return " ".join(parts)


def extract_emails_from_text(text: str) -> List[str]:
    """Find all email addresses in a block of text."""
    return list(set(_EMAIL_RE.findall(text)))


def extract_contact_names_from_text(text: str) -> List[str]:
    """Extract likely owner/manager names from text."""
    names: List[str] = []
    for pattern in _CONTACT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match.group(1).strip()
            if 2 <= len(name.split()) <= 4:
                names.append(name)
    return names


def extract_domain_from_url(url: str) -> Optional[str]:
    ext = tldextract.extract(url)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return None


def resolve_relative_url(base: str, href: str) -> str:
    return urljoin(base, href)


def is_same_domain(base: str, url: str) -> bool:
    try:
        b = tldextract.extract(base)
        u = tldextract.extract(url)
        return b.domain == u.domain and b.suffix == u.suffix
    except Exception:
        return False


def choose_best_email(emails: List[str]) -> Optional[str]:
    """
    Pick the best email from a list.
    Prefers personal/non-generic addresses.
    """
    if not emails:
        return None

    unique = list(dict.fromkeys(e.lower().strip() for e in emails if e))

    # Filter out obviously invalid
    valid = [e for e in unique if "@" in e and "." in e.split("@")[1]]
    if not valid:
        return None

    # Sort: non-generic first, then by length (shorter = simpler)
    def _score(email: str) -> int:
        prefix = email.split("@")[0].lower()
        return 0 if prefix in _GENERIC_PREFIXES else 1

    valid.sort(key=lambda e: (-_score(e), len(e)))
    return valid[0]
