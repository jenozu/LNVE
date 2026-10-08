"""web/routes/results.py — Prospect-pool and manual website-audit routes."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database.repository import Repository

bp = Blueprint("results", __name__)

_AUDIT_CONDITIONS = {
    "UNREVIEWED",
    "SEVERE",
    "POOR",
    "AVERAGE",
    "GOOD",
}


@bp.route("/results")
def results():
    repo = Repository()
    return render_template(
        "results.html",
        searches=repo.list_searches(),
        no_website_leads=repo.get_recent_leads_by_pool(False, 25),
        website_leads=repo.get_recent_leads_by_pool(True, 25),
    )


@bp.route("/search/<int:search_id>")
def search_detail(search_id: int):
    repo = Repository()
    search = repo.get_search(search_id)
    if not search:
        abort(404)

    no_website_leads = repo.get_leads_for_search_by_pool(search_id, False)
    website_leads = repo.get_leads_for_search_by_pool(search_id, True)

    return render_template(
        "search_detail.html",
        search=search,
        no_website_leads=no_website_leads,
        website_leads=website_leads,
    )


@bp.route("/lead/<int:lead_id>/audit", methods=["POST"])
def update_audit(lead_id: int):
    repo = Repository()
    lead = repo.get_lead(lead_id)
    if not lead:
        abort(404)

    condition = request.form.get("website_condition", "UNREVIEWED").upper()
    notes = request.form.get("audit_notes", "")

    if condition not in _AUDIT_CONDITIONS:
        flash("Invalid website condition.", "danger")
        return redirect(url_for("results.search_detail", search_id=lead["search_id"]))

    if lead.get("website_status") != "Has Website":
        flash("Only leads with an existing website can be audited.", "warning")
        return redirect(url_for("results.search_detail", search_id=lead["search_id"]))

    repo.update_website_audit(
        lead_id=lead_id,
        website_condition=condition,
        audit_notes=notes,
    )

    flash(f"Website audit saved for {lead['business_name']}.", "success")
    return redirect(url_for("results.search_detail", search_id=lead["search_id"]))
