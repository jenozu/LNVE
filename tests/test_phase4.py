import csv
import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GOOGLE_MAPS_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")

from flask import Flask

from config import settings
from database.repository import Repository
from scrapers.google_maps import GoogleMapsScraper
from web.routes.export import bp as export_bp
from web.routes.results import bp as results_bp
from web.routes.search import bp as search_bp


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return _FakeResponse(self.payload)


class Phase4Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "phase4.db")
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
            place_id="phase4-no-site",
            business_name="Phase 4 No Site Roofing",
            address="1 Main St, Mississauga, ON",
            phone_number="905-555-1000",
            rating=4.9,
            review_count=140,
            website_url=None,
            business_status="OPERATIONAL",
            google_maps_url="https://maps.example/no-site",
            latitude=43.59,
            longitude=-79.64,
        )
        self.repo.insert_lead(
            search_id=self.search_id,
            place_id="phase4-site",
            business_name="Phase 4 Old Site Roofing",
            address="2 Main St, Mississauga, ON",
            phone_number="905-555-2000",
            rating=4.8,
            review_count=230,
            website_url="https://oldsite.example",
            business_status="OPERATIONAL",
            google_maps_url="https://maps.example/site",
            latitude=43.60,
            longitude=-79.65,
        )

        website_lead = self.repo.get_leads_for_search_by_pool(
            self.search_id, True
        )[0]
        self.repo.update_website_audit(
            website_lead["id"],
            "POOR",
            "Slow mobile, outdated layout, weak quote CTA.",
        )
        self.repo.recompute_overall_status(self.search_id)

    def tearDown(self):
        self.tmp.cleanup()


class Phase4ExportRepositoryTests(Phase4Base):
    def test_all_export_contains_both_prospect_types(self):
        rows = self.repo.get_leads_for_export(search_id=self.search_id)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["website_status"] for row in rows},
            {"No Website Found", "Has Website"},
        )

    def test_pool_specific_exports_are_separate(self):
        no_site = self.repo.get_leads_for_export(
            search_id=self.search_id,
            pool="no_website",
        )
        audit = self.repo.get_leads_for_export(
            search_id=self.search_id,
            pool="website_audit",
        )

        self.assertEqual(len(no_site), 1)
        self.assertEqual(no_site[0]["business_name"], "Phase 4 No Site Roofing")
        self.assertEqual(len(audit), 1)
        self.assertEqual(
            audit[0]["business_name"],
            "Phase 4 Old Site Roofing",
        )

    def test_audit_data_is_present_in_export_query(self):
        audit = self.repo.get_leads_for_export(
            search_id=self.search_id,
            pool="website_audit",
        )[0]

        self.assertEqual(audit["website_condition"], "POOR")
        self.assertIn("weak quote CTA", audit["audit_notes"])
        self.assertIsNotNone(audit["audited_at"])

    def test_invalid_export_pool_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.get_leads_for_export(pool="not-a-pool")


class Phase4CsvRouteTests(Phase4Base):
    def setUp(self):
        super().setUp()
        template_folder = str(
            Path(__file__).resolve().parents[1] / "web" / "templates"
        )
        app = Flask(__name__, template_folder=template_folder)
        app.secret_key = "test-secret"
        app.register_blueprint(search_bp)
        app.register_blueprint(results_bp)
        app.register_blueprint(export_bp)
        self.client = app.test_client()

    @staticmethod
    def _csv_rows(response):
        text = response.data.decode("utf-8")
        return list(csv.DictReader(io.StringIO(text)))

    def test_export_all_csv_contains_both_types_and_final_headers(self):
        response = self.client.get(
            f"/export/csv?search_id={self.search_id}&pool=all"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")

        rows = self._csv_rows(response)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["Prospect Type"] for row in rows},
            {"NO_WEBSITE", "WEBSITE_AUDIT"},
        )

        required_headers = {
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
            "Minimum Rating",
            "Minimum Reviews",
            "Audited At",
            "Found At",
        }
        self.assertTrue(required_headers.issubset(rows[0].keys()))

    def test_no_website_csv_only_contains_immediate_outreach_pool(self):
        response = self.client.get(
            f"/export/csv?search_id={self.search_id}&pool=no_website"
        )
        rows = self._csv_rows(response)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Prospect Type"], "NO_WEBSITE")
        self.assertEqual(rows[0]["Website URL"], "")

    def test_audit_csv_preserves_manual_audit(self):
        response = self.client.get(
            f"/export/csv?search_id={self.search_id}&pool=website_audit"
        )
        rows = self._csv_rows(response)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Prospect Type"], "WEBSITE_AUDIT")
        self.assertEqual(rows[0]["Website Condition"], "POOR")
        self.assertIn("weak quote CTA", rows[0]["Audit Notes"])

    def test_invalid_pool_returns_400(self):
        response = self.client.get("/export/csv?pool=invalid")
        self.assertEqual(response.status_code, 400)

    def test_unknown_search_returns_404(self):
        response = self.client.get("/export/csv?search_id=999999")
        self.assertEqual(response.status_code, 404)


class Phase4GoogleFlowTests(unittest.TestCase):
    def test_mocked_google_search_stores_both_prospect_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "google-flow.db")
            repo = Repository(db_path)
            repo.init()

            search_id = repo.create_search(
                search_type="roofing contractor",
                location_name="Mississauga, ON",
                radius_km=25,
                latitude=43.589,
                longitude=-79.644,
                min_rating=4.5,
                min_reviews=30,
                gmaps_status="pending",
                yellowpages_status="skipped",
                overall_status="running",
            )

            payload = {
                "places": [
                    {
                        "id": "google-no-site",
                        "displayName": {"text": "Google No Site Roofing"},
                        "formattedAddress": "10 Main St, Mississauga, ON",
                        "nationalPhoneNumber": "(905) 555-1111",
                        "rating": 4.9,
                        "userRatingCount": 180,
                        "businessStatus": "OPERATIONAL",
                        "googleMapsUri": "https://maps.example/google-no-site",
                        "location": {
                            "latitude": 43.59,
                            "longitude": -79.64,
                        },
                    },
                    {
                        "id": "google-site",
                        "displayName": {"text": "Google Old Site Roofing"},
                        "formattedAddress": "20 Main St, Mississauga, ON",
                        "nationalPhoneNumber": "(905) 555-2222",
                        "websiteUri": "https://old-google-site.example",
                        "rating": 4.8,
                        "userRatingCount": 260,
                        "businessStatus": "OPERATIONAL",
                        "googleMapsUri": "https://maps.example/google-site",
                        "location": {
                            "latitude": 43.60,
                            "longitude": -79.65,
                        },
                    },
                    {
                        "id": "too-few-reviews",
                        "displayName": {"text": "Tiny Roofing"},
                        "rating": 5.0,
                        "userRatingCount": 4,
                        "businessStatus": "OPERATIONAL",
                        "location": {
                            "latitude": 43.60,
                            "longitude": -79.65,
                        },
                    },
                ]
            }

            session = _FakeSession(payload)
            scraper = GoogleMapsScraper(repo=repo, session=session)
            scraper.run(
                search_id=search_id,
                search_type="roofing contractor",
                center=(43.589, -79.644),
                radius_meters=25_000,
                min_rating=4.5,
                min_reviews=30,
            )

            no_site = repo.get_leads_for_search_by_pool(search_id, False)
            website = repo.get_leads_for_search_by_pool(search_id, True)
            search = repo.get_search(search_id)

            self.assertEqual(len(no_site), 1)
            self.assertEqual(len(website), 1)
            self.assertEqual(search["total_leads"], 2)
            self.assertEqual(search["status"], "completed")
            self.assertEqual(len(session.calls), 1)


class Phase4LegacyMigrationTests(unittest.TestCase):
    def test_pre_refactor_database_migrates_to_final_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "legacy.db")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_type TEXT NOT NULL,
                    location_name TEXT NOT NULL,
                    radius_km REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    total_leads INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER NOT NULL REFERENCES searches(id),
                    business_name TEXT NOT NULL,
                    address TEXT,
                    phone_number TEXT,
                    website_status TEXT,
                    source TEXT NOT NULL DEFAULT 'google_maps',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(search_id, business_name)
                );
                """
            )
            conn.commit()
            conn.close()

            Repository(db_path).init()

            conn = sqlite3.connect(db_path)
            lead_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(leads)")
            }
            search_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(searches)")
            }
            conn.close()

            for name in (
                "place_id",
                "rating",
                "review_count",
                "website_url",
                "business_status",
                "google_maps_url",
                "website_condition",
                "audit_notes",
                "audited_at",
            ):
                self.assertIn(name, lead_columns)

            for name in (
                "latitude",
                "longitude",
                "min_rating",
                "min_reviews",
                "gmaps_status",
                "yellowpages_status",
            ):
                self.assertIn(name, search_columns)


if __name__ == "__main__":
    unittest.main()

# Phase 4 CI verification marker.
