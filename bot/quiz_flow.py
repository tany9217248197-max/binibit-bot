"""Стартовый экран и короткий квиз сегмента пользователя."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from referral_manager import ReferralManager


def start_keyboard() -> InlineKeyboardMarkup:
    """Возвращает кнопки первого экрана."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть BiNiBit", url="https://binibit.com/ru"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Пройти регистрацию", callback_data="registration:start"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Риски и безопасность", callback_data="info:risks"
                ),
                InlineKeyboardButton(
                    text="Как работает стейкинг", callback_data="info:staking"
                ),
            ],
        ]
    )


def build_quiz_router(manager: ReferralManager, content: dict[str, str]) -> Router:
    """Создаёт роутер стартовых информационных экранов."""
    router = Router(name="quiz_flow")

    @router.callback_query(F.data == "info:risks")
    async def show_risks(callback: CallbackQuery) -> None:
        await callback.answer()
        await callback.message.answer(content["risks"], reply_markup=start_keyboard())

    @router.callback_query(F.data == "info:staking")
    async def show_staking_info(callback: CallbackQuery) -> None:
        await callback.answer()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Пройти регистрацию", callback_data="registration:start"
                    )
                ]
            ]
        )
        await callback.message.answer(content["staking_intro"], reply_markup=keyboard)

    @router.callback_query(F.data.startswith("segment:"))
    async def save_segment(callback: CallbackQuery) -> None:
        """Сохраняет необязательный сегмент для аналитики в журнале событий."""
        await callback.answer()
        if callback.from_user is None:
            return
        user = manager.create_or_get_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        segment = callback.data.split(":", maxsplit=1)[1]
        manager.set_step(user["id"], f"segment:{segment}")
        await callback.message.answer(
            "Спасибо. Подберём понятный маршрут без лишних шагов.",
            reply_markup=start_keyboard(),
        )

    return router