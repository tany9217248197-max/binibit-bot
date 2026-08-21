"""Регистрация, сохранение ссылки и передача скрина стейкинга на проверку."""

from __future__ import annotations

from collections.abc import Iterable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from admin_flow import send_review_to_admins
from referral_manager import ReferralLink, ReferralManager


STARTER_CURATORS = {
    "https://binibit.com/?i=k4f68x": "@Lidia_Murmansk",
    "https://binibit.com/?i=9n15ut": "@olushka467",
    "https://binibit.com/?i=mot171": "@marinasumina64",
    "https://binibit.com/?i=qxn6cw": "@elenashubina_s",
}


class RegistrationFlow(StatesGroup):
    """Состояния пользовательской воронки."""

    waiting_referral_link = State()
    waiting_staking_screenshot = State()


def registration_keyboard(registration_url: str) -> InlineKeyboardMarkup:
    """Кнопки шага регистрации по выданной ссылке."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть регистрацию", url=registration_url)],
            [
                InlineKeyboardButton(
                    text="Я зарегистрировался", callback_data="registration:done"
                )
            ],
        ]
    )


def next_steps_keyboard(deposit_guide_url: str) -> InlineKeyboardMarkup:
    """Кнопки после сохранения реферальной ссылки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Как внести депозит?", url=deposit_guide_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="Информация о стейкинге", callback_data="staking:info"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Я запустил стейкинг", callback_data="staking:submit"
                )
            ],
        ]
    )


def format_curator_hint(link: ReferralLink, support_url: str) -> str:
    """Возвращает подсказку, к кому обратиться по выданной стартовой ссылке."""
    curator_username = STARTER_CURATORS.get(link.url)
    if curator_username:
        return f"Если возникли трудности, обратитесь к куратору: {curator_username}"
    return f"Если возникли трудности, обратитесь к куратору: {support_url}"


def build_registration_router(
    manager: ReferralManager,
    content: dict[str, str],
    deposit_guide_url: str,
    admin_ids: Iterable[int],
) -> Router:
    """Создаёт роутер основного пользовательского пути."""
    router = Router(name="registration_flow")

    @router.callback_query(F.data == "registration:start")
    async def start_registration(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.from_user is None:
            return

        user = manager.create_or_get_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        support_url = content["support"]
        user_link = manager.get_user_referral_link(user["id"])

        if user_link is not None:
            if user["current_step"] == "active_partner" or user_link.status == "active":
                await callback.message.answer(
                    "Поздравляем! Теперь ваша реферальная ссылка активна для регистрации новых партнёров.\n\n"
                    f"Вот ваша ссылка:\n{user_link.url}"
                )
                return

            await callback.message.answer(
                "Вы уже проходили регистрацию ранее.\n\n"
                f"Вот ваша ссылка:\n{user_link.url}\n\n"
                "Ваша ссылка станет активной после активации стейкинга. "
                "Когда будете готовы, откройте информацию о стейкинге или напишите куратору."
            )
            return

        previous_link = manager.get_previously_issued_link(user["id"])
        if previous_link is not None:
            await callback.message.answer(
                "Ранее вам уже выдавалась ссылка для регистрации.\n"
                "Проверьте, завершили ли вы регистрацию, и пришлите в ответ свою реферальную ссылку для постановки в очередь.\n\n"
                f"Ваша ранее выданная ссылка:\n{previous_link.url}\n\n"
                f"{format_curator_hint(previous_link, support_url)}"
            )
            return

        link = manager.get_referral_link(user["id"])
        if link is None:
            await callback.message.answer(content["queue_unavailable"])
            return

        message = (
            f"{content['registration_intro']}\n\n"
            "Вот ваша ссылка для регистрации:\n"
            f"{link.url}\n\n"
            "После регистрации возвращайтесь, нажмите кнопку «Я зарегистрировался» "
            "и отправьте свою реферальную ссылку для включения в очередь."
        )
        await callback.message.answer(
            message,
            reply_markup=registration_keyboard(link.url),
        )

    @router.callback_query(F.data == "registration:done")
    async def registration_done(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        await callback.answer()
        if callback.from_user is None:
            return
        user = manager.create_or_get_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        manager.set_step(user["id"], "waiting_referral_link")
        await state.set_state(RegistrationFlow.waiting_referral_link)
        await callback.message.answer(
            "Поздравляю с регистрацией!\n\n"
            f"{content['code_instruction'].format(verification_code=user['verification_code'])}\n\n"
            "Отправьте мне свою реферальную ссылку для включения в очередь последующей регистрации новых партнёров."
        )

    @router.message(RegistrationFlow.waiting_referral_link, F.text)
    async def receive_referral_link(message: Message, state: FSMContext) -> None:
        if message.from_user is None or message.text is None:
            return
        user = manager.create_or_get_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        try:
            manager.submit_referral_link(user["id"], message.text)
        except ValueError as error:
            await message.answer(f"{error}\n\nОтправьте полную ссылку ещё раз.")
            return

        await state.clear()
        await message.answer(
            f"{content['referral_saved']}\n\n"
            "Ваша ссылка станет активной после активации стейкинга.\n\n"
            f"{content['deposit_guide']}\n\n"
            "Чтобы включить ссылку в очередь, достаточно активировать стейкинг от 50 USDT "
            "и прислать скрин активного статуса.\n\n"
            f"{content['staking_intro']}\n\n"
            f"Если нужна помощь, обратитесь к куратору: {content['support']}\n\n"
            f"{content['risks']}",
            reply_markup=next_steps_keyboard(deposit_guide_url),
        )

    @router.message(RegistrationFlow.waiting_referral_link)
    async def reject_non_link(message: Message) -> None:
        await message.answer(
            "Нужна текстовая ссылка, начинающаяся с https:// или http://."
        )

    @router.callback_query(F.data == "staking:info")
    async def show_staking(callback: CallbackQuery) -> None:
        await callback.answer()
        await callback.message.answer(
            f"{content['staking_intro']}\n\n{content['risks']}",
            reply_markup=next_steps_keyboard(deposit_guide_url),
        )

    @router.callback_query(F.data == "staking:submit")
    async def request_screenshot(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        await callback.answer()
        if callback.from_user is None:
            return
        user = manager.create_or_get_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        manager.set_step(user["id"], "waiting_staking_screenshot")
        await state.set_state(RegistrationFlow.waiting_staking_screenshot)
        await callback.message.answer(content["screenshot_request"])

    @router.message(RegistrationFlow.waiting_staking_screenshot, F.photo)
    async def receive_staking_screenshot(
        message: Message, state: FSMContext
    ) -> None:
        if message.from_user is None or not message.photo:
            return
        user = manager.create_or_get_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        try:
            review = manager.create_staking_review(user["id"], message.photo[-1].file_id)
        except ValueError as error:
            await message.answer(str(error))
            return

        await state.clear()
        await message.answer(content["review_pending"])
        await send_review_to_admins(message, manager, admin_ids, review["id"])

    @router.message(RegistrationFlow.waiting_staking_screenshot)
    async def reject_non_screenshot(message: Message) -> None:
        await message.answer("Пришлите, пожалуйста, один скрин активного стейкинга.")

    return router