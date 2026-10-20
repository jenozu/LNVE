"""
app.py — LNVE Flask application entry point.

MVP active surface:
- Google Places lead search
- Results
- CSV export

Legacy analytics, enrichment, and Yellow Pages modules are intentionally not
registered in the MVP. The pre-refactor application is preserved on the
`pre-mvp-refactor` branch.
"""

import logging
import os

from flask import Flask

from config import settings
from database.repository import Repository

logging.basicConfig(
    level=logging.DEBUG if settings.FLASK_DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="web/templates")
app.config["LNVE_DEMO_MODE"] = os.getenv("LNVE_DEMO_MODE") == "1"
app.secret_key = settings.SECRET_KEY

from web.routes.search import bp as search_bp
from web.routes.results import bp as results_bp
from web.routes.export import bp as export_bp

app.register_blueprint(search_bp)
app.register_blueprint(results_bp)
app.register_blueprint(export_bp)

with app.app_context():
    settings.validate()
    repository = Repository()
    repository.init()
    if app.config["LNVE_DEMO_MODE"]:
        # Strictly disallow preview seeding outside an isolated temp database.
        if not settings.DATABASE_PATH.startswith("/tmp/lnve-signal-preview"):
            raise RuntimeError("Demo mode requires a dedicated /tmp/lnve-signal-preview database.")
        from demo_seed import seed_demo
        seed_demo(repository)
    logger.info("LNVE MVP started — http://127.0.0.1:5000")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=settings.FLASK_DEBUG,
    )
