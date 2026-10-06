"""События из бесед: бота добавили или удалили, новые и отредактированные сообщения.

В беседу бот ничего не пишет — клиенты не должны его замечать.
Владельцу он сообщает о подключении в личный чат.
"""
import contextlib
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, Message

from application.use_cases.manage_support_chats import ManageSupportChats
from application.use_cases.record_chat_messages import RecordChatMessages
from presentation.telegram import bot_texts
from presentation.telegram.input.aiogram_message_conversion import (
    chat_type,
    starts_with_command,
    to_support_message,
)
from presentation.telegram.keyboards import menu_keyboards
from presentation.telegram.middlewares.access_control import GROUP_CHATS, AccessMiddleware

logger = logging.getLogger(__name__)
router = Router(name="group_chat_events")
router.message.filter(F.chat.type.in_(GROUP_CHATS))
router.edited_message.filter(F.chat.type.in_(GROUP_CHATS))
router.my_chat_member.filter(F.chat.type.in_(GROUP_CHATS))


@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def bot_added(
    event: ChatMemberUpdated, bot: Bot, chats: ManageSupportChats, access: AccessMiddleware
) -> None:
    adder = event.from_user
    if adder.is_bot or not access.allows(adder.id):
        logger.info("Chat rejected, user has no access: user=%s", adder.id)
        with contextlib.suppress(Exception):
            await bot.leave_chat(event.chat.id)
        await _notify(bot, adder.id, bot_texts.CHAT_REJECTED)
        return
    chat = await chats.connect(
        adder.id, event.chat.id, event.chat.title or str(event.chat.id), chat_type(event.chat.type)
    )
    me = await bot.me()
    is_admin = event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR
    await _notify(
        bot,
        adder.id,
        bot_texts.chat_connected(chat, me.can_read_all_group_messages or is_admin),
        menu_keyboards.back_to_main(),
    )


@router.my_chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def bot_removed(event: ChatMemberUpdated, chats: ManageSupportChats) -> None:
    await chats.bot_removed(event.chat.id)


@router.message(F.migrate_to_chat_id)
async def migrated_to(message: Message, chats: ManageSupportChats) -> None:
    await chats.migrated(message.chat.id, message.migrate_to_chat_id)


@router.message(F.migrate_from_chat_id)
async def migrated_from(message: Message, chats: ManageSupportChats) -> None:
    await chats.migrated(message.migrate_from_chat_id, message.chat.id)


@router.message()
async def record_message(
    message: Message, chats: ManageSupportChats, recorder: RecordChatMessages
) -> None:
    if starts_with_command(message):
        return
    if message.new_chat_title:
        await chats.renamed(message.chat.id, message.new_chat_title)
    await recorder.record(to_support_message(message))


@router.edited_message()
async def record_edit(message: Message, recorder: RecordChatMessages) -> None:
    await recorder.record_edit(to_support_message(message))


async def _notify(
    bot: Bot, user_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
    except Exception:
        # пользователь ещё не открывал бота — беседу он увидит в «Мои беседы» после /start
        logger.info("Chat owner not notified: user=%s", user_id)
