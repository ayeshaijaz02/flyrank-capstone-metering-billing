from database import Base, engine
import models  # noqa: F401  (import so SQLAlchemy knows about the tables)

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done! Tables created.")