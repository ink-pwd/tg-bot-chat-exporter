import logging

from application.errors import ApplicationError
from application.interfaces.telegram_chat_gateway import TelegramChatGateway
from domain.entities.support_chat import SupportChat
from domain.enums.chat_type import ChatType
from domain.errors import ChatNotFound
from domain.repositories.bot_user_repository import BotUserRepository
from domain.repositories.support_chat_repository import SupportChatRepository

logger = logging.getLogger(__name__)


class ManageSupportChats:
    """Подключение бесед (бота добавили в группу), просмотр и отключение своих бесед."""

    def __init__(
        self,
        users: BotUserRepository,
        chats: SupportChatRepository,
        gateway: TelegramChatGateway,
    ) -> None:
        self._users = users
        self._chats = chats
        self._gateway = gateway

    async def connect(
        self, owner_id: int, telegram_chat_id: int, title: str, chat_type: ChatType
    ) -> SupportChat:
        await self._users.ensure_exists(owner_id)
        chat = await self._chats.connect(telegram_chat_id, owner_id, title, chat_type)
        try:
            admin_ids = await self._gateway.get_admin_ids(telegram_chat_id)
        except ApplicationError:
            # список админов возьмём при первой выгрузке
            logger.warning("Chat admins not loaded: chat=%s", chat.id)
        else:
            await self._chats.save_admin_ids(chat.id, admin_ids)
        logger.info("Chat connected: chat=%s owner=%s", chat.id, owner_id)
        return chat

    async def bot_removed(self, telegram_chat_id: int) -> None:
        await self._chats.deactivate(telegram_chat_id)
        logger.info("Bot removed from chat")

    async def migrated(self, old_telegram_chat_id: int, new_telegram_chat_id: int) -> None:
        await self._chats.migrate(old_telegram_chat_id, new_telegram_chat_id)
        logger.info("Chat migrated to supergroup")

    async def renamed(self, telegram_chat_id: int, title: str) -> None:
        await self._chats.rename(telegram_chat_id, title)

    async def list(self, user_id: int) -> list[SupportChat]:
        return await self._chats.list_owned(user_id)

    async def get(self, user_id: int, chat_id: int) -> SupportChat:
        chat = await self._chats.get_owned(chat_id, user_id)
        if chat is None:
            raise ChatNotFound()
        return chat

    async def disconnect(self, user_id: int, chat_id: int) -> None:
        """Бот выходит из беседы, её история удаляется."""
        chat = await self.get(user_id, chat_id)
        if chat.active:
            try:
                await self._gateway.leave(chat.telegram_chat_id)
            except ApplicationError:
                # историю всё равно удаляем: доступ через бота должен пропасть
                logger.warning("Leaving chat failed: chat=%s", chat.id, exc_info=True)
        await self._chats.delete_owned(chat.id, user_id)
        logger.info("Chat disconnected: chat=%s owner=%s", chat.id, user_id)
