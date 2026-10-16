"""Synthetic, opt-in LNVE preview fixture.

Used only when LNVE_DEMO_MODE=1 and DATABASE_PATH points to /tmp.
Never uses Google Places, production credentials, or real customer data.
"""
from database.repository import Repository


def seed_demo(repo: Repository) -> None:
    """Insert fictional local businesses for visual evaluation, only once per DB."""
    if repo.list_searches(limit=1):
        return

    scenarios = [
        (
            "roofing contractor", "Mississauga, ON", 25, 4.5, 30,
            [
                ("Northline Roofworks", False, 4.9, 182),
                ("Fieldstone Exterior Co.", True, 4.8, 127),
                ("Summitcrest Roofing", False, 4.8, 96),
                ("Ironwood Roof Studio", True, 4.7, 156),
                ("Clearview Roof Care", False, 4.9, 228),
                ("Apex Ridge Exteriors", True, 4.7, 74),
                ("Slate & Stone Roofing", True, 4.6, 89),
                ("Lakeshore Roofline", False, 4.8, 113),
                ("Windsor Peak Contractors", True, 4.9, 246),
                ("Cedarline Roofing", False, 4.7, 61),
            ],
        ),
        (
            "HVAC contractor", "Oakville, ON", 15, 4.4, 25,
            [
                ("Evergreen Climate Services", False, 4.9, 173),
                ("Meridian Air Systems", True, 4.8, 301),
                ("Bluepeak Mechanical", True, 4.7, 124),
                ("Westpoint Comfort", False, 4.6, 89),
                ("Northstar Heating Co.", True, 4.9, 212),
                ("Crownline Air & Heat", False, 4.8, 151),
            ],
        ),
        (
            "landscaping contractor", "Etobicoke, ON", 20, 4.6, 40,
            [
                ("Wildfern Outdoor Design", True, 4.9, 143),
                ("Thornhill Landscape Studio", True, 4.7, 197),
                ("Maple Grove Hardscapes", False, 4.8, 118),
                ("Stonehaven Garden Works", True, 4.9, 167),
                ("Willowbend Landscaping", False, 4.7, 92),
                ("Urbanroot Gardens", False, 4.8, 111),
            ],
        ),
    ]
    condition_cycle = ("UNREVIEWED", "POOR", "AVERAGE", "SEVERE", "GOOD")
    audit_index = 0
    for sidx, (niche, city, radius, min_rating, min_reviews, businesses) in enumerate(scenarios):
        search_id = repo.create_search(
            search_type=niche,
            location_name=city,
            radius_km=radius,
            latitude=43.6,
            longitude=-79.65,
            min_rating=min_rating,
            min_reviews=min_reviews,
            gmaps_status="completed",
            yellowpages_status="skipped",
            overall_status="completed",
        )
        for bidx, (name, has_website, rating, reviews) in enumerate(businesses):
            repo.insert_lead(
                search_id=search_id,
                place_id=f"lnve-demo-{sidx}-{bidx}",
                business_name=name,
                address=f"{110 + 27 * bidx} Sample Avenue, {city}",
                phone_number=f"905-555-{1200 + sidx * 100 + bidx:04d}",
                rating=rating,
                review_count=reviews,
                website_url="https://example.com" if has_website else None,
                google_maps_url="",
                business_status="OPERATIONAL",
            )
        for lead in repo.get_leads_for_search_by_pool(search_id, True):
            condition = condition_cycle[audit_index % len(condition_cycle)]
            audit_index += 1
            if condition != "UNREVIEWED":
                repo.update_website_audit(
                    lead_id=lead["id"],
                    website_condition=condition,
                    audit_notes="Fictional sample assessment for exploring the LNVE interface.",
                )
        repo.recompute_overall_status(search_id)
