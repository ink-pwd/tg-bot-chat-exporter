import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, ExceptionTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message

from application.errors import ApplicationError, LoginNotStarted
from domain.errors import DomainError
from presentation.telegram import texts
from presentation.telegram.callbacks import MenuCallback
from presentation.telegram.keyboards import menus

logger = logging.getLogger(__name__)
router = Router(name="common")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.MAIN_MENU, reply_markup=menus.main_menu())


@router.callback_query(MenuCallback.filter(F.action == "main"))
async def main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await edit_or_answer(callback, texts.MAIN_MENU, menus.main_menu())


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.MAIN_MENU, reply_markup=menus.main_menu())


@router.errors(ExceptionTypeFilter(ApplicationError, DomainError))
async def user_error(event: ErrorEvent, **data) -> None:
    exc = event.exception
    if isinstance(exc, LoginNotStarted) and (state := data.get("state")) is not None:
        await state.clear()
    await reply_to_update(event, texts.error_text(exc) or texts.UNEXPECTED_ERROR)


@router.errors()
async def unexpected_error(event: ErrorEvent) -> None:
    logger.error("Unhandled error in update %s", event.update.update_id, exc_info=event.exception)
    await reply_to_update(event, texts.UNEXPECTED_ERROR)


async def reply_to_update(event: ErrorEvent, text: str) -> None:
    update = event.update
    try:
        if (callback := update.callback_query) is not None:
            try:
                await callback.answer(_strip_html(text), show_alert=True)
                return
            except TelegramBadRequest:
                # на callback уже ответили (долгий сценарий) — пишем сообщением
                if callback.message is not None:
                    await callback.message.answer(text)
        elif update.message is not None:
            await update.message.answer(text)
    except Exception:
        logger.warning("Failed to deliver error message", exc_info=True)


async def edit_or_answer(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """Редактирует сообщение с кнопками, а если нельзя (фото, старое) — шлёт новое."""
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
