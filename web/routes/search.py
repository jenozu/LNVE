"""
web/routes/search.py — Google-only qualified prospect search routes.

Phase 2 adds minimum rating/review filters and passes those criteria into the
Places API (New) prospect search.
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
    ("roofing contractor", "Roofing"),
    ("general contractor", "General Contractor"),
    ("HVAC contractor", "HVAC"),
    ("landscaping contractor", "Landscaping / Hardscaping"),
    ("plumbing contractor", "Plumbing"),
    ("electrical contractor", "Electrical"),
    ("waterproofing contractor", "Waterproofing"),
    ("concrete contractor", "Concrete"),
    ("interlock contractor", "Interlock / Paving"),
    ("window and door installer", "Windows & Doors"),
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
    radius_km = min(max(radius_km, 1.0), 50.0)

    try:
        min_rating = float(request.form.get("min_rating", 4.5))
    except ValueError:
        min_rating = 4.5
    min_rating = min(max(min_rating, 0.0), 5.0)

    try:
        min_reviews = int(request.form.get("min_reviews", 30))
    except ValueError:
        min_reviews = 30
    min_reviews = max(min_reviews, 0)

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
        min_rating=min_rating,
        min_reviews=min_reviews,
        gmaps_status="pending",
        yellowpages_status="skipped",
        overall_status="running",
    )

    Thread(
        target=GoogleMapsScraper(repo).run,
        args=(
            search_id,
            search_type,
            center,
            radius_km * 1000,
            min_rating,
            min_reviews,
        ),
        daemon=True,
    ).start()

    logger.info(
        "Search %d started: %s | %s | %.1f km | rating>=%.1f | reviews>=%d",
        search_id,
        search_type,
        location_name,
        radius_km,
        min_rating,
        min_reviews,
    )
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
            "min_rating": s.get("min_rating", 0),
            "min_reviews": s.get("min_reviews", 0),
        }
    )
