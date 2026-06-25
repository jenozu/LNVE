"""
enrichment/pipeline.py — Lead enrichment orchestrator.

Fetches leads without emails from the database, searches for their
web presence using configured search providers, scrapes pages for
email addresses and contact names, optionally verifies with Hunter.io,
then writes results back to the database.

Usage (CLI):
    python -m enrichment.pipeline --batch 50 --dry-run

Usage (programmatic):
    from enrichment import run_enrichment
    stats = run_enrichment(batch_size=30)
"""

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import settings
from database.repository import Repository
from .utils import (
    build_search_query,
    extract_emails_from_text,
    extract_contact_names_from_text,
    extract_domain_from_url,
    resolve_relative_url,
    is_same_domain,
    choose_best_email,
    fetch_with_retry,
    random_delay,
)

logger = logging.getLogger(__name__)


# ── Provider imports (lazy — only fail if the provider is actually used) ──────

def _load_providers(search_clients: list, scrapers: dict) -> Tuple[list, dict, Any]:
    """Initialise whichever providers are configured."""
    hunter_client = None

    if settings.has_bing():
        try:
            from .providers.bing_provider import BingSearchClient
            search_clients.append(BingSearchClient())
            logger.info("Bing search provider: ✓")
        except Exception as exc:
            logger.warning("Bing init failed: %s", exc)

    if settings.has_google_cse():
        try:
            from .providers.google_cse_provider import GoogleCSEClient
            search_clients.append(GoogleCSEClient())
            logger.info("Google CSE provider: ✓")
        except Exception as exc:
            logger.warning("Google CSE init failed: %s", exc)

    if settings.has_hunter():
        try:
            from .providers.hunter_provider import HunterClient
            hunter_client = HunterClient()
            logger.info("Hunter.io verifier: ✓")
        except Exception as exc:
            logger.warning("Hunter init failed: %s", exc)

    try:
        from .providers.fb_scraper import FacebookScraper
        scrapers["facebook"] = FacebookScraper()
    except Exception:
        scrapers["facebook"] = None

    try:
        from .providers.yelp_scraper import YelpScraper
        scrapers["yelp"] = YelpScraper()
    except Exception:
        scrapers["yelp"] = None

    try:
        from .providers.bbb_scraper import BBBScraper
        scrapers["bbb"] = BBBScraper()
    except Exception:
        scrapers["bbb"] = None

    return search_clients, scrapers, hunter_client


# ── Core enrichment logic ─────────────────────────────────────────────────────

def _search_for_urls(lead: Dict, clients: list) -> List[str]:
    query = build_search_query(
        lead["business_name"],
        lead.get("address"),
        lead.get("phone_number"),
    )
    urls: List[str] = []
    for client in clients:
        try:
            found = client.search(query)
            urls.extend(found)
        except Exception as exc:
            logger.error("%s search error: %s", client.__class__.__name__, exc)

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique[: settings.RESULTS_PER_LEAD]


def _scrape_page(
    url: str, scrapers: dict
) -> Tuple[List[str], List[str], List[str]]:
    """
    Scrape a URL for emails, contact names, and domains.
    Returns (emails, contact_names, domains).
    """
    emails: List[str] = []
    names: List[str] = []
    domains: List[str] = []

    domain = extract_domain_from_url(url)
    if domain:
        domains.append(domain)

    url_lower = url.lower()

    # Specialised scrapers
    if "facebook.com" in url_lower and scrapers.get("facebook"):
        e, n = scrapers["facebook"].scrape_page(url)
        return e, n, domains
    if "yelp.com" in url_lower and scrapers.get("yelp"):
        e, n = scrapers["yelp"].scrape_page(url)
        return e, n, domains
    if "bbb.org" in url_lower and scrapers.get("bbb"):
        e, n = scrapers["bbb"].scrape_page(url)
        return e, n, domains

    # Generic HTML scraping
    resp = fetch_with_retry(url)
    if not resp or resp.status_code != 200:
        return emails, names, domains

    try:
        soup = BeautifulSoup(resp.content, "html.parser")

        # mailto links
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if addr:
                    emails.append(addr)

        # Remove scripts/styles then parse text
        for el in soup(["script", "style"]):
            el.decompose()
        text = soup.get_text()
        emails.extend(extract_emails_from_text(text))
        names.extend(extract_contact_names_from_text(text))

        # Follow contact/about page links (one hop only)
        contact_urls = []
        for tag in soup.find_all("a", href=True):
            text_label = tag.get_text().lower().strip()
            if any(kw in text_label for kw in ["contact", "about", "reach us", "get in touch"]):
                abs_url = resolve_relative_url(url, tag["href"])
                if is_same_domain(url, abs_url) and abs_url not in contact_urls:
                    contact_urls.append(abs_url)

        for contact_url in contact_urls[:2]:
            random_delay(0.5, 1.0)
            cresp = fetch_with_retry(contact_url)
            if cresp and cresp.status_code == 200:
                csoup = BeautifulSoup(cresp.content, "html.parser")
                for tag in csoup.find_all("a", href=True):
                    if tag["href"].startswith("mailto:"):
                        addr = tag["href"][7:].split("?")[0].strip()
                        if addr:
                            emails.append(addr)
                for el in csoup(["script", "style"]):
                    el.decompose()
                ctext = csoup.get_text()
                emails.extend(extract_emails_from_text(ctext))
                names.extend(extract_contact_names_from_text(ctext))

    except Exception as exc:
        logger.error("Scraping error for %s: %s", url, exc)

    return emails, names, domains


def enrich_lead(
    lead: Dict,
    search_clients: list,
    scrapers: dict,
    hunter_client: Any = None,
) -> Dict:
    """
    Enrich a single lead. Returns a dict with keys:
        email, contact_name, enrichment_source, enrichment_confidence
    """
    result = {
        "email": None,
        "contact_name": None,
        "enrichment_source": None,
        "enrichment_confidence": 0,
    }

    try:
        urls = _search_for_urls(lead, search_clients)
        if not urls:
            logger.debug("No URLs found for %s", lead["business_name"])
            return result

        all_emails: List[str] = []
        all_names: List[str] = []
        all_domains: List[str] = []

        for url in urls:
            random_delay()
            emails, names, domains = _scrape_page(url, scrapers)
            all_emails.extend(emails)
            all_names.extend(names)
            all_domains.extend(domains)

        best_email = choose_best_email(all_emails)

        # Hunter domain search (if configured and we have a domain but no email yet)
        if not best_email and hunter_client and all_domains:
            for domain in list(dict.fromkeys(all_domains)):
                try:
                    hits = hunter_client.domain_search(domain)
                    if hits:
                        best_email = hits[0].get("email")
                        first = hits[0].get("first_name", "")
                        last = hits[0].get("last_name", "")
                        if first or last:
                            all_names.insert(0, f"{first} {last}".strip())
                        result["enrichment_source"] = "hunter+domain"
                        result["enrichment_confidence"] = hits[0].get("confidence", 50)
                        break
                except Exception as exc:
                    logger.error("Hunter domain search error (%s): %s", domain, exc)

        if best_email:
            result["email"] = best_email

            if not result["enrichment_source"]:
                parts = []
                if any(c.__class__.__name__ == "BingSearchClient" for c in search_clients):
                    parts.append("bing")
                if any(c.__class__.__name__ == "GoogleCSEClient" for c in search_clients):
                    parts.append("google_cse")
                parts.append("scrape")
                result["enrichment_source"] = "+".join(parts)
                result["enrichment_confidence"] = 50

            # Verify with Hunter if available
            if hunter_client and result["enrichment_source"] != "hunter+domain":
                try:
                    valid, confidence = hunter_client.verify_email(best_email)
                    if valid:
                        result["enrichment_source"] += "+hunter_verified"
                        result["enrichment_confidence"] = confidence
                    else:
                        result["enrichment_confidence"] = max(
                            25, result["enrichment_confidence"] - 25
                        )
                except Exception as exc:
                    logger.error("Hunter verify error (%s): %s", best_email, exc)

        if all_names:
            unique = list(dict.fromkeys(all_names))
            result["contact_name"] = unique[0]

    except Exception as exc:
        logger.exception("Unexpected error enriching lead %s: %s",
                         lead.get("id"), exc)

    return result


# ── Public API ────────────────────────────────────────────────────────────────

def run_enrichment(
    batch_size: int = 50,
    dry_run: bool = False,
    verbose: bool = False,
    db_path: Optional[str] = None,
) -> Dict[str, int]:
    """
    Enrich a batch of leads with emails and contact names.

    Args:
        batch_size: Maximum number of leads to process.
        dry_run: If True, print results but don't write to database.
        verbose: Enable debug logging.
        db_path: Override database path.

    Returns:
        {"processed": N, "enriched": N, "errors": N}
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG,
                            format="%(asctime)s %(levelname)s %(message)s")

    if not settings.has_enrichment_search():
        msg = ("No enrichment search provider configured. "
               "Add BING_V7_KEY or GOOGLE_CSE_KEY+GOOGLE_CSE_CX to your .env file.")
        logger.error(msg)
        return {"error": msg}

    repo = Repository(db_path) if db_path else Repository()

    search_clients: list = []
    scrapers: dict = {}
    search_clients, scrapers, hunter_client = _load_providers(search_clients, scrapers)

    if not search_clients:
        return {"error": "No search clients could be initialised."}

    leads = repo.get_leads_pending_enrichment(batch_size)
    logger.info("Enrichment: %d leads to process", len(leads))

    if not leads:
        return {"processed": 0, "enriched": 0, "errors": 0}

    stats = {"processed": 0, "enriched": 0, "errors": 0}

    for i, lead in enumerate(leads, 1):
        logger.info("[%d/%d] Enriching: %s", i, len(leads), lead["business_name"])
        try:
            data = enrich_lead(lead, search_clients, scrapers, hunter_client)
            stats["processed"] += 1

            if data["email"]:
                stats["enriched"] += 1
                logger.info("  ✓ %s → %s (conf %d%%)",
                            lead["business_name"], data["email"],
                            data["enrichment_confidence"])
                if not dry_run:
                    repo.update_lead_enrichment(
                        lead["id"],
                        data["email"],
                        data["contact_name"] or "",
                        data["enrichment_source"] or "",
                        data["enrichment_confidence"],
                    )
            else:
                logger.info("  ✗ %s — no email found", lead["business_name"])

            if i < len(leads):
                random_delay(settings.LEAD_PAUSE_MIN, settings.LEAD_PAUSE_MAX)

        except Exception as exc:
            logger.error("Error processing lead %s: %s", lead.get("id"), exc)
            stats["errors"] += 1

    logger.info(
        "Enrichment complete: %d processed, %d enriched, %d errors",
        stats["processed"], stats["enriched"], stats["errors"],
    )
    if dry_run:
        logger.info("DRY RUN — no database writes made")

    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="LNVE lead enrichment pipeline")
    parser.add_argument("--batch", type=int, default=50,
                        help="Number of leads to process (default: 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write to database")
    parser.add_argument("--verbose", action="store_true",
                        help="Debug logging")
    parser.add_argument("--db-path", default=None,
                        help="Override database file path")
    args = parser.parse_args()

    result = run_enrichment(
        batch_size=args.batch,
        dry_run=args.dry_run,
        verbose=args.verbose,
        db_path=args.db_path,
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"\nEnrichment summary")
    print(f"  Processed : {result['processed']}")
    print(f"  Enriched  : {result['enriched']}")
    print(f"  Errors    : {result['errors']}")
    if args.dry_run:
        print("  (dry run — no database writes)")


if __name__ == "__main__":
    _cli()
