"""web/routes/results.py — MVP results and search detail pages."""

from flask import Blueprint, abort, render_template

from database.repository import Repository

bp = Blueprint("results", __name__)


@bp.route("/results")
def results():
    repo = Repository()
    return render_template(
        "results.html",
        searches=repo.list_searches(),
        leads=repo.get_recent_leads(50),
    )


@bp.route("/search/<int:search_id>")
def search_detail(search_id: int):
    repo = Repository()
    search = repo.get_search(search_id)
    if not search:
        abort(404)

    return render_template(
        "search_detail.html",
        search=search,
        leads=repo.get_leads_for_search(search_id),
    )
