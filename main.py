from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from typing import Optional
from datetime import datetime
import time
import os
from dotenv import load_dotenv

from agora_token_builder import RtcTokenBuilder
from database import get_db, init_db, CallSession as CallSessionModel, TokenLog, CallStatus
from cache import (
    cache_token, get_cached_token,
    set_active_call, get_active_call, remove_active_call,
    ping_redis, close_redis
)

load_dotenv()

app = FastAPI(
    title="Agora Calls API",
    description="API для аудио/видео звонков через Agora",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

AGORA_APP_ID          = os.getenv("AGORA_APP_ID", "")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE", "")
TOKEN_EXPIRE_SECONDS  = int(os.getenv("TOKEN_EXPIRE_SECONDS", "3600"))


# ────────────────────────── Жизненный цикл ──────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    print("✅ БД инициализирована")


@app.on_event("shutdown")
async def shutdown():
    await close_redis()
    print("🛑 Redis соединение закрыто")


# ────────────────────────── Схемы ──────────────────────────

class TokenRequest(BaseModel):
    user_id: int
    channel_name: str
    role: Optional[str] = "publisher"


class TokenResponse(BaseModel):
    user_id: int
    channel_name: str
    token: str
    app_id: str
    expires_at: int
    role: str
    from_cache: bool = False


class CallSessionRequest(BaseModel):
    caller_id: int
    callee_id: int
    channel_name: str
    call_type: Optional[str] = "video"


class CallSessionResponse(BaseModel):
    session_id: int
    channel_name: str
    call_type: str
    caller: TokenResponse
    callee: TokenResponse


class EndCallRequest(BaseModel):
    channel_name: str
    status: Optional[str] = "ended"  # ended | missed | failed


# ────────────────────────── Утилиты ──────────────────────────

def _generate_token(user_id: int, channel_name: str, role_str: str) -> dict:
    """Генерирует Agora RTC токен."""
    if not AGORA_APP_ID or not AGORA_APP_CERTIFICATE:
        raise HTTPException(
            status_code=500,
            detail="AGORA_APP_ID и AGORA_APP_CERTIFICATE не заданы в .env"
        )
    role = 1 if role_str == "publisher" else 2
    expire_ts = int(time.time()) + TOKEN_EXPIRE_SECONDS
    token = RtcTokenBuilder.buildTokenWithUid(
        AGORA_APP_ID, AGORA_APP_CERTIFICATE,
        channel_name, user_id, role, expire_ts
    )
    return {
        "user_id": user_id,
        "channel_name": channel_name,
        "token": token,
        "app_id": AGORA_APP_ID,
        "expires_at": expire_ts,
        "role": role_str,
    }


async def build_token(user_id: int, channel_name: str, role_str: str, db: AsyncSession) -> dict:
    """
    Логика получения токена:
    1. Проверить Redis кэш → вернуть если есть
    2. Сгенерировать новый токен
    3. Сохранить в Redis
    4. Залогировать в PostgreSQL
    """
    # 1. Кэш
    cached = await get_cached_token(user_id, channel_name, role_str)
    if cached:
        cached["from_cache"] = True
        return cached

    # 2. Генерация
    token_data = _generate_token(user_id, channel_name, role_str)
    token_data["from_cache"] = False

    # 3. Кэшируем
    await cache_token(user_id, channel_name, role_str, token_data)

    # 4. Лог в БД
    db.add(TokenLog(
        user_id=user_id,
        channel_name=channel_name,
        role=role_str,
        expires_at=datetime.fromtimestamp(token_data["expires_at"])
    ))
    await db.commit()

    return token_data


# ────────────────────────── Роуты ──────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return """<html><body>
        <h2>Agora Calls API v2 🚀</h2>
        <p><a href="/docs">Swagger UI</a></p>
        <p><a href="/static/test.html">Тест звонков</a></p>
    </body></html>"""


@app.post("/api/token", response_model=TokenResponse, summary="Получить токен")
async def get_token(req: TokenRequest, db: AsyncSession = Depends(get_db)):
    """Возвращает Agora токен. Повторный запрос отдаёт из Redis кэша."""
    return await build_token(req.user_id, req.channel_name, req.role, db)


@app.get("/api/token", response_model=TokenResponse, summary="Получить токен (GET)")
async def get_token_query(
    user_id: int = Query(...),
    channel_name: str = Query(...),
    role: str = Query("publisher"),
    db: AsyncSession = Depends(get_db),
):
    return await build_token(user_id, channel_name, role, db)


@app.post("/api/call/session", response_model=CallSessionResponse, summary="Создать сессию звонка")
async def create_call_session(req: CallSessionRequest, db: AsyncSession = Depends(get_db)):
    """
    Создаёт звонок между двумя пользователями:
    - Проверяет что канал свободен (через Redis)
    - Сохраняет сессию в PostgreSQL
    - Возвращает токены для обоих участников
    """
    # Проверяем занятость канала
    if await get_active_call(req.channel_name):
        raise HTTPException(
            status_code=409,
            detail=f"Канал '{req.channel_name}' уже занят активным звонком"
        )

    # Сохраняем в БД
    session = CallSessionModel(
        channel_name=req.channel_name,
        caller_id=req.caller_id,
        callee_id=req.callee_id,
        call_type=req.call_type,
        status=CallStatus.initiated,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Токены
    caller_token = await build_token(req.caller_id, req.channel_name, "publisher", db)
    callee_token = await build_token(req.callee_id, req.channel_name, "publisher", db)

    # Помечаем канал занятым в Redis
    await set_active_call(req.channel_name, {
        "session_id": session.id,
        "caller_id": req.caller_id,
        "callee_id": req.callee_id,
        "call_type": req.call_type,
        "started_at": session.started_at.isoformat(),
    })

    return {
        "session_id": session.id,
        "channel_name": req.channel_name,
        "call_type": req.call_type,
        "caller": caller_token,
        "callee": callee_token,
    }


@app.post("/api/call/end", summary="Завершить звонок")
async def end_call(req: EndCallRequest, db: AsyncSession = Depends(get_db)):
    """
    Завершает звонок:
    - Обновляет статус и длительность в PostgreSQL
    - Удаляет канал из активных в Redis
    - Инвалидирует токены в кэше
    """
    result = await db.execute(
        select(CallSessionModel).where(CallSessionModel.channel_name == req.channel_name)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    ended_at = datetime.utcnow()
    duration = int((ended_at - session.started_at).total_seconds())

    await db.execute(
        update(CallSessionModel)
        .where(CallSessionModel.id == session.id)
        .values(status=req.status, ended_at=ended_at, duration_sec=duration)
    )
    await db.commit()

    # Чистим Redis
    await remove_active_call(req.channel_name)

    return {
        "message": "Звонок завершён",
        "channel_name": req.channel_name,
        "duration_sec": duration,
        "status": req.status,
    }


@app.get("/api/call/history/{user_id}", summary="История звонков пользователя")
async def call_history(
    user_id: int,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает историю входящих и исходящих звонков пользователя."""
    result = await db.execute(
        select(CallSessionModel)
        .where(or_(
            CallSessionModel.caller_id == user_id,
            CallSessionModel.callee_id == user_id
        ))
        .order_by(CallSessionModel.started_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": s.id,
            "channel_name": s.channel_name,
            "caller_id": s.caller_id,
            "callee_id": s.callee_id,
            "call_type": s.call_type,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_sec": s.duration_sec,
        }
        for s in result.scalars().all()
    ]


@app.get("/api/health", summary="Проверка работоспособности")
async def health():
    redis_ok = await ping_redis()
    return {
        "status": "ok",
        "agora_app_id_set": bool(AGORA_APP_ID),
        "agora_certificate_set": bool(AGORA_APP_CERTIFICATE),
        "redis": "connected" if redis_ok else "unavailable",
        "database": "connected",
    }
