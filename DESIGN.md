# Design Document — Usage Metering & Billing Engine

## The Problem

Every SaaS product needs to answer three questions: how much has a customer
used, how much should they pay, and have they hit their plan's limit? This
project is a backend service that answers all three — safely, even under
retries and failures.

## Who Has This Problem

Any company that charges customers based on usage (API calls, AI tokens,
storage, etc.) needs this. Real examples: OpenAI, Twilio, AWS.

## Plans and Quotas

| Plan | API calls / month | AI tokens / month | Price |
|------|-------------------|--------------------|-------|
| Free | 1,000             | 100,000            | $0    |
| Pro  | 10,000            | 1,000,000          | $20/month |

## Data Model

**tenants**
- id (primary key)
- name
- email
- created_at

**plans**
- id (primary key)
- name (Free / Pro)
- api_call_limit
- ai_token_limit
- price_cents

**subscriptions**
- id (primary key)
- tenant_id (foreign key → tenants)
- plan_id (foreign key → plans)
- stripe_subscription_id
- status (active / canceled / past_due)
- created_at

**usage_events**
- id (primary key)
- tenant_id (foreign key → tenants)
- type (api_call / ai_tokens)
- quantity
- idempotency_key (unique — prevents double-counting)
- created_at

## API Surface (planned endpoints)

- `POST /tenants` — create a tenant
- `POST /generate` — the dummy billable action (records usage, checks quota)
- `GET /usage` — see current usage, limit, and cost for a tenant
- `POST /checkout` — start a Stripe Checkout session to upgrade to Pro
- `POST /webhooks/stripe` — receives Stripe events (signature-verified)

## Non-Goal

We will NOT build invoicing, proration (mid-cycle plan changes), or overage
billing in the core system. These are optional stretch goals only.