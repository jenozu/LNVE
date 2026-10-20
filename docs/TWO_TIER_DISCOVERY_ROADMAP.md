# LNVE — Two-tier discovery & enrichment implementation roadmap

> **Living implementation checklist.** This is the single source of truth for the Geoapify + Google Maps Scraper (GMS) work. Check off tasks **only after their acceptance criteria pass**, add the completion commit/PR next to each completed task, and update "Next task" after each milestone.

**Status:** PLANNED — implementation not started  
**Next task:** `T0.1` — establish approval and source-use rules; then `T1.1` — create a free Geoapify account/key.  
**Development base:** `feat/lnve-lumo-interactive-redesign`  
**Production:** `main` and the current VPS production LNVE service **must not be modified** by these tasks without explicit deployment authorization.  
**Preview:** Current Vercel Signal preview is a **synthetic demo**, not durable production hosting.  
**Guiding objective:** Discover businesses without a Google Cloud billing account, qualify website opportunities, and selectively enrich matching leads with additional information **where permitted**, without duplicates or invented facts.

## Target workflow

```text
User: business type + area + radius
               |
        Geoapify Geocoding + Places
        (primary business discovery)
               |
     Normalize + deduplicate + save
               |
       Website state assessment
       /             |            \
  Website found   Unknown       Verified absent
       |             |            |
   Audit queue   Verify next    No-website pool
       \             |            /
           Select / queue enrichment
               |
     Optional GMS adapter on VPS
     (match listing by name + address
      + coordinates + phone)
               |
    Confidence + provenance checks
               |
   Fill missing permitted attributes:
   website, phone, Google Maps URL,
   ratings, review counts, review text,
   hours, descriptions (if available)
               |
    Reclassify / review / CSV export
```

**Nonnegotiable distinctions:**

- `Geoapify missing website` is **UNKNOWN**, not `NO_WEBSITE`. No-website candidates must have a documented secondary check and may remain unverified; never imply absence is proven simply by missing metadata.
- `No Google review data` is **UNKNOWN**, not `0 reviews`. Preserve nullability/status.
- `Geoapify place_id` and `Google Place ID` are **different identifier namespaces**.
- Review text and other Google-derived fields must not be permanently ingested, reused, or exported unless applicable permissions allow it. The GMS integration stays **disabled** until the source-use review in T0.2 is resolved; the first-tier system remains useful on its own.
- Do not collect email as if it were necessarily a GMS or Geoapify field. Use existing provider email only when available; direct business-site enrichment is a separate, optional future capability.
- Enrichment must **never overwrite** an existing nonempty verified value with an empty or lower-confidence value; preserve competing values and source information for review.
- No Google Cloud API, paid service, proxy purchase, or unexpected production deployment is required for the pilot.

## Phase tracker

| Phase | Goal | Status |
|---|---|---|
| T0 — Decisions and safety | Confirm data rights, boundaries, hosting | ⬜ Not started |
| T1 — Free data coverage pilot | Confirm Geoapify actually finds target trades | ⬜ Not started |
| T2 — Architecture and database | Source-aware, migration-safe records | ⬜ Not started |
| T3 — Geoapify integration | Real business discovery, no Google API key | ⬜ Not started |
| T4 — Reliable orchestration | Persistent jobs and source-agnostic search status | ⬜ Not started |
| T5 — GMS technical pilot | Evaluate fields, matching, rights and operation | ⬜ Not started |
| T6 — Selective enrichment | Match, merge and report missing fields | ⬜ Not started |
| T7 — UI / exports | Honest qualification and enrichment workflow | ⬜ Not started |
| T8 — Testing / deployment | Repeatable, isolated end-to-end delivery | ⬜ Not started |

Mark phases COMPLETE only when all constituent tasks and the phase's exit gate pass. Keep PRs scoped to one phase or small related task group.

## T0 — Decisions, licensing and safe environments

- [ ] **T0.1 — Set the pilot boundaries.** Start with Mississauga and three existing niches: roofing, HVAC, landscaping; modest manual search volume; separate test DB; no changes to production.
- [ ] **T0.2 — Review source permissions before enabling GMS.** Read current Google Maps and Geoapify terms, specifically automated extraction, storing business attributes, review text, creating lead lists, and attribution. Record which Google-derived fields (if any) LNVE may retain, display or export. If not permitted or uncertain, leave GMS disabled and define a licensed replacement/research-only workflow. **This is an approval gate, not a claim that low-volume scraping is authorized.**
- [ ] **T0.3 — Decide execution location.** Use the existing Hostinger VPS as a candidate for an **isolated** test worker + persistent SQLite DB, with its own folder, venv, service/port and credentials. Do not change the live LNVE service, domain, Nginx, SQLite database, or cron jobs. Vercel may continue to serve a demo front end.
- [ ] **T0.4 — Define limits.** Decide maximum businesses per search, optional GMS leads per run, manual-only vs automatic enrichment, retry ceiling, timeout, daily budget, and ability to stop jobs. Default GMS off; no proxy purchase; do not work around access denials.
- [ ] **T0.5 — Establish secure configuration.** Put keys exclusively in gitignored `.env` or host environment variables, never in templates, log output, screenshots, repo commits or public browser requests.

**Exit gate:** Written source-use decision, isolation strategy and initial limits recorded here in the Decision log. No external API calls until the user obtains a Geoapify key.

## T1 — Validate Geoapify coverage *before* building the integration

- [ ] **T1.1 — Obtain Geoapify key.** Create a free account at https://myprojects.geoapify.com/; confirm no credit card required; limit key usage where practical.
- [ ] **T1.2 — Test free geocoding.** Resolve `Mississauga, ON` to coordinates and test an explicit `lat,lon` input; document ambiguous address behavior and failed lookups.
- [ ] **T1.3 — Map niches to supported Geoapify categories.** Inspect the actual category taxonomy for roofing, HVAC, landscaping, plumbing, electrical and other LNVE niches. **Do not assume** Google-style free-text trade searches are supported directly. Define exact category mapping, any client-side name/tag filtering, and a clear unsupported-category response.
- [ ] **T1.4 — Run the controlled coverage experiment.** For roofing, HVAC and landscaping within one small Mississauga region, capture business count, names, addresses, coordinate coverage, phone availability, website availability, duplicates and obviously irrelevant businesses. Record raw count and qualified count separately.
- [ ] **T1.5 — Check API mechanics.** Use a hard geographic `filter=circle:lon,lat,radiusMeters` (not just `bias`), handle 1–500 results/page and `offset` carefully; document credit consumption and quota exhaustion.
- [ ] **T1.6 — Decide GO / ADJUST / NO-GO.** If category coverage is poor, refine taxonomy, test another open source (OSM / Foursquare / Overture), or narrow supported niches *before* implementing the full pipeline.

**Exit gate:** A short `docs/GEOAPIFY_COVERAGE_PILOT.md` with reproducible queries, measured results, useful/missing fields, category mappings, and a clear viability decision. No invented Google ratings.

## T2 — Source-aware architecture and additive database migration

- [ ] **T2.1 — Write a source-neutral discovery contract.** Define a typed normalized business record: `source`, `source_place_id`, `name`, `address`, `lat/lon`, `phone`, `website`, `categories`, `collected_at`, nullable reputation fields. Keep raw provider payloads out of permanent storage unless authorized.
- [ ] **T2.2 — Design additive schema changes in `database/repository.py`.** Plan source-specific IDs and field provenance, `website_verification_status` (unknown / candidate_missing / website_found / verified_no_website), `review_data_status` (unknown / available / unavailable / error), `geoapify_status`, `enrichment_status`, `enriched_at`, and an independent job table. Keep legacy columns readable during migration.
- [ ] **T2.3 — Make deduplication source aware.** Existing `UNIQUE(search_id, business_name)` and Google `place_id` assumptions are inadequate. Specify stable source IDs + a normalized name/address/coordinates identity policy; handle duplicate branches, chains, and companies at the same address.
- [ ] **T2.4 — Preserve audit records during merging.** Never delete `website_condition`, `audit_notes`, `audited_at`, or lead IDs on an enrichment rerun; do not move a prospect out of a pool without preserving its manual assessment.
- [ ] **T2.5 — Add repeatable migrations and rollback plan.** Migrate both a blank test DB and a copy of a historical schema, back up test fixtures, run migrations twice, preserve prior CSV output and known searches.
- [ ] **T2.6 — Add database tests.** Verify unknown website/review states, source attribution, conflicting fields, repeated saves, duplicate place names and old Phase 2–4 migrations.

**Exit gate:** Deterministic fixture tests pass; a historical database can migrate without losing any records or audits.

## T3 — Implement Geoapify as the primary provider

- [ ] **T3.1 — Add `integrations/geoapify.py`** (proposed path): requests with timeouts, HTTP errors, 429 handling, bounded retries, category mapping, circle search, pagination and contact parsing.
- [ ] **T3.2 — Make Google Cloud optional.** In `config.py`/`.env.example`, support `DISCOVERY_PROVIDER=geoapify` and `GEOAPIFY_API_KEY`. Remove the unconditional Google-key validation **for the Geoapify provider only**; keep existing Google client isolated and backwards-compatible where feasible.
- [ ] **T3.3 — Replace Google geocoding for Geoapify discovery.** Update `web/routes/search.py` through a provider abstraction; support city and explicit coordinates, invalid locations and safe radius handling.
- [ ] **T3.4 — Normalize and save results.** Persist newly discovered businesses as Geoapify sourced, with nullable reviews and UNKNOWN website state where appropriate. Preserve the exact source and retrieval time.
- [ ] **T3.5 — Replace Google-only form claims.** In `web/templates/index.html`, display the chosen provider and remove the inaccurate “paid Google Places request” note. Treat min-rating and min-review constraints as optional **post-enrichment** filters, not Geoapify discovery gates.
- [ ] **T3.6 — Mock API integration tests.** Cover 0 results, multiple pages, duplicated results, missing website, unavailable phone, valid website, 429, 500 and network timeout. Automated CI uses fixtures, never a real paid call.

**Exit gate:** Real Geoapify search completes with *no* `GOOGLE_MAPS_KEY`; results are saved and browseable; unsupported niches are reported clearly.

## T4 — Reliable discovery/enrichment jobs

- [ ] **T4.1 — Replace request-local daemon threading on deployment path.** Current `web/routes/search.py` starts a `Thread(..., daemon=True)`; Vercel serverless cannot reliably host background work. Use a persistent VPS worker or another durable task runner.
- [ ] **T4.2 — Add job states and source progress.** `queued/running/completed/partial/failed/cancelled`, attempts, created/started/finished timestamps, source-specific counts, and actionable errors.
- [ ] **T4.3 — Implement idempotent queue semantics.** Repeated clicks, retries, worker restarts and duplicate callbacks cannot create duplicate leads, review records or contradictory statuses.
- [ ] **T4.4 — Update cancel/poll endpoints and dashboard.** Preserve `/api/search-status/<id>` and existing results UI while accurately reporting Geoapify and optional enrichment stages, including partial results.
- [ ] **T4.5 — Add abuse and cost controls.** Authentication for real search, per-user/day request budgets, max radius/results, a kill switch and no expensive work triggered from an anonymous public Vercel demo.

**Exit gate:** Start, monitor, cancel, resume and complete a search after a worker restart using test fixtures.

## T5 — GMS feasibility, matching and permissions gate

- [ ] **T5.1 — Inspect and pin GMS version.** Use https://github.com/gosom/google-maps-scraper ; document exact release/commit, Docker image, supported JSON/CSV fields and REST job APIs, and expected CPU/memory.
- [ ] **T5.2 — Confirm permitted review-data usage.** Revisit T0.2 before executing any scrape or storing Google-sourced content. Only run a limited technical pilot if the proposed use is permitted. Otherwise mark GMS integration BLOCKED and substitute a licensed provider or manual link-out.
- [ ] **T5.3 — Prototype an isolated adapter.** Proposed `integrations/gms.py`; communicate only with a locally bound/private GMS service on the VPS. Do not expose its API publicly. No proxies or block-bypass automation by default.
- [ ] **T5.4 — Test carefully scoped name/address lookup.** Compare a small manually selected list of businesses (if permitted); record matched, unmatched, ambiguous and wrong matches; do not blindly accept the first search result.
- [ ] **T5.5 — Inventory available supplemental fields.** Check: missing website and phone, Google Maps URL, rating, review count, individual review text, opening hours and descriptions. Distinguish “not returned”, “extraction failed” and “verified empty”.
- [ ] **T5.6 — Decide review retention rules.** Specify allowed fields, whether individual review text may be displayed/stored, attribution, retention, export restrictions and manual data deletion. **Default: don't persist or export raw Google review text until permission is established.**
- [ ] **T5.7 — GO / ADJUST / NO-GO.** Record source coverage, matching precision, processing time, operational failures, terms decision and actual operating costs. A technical success alone does not authorize production scraping.

**Exit gate:** Documented GMS feasibility and rights decision; zero wrong matches accepted in the inspected pilot sample. GMS stays optional.

## T6 — Selective second-tier enrichment and merge rules

- [ ] **T6.1 — Implement explicit enrichment selection.** Support “Enrich this business” and a capped selected-business batch option. Future auto-enrichment after Geoapify may be enabled only by configuration with a strict max per run.
- [ ] **T6.2 — Build a confidence-scored business matcher.** Compare normalized name, formatted address, geographic distance and matching phone; define an acceptance threshold from pilot data; route ambiguous matches to manual confirmation.
- [ ] **T6.3 — Implement source-precedence and provenance.** Fill absent fields where permitted; never replace verified, audited or manual values silently. Preserve source, timestamp and any conflicts.
- [ ] **T6.4 — Re-evaluate website state after enrichment.** A found official website moves an unknown/missing-candidate business to website audit queue. Lack of a second source alone is not proof of absence. Avoid duplicate prospect rows.
- [ ] **T6.5 — Handle optional reviews and reputation correctly.** Record `rating`, `review_count`, Google Maps URL and individual review text **only to the extent authorized**; maintain UNKNOWN/ERROR states and do not convert null to zero.
- [ ] **T6.6 — Add matching and retry tests.** Cases: similar-name businesses, same address, multiple branches, missing coordinates, conflicting phone, blank provider fields, timeout, 429/block/captcha, idempotent rerun and a user-modified audit.
- [ ] **T6.7 — Fail gracefully.** A GMS outage never prevents Geoapify discovery, manual audits, CSV exports or viewing previously saved leads.

**Exit gate:** Only high-confidence matches enrich a single existing lead; every displayed supplemental field has provenance and all conditional data rights are respected.

## T7 — LNVE Signal dashboard, source statuses and CSV export

- [ ] **T7.1 — Keep existing two business opportunity pools** plus an **Unknown / Needs website verification** holding state so leads without source website info aren't falsely called “No website”.
- [ ] **T7.2 — Show source and enrichment badges.** Geoapify source, review unavailable, queued/enriched/ambiguous/failed, matched Google listing if permitted, date last checked.
- [ ] **T7.3 — Add controls to enrichment workflow.** Per-lead action and small batch queue with confirmation, caps, progress and errors. Do not trigger GMS automatically by simply viewing a page.
- [ ] **T7.4 — Make rating/review filters honest.** Allow discovery without review fields; only offer rating-based qualification where those fields truly exist and can be used. Null values are not 0-star businesses.
- [ ] **T7.5 — Update `web/routes/export.py`.** Include independent provider/source, website verification, enrichment status, and per-field provenance as appropriate. Do **not** export Google review text unless authorized.
- [ ] **T7.6 — Preserve Signal redesign behavior.** Sidebar, responsive mobile/tablet/desktop views, audit forms, sort/filter, recent searches, source counts and existing exports.
- [ ] **T7.7 — Update user-facing docs.** Onboarding for Geoapify key, honest data completeness labels, optional GMS and its usage restrictions, troubleshooting, backups and safe rollback.

**Exit gate:** The full discover → verify → audit → export journey works with Geoapify alone, and optional authorized enrichment does not disrupt it.

## T8 — Regression tests, staging and release

- [ ] **T8.1 — Run Python unit/integration suite.** Keep `tests/test_phase3.py`, `tests/test_phase4.py`, `tests/test_redesign.py` passing; add isolated Tier 1, worker, DB migration, matching and enrichment contract tests.
- [ ] **T8.2 — Run no-network CI.** Fake Geoapify/GMS responses; no Google Cloud API usage, third-party scraping or secrets required in GitHub Actions.
- [ ] **T8.3 — Browser smoke test.** Check desktop/tablet/mobile, filters, three website states, empty results, error paths, audit preservation and export contents.
- [ ] **T8.4 — Deploy **only** to isolated staging** with a distinct VPS directory, virtualenv, SQLite database, worker/service, credentials and hostname; do not touch the live app, live database, existing `systemd` unit, Nginx routes or production domain.
- [ ] **T8.5 — Execute a small permitted live Geoapify pilot.** Review real business records for relevance, duplicate rate, website status quality, missing-field coverage and API credits used. If T5 approved, selectively test authorized Tier 2 on a small manual sample.
- [ ] **T8.6 — Record explicit go/no-go review.** Confirm licensing, costs, privacy, security, backups, operator manual, rollback and reproducibility before any production cutover; never deploy solely because CI is green.

**Exit gate:** Staging has working real Geoapify searches and existing LNVE features, with verified safe fallback if GMS remains disabled. Any production change requires a separate explicit request.

## Known LNVE implementation touchpoints

These are **existing** project files inspected when writing this roadmap:

| Existing file | What needs attention |
|---|---|
| `config.py` and `.env.example` | Unconditionally require `GOOGLE_MAPS_KEY`; must allow a Geoapify-only mode |
| `web/routes/search.py` | Google-only geocoding, `GoogleMapsScraper` class, daemon thread, and Google-specific statuses |
| `scrapers/google_maps.py` | Actually Google **Places API (New)**, not the open-source gosom scraper; avoid naming confusion |
| `database/repository.py` | `UNIQUE(search_id, business_name)`, Google `place_id`, two fixed website states and default `review_count=0` |
| `web/routes/results.py` | Assumes only two classified website pools |
| `web/routes/export.py` | Missing/zero review ambiguity; no per-field provider or enrichment provenance |
| `web/templates/index.html` | Google-only rating/review criteria and paid Google Places message |
| `web/templates/results.html` and `web/templates/search_detail.html` | Need honest unknown state and enrichment actions |
| `app.py`, `demo_seed.py` | Current isolated demo mode, synthetic records and startup validation |
| `.github/workflows/ci.yml` | Preserve existing tests; add fixture-driven provider and worker verification |

**Proposed new files**, subject to T2 architecture review: `integrations/geoapify.py`, `integrations/gms.py`, `services/business_matching.py`, `services/discovery_pipeline.py`, `workers/jobs.py`, `tests/test_geoapify.py`, `tests/test_matching.py`, `tests/test_enrichment.py`, `docs/GEOAPIFY_COVERAGE_PILOT.md`. Paths are a plan, not current files.

## Quick implementation guidance

- **Milestone 1 (T0–T1):** Establish source rights and empirical coverage before investing in architecture.
- **Milestone 2 (T2–T4):** A complete usable **Geoapify-only LNVE**, no Google Cloud key or GMS dependency, persistent on safe staging.
- **Milestone 3 (T5–T6):** Optional, permission-reviewed GMS enrichment, including review data *only where authorized*.
- **Milestone 4 (T7–T8):** Good-quality UX, regression suite and cautious release.

The LNVE source code's existing `GoogleMapsScraper` name refers to the official Google **Places API** client. The separately named **GMS** in this plan refers to the Go project `gosom/google-maps-scraper`; never treat these as the same program.

## Decision log

| Date | Decision | State |
|---|---|---|
| 2026-10-20 | Primary discovery: Geoapify to avoid Google Cloud billing/card-hold requirement | Chosen, not integrated |
| 2026-10-20 | Desired Tier 2: GMS to fill missing website/phone/maps URL and optionally add ratings, review counts, review text and other details | Proposed, permissions gate pending |
| 2026-10-20 | Retain existing LNVE manual website audit and CSV workflow | Required |
| 2026-10-20 | Current main/production deployment remains unchanged; work on feature branches/test databases | Required |
| TBD | Geoapify taxonomy and coverage results | Pending T1 |
| TBD | GMS permitted uses and field retention policy | Pending T0/T5 |
| TBD | Hosting plan / staging worker | Pending T0/T4 |
| TBD | Production cutover authorization | Not granted |

## External references (re-check at implementation time)

- Geoapify Places API: https://apidocs.geoapify.com/docs/places/ (category+geometry searches, 500/page, offset, credits)
- Geoapify Place Details: https://apidocs.geoapify.com/docs/place-details/
- Geoapify accounts: https://myprojects.geoapify.com/
- GMS project: https://github.com/gosom/google-maps-scraper (CLI, `-extra-reviews`, Docker and REST API)
- Current Google Maps end-user terms: https://www.google.com/help/terms_maps/
- Geoapify pricing: https://www.geoapify.com/pricing/

## Progress notes / handoff format

At the end of each work session append a short record below. This is how we can resume without re-planning:

```text
Date:
Completed task IDs:
Commit / PR:
Tests / evidence:
Open issues:
Next task ID:
```

---
**Progress notes**

_No implementation tasks completed yet._
