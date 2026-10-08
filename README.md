# LNVE — Lean Website Lead Finder

LNVE is being refactored into a focused local-business prospecting tool.

## MVP goal

The finished MVP will search Google Places for strong local businesses and separate them into:

- **No Website** — immediate website-build prospects
- **Website Audit Queue** — businesses with an existing site that can be manually reviewed for rebuild opportunities

The refactor is being completed one phase at a time.

## Current status: Phase 1 complete

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
Next:
- current Places API search flow
- rating and review-count filters
- business website URL
- Place ID
- business status
- phone and address
- store both website and no-website prospects

### Phase 3 — Two prospect pools
- No Website
- Website Audit Queue
- manual website-condition review

### Phase 4 — CSV export + verification
- export final prospect fields
- smoke tests
- database migration checks
- final local run instructions

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_MAPS_KEY` | Yes | Google Maps / Places API |
| `SECRET_KEY` | Recommended | Flask session signing |
| `FLASK_DEBUG` | No | Set to `1` for local debugging |
| `DATABASE_PATH` | No | SQLite file path; defaults to `leads.db` |

## Notes

Do not commit your `.env` file. It is already covered by `.gitignore`.
