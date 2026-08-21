from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # checks the connection is alive before using it —
                          # avoids "SSL connection has been closed unexpectedly"
                          # errors from Supabase's pooler dropping idle conns
    pool_recycle=1800,    # recycle connections every 30 min
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()