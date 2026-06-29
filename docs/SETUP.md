# LNVE Setup Guide

---

## Phase 1 — Prerequisites

### 1. Python 3.11+

1. Go to **python.org/downloads**
2. Download the latest 3.11+ installer for Windows
3. Run the installer — **check "Add Python to PATH"** before clicking Install
4. Verify it worked: open a terminal and run `python --version`

### 2. Git

1. Go to **git-scm.com**
2. Download and run the installer with all default settings

---

## Phase 2 — Installation

Open a terminal (Command Prompt or PowerShell) and run these commands in order:

```bash
# 3. Clone the repo
git clone https://github.com/jenozu/LNVE.git
cd LNVE

# 4. Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 5. Install Python dependencies
pip install -r requirements.txt

# 6. Install the Playwright browser (needed for Yellow Pages scraping)
playwright install chromium
```

> You'll know step 4 worked when your terminal prompt starts with `(venv)`.

---

## Phase 3 — Configuration

### 7. Create your .env file

```bash
copy .env.example .env
```

Open `.env` in Notepad (or any text editor) and fill in your keys.

### 8. Required keys

**GOOGLE_MAPS_KEY** — your existing Google Maps API key.
Make sure these two APIs are enabled on it in **console.cloud.google.com**:
- Places API
- Geocoding API
- Custom Search API *(add this now for step below)*

```
GOOGLE_MAPS_KEY=AIzaSy...your key here...
```

**GOOGLE_CSE_KEY + GOOGLE_CSE_CX** — for email enrichment (finding contact emails).

- `GOOGLE_CSE_KEY` = same key as above (Google Maps key), just with Custom Search API enabled
- `GOOGLE_CSE_CX` = your Search Engine ID from programmablesearchengine.google.com

```
GOOGLE_CSE_KEY=AIzaSy...same key as above...
GOOGLE_CSE_CX=e3ceee74019224583
```

### 9. Set a secret key

Any long random string — used to secure Flask sessions:

```
SECRET_KEY=make-this-something-random-and-long
```

### 10. OpenAI key (you already have this)

```
OPENAI_API_KEY=sk-...your key...
```

### Optional keys

```
HUNTER_API_KEY=   # hunter.io — adds email verification confidence scores
```

---

## Phase 4 — First run

### 11. Start the app

Make sure your venv is active (`(venv)` shows in your prompt), then:

```bash
python app.py
```

You should see output like:
```
INFO  Configuration validated OK
INFO  Google Maps: ✓
INFO  OpenAI: ✓
INFO  Google CSE: ✓
INFO  Database initialised: leads.db
INFO  LNVE started — http://127.0.0.1:5000
```

### 12. Open in your browser

Go to **http://127.0.0.1:5000**

---

## Phase 5 — Daily workflow

### 13. Run a search
- Choose a business type (or type a custom keyword)
- Enter a city name (e.g. `Hamilton, ON`)
- Set a radius (25km is a good start)
- Check both Google Maps and Yellow Pages
- Click **Start Search** — it runs in the background

### 14. Review leads
- Go to the **Results** page
- See all businesses found without websites
- Leads from both sources are automatically deduplicated

### 15. Enrich for emails
- Click **Enrich 30 Leads** (or 100)
- The enrichment pipeline searches the web for each business's contact page
- Emails and contact names are saved back to the database

### 16. Export CSV
- Click **Export CSV** to download all leads with emails
- Ready to use in any outreach tool (Mailshake, Lemlist, etc.)

### 17. Check analytics
- Go to the **Analytics** page to see totals by source, niche, and date

---

## Pre-launch checklist

Before you start your first real search, verify:

- [ ] `.env` file exists inside the `LNVE/` folder (same level as `app.py`)
- [ ] `GOOGLE_MAPS_KEY` is set and Places + Geocoding APIs are enabled
- [ ] `GOOGLE_CSE_KEY` and `GOOGLE_CSE_CX` are both set
- [ ] Custom Search API is enabled in Google Cloud Console
- [ ] `OPENAI_API_KEY` is set
- [ ] `SECRET_KEY` is set to something unique
- [ ] Your venv is activated (`(venv)` shows in terminal) before running `python app.py`
- [ ] `playwright install chromium` has been run at least once

---

## Common errors

**"GOOGLE_MAPS_KEY is not set"**
→ The `.env` file is missing, or it's not saved in the `LNVE/` root folder (same folder as `app.py`).

**Enrichment shows as unavailable in the UI**
→ Check that both `GOOGLE_CSE_KEY` and `GOOGLE_CSE_CX` are present in `.env`.

**Yellow Pages scraper doesn't work**
→ Run `playwright install chromium` inside your activated venv.

**ModuleNotFoundError on startup**
→ Your venv isn't activated. Run `venv\Scripts\activate` first.

**Port 5000 already in use**
→ Another app is using port 5000. Run: `python app.py` after closing the other app, or change the port in `app.py`.

---

## To stop the app

Press `Ctrl + C` in the terminal.

## To restart later

```bash
cd LNVE
venv\Scripts\activate
python app.py
```
