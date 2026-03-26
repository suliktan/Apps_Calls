# 🚀 Гайд по деплою Agora Calls на VPS

## Что нужно иметь перед началом:
- [ ] Купленный VPS с Ubuntu 22.04
- [ ] Домен (например calls.myapp.com) направленный на IP сервера
- [ ] Ключи Agora (APP_ID и APP_CERTIFICATE)

---

## ЧАСТЬ 1 — Подключение к серверу

С Windows используй **PowerShell** или **PuTTY**:
```bash
ssh root@ВАШ_IP_СЕРВЕРА
```

---

## ЧАСТЬ 2 — Установка всего необходимого на сервер

Выполни эти команды по порядку:

```bash
# 1. Обновить систему
apt update && apt upgrade -y

# 2. Установить Docker
curl -fsSL https://get.docker.com | sh

# 3. Установить Docker Compose
apt install docker-compose -y

# 4. Установить Nginx
apt install nginx -y

# 5. Установить Certbot (для бесплатного HTTPS сертификата)
apt install certbot python3-certbot-nginx -y

# 6. Установить Git
apt install git -y
```

---

## ЧАСТЬ 3 — Загрузить код на сервер

### Вариант А: через Git (рекомендуется)
```bash
# На сервере:
cd /var/www
git clone https://github.com/ВАШ_АККАУНТ/agora-calls.git
cd agora-calls
```

### Вариант Б: напрямую с компьютера (через SCP)
```bash
# На твоём Windows компьютере в PowerShell:
scp -r C:\Users\ALEM\Desktop\agora_calls root@ВАШ_IP:/var/www/agora-calls
```

---

## ЧАСТЬ 4 — Настроить переменные окружения

```bash
# На сервере, в папке проекта:
cd /var/www/agora-calls
cp .env.example .env
nano .env
```

Вставь реальные ключи:
```env
AGORA_APP_ID=твой_реальный_app_id
AGORA_APP_CERTIFICATE=твой_реальный_certificate
```
Сохранить: Ctrl+O → Enter → Ctrl+X

---

## ЧАСТЬ 5 — Настроить Nginx

```bash
# Скопировать конфиг nginx
cp /var/www/agora-calls/nginx.conf /etc/nginx/sites-available/agora-calls

# Заменить YOUR_DOMAIN на твой домен
nano /etc/nginx/sites-available/agora-calls
# Найди все YOUR_DOMAIN и замени на например: calls.myapp.com

# Активировать сайт
ln -s /etc/nginx/sites-available/agora-calls /etc/nginx/sites-enabled/

# Проверить конфиг на ошибки
nginx -t

# Перезапустить Nginx
systemctl restart nginx
```

---

## ЧАСТЬ 6 — Получить HTTPS сертификат (бесплатно!)

```bash
certbot --nginx -d YOUR_DOMAIN
```

Certbot спросит email и согласие — вводи и соглашайся. Сертификат выдаётся автоматически и обновляется каждые 90 дней сам.

---

## ЧАСТЬ 7 — Запустить приложение через Docker

```bash
cd /var/www/agora-calls

# Собрать и запустить контейнер
docker-compose up -d --build

# Проверить что запущено
docker-compose ps

# Посмотреть логи
docker-compose logs -f
```

---

## ЧАСТЬ 8 — Проверка

Открой в браузере:
- `https://YOUR_DOMAIN/api/health` → должно быть `{"status":"ok","agora_app_id_set":true,...}`
- `https://YOUR_DOMAIN/docs` → Swagger UI
- `https://YOUR_DOMAIN/static/test.html` → тест звонков

---

## Полезные команды после деплоя

```bash
# Перезапустить приложение (после обновления кода)
docker-compose down && docker-compose up -d --build

# Посмотреть логи в реальном времени
docker-compose logs -f agora-calls

# Остановить приложение
docker-compose down

# Статус контейнера
docker-compose ps

# Зайти внутрь контейнера (для отладки)
docker exec -it agora_calls_app bash
```

## Обновление кода (после изменений)

```bash
cd /var/www/agora-calls
git pull                              # получить новый код
docker-compose down
docker-compose up -d --build          # пересобрать и запустить
```
