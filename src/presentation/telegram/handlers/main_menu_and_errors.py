"""Главное меню (/start), общие помощники для сообщений и обработка ошибок для пользователя."""
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, ExceptionTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, InlineKeyboardMarkup, Message

from application.use_cases.configure_auto_export import ConfigureAutoExport
from application.use_cases.manage_support_chats import ManageSupportChats
from application.user_facing_errors import ApplicationError
from domain.business_rule_errors import DomainError
from presentation.telegram import bot_texts
from presentation.telegram.callback_data import MenuCallback
from presentation.telegram.keyboards import menu_keyboards

logger = logging.getLogger(__name__)
router = Router(name="main_menu_and_errors")


@router.message(CommandStart())
@router.message(Command("cancel"))
async def start(
    message: Message,
    state: FSMContext,
    bot: Bot,
    chats: ManageSupportChats,
    auto_export: ConfigureAutoExport,
) -> None:
    await state.clear()
    text, markup = await main_menu_view(message.from_user.id, bot, chats, auto_export)
    await message.answer(text, reply_markup=markup)


@router.callback_query(MenuCallback.filter(F.action == "main"))
async def main_menu(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    chats: ManageSupportChats,
    auto_export: ConfigureAutoExport,
) -> None:
    await state.clear()
    await callback.answer()
    text, markup = await main_menu_view(callback.from_user.id, bot, chats, auto_export)
    await edit_or_answer(callback, text, markup)


async def main_menu_view(
    user_id: int, bot: Bot, chats: ManageSupportChats, auto_export: ConfigureAutoExport
) -> tuple[str, InlineKeyboardMarkup]:
    owned = await chats.list(user_id)
    schedule = await auto_export.get(user_id)
    me = await bot.me()
    return bot_texts.main_menu(owned), menu_keyboards.main_menu(owned, schedule, me.username)


@router.errors(ExceptionTypeFilter(ApplicationError, DomainError))
async def user_error(event: ErrorEvent) -> None:
    await reply_to_update(event, bot_texts.error_text(event.exception) or bot_texts.UNEXPECTED_ERROR)


@router.errors()
async def unexpected_error(event: ErrorEvent) -> None:
    logger.error("Unhandled error in update %s", event.update.update_id, exc_info=event.exception)
    await reply_to_update(event, bot_texts.UNEXPECTED_ERROR)


async def reply_to_update(event: ErrorEvent, text: str) -> None:
    """Отвечает только в личном чате: в беседе с клиентами бот молчит."""
    update = event.update
    try:
        if (callback := update.callback_query) is not None:
            try:
                await callback.answer(_strip_html(text), show_alert=True)
                return
            except TelegramBadRequest:
                # на callback уже ответили (долгий сценарий) — пишем сообщением
                if callback.message is not None and callback.message.chat.type == ChatType.PRIVATE:
                    await callback.message.answer(text)
        elif update.message is not None and update.message.chat.type == ChatType.PRIVATE:
            await update.message.answer(text)
    except Exception:
        logger.warning("Failed to deliver error message", exc_info=True)


async def edit_or_answer(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """Редактирует сообщение с кнопками, а если нельзя (старое, не текст) — шлёт новое."""
    message = callback.message
    if message is not None and message.text is not None:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except TelegramBadRequest:
            pass
    if message is not None:
        await message.answer(text, reply_markup=reply_markup)


def _strip_html(text: str) -> str:
    # всплывающие уведомления не поддерживают разметку
    for tag in ("<b>", "</b>", "<code>", "</code>"):
        text = text.replace(tag, "")
    return text
