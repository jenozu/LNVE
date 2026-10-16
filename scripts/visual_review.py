"""Render LNVE Signal from a disposable, synthetic SQLite fixture.

Run inside CI with Playwright Chromium. Never reads production data, env, or APIs.
"""
from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

fixture_dir = tempfile.TemporaryDirectory(prefix="lnve-signal-")
os.environ["DATABASE_PATH"] = str(Path(fixture_dir.name) / "visual.db")
os.environ["GOOGLE_MAPS_KEY"] = "synthetic-browser-fixture"
os.environ["SECRET_KEY"] = "visual-review-only"
os.environ["FLASK_DEBUG"] = "0"

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import app
from database.repository import Repository


def seed() -> int:
    repo = Repository()
    query = repo.create_search(
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
    without = [
        "Birch & Stone Roofing", "Hearthline Exterior Co.", "Keystone Roofing Group",
        "Evergreen Roof Systems", "Northpoint Restoration", "Monarch Roofing Services",
        "Cedarline Contractors", "Summit Valley Exteriors",
    ]
    with_site = [
        "Atlas Roof & Repair", "Cobalt Home Solutions", "Maplecrest Renovations",
        "Northstar Roofing", "Vantage Exterior Design", "Strata Roofing Co.",
        "Harbourline Roofing", "Westfield Restoration",
    ]
    for i, name in enumerate(without + with_site):
        repo.insert_lead(
            search_id=query,
            place_id="visual-fixture-" + str(i),
            business_name=name,
            address=str(110 + i * 13) + " Example Road, Mississauga, ON",
            phone_number="905-555-" + str(1400 + i),
            rating=round(4.5 + (i % 5) * 0.1, 1),
            review_count=35 + i * 15,
            website_url=("https://example.com" if i >= len(without) else None),
            google_maps_url="https://maps.google.com/?q=Mississauga",
            business_status="OPERATIONAL",
        )
    repo.recompute_overall_status(query)
    audit_leads = repo.get_leads_for_search_by_pool(query, True)
    for lead, status in zip(audit_leads[:4], ["SEVERE", "POOR", "AVERAGE", "GOOD"]):
        repo.update_website_audit(lead["id"], status, "Synthetic fixture for visual inspection.")
    return query


def run() -> None:
    search_id = seed()
    output = Path("artifacts/screenshots")
    output.mkdir(parents=True, exist_ok=True)
    server = make_server("127.0.0.1", 8877, app)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            for label, width, height in (("desktop", 1440, 900), ("mobile", 390, 844), ("tablet", 820, 1040)):
                context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
                page = context.new_page()
                exceptions = []
                page.on("pageerror", lambda exc: exceptions.append(str(exc)))
                for name, route in (
                    ("discover", "/"),
                    ("prospects", "/results"),
                    ("search-detail", "/search/" + str(search_id)),
                ):
                    page.goto("http://127.0.0.1:8877" + route, wait_until="domcontentloaded")
                    page.locator("#main-content").wait_for()
                    page.wait_for_timeout(350)
                    if name == "prospects":
                        page.get_by_role("tab", name="Website audit queue").click()
                        page.get_by_role("tab", name="No website").click()
                    if name == "search-detail":
                        page.get_by_role("tab", name="Website audit queue").click()
                        page.locator(".audit-disclosure summary").first.click()
                    width_ok = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                    assert width_ok, f"Unwanted page-level horizontal overflow: {label}/{name}"
                    page.screenshot(path=str(output / (label + "-" + name + ".png")), full_page=True, animations="disabled")
                    print(f"VISUAL PASS {label}/{name}: {page.title()}")
                assert not exceptions, f"JavaScript page errors: {exceptions}"
                context.close()
            browser.close()
    finally:
        server.shutdown()
        fixture_dir.cleanup()


if __name__ == "__main__":
    run()
