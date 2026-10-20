"""Regression checks for the isolated LNVE Signal UI redesign.

All fixtures are local SQLite records. No live Google Places calls are made.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GOOGLE_MAPS_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")

from flask import Flask

from config import settings
from database.repository import Repository
from web.routes.export import bp as export_bp
from web.routes.results import bp as results_bp
from web.routes.search import bp as search_bp


class SignalRedesignTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = settings.DATABASE_PATH
        self.db_path = str(Path(self.temp_dir.name) / "signal-preview.db")
        settings.DATABASE_PATH = self.db_path
        self.repo = Repository(self.db_path)
        self.repo.init()
        self.search_id = self.repo.create_search(
            search_type="roofing contractor",
            location_name="Mississauga, ON",
            radius_km=25,
            latitude=43.589,
            longitude=-79.644,
            min_rating=4.5,
            min_reviews=30,
            gmaps_status="completed",
            yellowpages_status="skipped",
            overall_status="completed",
        )
        self.repo.insert_lead(
            search_id=self.search_id,
            place_id="signal-no-site",
            business_name="Signal No Website",
            rating=4.9,
            review_count=122,
            website_url=None,
        )
        self.repo.insert_lead(
            search_id=self.search_id,
            place_id="signal-old-site",
            business_name="Signal Old Website",
            rating=4.5,
            review_count=87,
            website_url="https://example.com",
        )
        self.repo.recompute_overall_status(self.search_id)
        app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "web" / "templates"))
        app.secret_key = "test-secret"
        app.register_blueprint(search_bp)
        app.register_blueprint(results_bp)
        app.register_blueprint(export_bp)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        settings.DATABASE_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_exact_summary_counts_and_review_progress(self):
        summary = self.repo.get_prospect_summary()
        self.assertEqual(summary, {"total": 2, "no_website": 1, "website_audit": 1, "reviewed": 0})
        audit_lead = self.repo.get_leads_for_search_by_pool(self.search_id, True)[0]
        self.repo.update_website_audit(audit_lead["id"], "POOR", "outdated design")
        self.assertEqual(self.repo.get_prospect_summary()["reviewed"], 1)

    def test_discover_controls_keep_existing_form_contract(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        for param in ("search_type", "custom_type", "location_name", "radius", "min_rating", "min_reviews"):
            self.assertIn(('name="' + param + '"').encode(), response.data)
        self.assertIn(b"/search", response.data)
        self.assertIn(b"Start discovery", response.data)

    def test_prospect_overview_renders_real_pool_counts(self):
        response = self.client.get("/results")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Signal No Website", response.data)
        self.assertIn(b"Signal Old Website", response.data)
        self.assertIn(b"No Website", response.data)
        self.assertIn(b"Website Audit Queue", response.data)
        self.assertIn(b"All CSV", response.data)

    def test_search_detail_retains_manual_audit_post_fields(self):
        response = self.client.get("/search/" + str(self.search_id))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Manual Audit", response.data)
        self.assertIn(b' name="website_condition"', response.data)
        self.assertIn(b' name="audit_notes"', response.data)
        self.assertIn(("/lead/" + str(self.repo.get_leads_for_search_by_pool(self.search_id, True)[0]["id"]) + "/audit").encode(), response.data)


if __name__ == "__main__":
    unittest.main()
