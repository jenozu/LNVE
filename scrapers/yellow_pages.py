"""
scrapers/yellow_pages.py — Yellow Pages Canada scraper using Playwright.

Runs an async Playwright session inside a background thread (via
asyncio.new_event_loop()). Writes no-website leads to the database.
"""

import asyncio
import logging
import re

from database.repository import Repository

logger = logging.getLogger(__name__)

_CONFIG = {
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115 Safari/537.36"
    ),
    "page_load_timeout": 15_000,
    "max_pages": 5,
    "listing_delay_min": 0.8,
    "listing_delay_max": 2.0,
}

# CSS selectors — Yellow Pages occasionally changes their templates,
# so multiple fallbacks are listed for each field.
_NAME_SELECTORS = [
    ".listing__name--link",
    ".listing__name a",
    "h3 a",
    '[data-qa="result-item-title"] a',
    "h3",
]
_PHONE_SELECTORS = [
    ".listing__phone",
    ".phone",
    ".mlr__item__cta a.a--telephone",
    '[data-qa="result-item-phone"]',
]
_ADDRESS_SELECTORS = [
    ".listing__address",
    ".address",
    '[data-qa="result-item-address"]',
]
_WEBSITE_SELECTORS = [
    'a[href^="http"]:not([href*="yellowpages"])',
    ".listing__website a",
    '[data-qa="result-item-website"]',
]
_SCHEMA_ADDRESS_PARTS = [
    "[itemprop='streetAddress']",
    "[itemprop='addressLocality']",
    "[itemprop='addressRegion']",
    "[itemprop='postalCode']",
]


def _clean(text: str) -> str:
    if not text:
        return "N/A"
    cleaned = re.sub(r"\s+", " ", text.strip())
    return cleaned or "N/A"


def _normalise_phone(raw: str) -> str:
    if not raw:
        return "N/A"
    s = re.sub(r"^tel:", "", raw.strip(), flags=re.I)
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 10:
        d = digits[-10:]
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    return _clean(s)


class YellowPagesScraper:
    """Scrapes yellowpages.ca for businesses without websites."""

    def __init__(self, repo: Repository = None):
        self.repo = repo or Repository()

    # ── Public entry point ────────────────────────────────────

    def run(self, search_id: int, search_type: str, location_name: str) -> None:
        """
        Run in a background thread. Creates its own asyncio event loop.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._scrape(search_id, search_type, location_name)
            )
        finally:
            loop.close()

    # ── Async implementation ──────────────────────────────────

    async def _scrape(
        self, search_id: int, search_type: str, location_name: str
    ) -> None:
        from playwright.async_api import async_playwright
        import asyncio as _asyncio

        self.repo.update_search_status(search_id, "yellowpages", "running")

        if self.repo.is_cancelled(search_id, "yellowpages"):
            self.repo.update_search_status(search_id, "yellowpages", "cancelled")
            self.repo.recompute_overall_status(search_id)
            return

        leads_found = 0

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )
                ctx = await browser.new_context(
                    user_agent=_CONFIG["user_agent"],
                    viewport={"width": 1920, "height": 1080},
                )
                page = await ctx.new_page()
                await page.set_extra_http_headers({
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                })

                query = search_type.replace("_", " ")

                for page_num in range(1, _CONFIG["max_pages"] + 1):
                    if self.repo.is_cancelled(search_id, "yellowpages"):
                        break

                    url = (
                        f"https://www.yellowpages.ca/search/si/"
                        f"{page_num}/{query}/{location_name}"
                    )
                    logger.info("[YP %d] Page %d: %s", search_id, page_num, url)

                    try:
                        await page.goto(url, timeout=_CONFIG["page_load_timeout"])
                        await page.wait_for_load_state("domcontentloaded")
                        try:
                            await page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:
                            pass
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await _asyncio.sleep(0.5)
                    except Exception as exc:
                        logger.warning("[YP %d] Page load error: %s", search_id, exc)
                        break

                    listings = await page.locator(".listing").all()
                    if not listings:
                        logger.info("[YP %d] No listings on page %d", search_id, page_num)
                        break

                    logger.info("[YP %d] %d listings on page %d",
                                search_id, len(listings), page_num)

                    for listing in listings:
                        if self.repo.is_cancelled(search_id, "yellowpages"):
                            break

                        # ── Name ──────────────────────────────
                        name = "N/A"
                        for sel in _NAME_SELECTORS:
                            el = listing.locator(sel).first
                            if await el.count() > 0:
                                txt = (await el.inner_text()).strip()
                                if txt:
                                    name = _clean(txt)
                                    break

                        if name == "N/A":
                            continue

                        # ── Phone ─────────────────────────────
                        phone = "N/A"
                        tel_el = listing.locator("a[href^='tel:']").first
                        if await tel_el.count() > 0:
                            href = await tel_el.get_attribute("href")
                            phone = _normalise_phone(href or "")
                        else:
                            for sel in _PHONE_SELECTORS:
                                el = listing.locator(sel).first
                                if await el.count() > 0:
                                    txt = (await el.inner_text()).strip()
                                    if txt:
                                        phone = _normalise_phone(txt)
                                        break

                        # ── Address ───────────────────────────
                        parts = []
                        for sel in _SCHEMA_ADDRESS_PARTS:
                            el = listing.locator(sel).first
                            if await el.count() > 0:
                                t = (await el.inner_text()).strip()
                                if t:
                                    parts.append(t)

                        address = ", ".join(parts) if parts else "N/A"
                        if address == "N/A":
                            for sel in _ADDRESS_SELECTORS:
                                el = listing.locator(sel).first
                                if await el.count() > 0:
                                    txt = (await el.inner_text()).strip()
                                    address = _clean(
                                        txt.replace("Get directions", "").strip()
                                    )
                                    break

                        # ── Website check ─────────────────────
                        has_website = False
                        for sel in _WEBSITE_SELECTORS:
                            if await listing.locator(sel).count() > 0:
                                has_website = True
                                break

                        if not has_website:
                            inserted = self.repo.insert_lead(
                                search_id, name, address, phone, "yellow_pages"
                            )
                            if inserted:
                                leads_found += 1
                                logger.info("[YP %d] Lead: %s", search_id, name)

                        await _asyncio.sleep(
                            _CONFIG["listing_delay_min"] +
                            (_CONFIG["listing_delay_max"] - _CONFIG["listing_delay_min"]) * 0.5
                        )

                await browser.close()

        except Exception as exc:
            logger.exception("[YP %d] Unexpected error: %s", search_id, exc)
            self.repo.update_search_status(search_id, "yellowpages", "failed")
            self.repo.recompute_overall_status(search_id)
            return

        final = (
            "cancelled"
            if self.repo.is_cancelled(search_id, "yellowpages")
            else "completed"
        )
        self.repo.update_search_status(search_id, "yellowpages", final, leads_found)
        self.repo.recompute_overall_status(search_id)
        logger.info("[YP %d] Done: status=%s leads=%d", search_id, final, leads_found)
