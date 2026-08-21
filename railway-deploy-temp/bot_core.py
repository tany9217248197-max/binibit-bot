"""Точка входа Telegram-бота BiNiBit 3×3."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

from admin_flow import build_admin_router
from database import Database
from quiz_flow import build_quiz_router, start_keyboard
from referral_manager import ReferralManager
from registration_flow import build_registration_router

BASE_DIR = Path(__file__).resolve().parent


def load_content() -> dict[str, str]:
    """Загружает пользовательские тексты из JSON-файла."""
    with (BASE_DIR / "content.json").open(encoding="utf-8") as file:
        return json.load(file)


def load_admin_ids(raw_value: str) -> list[int]:
    """Преобразует список Telegram ID из переменной окружения."""
    return [int(item.strip()) for item in raw_value.split(",") if item.strip()]


def waiting_keyboard() -> InlineKeyboardMarkup:
    """Кнопка подписки на уведомление о следующем маршруте."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подписаться на уведомление",
                    callback_data="waitlist:join",
                )
            ]
        ]
    )


def build_common_router(
    manager: ReferralManager,
    content: dict[str, str],
) -> Router:
    """Создаёт базовые команды и выдачу текущей ссылки из очереди."""
    router = Router(name="common")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if message.from_user is None:
            return
        manager.create_or_get_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        await message.answer(
            content["welcome"], reply_markup=start_keyboard(content["support"])
        )

    @router.message(Command("link"))
    async def issue_link(message: Message) -> None:
        if message.from_user is None:
            return
        user = manager.create_or_get_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        link = manager.get_referral_link(user["id"])
        if link is None:
            await message.answer(
                content["queue_unavailable"],
                reply_markup=waiting_keyboard(),
            )
            return

        await message.answer(
            "Ваш маршрут регистрации:\n"
            f"{link.url}\n\n"
            "После регистрации вернитесь в бот и нажмите «Пройти регистрацию», "
            "чтобы получить личный код и сохранить свою реферальную ссылку."
        )

    @router.callback_query(F.data == "waitlist:join")
    async def join_waitlist(callback) -> None:
        if callback.from_user is None:
            return
        user = manager.create_or_get_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        manager.add_to_waitlist(user["id"])
        await callback.answer()
        await callback.message.answer(content["waitlist_saved"])

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            "Команды:\n"
            "/start — начать путь\n"
            "/link — получить текущую ссылку регистрации\n"
            "/help — показать справку\n\n"
            f"{content['risks']}"
        )

    return router


async def main() -> None:
    """Инициализирует сервисы и запускает long polling."""
    load_dotenv(BASE_DIR / ".env")

    token = os.getenv("BOT_TOKEN")
    if not token or token == "replace_with_token_from_botfather":
        raise RuntimeError(
            "Укажите реальный BOT_TOKEN в локальном файле bot/.env."
        )

    admin_ids = load_admin_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))
    if not admin_ids:
        raise RuntimeError("Укажите хотя бы один ADMIN_TELEGRAM_IDS в bot/.env.")

    database_path = os.getenv("DATABASE_PATH", "binibit_bot.db")
    database = Database(BASE_DIR / database_path)
    database.initialize()

    content = load_content()
    deposit_guide_url = os.getenv(
        "DEPOSIT_GUIDE_URL", "https://binibit.com/ru"
    )
    content["support"] = os.getenv("SUPPORT_URL", content["support"])

    manager = ReferralManager(database)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_common_router(manager, content))
    dispatcher.include_router(build_quiz_router(manager, content))
    dispatcher.include_router(
        build_registration_router(
            manager,
            content,
            deposit_guide_url,
            admin_ids,
        )
    )
    dispatcher.include_router(build_admin_router(manager, content, admin_ids))

    logging.info("Бот BiNiBit запущен.")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())