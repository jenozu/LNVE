"""web/routes/export.py — Final CSV export endpoints for the LNVE MVP."""

import csv
import io
import logging
from datetime import datetime

from flask import Blueprint, Response, abort, request

from database.repository import Repository

logger = logging.getLogger(__name__)
bp = Blueprint("export", __name__)

_VALID_POOLS = {"all", "no_website", "website_audit"}


def _prospect_type(row: dict) -> str:
    if row.get("website_status") == "No Website Found":
        return "NO_WEBSITE"
    return "WEBSITE_AUDIT"


@bp.route("/export/csv")
def export_csv():
    """
    Export qualified prospects to CSV.

    Optional query parameters:
    - search_id=N
    - pool=all|no_website|website_audit
    """
    repo = Repository()
    search_id = request.args.get("search_id", type=int)
    pool = request.args.get("pool", "all").strip().lower()

    if pool not in _VALID_POOLS:
        abort(400, description="Invalid export pool.")

    if search_id is not None and not repo.get_search(search_id):
        abort(404)

    rows = repo.get_leads_for_export(
        search_id=search_id,
        pool=pool,
    )

    output = io.StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow(
        [
            "Prospect Type",
            "Business Name",
            "Rating",
            "Review Count",
            "Website URL",
            "Website Condition",
            "Audit Notes",
            "Phone",
            "Address",
            "Google Maps URL",
            "Place ID",
            "Business Status",
            "Search Type",
            "Search Location",
            "Radius (km)",
            "Minimum Rating",
            "Minimum Reviews",
            "Latitude",
            "Longitude",
            "Audited At",
            "Found At",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                _prospect_type(row),
                row.get("business_name", ""),
                row.get("rating", ""),
                row.get("review_count", 0),
                row.get("website_url", ""),
                row.get("website_condition", "UNREVIEWED"),
                row.get("audit_notes", ""),
                row.get("phone_number", ""),
                row.get("address", ""),
                row.get("google_maps_url", ""),
                row.get("place_id", ""),
                row.get("business_status", ""),
                row.get("search_type", ""),
                row.get("location_name", ""),
                row.get("radius_km", ""),
                row.get("min_rating", ""),
                row.get("min_reviews", ""),
                row.get("latitude", ""),
                row.get("longitude", ""),
                row.get("audited_at", ""),
                row.get("created_at", ""),
            ]
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scope = f"search_{search_id}" if search_id is not None else "all_searches"
    filename = f"lnve_{scope}_{pool}_{timestamp}.csv"

    logger.info(
        "CSV export: %d rows | search_id=%s | pool=%s | %s",
        len(rows),
        search_id,
        pool,
        filename,
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
