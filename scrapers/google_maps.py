"""
scrapers/google_maps.py — Google Maps Places API scraper.

Searches for businesses of a given type within a radius, fetches
details for each place, and writes leads (no-website businesses)
to the database via Repository.
"""

import logging
import random
import time
from typing import Tuple

import googlemaps
from googlemaps.exceptions import ApiError

from config import settings
from database.repository import Repository

logger = logging.getLogger(__name__)

_RATE_CONFIG = {
    "min_detail_delay": 0.5,
    "max_detail_delay": 1.5,
    "min_page_delay":   2.0,
    "max_page_delay":   5.0,
    "max_rpm":          50,
    "error_backoff":    10.0,
}


def _delay(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


class GoogleMapsScraper:
    """
    Scrapes Google Maps Places API for businesses without websites.

    Designed to run in a background thread. Checks the cancelled flag
    in the database between each page and each place detail request so
    the user can cancel a running search at any time.
    """

    def __init__(self, repo: Repository = None):
        self.repo = repo or Repository()
        self._client = googlemaps.Client(key=settings.GOOGLE_MAPS_KEY)

    def run(
        self,
        search_id: int,
        search_type: str,
        center: Tuple[float, float],
        radius_meters: float,
    ) -> None:
        """
        Entry point called from a background thread.

        Args:
            search_id: DB row ID of the parent search.
            search_type: Business type keyword (e.g. "electrician").
            center: (latitude, longitude) tuple.
            radius_meters: Search radius in metres.
        """
        logger.info(
            "[GM %d] Starting: type=%s centre=%s radius=%dm",
            search_id, search_type, center, radius_meters,
        )
        self.repo.update_search_status(search_id, "gmaps", "running")

        if self.repo.is_cancelled(search_id, "gmaps"):
            self.repo.update_search_status(search_id, "gmaps", "cancelled")
            self.repo.recompute_overall_status(search_id)
            return

        leads_found = 0
        next_page_token = None
        page = 0
        total_requests = 0
        start = time.time()

        try:
            while True:
                if self.repo.is_cancelled(search_id, "gmaps"):
                    break

                page += 1
                logger.info("[GM %d] Page %d", search_id, page)

                kwargs = dict(
                    location=center,
                    radius=radius_meters,
                    type="establishment",
                    keyword=search_type,
                )
                if next_page_token:
                    _delay(_RATE_CONFIG["min_page_delay"], _RATE_CONFIG["max_page_delay"])
                    kwargs["page_token"] = next_page_token

                try:
                    result = self._client.places_nearby(**kwargs)
                    total_requests += 1
                except ApiError as exc:
                    logger.error("[GM %d] API error: %s", search_id, exc)
                    backoff = min(30, 2 ** page)
                    time.sleep(backoff)
                    break

                places = result.get("results", [])
                logger.info("[GM %d] Page %d returned %d places", search_id, page, len(places))

                for i, place in enumerate(places, 1):
                    if self.repo.is_cancelled(search_id, "gmaps"):
                        break

                    if i > 1:
                        _delay(
                            _RATE_CONFIG["min_detail_delay"],
                            _RATE_CONFIG["max_detail_delay"],
                        )

                    place_id = place.get("place_id")
                    try:
                        detail = self._client.place(
                            place_id=place_id,
                            fields=["name", "formatted_address",
                                    "formatted_phone_number", "website"],
                        )
                        total_requests += 1
                    except ApiError as exc:
                        logger.warning("[GM %d] Detail API error for %s: %s",
                                       search_id, place_id, exc)
                        continue

                    d = detail.get("result", {})
                    name = d.get("name")
                    address = d.get("formatted_address", "N/A")
                    phone = d.get("formatted_phone_number", "N/A")
                    website = d.get("website")

                    if website is None and name:
                        inserted = self.repo.insert_lead(
                            search_id, name, address, phone, "google_maps"
                        )
                        if inserted:
                            leads_found += 1
                            logger.info("[GM %d] Lead: %s", search_id, name)

                    # Throttle check
                    elapsed = time.time() - start
                    rpm = total_requests / (elapsed / 60) if elapsed > 0 else 0
                    if rpm > _RATE_CONFIG["max_rpm"] * 0.8:
                        _delay(3.0, 8.0)

                next_page_token = result.get("next_page_token")
                if not next_page_token:
                    break

        except Exception as exc:
            logger.exception("[GM %d] Unexpected error: %s", search_id, exc)
            self.repo.update_search_status(search_id, "gmaps", "failed")
            self.repo.recompute_overall_status(search_id)
            return

        final = "cancelled" if self.repo.is_cancelled(search_id, "gmaps") else "completed"
        self.repo.update_search_status(search_id, "gmaps", final, leads_found)
        self.repo.recompute_overall_status(search_id)

        elapsed = time.time() - start
        logger.info(
            "[GM %d] Done: status=%s leads=%d pages=%d requests=%d time=%.1fs",
            search_id, final, leads_found, page, total_requests, elapsed,
        )
