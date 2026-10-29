from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


from config import settings

# pool_pre_ping checks a connection before using it, so a database restart
# doesn't cause "connection closed" errors


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal= sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency one database siion per request, always closed"""

    with SessionLocal() as db:
        yield db