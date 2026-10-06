"""Тексты бота и перевод ошибок в понятные пользователю сообщения."""
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

from application.errors import ExportTooLarge, TelegramUnavailable, TooManyAttempts
from application.interfaces.export_progress import ExportStage
from domain.entities.export_schedule import ExportSchedule
from domain.entities.support_chat import SupportChat
from domain.errors import ChatNotFound, ExportDayTooOld, InvalidExportDay, InvalidTimezone

HOW_TO_CONNECT = (
    "Добавьте бота в беседу кнопкой «➕ Добавить в беседу». С этого момента бот сохраняет "
    "её сообщения: прочитать историю до своего добавления бот не может.\n\n"
    "Беседу и её выгрузки видит только тот, кто добавил бота. В самой беседе бот ничего не пишет."
)
NO_CHATS = "Подключённых бесед пока нет.\n\n" + HOW_TO_CONNECT
CHATS = "Ваши беседы:"
CHOOSE_DAY = (
    "📥 За какой день выгрузить переписки?\n\n"
    "Сообщения хранятся 7 дней, поэтому доступны сегодня и шесть предыдущих дней."
)
ASK_TIMEZONE = (
    "Выберите часовой пояс или отправьте его название в формате IANA, "
    "например <code>Europe/Lisbon</code> или <code>America/Chicago</code>."
)
ASK_SCHEDULE_TIME = "Отправьте время автовыгрузки, например <code>07:45</code>."
INVALID_TIME = "Не понял время. Пример: <code>07:45</code>."
TIMEZONE_KEPT = "Хорошо, время автовыгрузки не меняется."
UNEXPECTED_ERROR = "Что-то пошло не так. Попробуйте ещё раз позже."
CHAT_REJECTED = "У вас нет доступа к этому боту, поэтому он вышел из беседы."
PRIVACY_WARNING = (
    "⚠️ Сейчас бот видит в беседе только команды. Чтобы он сохранял все сообщения, "
    "сделайте его администратором беседы или выключите privacy mode в @BotFather "
    "(<code>/setprivacy</code> → Disable), а затем добавьте бота в беседу заново."
)


def main_menu(chats: list[SupportChat]) -> str:
    active = sum(1 for chat in chats if chat.active)
    text = "Выгрузка переписок из бесед поддержки за день: JSON и HTML-отчёт.\n\n"
    if not chats:
        return text + HOW_TO_CONNECT
    return text + f"Подключено бесед: <b>{active}</b>. Выгрузка собирает все ваши беседы в один файл."


_WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def format_day(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def day_button(day: date, today: date) -> str:
    if day == today:
        name = "Сегодня"
    elif (today - day).days == 1:
        name = "Вчера"
    else:
        name = _WEEKDAYS[day.weekday()]
    return f"{name}, {day:%d.%m}"


def nothing_recorded(day: date) -> str:
    return (
        f"За {format_day(day)} сообщений из ваших бесед ещё не зафиксировано, "
        "выгружать нечего.\n\n"
        "Бот сохраняет сообщения только с момента, когда его добавили в беседу."
    )


_STAGES = {
    ExportStage.COLLECTING: "Собираю сообщения бесед",
    ExportStage.ANALYZING: "Анализирую обращения и время ответа",
    ExportStage.SENDING: "Формирую и отправляю файлы",
}
_BAR_CELLS = 12


def export_progress(day: date, stage: ExportStage | None) -> str:
    """⏳ Выгрузка за 06.10.2026 / ▰▰▰▰▰▰▰▰▱▱▱▱ 2/3 / Анализирую обращения…"""
    total = len(ExportStage)
    # текущий этап закрашен наполовину: полная шкала была бы обманом, пока файлы не ушли
    done = 0.0 if stage is None else stage.value - 0.5
    filled = round(_BAR_CELLS * done / total)
    step = f"{stage.value}/{total} · {_STAGES[stage]}…" if stage else "Начинаю…"
    return (
        f"⏳ Выгрузка за {format_day(day)}\n"
        f"{'▰' * filled}{'▱' * (_BAR_CELLS - filled)}\n{step}"
    )


def export_caption(day: date, conversations: int, messages: int) -> str:
    return f"📦 <b>Беседы поддержки</b> — {format_day(day)}\nЧатов: {conversations}, сообщений: {messages}"


def export_summary(
    day: date,
    conversations: int,
    messages: int,
    exported_at: datetime,
    from_cache: bool,
    timezone: ZoneInfo,
) -> str:
    if messages == 0:
        return nothing_recorded(day)
    text = f"✅ Готово: чатов {conversations}, сообщений {messages}."
    if from_cache:
        text += f"\nДанные на {exported_at.astimezone(timezone):%H:%M} (из кеша)."
    return text


def utc_offset(timezone: ZoneInfo, now: datetime | None = None) -> str:
    offset = (now or datetime.now(timezone)).astimezone(timezone).utcoffset()
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "−"
    hours, minutes = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def timezone_label(timezone: ZoneInfo) -> str:
    return f"{timezone.key}, {utc_offset(timezone)}"


def settings(timezone: ZoneInfo) -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"Часовой пояс: <b>{timezone_label(timezone)}</b>\n"
        "По нему считаются границы суток в выгрузках и время автовыгрузки."
    )


def timezone_menu(timezone: ZoneInfo) -> str:
    return f"Сейчас: <b>{timezone_label(timezone)}</b>\n\n{ASK_TIMEZONE}"


def timezone_changed(timezone: ZoneInfo) -> str:
    return f"✅ Часовой пояс: <b>{timezone_label(timezone)}</b>."


def ask_change_schedule_time(timezone: ZoneInfo, schedule: ExportSchedule) -> str:
    return (
        f"{timezone_changed(timezone)}\n\n"
        f"Автовыгрузка теперь идёт в {schedule.local_time:%H:%M} по новому поясу. Изменить время?"
    )


def auto_export(schedule: ExportSchedule, timezone: ZoneInfo) -> str:
    status = (
        f"включена, каждый день в <b>{schedule.local_time:%H:%M}</b>"
        if schedule.enabled
        else "<b>выключена</b>"
    )
    return (
        f"⏰ Автовыгрузка: {status}.\n\n"
        "В выбранное время бот пришлёт выгрузку всех ваших бесед за прошедший день. "
        f"Часовой пояс: {timezone_label(timezone)}, сменить его можно в «Настройках».\n\n"
        "Выберите время:"
    )


def auto_export_completed_note(day: date, messages: int) -> str:
    if messages == 0:
        return f"⏰ Автовыгрузка за {format_day(day)}: сообщений из ваших бесед не зафиксировано."
    return f"⏰ Автовыгрузка за {format_day(day)} выполнена."


def auto_export_failed(day: date, reason: str) -> str:
    return (
        f"❌ Не удалось выполнить автовыгрузку за {format_day(day)}.\n{reason}\n\n"
        "Этот день можно выгрузить вручную: «📥 Выгрузить» в главном меню."
    )


def chat_connected(chat: SupportChat, can_read_all: bool) -> str:
    text = (
        f"✅ Беседа <b>{escape(chat.title)}</b> подключена. Бот сохраняет её сообщения "
        "начиная с этого момента. Выгрузки доступны только вам."
    )
    return text if can_read_all else f"{text}\n\n{PRIVACY_WARNING}"


def chat_card(chat: SupportChat) -> str:
    status = "✅ бот в беседе, сообщения сохраняются" if chat.active else "⚠️ бота удалили из беседы"
    return (
        f"<b>{escape(chat.title)}</b>\n{status}\n\n"
        "Поддержкой в отчёте считаются администраторы беседы и вы, клиентами — остальные участники."
    )


def disconnect_confirm(chat: SupportChat) -> str:
    return (
        f"Отключить беседу <b>{escape(chat.title)}</b>?\n\n"
        "Бот выйдет из неё и удалит все сохранённые сообщения этой беседы. Отменить это нельзя."
    )


CHAT_DISCONNECTED = "Беседа отключена, её сообщения удалены."


def error_text(exc: Exception) -> str | None:
    """Текст для пользователя или None, если ошибка неожиданная."""
    match exc:
        case ChatNotFound():
            return "Беседа не найдена."
        case InvalidTimezone():
            return "Не знаю такого часового пояса. Пример: <code>Europe/Lisbon</code>."
        case InvalidExportDay():
            return "Этот день ещё не наступил."
        case ExportDayTooOld():
            return "Сообщения хранятся 7 дней, этот день уже недоступен."
        case ExportTooLarge():
            return "Выгрузка за этот день слишком большая для отправки через Telegram."
        case TooManyAttempts(retry_after_seconds=seconds) if seconds:
            return f"Telegram просит подождать. Попробуйте через {_duration(seconds)}."
        case TooManyAttempts():
            return "Telegram просит подождать. Попробуйте позже."
        case TelegramUnavailable():
            return "Telegram сейчас недоступен. Попробуйте ещё раз позже."
    return None


def _duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} с"
    minutes = -(-seconds // 60)
    if minutes < 60:
        return f"{minutes} мин"
    return f"{-(-minutes // 60)} ч"
