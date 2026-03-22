# 📡 Agora Calls — FastAPI

Сервис аудио/видео звонков на FastAPI + Agora RTC.

---

## 🚀 Быстрый старт

### 1. Получить ключи Agora (бесплатно)

1. Перейдите на [console.agora.io](https://console.agora.io)
2. Создайте проект → выберите **"Secured mode"**
3. Скопируйте **App ID** и **App Certificate**

---

### 2. Установка

```bash
# Клонируйте или создайте папку проекта
cd agora_calls

# Виртуальное окружение
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Зависимости
pip install -r requirements.txt
```

---

### 3. Настройка .env

```bash
cp .env.example .env
# Откройте .env и вставьте ваши ключи Agora
```

```env
AGORA_APP_ID=ВАШ_APP_ID
AGORA_APP_CERTIFICATE=ВАШ_APP_CERTIFICATE
```

---

### 4. Запуск

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🧪 Тестирование

| Инструмент | URL |
|---|---|
| Тест-страница звонков | http://localhost:8000/static/test.html |
| Swagger UI | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health |

### Тест двух участников:
1. Откройте `test.html` в **двух разных вкладках** (или устройствах)
2. В первой вкладке: `user_id=1001`, channel=`test-room`
3. Во второй вкладке: `user_id=1002`, channel=`test-room`
4. В обеих нажмите "Получить токен" → "Войти в звонок"

---

## 📡 API Эндпоинты

### `POST /api/token` — получить токен для пользователя
```json
{
  "user_id": 1001,
  "channel_name": "test-room",
  "role": "publisher"
}
```

### `GET /api/token` — то же самое через query params
```
GET /api/token?user_id=1001&channel_name=test-room&role=publisher
```

### `POST /api/call/session` — создать сессию между двумя пользователями
```json
{
  "caller_id": 1001,
  "callee_id": 1002,
  "channel_name": "call_1001_1002",
  "call_type": "video"
}
```
Ответ содержит токены **сразу для обоих** участников — удобно для инициации звонка.

---

## 🏗 Структура проекта

```
agora_calls/
├── main.py              # FastAPI приложение
├── requirements.txt     # Зависимости
├── .env.example         # Шаблон переменных окружения
├── .env                 # Ваши ключи (не коммитить в git!)
├── static/
│   └── test.html        # Тест-страница звонков
└── README.md
```

---

## 🔒 Безопасность (для продакшна)

- [ ] Добавить JWT-авторизацию перед выдачей токенов
- [ ] Проверять, что `user_id` из JWT совпадает с запрошенным
- [ ] Ограничить CORS (убрать `allow_origins=["*"]`)
- [ ] Хранить `AGORA_APP_CERTIFICATE` в secrets manager
- [ ] Добавить rate limiting (например, `slowapi`)

---

## 📊 Тарификация Agora

- **Бесплатно**: первые **10,000 минут/месяц**
- Аудио: ~$0.99 / 1000 мин
- Видео HD: ~$3.99 / 1000 мин
- Для 100k пользователей рекомендуется Enterprise план
