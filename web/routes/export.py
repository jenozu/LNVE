"""web/routes/export.py — CSV and JSON export endpoints."""

import csv
import io
import logging
from datetime import datetime

from flask import Blueprint, Response, request

from database.repository import Repository

logger = logging.getLogger(__name__)
bp = Blueprint("export", __name__)


@bp.route("/export/csv")
def export_csv():
    """
    Export leads to CSV.
    Optional query param: ?search_id=N to export one search only.
    """
    repo = Repository()
    search_id = request.args.get("search_id", type=int)

    if search_id:
        rows_raw = repo.get_leads_for_search(search_id)
        # Normalise to the same field order as get_all_leads_for_export
        rows = [
            {
                "business_name":          r.get("business_name"),
                "address":                r.get("address", ""),
                "phone_number":           r.get("phone_number", ""),
                "email":                  r.get("email", ""),
                "contact_name":           r.get("contact_name", ""),
                "source":                 r.get("source", ""),
                "enrichment_source":      r.get("enrichment_source", ""),
                "enrichment_confidence":  r.get("enrichment_confidence", 0),
                "created_at":             r.get("created_at", ""),
                "search_type":            "",
                "location_name":          "",
            }
            for r in rows_raw
        ]
        filename_tag = f"search_{search_id}"
    else:
        rows = repo.get_all_leads_for_export()
        filename_tag = "all"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Business Name", "Address", "Phone", "Email", "Contact Name",
        "Source", "Enrichment Source", "Confidence (%)", "Created At",
        "Search Type", "Location",
    ])
    for r in rows:
        writer.writerow([
            r.get("business_name", ""),
            r.get("address", ""),
            r.get("phone_number", ""),
            r.get("email", ""),
            r.get("contact_name", ""),
            r.get("source", ""),
            r.get("enrichment_source", ""),
            r.get("enrichment_confidence", 0),
            r.get("created_at", ""),
            r.get("search_type", ""),
            r.get("location_name", ""),
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"lnve_leads_{filename_tag}_{timestamp}.csv"
    logger.info("CSV export: %d rows → %s", len(rows), filename)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
