Проект: BiNiBit — бот-воронка 3×3
Завершённость: [█████████░░░░░░] 65% — подготовка Railway-деплоя

# Handoff

## Что подтверждено

- Реализован MVP Telegram-бота с FIFO-механикой 3×3.
- Каждая активная реферальная ссылка выдаётся максимум трём новичкам.
- Порядок выдачи: по времени активации, затем по ID ссылки.
- Новый пользователь сразу передаёт свою ссылку, но она остаётся неактивной до проверки стейкинга.
- После одного скрина активного стейкинга куратор вручную одобряет или отклоняет заявку.
- При одобрении ссылка активируется и добавляется в хвост FIFO-очереди.
- API Binibit в MVP не используется.
- Бот не запрашивает документы, пароли, 2FA-коды или API-ключи.
- Локальный `bot/.env` создан и читается ботом.
- `pytest` снова проходит: `4 passed`.
- Бот стартует до `Start polling`, но не может подключиться к `api.telegram.org:443` с текущей Windows-машины.
- Для постоянной работы выбран Railway Worker, исходный код будет храниться в private GitHub-репозитории.
- Новый Telegram-токен перевыпущен пользователем и не передавался в чат или Git.
- Добавлены Railway-файлы: корневые `Dockerfile`, `.dockerignore` и `RAILWAY_DEPLOY.md`.
- Добавлены альтернативные VPS-файлы в `bot/`: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `DEPLOY_VPS.md`.

## Последняя проверка

- Рабочая среда: `bot/.venv` на CPython 3.14.5.
- SQLite: 3.53.1.
- Зависимости установлены: aiogram 3.30.0, pytest 8.4.2, python-dotenv 1.2.2.
- `bot/.venv/Scripts/python.exe -m pytest tests -q` → **4 passed in 0.47s**.
- Основные модули успешно прошли `py_compile`.
- `bot_core.py` стартует и пишет `Бот BiNiBit запущен.` и `Start polling`.
- В live-логе зафиксирована ошибка сети:
  - `Cannot connect to host api.telegram.org:443`
  - `aiogram.exceptions.TelegramNetworkError`

## Важная техническая заметка

Не используйте Python из `C:\Program Files\QGIS 3.44.5\apps\Python312`: в нём не загружается встроенный SQLite-модуль. Рабочий CPython доступен через:

```text
C:\Users\dmitrieva.li\.local\bin\python3.14.exe
```

Текущий `.venv` уже создан на правильном CPython. Для команд проекта используйте:

```powershell
Set-Location -LiteralPath 'C:\Users\dmitrieva.li\Documents\Cline\BiNiBit\bot'
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Следующий точный шаг

Создать private GitHub-репозиторий и отправить только безопасный код. Не добавлять `bot/.env`, SQLite-базы, медиа, исходные документы и устаревший `deployment-map.md` с раскрытым старым токеном.

После push в Railway создать сервис из GitHub repo, добавить Variables:

```text
BOT_TOKEN=<новый токен>
ADMIN_TELEGRAM_IDS=<ваш Telegram ID>
DEPOSIT_GUIDE_URL=https://binibit.com/ru
SUPPORT_URL=<ссылка на поддержку>
DATABASE_PATH=/data/binibit_bot.db
```

Затем подключить Railway Volume в `/data`, дождаться логов `Бот BiNiBit запущен.` и `Start polling`, после чего проверить `/start` с телефона.

## Ограничения

- Реальный Telegram-поток ещё не проверен: Railway Worker не создан.
- Git remote пока не настроен; private GitHub-репозиторий ещё предстоит создать.
- Railway Volume с mount path `/data` обязателен для сохранения SQLite-данных между deploy.
- Локальная Docker-сборка не проверена: Docker CLI на Windows не установлен.
- Большие исходные PDF, DOCX, MP4 и изображения не включать в кодовый commit без отдельного решения.
