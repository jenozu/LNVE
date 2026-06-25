# LNVE Architecture

## Folder Structure

```
LNVE/
├── app.py                  # Flask entry point (≈40 lines)
├── config.py               # Single settings loader (reads .env)
├── requirements.txt
├── .env.example            # Template — copy to .env and fill in
│
├── core/                   # Safety infrastructure
│   ├── rate_limit.py       # TokenBucket rate limiter
│   ├── proxy_manager.py    # Proxy rotation + failure tracking
│   └── safe_request.py     # HTTP wrapper (retry, backoff, proxy)
│
├── scrapers/               # Data acquisition
│   ├── google_maps.py      # Google Maps Places API scraper
│   └── yellow_pages.py     # YellowPages.ca Playwright scraper
│
├── enrichment/             # Email + contact discovery
│   ├── pipeline.py         # Main orchestrator — run_enrichment()
│   ├── utils.py            # Shared helpers (fetch, regex, etc.)
│   └── providers/
│       ├── bing_provider.py
│       ├── google_cse_provider.py
│       ├── hunter_provider.py
│       ├── snov_provider.py
│       ├── fb_scraper.py
│       ├── yelp_scraper.py
│       └── bbb_scraper.py
│
├── database/
│   └── repository.py       # All SQLite operations (WAL mode)
│
├── web/
│   ├── routes/
│   │   ├── search.py       # /, /search, /cancel, /api/search-status
│   │   ├── results.py      # /results, /search/<id>
│   │   ├── analytics.py    # /analytics
│   │   ├── enrichment.py   # /enrich/run, /enrich/status
│   │   └── export.py       # /export/csv
│   └── templates/          # Jinja2 HTML templates
│       ├── base.html
│       ├── index.html
│       ├── results.html
│       ├── search_detail.html
│       └── analytics.html
│
├── tests/
│   ├── test_safety.py
│   └── test_database.py
│
└── docs/
    └── ARCHITECTURE.md     # This file
```

## Data Flow

```
User submits /search
  → web/routes/search.py resolves location + creates DB row
  → spawns Thread(GoogleMapsScraper.run)   [if gmaps selected]
  → spawns Thread(YellowPagesScraper.run)  [if yellowpages selected]

Scraper threads:
  → check is_cancelled() between each page/place
  → call repo.insert_lead() for each no-website business
  → call repo.update_search_status() on completion

User visits /results
  → repo.list_searches() + repo.get_recent_leads()
  → Jinja2 renders results.html

User clicks "Enrich N Leads"
  → /enrich/run spawns Thread(_background_enrich)
  → enrichment/pipeline.py fetches pending leads from DB
  → for each lead: searches web → scrapes pages → writes email back

User clicks "Export CSV"
  → /export/csv queries all leads → returns CSV download
```

## Configuration

All settings live in `.env` (never committed to git).
`config.py` reads them once at startup and exposes a `settings` singleton.
Every module imports `from config import settings` — nothing reads `os.getenv()` directly.

## Database

Single SQLite file (`leads.db`) with WAL mode enabled.
All queries go through `database/repository.py` — no raw `sqlite3` calls in other modules.

## Adding a New Scraper

1. Create `scrapers/my_source.py` with a class that has a `run(search_id, ...)` method.
2. In `run()`, call `self.repo.update_search_status(...)`, `self.repo.insert_lead(...)`, etc.
3. Register in `web/routes/search.py` — add checkbox to template + Thread spawn.

## Adding a New Enrichment Provider

1. Create `enrichment/providers/my_provider.py` with a class that has `search(query) -> List[str]`.
2. Import and instantiate in `enrichment/pipeline.py::_load_providers()`.
3. Add the API key to `.env.example` and `config.py`.
