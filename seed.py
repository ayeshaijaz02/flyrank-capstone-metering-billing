from database import SessionLocal
from models import Plan

db = SessionLocal()

existing = db.query(Plan).count()
if existing > 0:
    print("Plans already exist, skipping seed.")
else:
    free_plan = Plan(
        name="free",
        api_call_limit=1000,
        ai_token_limit=100_000,
        price_cents=0,
    )
    pro_plan = Plan(
        name="pro",
        api_call_limit=10_000,
        ai_token_limit=1_000_000,
        price_cents=2000,  # $20.00
    )
    db.add(free_plan)
    db.add(pro_plan)
    db.commit()
    print("Seeded Free and Pro plans.")

db.close()