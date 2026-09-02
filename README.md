# Usage Metering & Billing Engine

A backend system that tracks API usage per tenant, enforces plan-based quotas, and integrates with Stripe for subscription billing — built as a FastAPI + PostgreSQL capstone project.

## Features

- Multi-tenant usage tracking (API calls, AI tokens)
- Plan-based quota enforcement (Free / Pro)
- Idempotent usage event ingestion
- Stripe Checkout integration for plan upgrades
- Stripe webhook handling (auto-upgrades tenant on successful payment)
- Real-time cost calculation based on usage

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL (via Docker)
- **Payments:** Stripe (Checkout + Webhooks)
- **ORM:** SQLAlchemy

## Setup

1. Clone the repo