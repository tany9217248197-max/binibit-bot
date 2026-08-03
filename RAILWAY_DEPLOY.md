Проект: BiNiBit — бот-воронка 3×3
Завершённость: [█████████░░░░░░] 65% — подготовка Railway-деплоя

# Railway-деплой BiNiBit

## Что развёртывается

Telegram-бот с long polling. Это Worker-сервис: публичный домен, HTTP-порт и webhook не требуются.

Корневой `Dockerfile` собирает приложение из папки `bot/` и запускает:

```text
python bot_core.py
```

## Подготовка GitHub

Создайте **private**-репозиторий, например `binibit-bot`.

В репозиторий включаются только код и безопасная конфигурация:

- `bot/*.py`
- `bot/content.json`
- `bot/requirements.txt`
- `bot/.env.example`
- `Dockerfile`
- `.dockerignore`
- `.gitignore`
- `RAILWAY_DEPLOY.md`
- `cline_docs/`

Не добавляйте:

- `bot/.env`
- `bot/*.db`
- старый `deployment-map.md`: он содержит скомпрометированный токен;
- PDF, DOCX, видео, изображения и прочие исходные материалы.

## Настройка Railway

1. В Railway создайте новый проект.
2. Нажмите **New → GitHub Repo** и выберите private-репозиторий `binibit-bot`.
3. Railway автоматически найдёт корневой `Dockerfile`.
4. В сервисе откройте **Variables** и добавьте:

```env
BOT_TOKEN=<новый токен из BotFather>
ADMIN_TELEGRAM_IDS=<ваш числовой Telegram ID>
DEPOSIT_GUIDE_URL=https://binibit.com/ru
SUPPORT_URL=<ссылка на Telegram-поддержку>
DATABASE_PATH=/data/binibit_bot.db
```

5. В сервисе откройте **Volumes** и создайте volume с mount path:

```text
/data
```

Это обязательно: в `/data/binibit_bot.db` находится SQLite-база пользователей, ссылок, очереди и заявок.

6. Запустите deploy.

## Проверка

В **Deploy Logs** должны быть строки:

```text
Бот BiNiBit запущен.
Start polling
```

После этого с телефона отправьте `/start` боту `@Binibit_Global_bot`.

## Важные ограничения

- Не создавайте публичный домен: для polling он не нужен.
- Не используйте GitHub Actions для постоянного запуска бота.
- Railway Variables — единственное место для `BOT_TOKEN`.
- Если удалить Railway Volume, SQLite-данные будут потеряны.
- При любом redeploy volume в `/data` сохраняется.