# LNVE Setup Guide

## Prerequisites

- Python 3.11+
- A Google Maps API key (Places API enabled)
- Optional: Bing Search API key or Google CSE key (for email enrichment)

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/jenozu/LNVE.git
cd LNVE

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser
playwright install chromium

# 5. Create your .env file
copy .env.example .env      # Windows
# cp .env.example .env      # Mac / Linux
```

## Configure .env

Open `.env` and fill in at minimum:

```
GOOGLE_MAPS_KEY=AIza...your key here...
SECRET_KEY=any-long-random-string
```

For email enrichment, add at least one of:
```
BING_V7_KEY=your_bing_key
```
or
```
GOOGLE_CSE_KEY=your_cse_key
GOOGLE_CSE_CX=your_cx_id
```

## Run

```bash
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## Common Issues

**"GOOGLE_MAPS_KEY is not set"** — Make sure `.env` exists in the project root and contains `GOOGLE_MAPS_KEY=...`

**Yellow Pages scraper fails** — Run `playwright install chromium` and make sure you're inside the venv.

**No enrichment options in UI** — Add `BING_V7_KEY` or `GOOGLE_CSE_KEY+GOOGLE_CSE_CX` to `.env`.
