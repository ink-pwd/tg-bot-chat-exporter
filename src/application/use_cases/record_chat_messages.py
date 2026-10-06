from domain.entities.support_message import SupportMessage
from domain.repositories.chat_message_repository import ChatMessageRepository
from domain.repositories.support_chat_repository import SupportChatRepository


class RecordChatMessages:
    """Сохраняет сообщения из подключённых бесед.

    Bot API не отдаёт историю, поэтому выгрузка строится только из того,
    что бот получил и сохранил сам.
    """

    def __init__(self, chats: SupportChatRepository, messages: ChatMessageRepository) -> None:
        self._chats = chats
        self._messages = messages

    async def record(self, message: SupportMessage) -> None:
        chat = await self._chats.find_active(message.chat_id)
        if chat is None:
            return  # беседа не подключена или бота из неё удалили
        await self._messages.add(chat.id, message)

    async def record_edit(self, message: SupportMessage) -> None:
        await self._messages.update_edited(message)
