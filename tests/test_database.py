"""Tests for the database repository."""

import pytest
from database.repository import Repository


@pytest.fixture
def repo(tmp_path):
    """Fresh in-memory-like repository for each test."""
    r = Repository(db_path=str(tmp_path / "test.db"))
    r.init()
    return r


class TestRepository:
    def test_create_and_get_search(self, repo):
        sid = repo.create_search("electrician", "Hamilton, ON", 25.0)
        s = repo.get_search(sid)
        assert s is not None
        assert s["search_type"] == "electrician"
        assert s["location_name"] == "Hamilton, ON"

    def test_insert_lead_dedup(self, repo):
        sid = repo.create_search("plumber", "Toronto, ON", 10.0)
        r1 = repo.insert_lead(sid, "Acme Plumbing", "123 Main St", "555-1234")
        r2 = repo.insert_lead(sid, "Acme Plumbing", "123 Main St", "555-1234")
        assert r1 is True
        assert r2 is False  # duplicate

    def test_leads_for_search(self, repo):
        sid = repo.create_search("roofer", "Mississauga, ON", 15.0)
        repo.insert_lead(sid, "Top Roofing", "1 King St", "555-0001")
        repo.insert_lead(sid, "Peak Roofs",  "2 Queen St", "555-0002")
        leads = repo.get_leads_for_search(sid)
        assert len(leads) == 2

    def test_update_enrichment(self, repo):
        sid = repo.create_search("hvac", "London, ON", 20.0)
        repo.insert_lead(sid, "Cool Air", "5 Park Ave", "555-9999")
        leads = repo.get_leads_for_search(sid)
        repo.update_lead_enrichment(leads[0]["id"], "owner@coolair.ca", "Bob Smith", "bing+scrape", 75)
        updated = repo.get_leads_for_search(sid)
        assert updated[0]["email"] == "owner@coolair.ca"
        assert updated[0]["contact_name"] == "Bob Smith"

    def test_cancel_search(self, repo):
        sid = repo.create_search("painter", "Ottawa, ON", 25.0)
        repo.cancel_search(sid, "all")
        s = repo.get_search(sid)
        assert s["gmaps_status"] == "cancelled"

    def test_analytics(self, repo):
        stats = repo.get_analytics()
        assert "total_searches" in stats
        assert "total_leads" in stats
