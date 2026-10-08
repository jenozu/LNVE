# LNVE — Lean Website Lead Finder

LNVE is being refactored into a focused local-business prospecting tool.

## MVP goal

The finished MVP will search Google Places for strong local businesses and separate them into:

- **No Website** — immediate website-build prospects
- **Website Audit Queue** — businesses with an existing site that can be manually reviewed for rebuild opportunities

The refactor is being completed one phase at a time.

## Current status: MVP refactor complete (Phase 4)

Phase 1 reduced the active application to the minimum foundation:

- Flask web app
- SQLite database
- Google Places / Maps search path
- results pages
- CSV export

The following older features are intentionally inactive in the MVP:

- Yellow Pages browser scraping
- email enrichment
- Bing / Google CSE / Hunter / Snov providers
- OpenAI analysis
- analytics dashboard
- proxy configuration

The complete pre-refactor application is preserved in the Git branch:

`pre-mvp-refactor`

Legacy source files may remain in the main branch temporarily, but they are not registered or required by the active Flask application.

## Setup

### 1. Clone the repository

```powershell
git clone https://github.com/jenozu/LNVE.git
cd LNVE
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create your environment file

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
GOOGLE_MAPS_KEY=your_existing_google_maps_api_key
SECRET_KEY=replace-with-any-long-random-string
FLASK_DEBUG=0
DATABASE_PATH=leads.db
```

Only `GOOGLE_MAPS_KEY` is an external credential.

### 5. Run the app

```powershell
python app.py
```

Open:

`http://127.0.0.1:5000`

## Refactor roadmap

### Phase 1 — Preservation + cleanup
Complete.

### Phase 2 — Google prospect search
Complete:
- Places API (New) Text Search flow
- rating and review-count filters
- business website URL
- Place ID
- business status
- phone and address
- Google Maps URL and coordinates
- up to three pages / 60 Google results per search
- pure service-area businesses included
- local radius validation
- stores both website and no-website prospects

### Phase 3 — Two prospect pools
Complete:
- **No Website** pool for immediate outreach
- **Website Audit Queue** for rebuild prospects
- manual website condition: Unreviewed / Severely poor / Poor / Average / Good
- short audit notes for outreach observations
- audit timestamp
- safe Phase 2 → Phase 3 database migration
- repository and route tests for pool separation and audit updates

### Phase 4 — CSV export + final verification
Complete:
- CSV export for all prospects
- CSV export for **No Website** only
- CSV export for **Website Audit Queue** only
- search-specific exports
- rating, reviews, website, audit condition/notes, phone, address, Maps URL, Place ID, business status, search criteria, coordinates, and timestamps included
- mocked Google Places end-to-end prospect test
- pre-refactor database → final schema migration test
- Phase 3 workflow regression tests
- active Python module compilation
- Flask startup/import verification
- final GitHub Actions verification: 20/20 active tests passed

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_MAPS_KEY` | Yes | Google Maps / Places API |
| `SECRET_KEY` | Recommended | Flask session signing |
| `FLASK_DEBUG` | No | Set to `1` for local debugging |
| `DATABASE_PATH` | No | SQLite file path; defaults to `leads.db` |

## Notes

Do not commit your `.env` file. It is already covered by `.gitignore`.


## Website audit workflow

For businesses with an existing website, open the search detail page and review the site manually. LNVE lets you record:

- **Unreviewed**
- **Severely poor**
- **Poor**
- **Average / improvable**
- **Good**

You can also save a short note such as:

`slow mobile, outdated design, weak quote CTA`

This intentionally remains manual in the MVP. Automated PageSpeed/Lighthouse/AI audits are postponed until the outreach process is validated.


## Final MVP workflow

1. Enter a high-ticket business niche and location.
2. Set minimum rating and minimum review count.
3. Run the Google Places search.
4. Review **No Website** prospects for immediate outreach.
5. Review **Website Audit Queue** prospects and record the site's condition plus a short audit note.
6. Export all prospects or either pool to CSV.

### CSV export options

From the Results page or an individual search, you can export:

- **All**
- **No Website**
- **Audit Queue**

The CSV includes the prospect type and all qualification/audit data needed for manual outreach.

## Verification

GitHub Actions verifies the active MVP with:

- Phase 3 prospect-pool and audit tests
- Phase 4 export and end-to-end tests
- Python syntax compilation
- Flask app startup/import

The final Phase 4 verification passed **20/20 active tests**.

## Preserved versions

- `pre-mvp-refactor` — original advanced LNVE before the lean refactor
- `phase2-complete` — completed Google prospect-search phase
- `phase3-complete` — completed prospect-pool/manual-audit phase
- `phase4-complete` — final verified lean MVP
