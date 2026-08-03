Проект: BiNiBit — бот-воронка 3×3
Завершённость: [█████████░░░░░░] 65% — подготовка VPS-деплоя

# Развёртывание BiNiBit на VPS

## Назначение

Бот работает через long polling. Домен, входящие порты и SSL не нужны: VPS должен иметь исходящий HTTPS-доступ к `api.telegram.org:443`.

Данные SQLite хранятся в Docker volume `binibit-data` и не пропадают при пересоздании контейнера.

## Перед началом

1. Перевыпустите токен для `@Binibit_Global_bot` через `@BotFather`.
2. Не отправляйте новый токен в чат и не добавляйте его в Git.
3. Убедитесь, что на VPS установлены Docker и Docker Compose.

Старый токен нужно считать скомпрометированным, потому что он оказался в раннем черновике `deployment-map.md` и переписке.

## Первый запуск на VPS

Выполните на VPS:

```bash
sudo mkdir -p /opt/binibit-bot
sudo chown "$USER":"$USER" /opt/binibit-bot
cd /opt/binibit-bot
```

Скопируйте в эту папку содержимое локальной папки `bot/`, кроме `.env`, `.venv/`, `*.db` и кэшей Python.

Создайте серверный файл `.env`:

```bash
nano .env
```

Содержимое:

```env
BOT_TOKEN=<новый токен из BotFather>
ADMIN_TELEGRAM_IDS=<ваш числовой Telegram ID>
DEPOSIT_GUIDE_URL=https://binibit.com/ru
SUPPORT_URL=<ссылка на Telegram-поддержку>
```

Ограничьте доступ к секретам и запустите сервис:

```bash
chmod 600 .env
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

## Проверка

Успешный запуск содержит в логах:

```text
Бот BiNiBit запущен.
Start polling
```

После этого отправьте `/start` в `@Binibit_Global_bot` с телефона.

## Повторный запуск

```bash
cd /opt/binibit-bot
docker compose up -d --build
docker compose logs -f bot
```

## Остановка

```bash
cd /opt/binibit-bot
docker compose down
```

Не используйте `docker compose down -v`: эта команда удалит SQLite volume с данными пользователей.

## Диагностика

Проверить доступ VPS к Telegram API:

```bash
curl -I --max-time 10 https://api.telegram.org
```

Проверить состояние контейнера:

```bash
docker compose ps
docker compose logs --tail=100 bot
```
