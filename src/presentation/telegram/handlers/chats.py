from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from application.use_cases.manage_support_chats import ManageSupportChats
from presentation.telegram import texts
from presentation.telegram.callbacks import ChatCallback, MenuCallback
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus

router = Router(name="chats")


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
    await edit_or_answer(callback, texts.chat_card(chat), menus.chat_card(chat))


@router.callback_query(ChatCallback.filter(F.action == "disconnect"))
async def ask_disconnect(
    callback: CallbackQuery, callback_data: ChatCallback, chats: ManageSupportChats
) -> None:
    chat = await chats.get(callback.from_user.id, callback_data.chat_id)
    await callback.answer()
    await edit_or_answer(callback, texts.disconnect_confirm(chat), menus.disconnect_confirm(chat))


@router.callback_query(ChatCallback.filter(F.action == "disconnect_confirm"))
async def disconnect(
    callback: CallbackQuery, callback_data: ChatCallback, bot: Bot, chats: ManageSupportChats
) -> None:
    await chats.disconnect(callback.from_user.id, callback_data.chat_id)
    await callback.answer(texts.CHAT_DISCONNECTED)
    await _show_list(callback, bot, chats)


async def _show_list(callback: CallbackQuery, bot: Bot, chats: ManageSupportChats) -> None:
    owned = await chats.list(callback.from_user.id)
    me = await bot.me()
    await edit_or_answer(
        callback, texts.CHATS if owned else texts.NO_CHATS, menus.chats_list(owned, me.username)
    )
