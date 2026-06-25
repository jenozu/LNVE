"""
web/routes/search.py — Search form and scraper launch endpoints.
"""

import logging
import re
from threading import Thread

from flask import Blueprint, redirect, render_template, request, url_for, flash

from config import settings
from database.repository import Repository
from scrapers.google_maps import GoogleMapsScraper
from scrapers.yellow_pages import YellowPagesScraper

logger = logging.getLogger(__name__)
bp = Blueprint("search", __name__)

_SEARCH_TYPES = [
    ("electrician",  "Electrician"),
    ("plumber",      "Plumber"),
    ("contractor",   "General Contractor"),
    ("hvac",         "HVAC"),
    ("landscaper",   "Landscaper"),
    ("painter",      "Painter"),
    ("roofer",       "Roofer"),
    ("locksmith",    "Locksmith"),
    ("carpenter",    "Carpenter"),
    ("pest_control", "Pest Control"),
    ("cleaner",      "Cleaning Service"),
    ("handyman",     "Handyman"),
]


@bp.route("/")
def index():
    return render_template("index.html", search_types=_SEARCH_TYPES)


@bp.route("/search", methods=["POST"])
def start_search():
    # Determine search type
    custom = request.form.get("custom_type", "").strip()
    selected = request.form.get("search_type", "").strip()
    search_type = custom if custom else selected

    if not search_type:
        flash("Please select or enter a business type.", "warning")
        return redirect(url_for("search.index"))

    location_name = request.form.get("location_name", "").strip()
    try:
        radius_km = float(request.form.get("radius", 25))
    except ValueError:
        radius_km = 25.0

    sources = request.form.getlist("sources")
    use_gm = "gmaps" in sources
    use_yp = "yellow_pages" in sources

    if not use_gm and not use_yp:
        flash("Select at least one source.", "warning")
        return redirect(url_for("search.index"))

    # Resolve coordinates
    import googlemaps
    center = None
    lat = lon = 0.0

    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", location_name)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        center = (lat, lon)

    if use_gm and center is None:
        try:
            gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_KEY)
            geo = gmaps.geocode(location_name)
            if not geo:
                flash(f"Could not geocode '{location_name}'.", "danger")
                return redirect(url_for("search.index"))
            loc = geo[0]["geometry"]["location"]
            lat, lon = loc["lat"], loc["lng"]
            center = (lat, lon)
        except Exception as exc:
            logger.error("Geocoding error: %s", exc)
            flash(f"Geocoding failed: {exc}", "danger")
            return redirect(url_for("search.index"))

    gm_init = "pending" if use_gm else "skipped"
    yp_init = "pending" if use_yp else "skipped"

    repo = Repository()
    search_id = repo.create_search(
        search_type=search_type,
        location_name=location_name,
        radius_km=radius_km,
        latitude=lat,
        longitude=lon,
        gmaps_status=gm_init,
        yellowpages_status=yp_init,
        overall_status="running",
    )

    radius_m = radius_km * 1000

    if use_gm and center:
        Thread(
            target=GoogleMapsScraper(repo).run,
            args=(search_id, search_type, center, radius_m),
            daemon=True,
        ).start()

    if use_yp:
        Thread(
            target=YellowPagesScraper(repo).run,
            args=(search_id, search_type, location_name),
            daemon=True,
        ).start()

    logger.info("Search %d started (GM:%s YP:%s)", search_id, use_gm, use_yp)
    return redirect(url_for("results.results"))


@bp.route("/cancel/<int:search_id>", methods=["POST"])
def cancel_search(search_id: int):
    source = request.args.get("source", "all")
    Repository().cancel_search(search_id, source)
    return redirect(url_for("results.results"))


@bp.route("/api/search-status/<int:search_id>")
def search_status(search_id: int):
    from flask import jsonify
    s = Repository().get_search(search_id)
    if not s:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "status":              s["status"],
        "gmaps_status":        s["gmaps_status"],
        "yellowpages_status":  s["yellowpages_status"],
        "total_leads":         s["total_leads"],
        "gmaps_leads":         s["gmaps_leads"],
        "yellowpages_leads":   s["yellowpages_leads"],
    })
