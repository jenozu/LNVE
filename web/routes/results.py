"""web/routes/results.py — Results and search detail pages."""

import logging

from flask import Blueprint, render_template

from database.repository import Repository

logger = logging.getLogger(__name__)
bp = Blueprint("results", __name__)


@bp.route("/results")
def results():
    repo = Repository()
    searches = repo.list_searches()
    leads = repo.get_recent_leads(50)
    return render_template(
        "results.html",
        searches=searches,
        leads=leads,
        enrichment_available=_enrichment_available(),
    )


@bp.route("/search/<int:search_id>")
def search_detail(search_id: int):
    repo = Repository()
    search = repo.get_search(search_id)
    if not search:
        from flask import abort
        abort(404)
    leads = repo.get_leads_for_search(search_id)
    enriched_count = sum(1 for l in leads if l.get("email"))
    return render_template(
        "search_detail.html",
        search=search,
        leads=leads,
        enriched_count=enriched_count,
    )


def _enrichment_available() -> bool:
    from config import settings
    return settings.has_enrichment_search()
