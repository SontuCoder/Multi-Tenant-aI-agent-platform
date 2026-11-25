from sqlmodel import create_engine, Session, SQLModel
from core import settings
from contextlib import contextmanager
database_url = settings.DATABASE_URL

if database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=300,
    connect_args={
        "connect_timeout": 10
    },
    echo=False,
)


def get_session():
    with Session(engine) as session:
        yield session


def create_tables():
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE EXTENSION IF NOT EXISTS vector"
        )
    SQLModel.metadata.create_all(engine)

# For background tasks
@contextmanager
def get_background_session():
    with Session(engine) as session:
        yield session