"""JSON-файл выгрузки. Формат тот же, что у прежнего export.py (плюс поле timezone)."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.support_message import SupportMessage


def render_export_json(export: DailyConversationExport) -> bytes:
    tz = export.day.timezone
    document = {
        "date": export.day.day.isoformat(),
        "timezone": tz.key,
        "account": {
            "id": export.profile.telegram_user_id,
            "name": export.profile.display_name,
            "username": export.profile.username,
            "phone": export.phone,
        },
        "exported_at": _local(export.exported_at, tz),
        "chats": [
            {
                "id": conversation.chat_id,
                "name": conversation.title,
                "type": conversation.chat_type.value,
                "messages": [_message(m, tz) for m in conversation.messages],
            }
            for conversation in export.conversations
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")


def _message(message: SupportMessage, tz: ZoneInfo) -> dict:
    return {
        "id": message.id,
        "date": _local(message.sent_at, tz),
        "edit_date": _local(message.edited_at, tz) if message.edited_at else None,
        "from_id": message.sender_id,
        "from": message.sender_name,
        "out": message.is_outgoing,
        "text": message.text,
        "reply_to": message.reply_to_id,
        "forwarded_from": message.forwarded_from,
        "media": message.media_type,
        "action": message.action,
    }


def _local(moment: datetime, tz: ZoneInfo) -> str:
    return moment.astimezone(tz).isoformat()
