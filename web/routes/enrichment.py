"""web/routes/enrichment.py — Enrichment trigger and status endpoints."""

import logging
from threading import Thread

from flask import Blueprint, jsonify, redirect, request, url_for

from database.repository import Repository

logger = logging.getLogger(__name__)
bp = Blueprint("enrichment", __name__)

# In-memory job state (resets on server restart — acceptable for single-user tool)
_status = {
    "running": False,
    "last_run": None,
    "message": None,
    "last_stats": None,
}


def _background_enrich(limit: int) -> None:
    global _status
    try:
        _status["running"] = True
        _status["message"] = f"Enriching up to {limit} leads…"

        from enrichment.pipeline import run_enrichment
        stats = run_enrichment(batch_size=limit)

        _status["last_stats"] = stats
        from datetime import datetime
        _status["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "error" in stats:
            _status["message"] = f"Error: {stats['error']}"
        else:
            _status["message"] = (
                f"Done — {stats.get('enriched', 0)} emails found "
                f"from {stats.get('processed', 0)} leads"
            )
    except Exception as exc:
        logger.exception("Enrichment error: %s", exc)
        _status["message"] = f"Error: {exc}"
    finally:
        _status["running"] = False


@bp.route("/enrich/run")
def run_enrichment():
    from config import settings
    if not settings.has_enrichment_search():
        return "No enrichment provider configured in .env", 400

    if _status["running"]:
        return redirect(url_for("results.results"))

    limit = min(500, max(1, request.args.get("limit", 50, type=int)))
    Thread(target=_background_enrich, args=(limit,), daemon=True).start()
    return redirect(url_for("results.results"))


@bp.route("/enrich/status")
def enrichment_status():
    return jsonify(_status)
