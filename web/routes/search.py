"""
web/routes/search.py — Lean Google-only search routes for the LNVE MVP.

Phase 1 intentionally removes Yellow Pages and enrichment from the active
application while preserving the existing Google scraper. Phase 2 will replace
that scraper with the new prospect-search logic.
"""

import logging
import re
from threading import Thread

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from config import settings
from database.repository import Repository
from scrapers.google_maps import GoogleMapsScraper

logger = logging.getLogger(__name__)
bp = Blueprint("search", __name__)

_SEARCH_TYPES = [
    ("roofer", "Roofing"),
    ("contractor", "General Contractor"),
    ("hvac", "HVAC"),
    ("landscaper", "Landscaping / Hardscaping"),
    ("plumber", "Plumbing"),
    ("electrician", "Electrical"),
]


@bp.route("/")
def index():
    return render_template("index.html", search_types=_SEARCH_TYPES)


@bp.route("/search", methods=["POST"])
def start_search():
    custom = request.form.get("custom_type", "").strip()
    selected = request.form.get("search_type", "").strip()
    search_type = custom if custom else selected

    if not search_type:
        flash("Please select or enter a business type.", "warning")
        return redirect(url_for("search.index"))

    location_name = request.form.get("location_name", "").strip()
    if not location_name:
        flash("Please enter a location.", "warning")
        return redirect(url_for("search.index"))

    try:
        radius_km = float(request.form.get("radius", 25))
    except ValueError:
        radius_km = 25.0

    radius_km = min(max(radius_km, 1.0), 100.0)

    center = None
    lat = lon = 0.0

    coordinate_match = re.match(
        r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$",
        location_name,
    )
    if coordinate_match:
        lat = float(coordinate_match.group(1))
        lon = float(coordinate_match.group(2))
        center = (lat, lon)

    if center is None:
        try:
            import googlemaps

            gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_KEY)
            geo = gmaps.geocode(location_name)
            if not geo:
                flash(f"Could not geocode '{location_name}'.", "danger")
                return redirect(url_for("search.index"))
            loc = geo[0]["geometry"]["location"]
            lat, lon = loc["lat"], loc["lng"]
            center = (lat, lon)
        except Exception as exc:
            logger.exception("Geocoding failed")
            flash(f"Geocoding failed: {exc}", "danger")
            return redirect(url_for("search.index"))

    repo = Repository()
    search_id = repo.create_search(
        search_type=search_type,
        location_name=location_name,
        radius_km=radius_km,
        latitude=lat,
        longitude=lon,
        gmaps_status="pending",
        yellowpages_status="skipped",
        overall_status="running",
    )

    Thread(
        target=GoogleMapsScraper(repo).run,
        args=(search_id, search_type, center, radius_km * 1000),
        daemon=True,
    ).start()

    logger.info("Search %d started (Google only)", search_id)
    return redirect(url_for("results.results"))


@bp.route("/cancel/<int:search_id>", methods=["POST"])
def cancel_search(search_id: int):
    Repository().cancel_search(search_id, "gmaps")
    return redirect(url_for("results.results"))


@bp.route("/api/search-status/<int:search_id>")
def search_status(search_id: int):
    s = Repository().get_search(search_id)
    if not s:
        return jsonify({"error": "Not found"}), 404

    return jsonify(
        {
            "status": s["status"],
            "gmaps_status": s["gmaps_status"],
            "total_leads": s["total_leads"],
            "gmaps_leads": s["gmaps_leads"],
        }
    )
