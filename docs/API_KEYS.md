# API Keys Setup Guide

A step-by-step guide to getting every key LNVE needs.
Keys are listed in priority order — **Required** ones must be set before the app will run.

---

## 1. Google Maps API Key — REQUIRED (for scraping)

This is what finds businesses. Without it the app won't start.

**You likely already have one** from your original script.
Before using it, confirm the right APIs are enabled:

1. Go to **console.cloud.google.com**
2. Sign in → select your project
3. Go to **APIs & Services → Library** and make sure these are enabled:
   - **Places API**
   - **Geocoding API**
   - **Custom Search API** ← add this now, you'll need it for Step 2

If you need a new key:
- **APIs & Services → Credentials → Create Credentials → API Key**

**Cost:** Places API charges ~$17 per 1,000 detail lookups.
Google gives $200/month free credit — covers ~11,000 business lookups. Normal use = $0.

---

## 2. Google Custom Search Engine — REQUIRED for email enrichment

> **Note:** Bing Search v7 is retired. Google CSE is the replacement.

This is how LNVE finds email addresses — it searches the web for each business's
contact page. You need both a **CSE Key** and a **CX (engine) ID**.

**Step A — Create the search engine (~2 min):**

1. Go to **programmablesearchengine.google.com**
2. Sign in with your Google account
3. Tap/click **Get started** or **Add**
4. Under "What to search" → select **Search the entire web**
5. Name it `LNVE`
6. Click **Create**
7. On the confirmation page, click **Customize**
8. Copy the **Search engine ID** shown at the top
   (looks like `a1b2c3d4e5f6:something`)
   → This is your **`GOOGLE_CSE_CX`**

**Step B — Enable the API and get the key (~2 min):**

1. Go to **console.cloud.google.com** (you're already signed in)
2. Search bar → type **Custom Search API** → click it → click **Enable**
3. Go to **APIs & Services → Credentials**
4. Click your existing API key (the one used for Google Maps)
5. Under "API restrictions" → add **Custom Search API** to the allowed list
6. Save — use this same key as your **`GOOGLE_CSE_KEY`**

Add both to your `.env`:
```
GOOGLE_CSE_KEY=your_google_api_key_here
GOOGLE_CSE_CX=your_engine_id_here
```

**Cost:** 100 free queries/day. $5 per 1,000 if you go over.
100/day = enriching ~100 leads per day for free.

---

## 3. Hunter.io API Key — OPTIONAL (email verification + confidence scores)

Hunter verifies that found emails actually exist and adds a confidence percentage.
Without it, enrichment still works — emails just won't be verified.

**Steps (~5 min):**

1. Go to **hunter.io** → create a free account
2. Confirm your email address
3. Go to **Dashboard → API** (top right menu)
4. Copy the API key shown on that page

Add to your `.env`:
```
HUNTER_API_KEY=your_key_here
```

**Cost:** Free plan = 25 searches + 50 verifications/month.
Starter = $49/month for 500 searches. Optional — skip for now.

---

## 4. Snov.io API Key — OPTIONAL (extra email finder)

Additional email discovery on top of Google CSE. Low priority.

**Steps:**
1. Go to **snov.io** → create a free account
2. Go to **Settings → API** → copy your Client ID

```
SNOV_API_KEY=your_client_id_here
```

**Cost:** Free = 50 credits/month.

---

## Summary

| Priority | Key | Where | Time | Cost |
|---|---|---|---|---|
| 🔴 Required | `GOOGLE_MAPS_KEY` | console.cloud.google.com | Have it | $200 free/mo |
| 🔴 Required | `GOOGLE_CSE_KEY` + `GOOGLE_CSE_CX` | programmablesearchengine.google.com | ~5 min | 100 free/day |
| 🟡 Recommended | `HUNTER_API_KEY` | hunter.io | ~5 min | Free (25/mo) |
| 🟢 Optional | `SNOV_API_KEY` | snov.io | ~5 min | Free (50/mo) |

**Minimum to get fully running:** Google Maps key (you have it) + Google CSE (~5 min to set up).
