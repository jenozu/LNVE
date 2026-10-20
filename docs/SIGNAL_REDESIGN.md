# LNVE Signal — Isolated interactive redesign

**Review branch:** `feat/lnve-lumo-interactive-redesign`

This is an experimental, design-first evolution of the existing Flask + Jinja2 +
SQLite prospecting MVP. The original deployment and existing branches must not be
updated by this experiment.

## What changed

- A dark, editorial application shell with new branding, responsive sidebar,
  minimal navigation and keyboard-accessible controls.
- A cinematic market-discovery introduction that leads directly into the
  real Google Places form (all original field names and semantics retained).
- Custom range/number pairs, form validation and submission feedback.
- A prospect intelligence overview with **exact counts from SQLite**, separate
  website/no-website totals, a real opportunity distribution bar, and real
  manual-audit progress.
- Search history, live updates for running searches, client-side filtering,
  sortable tables, tabbed pools with URL anchors, and direct links to details.
- Search-specific CSV exports and a native HTML `details` + POST-form audit
  editor that works without JavaScript. Audit conditions remain
  `UNREVIEWED`, `SEVERE`, `POOR`, `AVERAGE`, `GOOD`.
- Responsive design and reduced-motion accommodations.

The initial results preview is capped at **25 recent businesses per pool**, as
it was in the MVP. These preview counts are **not** used as total metrics.

No new enrichment pipeline, automated scoring, lead-priority judgments,
background scraping service or website health diagnostics are enabled.

## Design tokens

| Element | Implementation |
| --- | --- |
| Background | Near black `#090e11` |
| Sidebar | Dark graphite `#0d1417` |
| Surface | Ink `#111a1e` |
| Primary text | Off-white `#eef3ef` |
| Primary accent | Mint `#b5eccd` |
| Secondary accent | Warm copper `#d3a981` |
| Typography | Space Grotesk for headings and metrics; DM Sans for UI; system fallbacks |
| Radius | 9px on controls; 14–16px on panels |
| Motion | Short transform/opacity entrances, 200ms interaction feedback; disabled for reduced motion |

The primary styles are in `static/lnve.css`. The dependency-light enhancement
layer is in `static/lnve.js`.

## Testing

```bash
# Set a dummy key; all test API responses are mocked/local
GOOGLE_MAPS_KEY=test-key SECRET_KEY=test-secret python -m unittest discover -s tests -v
```

CI runs the original Phase 3 and Phase 4 suites plus
`tests/test_redesign.py`. A separate GitHub Actions browser task uses a
temporary SQLite database of **fictional businesses**, renders the Flask
pages in headless Chromium at desktop/tablet/mobile widths, checks for
page-level overflow and JavaScript errors, and uploads screenshots as an
Actions artifact. Screenshots are synthetic fixtures, **not** real leads.

## Production isolation and staging

This branch deliberately **does not** contain an automatic deployment script
that could touch the production host, SQLite database or Nginx/systemd
services. A proper live preview needs an authorized host with a persistent
writable filesystem (or a separately configured persistence layer).

Vercel can run Flask functions, but ordinary Vercel serverless storage is not
persistent SQLite storage; do not use the LNVE MVP as-is for a production-like
Vercel preview. Never point staging at production's `DATABASE_PATH`.

Recommended isolated VPS staging arrangement, **only after approval**:

1. Set up a separate checkout of this feature branch, e.g.
   `/srv/lnve-signal-preview`, independent from the production LNVE folder.
2. Create a new `.venv` and install `requirements.txt` plus a WSGI server.
3. Give staging its own `SECRET_KEY`, `DATABASE_PATH` pointing to a new
   writable staging-only SQLite file, and separate/test Google API
   configuration. All private settings remain outside Git.
4. Bind a separate, private high port, not production's port 5000. Keep it
   unexposed until an independent TLS preview hostname/reverse proxy and
   access controls are approved.
5. Test uploads, searches and audits with staging-only synthetic or
   explicitly authorized test records.
6. Leave production's existing service, environment, database, domain,
   DNS, routing, and deployment configuration untouched.

A staging hostname cannot be claimed until it actually resolves and serves
the isolated application.

## Scope and known limitations

- Responsive screenshots are available from the branch's GitHub Actions
  workflow artifact; no claim is made that a persistent staging deployment
  exists until it has been independently verified.
- Browser tables filter the records currently shown; the 25-row global
  preview is not server-side pagination. Search detail loads all results for
  one search, as before.
- Fonts and icon glyphs use remote providers with system-font/text fallbacks.
- Manual website review remains a human task; "good" and "poor" are entered
  by the operator, never algorithmically inferred.
- The search button can incur Google Places charges when real credentials
  are configured. Automated tests and screenshots make zero live API calls.

Do not merge this branch or deploy it to `lnve.andel-vps.space` without
explicit user authorization.
