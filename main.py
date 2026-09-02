import os
import uuid
import stripe
PRICE_PER_API_CALL = 0.001
PRICE_PER_AI_TOKEN = 0.00002
from fastapi import FastAPI, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from database import get_db
from models import Tenant, Plan, Subscription, UsageEvent

app = FastAPI(title="Usage Metering & Billing Engine")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


# ---------- Request/response shapes ----------

class TenantCreate(BaseModel):
    name: str
    email: str


class GenerateRequest(BaseModel):
    tenant_id: str
    type: str          # "api_call" or "ai_tokens"
    quantity: int
    idempotency_key: str


# ---------- Endpoints ----------

@app.post("/tenants")
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    # every new tenant starts on the Free plan
    free_plan = db.query(Plan).filter(Plan.name == "free").first()
    if not free_plan:
        raise HTTPException(status_code=500, detail="Free plan not seeded yet")

    tenant = Tenant(name=payload.name, email=payload.email)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=free_plan.id,
        status="active",
    )
    db.add(subscription)
    db.commit()

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "email": tenant.email,
        "plan": free_plan.name,
    }


@app.post("/generate")
def generate(payload: GenerateRequest, db: Session = Depends(get_db)):
    tenant_id = uuid.UUID(payload.tenant_id)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # --- Step 1: check quota BEFORE recording usage ---
    subscription = (
        db.query(Subscription)
        .filter(Subscription.tenant_id == tenant_id, Subscription.status == "active")
        .first()
    )
    plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first()

    current_total = (
        db.query(UsageEvent)
        .filter(UsageEvent.tenant_id == tenant_id, UsageEvent.type == payload.type)
        .with_entities(UsageEvent.quantity)
        .all()
    )
    used_so_far = sum(q[0] for q in current_total)

    limit = plan.api_call_limit if payload.type == "api_call" else plan.ai_token_limit

    if used_so_far + payload.quantity > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Usage quota exceeded for '{payload.type}'. Used {used_so_far}/{limit}.",
        )

    # --- Step 2: record usage safely (idempotent) ---
    event = UsageEvent(
        tenant_id=tenant_id,
        type=payload.type,
        quantity=payload.quantity,
        idempotency_key=payload.idempotency_key,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # same idempotency_key already used -> this is a retry, not a new event
        db.rollback()
        existing = (
            db.query(UsageEvent)
            .filter(UsageEvent.idempotency_key == payload.idempotency_key)
            .first()
        )
        return {
            "status": "duplicate_ignored",
            "usage_event_id": str(existing.id),
            "message": "This request was already processed (idempotency key reused).",
        }

    return {
        "status": "recorded",
        "usage_event_id": str(event.id),
        "used_so_far": used_so_far + payload.quantity,
        "limit": limit,
    }


@app.get("/usage")
def get_usage(tenant_id: str, db: Session = Depends(get_db)):
    tid = uuid.UUID(tenant_id)

    subscription = (
        db.query(Subscription)
        .filter(Subscription.tenant_id == tid, Subscription.status == "active")
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription for this tenant")

    plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first()

    events = db.query(UsageEvent).filter(UsageEvent.tenant_id == tid).all()

    api_calls_used = sum(e.quantity for e in events if e.type == "api_call")
    ai_tokens_used = sum(e.quantity for e in events if e.type == "ai_tokens")

    api_calls_cost = round(api_calls_used * PRICE_PER_API_CALL, 4)
    ai_tokens_cost = round(ai_tokens_used * PRICE_PER_AI_TOKEN, 4)
    total_cost = round(api_calls_cost + ai_tokens_cost, 4)

    return {
        "plan": plan.name,
        "api_calls": {"used": api_calls_used, "limit": plan.api_call_limit},
        "ai_tokens": {"used": ai_tokens_used, "limit": plan.ai_token_limit},
        "cost": {
            "api_calls_cost": api_calls_cost,
            "ai_tokens_cost": ai_tokens_cost,
            "total_cost": total_cost,
        },
    }
@app.post("/checkout")
def create_checkout_session(tenant_id: str, db: Session = Depends(get_db)):
    tid = uuid.UUID(tenant_id)
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRO_PRICE_ID, "quantity": 1}],
        customer_email=tenant.email,
        success_url="http://127.0.0.1:8000/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://127.0.0.1:8000/cancel",
        metadata={"tenant_id": str(tenant.id)},
    )

    return {"checkout_url": session.url}
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None), db: Session = Depends(get_db)):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        # signature is invalid or forged -> reject it
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        data_object = data_object.to_dict()
        tenant_id = data_object.get("metadata", {}).get("tenant_id")
        stripe_subscription_id = data_object.get("subscription")

        if tenant_id:
            tid = uuid.UUID(tenant_id)
            pro_plan = db.query(Plan).filter(Plan.name == "pro").first()

            # deactivate old subscription, create the new Pro one
            old_sub = (
                db.query(Subscription)
                .filter(Subscription.tenant_id == tid, Subscription.status == "active")
                .first()
            )
            if old_sub:
                old_sub.status = "canceled"

            new_sub = Subscription(
                tenant_id=tid,
                plan_id=pro_plan.id,
                stripe_subscription_id=stripe_subscription_id,
                status="active",
            )
            db.add(new_sub)
            db.commit()

    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = data_object.get("id")
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub_id)
            .first()
        )
        if sub:
            sub.status = "canceled"
            db.commit()

    return {"status": "received"}