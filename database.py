from sqlalchemy import Column, Integer, String, DateTime, Enum, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import enum
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://calls_user:calls_pass@localhost:5432/calls_db"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


# ── Енумы ──

class CallType(str, enum.Enum):
    video = "video"
    audio = "audio"


class CallStatus(str, enum.Enum):
    initiated  = "initiated"   # звонок создан
    active     = "active"      # оба участника в канале
    ended      = "ended"       # завершён нормально
    missed     = "missed"      # никто не ответил
    failed     = "failed"      # ошибка соединения


# ── Модели ──

class CallSession(Base):
    """История всех звонков."""
    __tablename__ = "call_sessions"

    id           = Column(Integer, primary_key=True, index=True)
    channel_name = Column(String(100), unique=True, index=True, nullable=False)
    caller_id    = Column(BigInteger, nullable=False, index=True)
    callee_id    = Column(BigInteger, nullable=False, index=True)
    call_type    = Column(Enum(CallType), default=CallType.video, nullable=False)
    status       = Column(Enum(CallStatus), default=CallStatus.initiated, nullable=False)
    started_at   = Column(DateTime, default=datetime.utcnow)
    ended_at     = Column(DateTime, nullable=True)
    duration_sec = Column(Integer, nullable=True)  # длительность в секундах


class TokenLog(Base):
    """Лог выданных токенов (для аудита)."""
    __tablename__ = "token_logs"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(BigInteger, nullable=False, index=True)
    channel_name = Column(String(100), nullable=False)
    role         = Column(String(20), nullable=False)
    issued_at    = Column(DateTime, default=datetime.utcnow)
    expires_at   = Column(DateTime, nullable=False)


# ── Dependency для FastAPI ──

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Создать таблицы при старте (если не существуют)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
