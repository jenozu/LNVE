"""Yelp business page scraper."""

import logging
from typing import List, Tuple

from bs4 import BeautifulSoup

from enrichment.utils import fetch_with_retry, extract_emails_from_text

logger = logging.getLogger(__name__)


class YelpScraper:
    """Scrape Yelp business pages for contact info."""

    def scrape_page(self, url: str) -> Tuple[List[str], List[str]]:
        emails: List[str] = []
        names: List[str] = []
        try:
            resp = fetch_with_retry(url)
            if not resp or resp.status_code != 200:
                return emails, names
            soup = BeautifulSoup(resp.content, "html.parser")
            # Owner name sometimes in .biz-owner-reply-author or aria-label
            for el in soup.select(".biz-owner-reply-author, [aria-label*='owner']"):
                text = el.get_text().strip()
                if text:
                    names.append(text)
            for el in soup(["script", "style"]):
                el.decompose()
            emails = extract_emails_from_text(soup.get_text())
        except Exception as exc:
            logger.error("Yelp scraper error (%s): %s", url, exc)
        return emails, names
