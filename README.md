Проект: BiNiBit — бот-воронка 3×3
Завершённость: [█████████████░] 90% — упаковка для отдельного деплоя

# BiNiBit

Telegram-бот для воронки регистрации, передачи реферальных ссылок и ручной модерации стейкинга по модели 3×3.

## Что находится в репозитории

- `bot/` — канонический исходник для отдельного деплоя на сервер.
- `bot/docker-compose.yml` — отдельный Docker Compose для запуска на VPS.
- `bot/Dockerfile` — контейнер бота.
- `bot/.env.example` — шаблон обязательных переменных окружения.
- `bot/tests/` — локальные тесты ядра FIFO.
- `cline_docs/` — continuity-файлы текущей рабочей истории.
- корневой `Dockerfile` — исторический контейнерный вариант; для нового отдельного серверного деплоя использовать папку `bot/`.

## Что не входит в deploy-артефакт

В корне проекта лежат рабочие материалы: PDF, DOCX, JPG, MP4, XLSX, RTF и черновые заметки. Они не нужны для запуска бота на сервере и не должны копироваться в production-папку.

Для серверного деплоя используйте только содержимое папки `bot/` и отдельный серверный `.env`.

## Быстрый состав deploy-папки

Скопируйте на сервер только эти файлы и папки из `bot/`:

- `.env` — создать на сервере вручную
- `.env.example`
- `.dockerignore`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `bot_core.py`
- `admin_flow.py`
- `database.py`
- `quiz_flow.py`
- `referral_manager.py`
- `registration_flow.py`
- `content.json`

Не копируйте:

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `*.db`
- локальные `.env`
- любые файлы из корня проекта, не относящиеся к коду бота

## Локальный запуск

```powershell
cd bot
Copy-Item .env.example .env
docker compose up --build
```

## Обязательные переменные окружения

Пример находится в `bot/.env.example`:

```env
BOT_TOKEN=replace_with_token_from_botfather
ADMIN_TELEGRAM_IDS=123456789
DATABASE_PATH=binibit_bot.db
DEPOSIT_GUIDE_URL=https://example.com/deposit-guide
SUPPORT_URL=https://t.me/example_support
```

Для Docker Compose на сервере база будет храниться во volume, а `DATABASE_PATH` переопределяется в `/data/binibit_bot.db`.

## Отдельный деплой на сервер

Подробная инструкция: `bot/DEPLOY_VPS.md`

Коротко:

```bash
mkdir -p /opt/binibit-bot
cd /opt/binibit-bot
# скопировать сюда содержимое локальной папки bot/
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

## Проверка после запуска

Успешный старт должен дать в логах:

```text
Бот BiNiBit запущен.
Start polling
```

После этого нужно проверить `/start` в Telegram.

## Изоляция проекта

Этот репозиторий должен деплоиться отдельно от проекта «Шереметьевский».

- не использовать общую базу данных;
- не использовать общий Docker Compose;
- не складывать оба проекта в одну серверную папку;
- не смешивать `.env` и секреты между проектами.

Рекомендуемая серверная директория:

```text
/opt/binibit-bot
```

## Текущее состояние

- код бота и Docker Compose для VPS уже присутствуют;
- шаблон env присутствует;
- отдельная инструкция VPS присутствует;
- проект требует только отдельной упаковки и переноса на сервер без Railway.