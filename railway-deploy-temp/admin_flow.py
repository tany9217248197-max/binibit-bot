"""Админ-команды и ручная проверка заявок на стейкинг."""

from __future__ import annotations

from collections.abc import Iterable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from referral_manager import ReferralManager


def review_keyboard(review_id: int) -> InlineKeyboardMarkup:
    """Кнопки решения куратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Одобрить", callback_data=f"review:approve:{review_id}"
                ),
                InlineKeyboardButton(
                    text="Отклонить", callback_data=f"review:reject:{review_id}"
                ),
            ]
        ]
    )


def build_admin_router(
    manager: ReferralManager,
    content: dict[str, str],
    admin_ids: Iterable[int],
) -> Router:
    """Создаёт роутер, доступный только списку кураторов."""
    router = Router(name="admin_flow")
    allowed_admin_ids = set(admin_ids)

    def is_admin(telegram_id: int | None) -> bool:
        return telegram_id is not None and telegram_id in allowed_admin_ids

    @router.message(Command("add_referral"))
    async def add_referral(message: Message) -> None:
        if not is_admin(message.from_user.id if message.from_user else None):
            await message.answer("Эта команда доступна только куратору.")
            return

        command_parts = (message.text or "").split(maxsplit=1)
        if len(command_parts) != 2:
            await message.answer("Формат: /add_referral https://ваша-ссылка")
            return

        try:
            link = manager.add_admin_referral_link(command_parts[1])
        except ValueError as error:
            await message.answer(str(error))
            return

        await message.answer(
            f"Ссылка добавлена в конец очереди 3×3.\n"
            f"Лимит выдач: {link.max_limit}."
        )
        await _notify_waitlist(message, manager)

    @router.callback_query(F.data.startswith("review:"))
    async def decide_review(callback: CallbackQuery) -> None:
        if not is_admin(callback.from_user.id if callback.from_user else None):
            await callback.answer("Нет доступа.", show_alert=True)
            return

        await callback.answer()
        try:
            _, action, raw_review_id = callback.data.split(":")
            review_id = int(raw_review_id)
            review = manager.get_pending_review(review_id)
            if review is None:
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.answer("Заявка уже обработана.")
                return

            approved = action == "approve"
            manager.decide_review(review_id, callback.from_user.id, approved)
        except (ValueError, AttributeError):
            await callback.message.answer("Не удалось обработать заявку.")
            return

        await callback.message.edit_reply_markup(reply_markup=None)
        if approved:
            await callback.message.answer("Заявка одобрена, ссылка добавлена в очередь.")
            await callback.bot.send_message(
                review["telegram_id"], content["review_approved"]
            )
            await _notify_waitlist(callback.message, manager)
        else:
            await callback.message.answer("Заявка отклонена.")
            await callback.bot.send_message(
                review["telegram_id"], content["review_rejected"]
            )

    return router


async def send_review_to_admins(
    message: Message,
    manager: ReferralManager,
    admin_ids: Iterable[int],
    review_id: int,
) -> None:
    """Пересылает скрин и данные заявки всем назначенным кураторам."""
    review = manager.get_pending_review(review_id)
    if review is None:
        return

    username = f"@{review['username']}" if review["username"] else "не указан"
    caption = (
        "<b>Новая заявка на проверку стейкинга</b>\n"
        f"Пользователь: {review['full_name']} ({username})\n"
        f"Telegram ID: <code>{review['telegram_id']}</code>\n"
        f"Код: <code>{review['verification_code']}</code>\n"
        f"Ссылка: {review['referral_url']}"
    )
    for admin_id in set(admin_ids):
        await message.bot.send_photo(
            admin_id,
            review["screenshot_file_id"],
            caption=caption,
            reply_markup=review_keyboard(review_id),
        )


async def _notify_waitlist(message: Message, manager: ReferralManager) -> None:
    """Уведомляет ожидающих о появлении нового маршрута."""
    for user_id in manager.pop_waitlist_users():
        try:
            await message.bot.send_message(
                user_id,
                "Появился следующий маршрут регистрации. Откройте бота и начните регистрацию.",
            )
        except Exception:
            # Пользователь мог заблокировать бота; это не отменяет активацию ссылки.
            continue