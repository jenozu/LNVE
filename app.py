"""
app.py — LNVE Flask application entry point.

Start the development server:
    python app.py

Production (gunicorn):
    gunicorn -w 2 -b 0.0.0.0:5000 app:app
"""

import logging

from flask import Flask

from config import settings
from database.repository import Repository

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.FLASK_DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="web/templates")
app.secret_key = settings.SECRET_KEY

# Register blueprints
from web.routes.search     import bp as search_bp
from web.routes.results    import bp as results_bp
from web.routes.analytics  import bp as analytics_bp
from web.routes.enrichment import bp as enrichment_bp
from web.routes.export     import bp as export_bp

app.register_blueprint(search_bp)
app.register_blueprint(results_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(enrichment_bp)
app.register_blueprint(export_bp)

# ── Startup ───────────────────────────────────────────────────────────────────
with app.app_context():
    settings.validate()
    Repository().init()
    logger.info("LNVE started — http://127.0.0.1:5000")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=settings.FLASK_DEBUG,
    )
