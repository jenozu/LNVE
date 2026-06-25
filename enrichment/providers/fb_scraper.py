"""Facebook business page scraper (basic — no login required)."""

import logging
from typing import List, Tuple

from enrichment.utils import fetch_with_retry, extract_emails_from_text

logger = logging.getLogger(__name__)


class FacebookScraper:
    """Scrape publicly-visible Facebook business pages for contact info."""

    def scrape_page(self, url: str) -> Tuple[List[str], List[str]]:
        emails: List[str] = []
        names: List[str] = []
        try:
            resp = fetch_with_retry(url)
            if not resp or resp.status_code != 200:
                return emails, names
            # Facebook renders little in plain HTML without JS —
            # extract whatever emails appear in the raw source.
            emails = extract_emails_from_text(resp.text)
        except Exception as exc:
            logger.error("FB scraper error (%s): %s", url, exc)
        return emails, names
