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
from web.routes.results import bp as results_bp


class Phase3RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "phase3.db")
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
            place_id="no-site-1",
            business_name="No Site Roofing",
            address="1 Main St",
            phone_number="905-555-0001",
            rating=4.9,
            review_count=120,
            website_url=None,
            business_status="OPERATIONAL",
            google_maps_url="https://maps.example/no-site",
        )
        self.repo.insert_lead(
            search_id=self.search_id,
            place_id="site-1",
            business_name="Old Site Roofing",
            address="2 Main St",
            phone_number="905-555-0002",
            rating=4.8,
            review_count=210,
            website_url="https://example.com",
            business_status="OPERATIONAL",
            google_maps_url="https://maps.example/site",
        )
        self.repo.recompute_overall_status(self.search_id)

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_prospect_pools_are_separate(self):
        no_site = self.repo.get_leads_for_search_by_pool(self.search_id, False)
        website = self.repo.get_leads_for_search_by_pool(self.search_id, True)

        self.assertEqual([x["business_name"] for x in no_site], ["No Site Roofing"])
        self.assertEqual([x["business_name"] for x in website], ["Old Site Roofing"])
        self.assertEqual(website[0]["website_condition"], "UNREVIEWED")

    def test_manual_website_audit_is_saved(self):
        lead = self.repo.get_leads_for_search_by_pool(self.search_id, True)[0]

        changed = self.repo.update_website_audit(
            lead["id"],
            "POOR",
            "Slow mobile experience and weak quote CTA.",
        )

        self.assertTrue(changed)
        updated = self.repo.get_lead(lead["id"])
        self.assertEqual(updated["website_condition"], "POOR")
        self.assertEqual(
            updated["audit_notes"],
            "Slow mobile experience and weak quote CTA.",
        )
        self.assertIsNotNone(updated["audited_at"])

    def test_no_website_lead_cannot_be_manually_audited(self):
        lead = self.repo.get_leads_for_search_by_pool(self.search_id, False)[0]
        changed = self.repo.update_website_audit(
            lead["id"],
            "SEVERE",
            "Should not be applied.",
        )
        self.assertFalse(changed)

        unchanged = self.repo.get_lead(lead["id"])
        self.assertEqual(unchanged["website_condition"], "UNREVIEWED")

    def test_invalid_condition_is_rejected(self):
        lead = self.repo.get_leads_for_search_by_pool(self.search_id, True)[0]
        with self.assertRaises(ValueError):
            self.repo.update_website_audit(lead["id"], "BROKEN_SCORE", "x")

    def test_audit_notes_are_bounded(self):
        lead = self.repo.get_leads_for_search_by_pool(self.search_id, True)[0]
        self.repo.update_website_audit(lead["id"], "AVERAGE", "x" * 800)
        updated = self.repo.get_lead(lead["id"])
        self.assertEqual(len(updated["audit_notes"]), 500)


class Phase3MigrationTests(unittest.TestCase):
    def test_phase2_database_migrates_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "phase2.db")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_type TEXT NOT NULL,
                    location_name TEXT NOT NULL,
                    latitude REAL NOT NULL DEFAULT 0,
                    longitude REAL NOT NULL DEFAULT 0,
                    radius_km REAL NOT NULL,
                    min_rating REAL NOT NULL DEFAULT 0,
                    min_reviews INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    gmaps_status TEXT NOT NULL DEFAULT 'pending',
                    yellowpages_status TEXT NOT NULL DEFAULT 'skipped',
                    total_leads INTEGER NOT NULL DEFAULT 0,
                    gmaps_leads INTEGER NOT NULL DEFAULT 0,
                    yellowpages_leads INTEGER NOT NULL DEFAULT 0,
                    market_score INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER NOT NULL REFERENCES searches(id),
                    place_id TEXT,
                    business_name TEXT NOT NULL,
                    address TEXT,
                    phone_number TEXT,
                    rating REAL,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    website_url TEXT,
                    website_status TEXT,
                    business_status TEXT,
                    google_maps_url TEXT,
                    latitude REAL,
                    longitude REAL,
                    source TEXT NOT NULL DEFAULT 'google_maps',
                    email TEXT,
                    contact_name TEXT,
                    enrichment_source TEXT,
                    enrichment_confidence INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(search_id, business_name)
                );
                """
            )
            conn.commit()
            conn.close()

            Repository(db_path).init()

            conn = sqlite3.connect(db_path)
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()
            }
            conn.close()

            self.assertIn("website_condition", columns)
            self.assertIn("audit_notes", columns)
            self.assertIn("audited_at", columns)


class Phase3RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "routes.db")
        settings.DATABASE_PATH = self.db_path
        repo = Repository(self.db_path)
        repo.init()

        self.search_id = repo.create_search(
            search_type="roofing contractor",
            location_name="Mississauga, ON",
            radius_km=25,
            min_rating=4.5,
            min_reviews=30,
            gmaps_status="completed",
            yellowpages_status="skipped",
            overall_status="completed",
        )
        repo.insert_lead(
            search_id=self.search_id,
            place_id="route-no-site",
            business_name="Route No Site",
            rating=4.9,
            review_count=80,
            website_url=None,
        )
        repo.insert_lead(
            search_id=self.search_id,
            place_id="route-site",
            business_name="Route Audit Site",
            rating=4.8,
            review_count=150,
            website_url="https://example.com",
        )
        repo.recompute_overall_status(self.search_id)

        template_folder = str(
            Path(__file__).resolve().parents[1] / "web" / "templates"
        )
        app = Flask(__name__, template_folder=template_folder)
        app.secret_key = "test-secret"
        app.register_blueprint(results_bp)
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_results_page_shows_both_pools(self):
        response = self.client.get("/results")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No Website", response.data)
        self.assertIn(b"Website Audit Queue", response.data)
        self.assertIn(b"Route No Site", response.data)
        self.assertIn(b"Route Audit Site", response.data)

    def test_search_detail_shows_manual_audit_form(self):
        response = self.client.get(f"/search/{self.search_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Immediate Outreach", response.data)
        self.assertIn(b"Manual Audit", response.data)
        self.assertIn(b"website_condition", response.data)

    def test_post_audit_updates_existing_website_lead(self):
        repo = Repository(self.db_path)
        website_lead = repo.get_leads_for_search_by_pool(self.search_id, True)[0]

        response = self.client.post(
            f"/lead/{website_lead['id']}/audit",
            data={
                "website_condition": "SEVERE",
                "audit_notes": "Very slow and outdated.",
            },
        )
        self.assertEqual(response.status_code, 302)

        updated = repo.get_lead(website_lead["id"])
        self.assertEqual(updated["website_condition"], "SEVERE")
        self.assertEqual(updated["audit_notes"], "Very slow and outdated.")


if __name__ == "__main__":
    unittest.main()
