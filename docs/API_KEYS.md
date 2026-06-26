# API Keys Setup Guide

A step-by-step guide to getting every key LNVE needs.
Keys are listed in priority order — **Required** ones must be set before the app will run.

---

## 1. Google Maps API Key — REQUIRED (for scraping)

This is what finds businesses. Without it the app won't start.

**You already have one** (`AIzaSyAF2o41pCgmvCJVQaIwfXfp7-fHXDrpblM`) from your original script.
Before using it, confirm two things in Google Cloud Console:

1. Go to **console.cloud.google.com**
2. Sign in → select your project
3. Go to **APIs & Services → Enabled APIs**
4. Make sure both of these are enabled:
   - **Places API**
   - **Geocoding API**
5. Go to **APIs & Services → Credentials** → click your key → confirm it isn't restricted to a domain or IP that would block it

If the key is expired or restricted, create a new one:
- **Credentials → Create Credentials → API Key**
- Restrict it to "Places API" and "Geocoding API" only (good security practice)

**Cost:** Places API charges ~$17 per 1,000 detail lookups. Google gives you $200/month free credit, which covers roughly 11,000 business detail calls. For normal use you won't pay anything.

---

## 2. Bing Web Search API — REQUIRED for email enrichment

This is how LNVE finds email addresses — it searches the web for each business's contact page.
You need **at least one** of Bing or Google CSE. Bing is easier and cheaper to set up.

**Steps:**

1. Go to **portal.azure.com** and sign in (create a free Microsoft Azure account if you don't have one — no credit card required for free tier)
2. Click **Create a resource** (the big + button)
3. Search for **"Bing Search v7"**
4. Click **Bing Search v7** → **Create**
5. Fill in:
   - **Subscription:** Free Trial (or your existing subscription)
   - **Resource group:** Create new → name it `lnve`
   - **Name:** anything, e.g. `lnve-bing`
   - **Pricing tier:** Select **F1 (Free)** — 1,000 searches/month at no cost
6. Click **Review + Create** → **Create**
7. Once deployed, click **Go to resource**
8. In the left sidebar click **Keys and Endpoint**
9. Copy **Key 1**

Paste it in your `.env`:
```
BING_V7_KEY=your_key_here
```

**Cost:** Free tier = 1,000 calls/month. Each lead enrichment uses ~1 search call.
Paid tier (S1) = $7/1,000 calls if you need more.

---

## 3. Hunter.io API Key — OPTIONAL (email verification)

Hunter verifies that found emails actually exist and gives a confidence score.
Without it, enrichment still works — emails just won't be verified.

**Steps:**

1. Go to **hunter.io** and create a free account
2. Confirm your email
3. Go to **Dashboard → API** (top right menu or sidebar)
4. Your API key is shown on that page — copy it

Paste it in your `.env`:
```
HUNTER_API_KEY=your_key_here
```

**Cost:** Free plan = 25 searches/month + 50 verifications/month.
Starter plan = $49/month for 500 searches. Only needed if you want email confidence scores.

---

## 4. Google Custom Search Engine — OPTIONAL (alternative to Bing)

A second search provider for enrichment. Only set this up if Bing isn't working or you want more search coverage. You need **both** a CSE key and a CX (engine) ID.

**Step A — Create the search engine:**

1. Go to **programmablesearchengine.google.com**
2. Click **Add** (or **Get Started**)
3. Under "Sites to search" type `*.com` (search the whole web)
4. Name it `LNVE`
5. Click **Create**
6. Click **Customize** on your new engine
7. Turn on **"Search the entire web"**
8. Copy the **Search engine ID** — this is your `GOOGLE_CSE_CX`

**Step B — Get the API key:**

1. Go to **console.cloud.google.com**
2. **APIs & Services → Library** → search **Custom Search API** → Enable it
3. **APIs & Services → Credentials → Create Credentials → API Key**
4. Copy the key

Paste both in your `.env`:
```
GOOGLE_CSE_KEY=your_api_key_here
GOOGLE_CSE_CX=your_engine_id_here
```

**Cost:** Free = 100 queries/day. Paid = $5 per 1,000 queries.

---

## 5. Snov.io API Key — OPTIONAL (extra email finder)

Another email discovery service. Lower priority — only add this if Hunter + Bing aren't finding enough emails.

**Steps:**

1. Go to **snov.io** → create a free account
2. Go to **Settings → API**
3. Copy your **Client ID** (used as the API key)

Paste it in your `.env`:
```
SNOV_API_KEY=your_client_id_here
```

**Cost:** Free plan = 50 credits/month.

---

## Summary — What to set up first

| Priority | Key | Where | Time | Cost |
|---|---|---|---|---|
| 🔴 Required | `GOOGLE_MAPS_KEY` | Google Cloud Console | Already have it | $200 free/month |
| 🔴 Required | `BING_V7_KEY` | portal.azure.com | ~10 min | Free (1k/month) |
| 🟡 Recommended | `HUNTER_API_KEY` | hunter.io | ~5 min | Free (25/month) |
| 🟢 Optional | `GOOGLE_CSE_KEY` + `GOOGLE_CSE_CX` | Google Cloud + PSE | ~15 min | Free (100/day) |
| 🟢 Optional | `SNOV_API_KEY` | snov.io | ~5 min | Free (50/month) |

**Minimum to get everything working:** Google Maps key (you have it) + Bing key (~10 minutes to set up).
