from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings
from app.core.observability import headers
from sqlalchemy import event
import json

engine = create_engine(get_settings().DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(Session, "before_flush")
def store_event_context(session, flush_context, instances):
    from app.models import OutboxEvent
    for record in session.new:
        if isinstance(record, OutboxEvent) and record.context is None:
            record.context = json.dumps(headers())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
