# Build Log

## Phase 1 — Design
- Defined data model: Tenants, Plans, Subscriptions, UsageEvents
- Set up `.gitignore` and `.env.example`
- Documented architecture in `DESIGN.md`

## Phase 2 — Core Billing Logic
- Set up Docker + PostgreSQL (port 5433)
- Created and seeded 4 tables (including Free and Pro plans)
- Built `/tenants`, `/generate`, `/usage` endpoints
- Implemented idempotency for usage event ingestion (duplicate requests don't double-count)
- Implemented quota enforcement (requests blocked once a tenant exceeds their plan limit)
- Verified both idempotency and quota enforcement with manual tests

## Part B — Stripe Integration
- Created Stripe sandbox account and installed Stripe CLI
- Built `/checkout` endpoint to create a Stripe Checkout Session for plan upgrades
- Built `/webhooks/stripe` endpoint to receive and process Stripe events
- Debugged a webhook failure: Stripe's Python SDK returns `Session` objects (not plain dicts) as of the current API version, so `.get()` calls failed with `AttributeError`. Fixed by calling `.to_dict()` on the event's data object before accessing fields.
- Verified full payment flow end-to-end: Checkout → payment → `checkout.session.completed` webhook → tenant plan upgraded from Free to Pro in the database

## Part C — Cost Calculation
- Added pricing constants: $0.001 per API call, $0.00002 per AI token
- Extended `/usage` endpoint to return a `cost` breakdown (per-metric cost + total cost)
- Verified calculation against known usage numbers

## Part D — Documentation
- Wrote README.md, EVIDENCE.md, BUILDLOG.md, capstone.yaml
- Compiled evidence screenshots for each phase
- Final push to GitHub and submission