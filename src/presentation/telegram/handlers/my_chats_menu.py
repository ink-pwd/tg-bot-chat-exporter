"""Меню «Мои беседы»: список, карточка беседы, отключение с удалением сообщений."""
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from application.use_cases.manage_support_chats import ManageSupportChats
from presentation.telegram import bot_texts
from presentation.telegram.callback_data import ChatCallback, MenuCallback
from presentation.telegram.handlers.main_menu_and_errors import edit_or_answer
from presentation.telegram.keyboards import menu_keyboards

router = Router(name="my_chats_menu")


@router.callback_query(MenuCallback.filter(F.action == "chats"))
async def list_chats(callback: CallbackQuery, bot: Bot, chats: ManageSupportChats) -> None:
    await callback.answer()
    await _show_list(callback, bot, chats)


@router.callback_query(ChatCallback.filter(F.action == "open"))
async def open_chat(
    callback: CallbackQuery, callback_data: ChatCallback, chats: ManageSupportChats
) -> None:
    chat = await chats.get(callback.from_user.id, callback_data.chat_id)
    await callback.answer()
    await edit_or_answer(callback, bot_texts.chat_card(chat), menu_keyboards.chat_card(chat))


@router.callback_query(ChatCallback.filter(F.action == "disconnect"))
async def ask_disconnect(
    callback: CallbackQuery, callback_data: ChatCallback, chats: ManageSupportChats
) -> None:
    chat = await chats.get(callback.from_user.id, callback_data.chat_id)
    await callback.answer()
    await edit_or_answer(callback, bot_texts.disconnect_confirm(chat), menu_keyboards.disconnect_confirm(chat))


@router.callback_query(ChatCallback.filter(F.action == "disconnect_confirm"))
async def disconnect(
    callback: CallbackQuery, callback_data: ChatCallback, bot: Bot, chats: ManageSupportChats
) -> None:
    await chats.disconnect(callback.from_user.id, callback_data.chat_id)
    await callback.answer(bot_texts.CHAT_DISCONNECTED)
    await _show_list(callback, bot, chats)


async def _show_list(callback: CallbackQuery, bot: Bot, chats: ManageSupportChats) -> None:
    owned = await chats.list(callback.from_user.id)
    me = await bot.me()
    await edit_or_answer(
        callback, bot_texts.CHATS if owned else bot_texts.NO_CHATS, menu_keyboards.chats_list(owned, me.username)
    )
