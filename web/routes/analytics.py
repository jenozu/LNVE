"""web/routes/analytics.py — Analytics dashboard."""

from flask import Blueprint, render_template
from database.repository import Repository

bp = Blueprint("analytics", __name__)


@bp.route("/analytics")
def analytics():
    stats = Repository().get_analytics()
    return render_template("analytics.html", stats=stats)
