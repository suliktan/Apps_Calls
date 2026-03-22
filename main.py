from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import os
from dotenv import load_dotenv

from agora_token_builder import RtcTokenBuilder

load_dotenv()

app = FastAPI(
    title="Agora Calls API",
    description="API для аудио/видео звонков через Agora",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика для HTML тест-страницы
app.mount("/static", StaticFiles(directory="static"), name="static")

AGORA_APP_ID  = os.getenv("AGORA_APP_ID", "")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE", "")
TOKEN_EXPIRE_SECONDS = 3600  # 1 час


# ────────────────────────── Схемы ──────────────────────────

class TokenRequest(BaseModel):
    user_id: int
    channel_name: str
    role: Optional[str] = "publisher"   # publisher | subscriber


class TokenResponse(BaseModel):
    user_id: int
    channel_name: str
    token: str
    app_id: str
    expires_at: int
    role: str


class CallSession(BaseModel):
    caller_id: int
    callee_id: int
    channel_name: str
    call_type: Optional[str] = "video"  # video | audio


class CallSessionResponse(BaseModel):
    channel_name: str
    call_type: str
    caller: TokenResponse
    callee: TokenResponse


# ────────────────────────── Утилиты ──────────────────────────

def build_token(user_id: int, channel_name: str, role_str: str) -> dict:
    """Генерирует Agora RTC токен для пользователя."""
    if not AGORA_APP_ID or not AGORA_APP_CERTIFICATE:
        raise HTTPException(
            status_code=500,
            detail="AGORA_APP_ID и AGORA_APP_CERTIFICATE не заданы в .env"
        )

    # 1 = publisher, 2 = subscriber (новая версия agora-token-builder)
    role = 1 if role_str == "publisher" else 2
    expire_ts = int(time.time()) + TOKEN_EXPIRE_SECONDS

    token = RtcTokenBuilder.buildTokenWithUid(
        AGORA_APP_ID,
        AGORA_APP_CERTIFICATE,
        channel_name,
        user_id,
        role,
        expire_ts
    )

    return {
        "user_id": user_id,
        "channel_name": channel_name,
        "token": token,
        "app_id": AGORA_APP_ID,
        "expires_at": expire_ts,
        "role": role_str,
    }


# ────────────────────────── Роуты ──────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html><body>
        <h2>Agora Calls API 🚀</h2>
        <p><a href="/docs">Swagger UI</a></p>
        <p><a href="/static/test.html">Тест звонков</a></p>
    </body></html>
    """


@app.post("/api/token", response_model=TokenResponse, summary="Получить токен для звонка")
async def get_token(req: TokenRequest):
    """
    Генерирует Agora RTC токен по user_id и channel_name.

    - **user_id**: уникальный ID пользователя в вашей системе
    - **channel_name**: название канала (комнаты) звонка
    - **role**: publisher (говорит) или subscriber (слушает)
    """
    return build_token(req.user_id, req.channel_name, req.role)


@app.get("/api/token", response_model=TokenResponse, summary="Получить токен (GET)")
async def get_token_query(
    user_id: int = Query(..., description="ID пользователя"),
    channel_name: str = Query(..., description="Название канала"),
    role: str = Query("publisher", description="publisher или subscriber"),
):
    return build_token(user_id, channel_name, role)


@app.post(
    "/api/call/session",
    response_model=CallSessionResponse,
    summary="Создать сессию звонка между двумя пользователями"
)
async def create_call_session(session: CallSession):
    """
    Создаёт токены сразу для двух участников звонка.
    Оба получают токен для одного channel_name — это гарантирует
    что они попадут в одну комнату.

    - **caller_id**: ID звонящего
    - **callee_id**: ID принимающего
    - **channel_name**: уникальное имя канала (например: "call_101_202")
    - **call_type**: video или audio
    """
    caller_token = build_token(session.caller_id, session.channel_name, "publisher")
    callee_token = build_token(session.callee_id, session.channel_name, "publisher")

    return {
        "channel_name": session.channel_name,
        "call_type": session.call_type,
        "caller": caller_token,
        "callee": callee_token,
    }


@app.get("/api/health", summary="Проверка работоспособности")
async def health():
    return {
        "status": "ok",
        "agora_app_id_set": bool(AGORA_APP_ID),
        "agora_certificate_set": bool(AGORA_APP_CERTIFICATE),
    }
