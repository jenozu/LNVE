"""
scrapers/google_maps.py — Google Places API (New) prospect search.

Phase 2 replaces the legacy Places flow with Text Search (New). It stores both
no-website and website-present businesses, while filtering for business quality
using minimum rating and review-count thresholds.
"""

import logging
import math
import time
from typing import Optional, Tuple

import requests

from config import settings
from database.repository import Repository

logger = logging.getLogger(__name__)

_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.googleMapsUri",
        "places.location",
        "nextPageToken",
    ]
)

_PAGE_SIZE = 20
_MAX_PAGES = 3
_REQUEST_TIMEOUT = 20
_MAX_RETRIES = 3


def _haversine_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return great-circle distance in metres between two coordinates."""
    earth_radius_m = 6_371_000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


class GoogleMapsScraper:
    """
    Google Places Text Search (New) client.

    The class name is retained to avoid unnecessary wiring changes elsewhere in
    the app. The implementation no longer uses the legacy Nearby Search +
    per-place Detail request pattern.
    """

    def __init__(
        self,
        repo: Repository = None,
        session: requests.Session = None,
    ):
        self.repo = repo or Repository()
        self._session = session or requests.Session()

    def _request_page(self, body: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.GOOGLE_MAPS_KEY,
            "X-Goog-FieldMask": _FIELD_MASK,
        }

        last_error: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._session.post(
                    _PLACES_TEXT_SEARCH_URL,
                    headers=headers,
                    json=body,
                    timeout=_REQUEST_TIMEOUT,
                )

                if response.status_code == 200:
                    return response.json()

                try:
                    error_payload = response.json()
                except ValueError:
                    error_payload = response.text

                message = (
                    f"Places API returned HTTP {response.status_code}: "
                    f"{error_payload}"
                )

                # Retry only transient failures.
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = RuntimeError(message)
                    if attempt < _MAX_RETRIES:
                        time.sleep(min(8, 2 ** attempt))
                        continue

                raise RuntimeError(message)

            except requests.RequestException as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(min(8, 2 ** attempt))
                    continue
                raise RuntimeError(f"Places API request failed: {exc}") from exc

        raise RuntimeError(f"Places API request failed: {last_error}")

    def run(
        self,
        search_id: int,
        search_type: str,
        center: Tuple[float, float],
        radius_meters: float,
        min_rating: float = 0.0,
        min_reviews: int = 0,
    ) -> None:
        """
        Find and store qualified businesses.

        Text Search uses a location bias, so returned results can theoretically
        fall outside the circle. LNVE therefore performs an additional
        coordinate-distance check before storing each prospect.
        """
        radius_meters = min(max(float(radius_meters), 1.0), 50_000.0)
        min_rating = min(max(float(min_rating), 0.0), 5.0)
        min_reviews = max(int(min_reviews), 0)

        logger.info(
            "[GM %d] Starting Text Search (New): type=%s center=%s "
            "radius=%.0fm min_rating=%.1f min_reviews=%d",
            search_id,
            search_type,
            center,
            radius_meters,
            min_rating,
            min_reviews,
        )

        self.repo.update_search_status(search_id, "gmaps", "running")

        if self.repo.is_cancelled(search_id, "gmaps"):
            self.repo.update_search_status(search_id, "gmaps", "cancelled")
            self.repo.recompute_overall_status(search_id)
            return

        leads_found = 0
        page_token = None
        pages_requested = 0
        places_seen = 0

        try:
            while pages_requested < _MAX_PAGES:
                if self.repo.is_cancelled(search_id, "gmaps"):
                    break

                body = {
                    "textQuery": search_type,
                    "pageSize": _PAGE_SIZE,
                    "locationBias": {
                        "circle": {
                            "center": {
                                "latitude": center[0],
                                "longitude": center[1],
                            },
                            "radius": radius_meters,
                        }
                    },
                }

                # Let Google pre-filter obvious low-rating results, then apply
                # the same threshold locally as a final guard.
                if min_rating > 0:
                    body["minRating"] = min_rating

                if page_token:
                    body["pageToken"] = page_token

                result = self._request_page(body)
                pages_requested += 1

                places = result.get("places", [])
                logger.info(
                    "[GM %d] Page %d returned %d places",
                    search_id,
                    pages_requested,
                    len(places),
                )

                for place in places:
                    if self.repo.is_cancelled(search_id, "gmaps"):
                        break

                    places_seen += 1

                    display_name = place.get("displayName") or {}
                    name = (display_name.get("text") or "").strip()
                    if not name:
                        continue

                    rating_raw = place.get("rating")
                    rating = float(rating_raw) if rating_raw is not None else None
                    review_count = int(place.get("userRatingCount") or 0)

                    if min_rating > 0 and (rating is None or rating < min_rating):
                        continue
                    if review_count < min_reviews:
                        continue

                    business_status = place.get("businessStatus") or ""
                    if business_status and business_status != "OPERATIONAL":
                        continue

                    location = place.get("location") or {}
                    latitude = location.get("latitude")
                    longitude = location.get("longitude")

                    # Text Search locationBias is not a hard geographic
                    # restriction. Reject known out-of-radius results locally.
                    if latitude is not None and longitude is not None:
                        distance = _haversine_meters(
                            center[0],
                            center[1],
                            float(latitude),
                            float(longitude),
                        )
                        if distance > radius_meters:
                            continue

                    website_url = (place.get("websiteUri") or "").strip() or None

                    inserted = self.repo.insert_lead(
                        search_id=search_id,
                        place_id=place.get("id"),
                        business_name=name,
                        address=place.get("formattedAddress") or "",
                        phone_number=place.get("nationalPhoneNumber") or "",
                        rating=rating,
                        review_count=review_count,
                        website_url=website_url,
                        business_status=business_status,
                        google_maps_url=place.get("googleMapsUri") or "",
                        latitude=latitude,
                        longitude=longitude,
                        source="google_maps",
                    )

                    if inserted:
                        leads_found += 1
                        logger.info(
                            "[GM %d] Qualified prospect: %s | %.1f | %d reviews | %s",
                            search_id,
                            name,
                            rating or 0,
                            review_count,
                            "website" if website_url else "no website",
                        )

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

                # Small gap between page-token requests.
                time.sleep(1.0)

        except Exception as exc:
            logger.exception("[GM %d] Search failed: %s", search_id, exc)
            self.repo.update_search_status(search_id, "gmaps", "failed", leads_found)
            self.repo.recompute_overall_status(search_id)
            return

        final_status = (
            "cancelled"
            if self.repo.is_cancelled(search_id, "gmaps")
            else "completed"
        )
        self.repo.update_search_status(
            search_id,
            "gmaps",
            final_status,
            leads_found,
        )
        self.repo.recompute_overall_status(search_id)

        logger.info(
            "[GM %d] Done: status=%s stored=%d seen=%d pages=%d",
            search_id,
            final_status,
            leads_found,
            places_seen,
            pages_requested,
        )
