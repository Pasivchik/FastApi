from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./app.py.db"

engine = create_async_engine(DATABASE_URL, echo=True)

async_session = sessionmaker(
  engine,
  expire_on_commit=False,
  class_=AsyncSession
)

session = async_session()
Base = declarative_base()
