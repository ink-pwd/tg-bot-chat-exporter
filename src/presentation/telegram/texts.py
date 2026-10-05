"""Тексты бота и перевод ошибок в понятные пользователю сообщения."""
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

from application.dto.login import CodeDelivery, CodeSent
from application.errors import (
    CodeExpired,
    ExportTooLarge,
    CodeResendUnavailable,
    InvalidCode,
    InvalidPassword,
    LoginNotStarted,
    PhoneNumberRejected,
    TelegramUnavailable,
    TooManyAttempts,
)
from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from domain.errors import (
    AccountNotFound,
    AccountOwnedByAnotherUser,
    AccountRevoked,
    InvalidExportDay,
    InvalidPhoneNumber,
)

MAIN_MENU = (
    "Выгрузка переписок Telegram за день в JSON.\n\n"
    "Подключите аккаунт, чтобы выгружать его переписки."
)
NO_ACCOUNTS = "Подключённых аккаунтов пока нет."
ACCOUNTS = "Ваши аккаунты:"
LOGIN_METHODS = (
    "Как подключить аккаунт?\n\n"
    "<b>QR-код</b> — быстрее всего: отсканируйте его в Telegram на телефоне "
    "(«Настройки → Устройства → Подключить устройство»).\n\n"
    "<b>По номеру телефона</b> — код подтверждения введёте кнопками."
)
QR_CAPTION = (
    "Отсканируйте QR-код в Telegram на телефоне:\n"
    "«Настройки → Устройства → Подключить устройство».\n\n"
    "Код обновляется автоматически."
)
QR_EXPIRED = "Время на вход по QR-коду вышло. Попробуйте ещё раз."
ASK_PHONE = "Отправьте номер телефона аккаунта в международном формате, например <code>+380501234567</code>."
ASK_PASSWORD = (
    "На аккаунте включена двухэтапная проверка.\n\n"
    "Отправьте пароль сообщением — бот сразу удалит его из чата."
)
CODE_AS_MESSAGE = (
    "Код нужно вводить кнопками под сообщением с кодом. Если вы отправили код "
    "сообщением, Telegram мог его аннулировать — нажмите «Отправить код повторно»."
)
PASSWORD_DELETE_HINT = "Не удалось удалить сообщение с паролем — удалите его вручную."
LOGIN_CANCELLED = "Вход отменён."
LOGIN_EXPIRED = "Вход не найден или устарел. Начните заново."
ASK_DATE = (
    "За какой день выгрузить переписки?\n\n"
    "Отправьте дату, например <code>04.10</code> или <code>2026-10-04</code>."
)
INVALID_DATE = "Не понял дату. Пример: <code>04.10</code> или <code>2026-10-04</code>."
UNEXPECTED_ERROR = "Что-то пошло не так. Попробуйте ещё раз позже."

_DELIVERY = {
    CodeDelivery.APP: "в приложение Telegram (чат «Telegram» на другом вашем устройстве)",
    CodeDelivery.SMS: "по SMS",
    CodeDelivery.CALL: "звонком — код продиктуют",
    CodeDelivery.FLASH_CALL: "сбросом звонка — код это последние цифры номера",
    CodeDelivery.MISSED_CALL: "пропущенным звонком — код это последние цифры номера",
    CodeDelivery.EMAIL: "на почту, привязанную к аккаунту",
    CodeDelivery.FRAGMENT: "через Fragment",
    CodeDelivery.OTHER: "",
}


def code_prompt(sent: CodeSent, entered: int, notice: str | None = None) -> str:
    where = _DELIVERY[sent.delivery]
    lines = [f"Код отправлен {where}." if where else "Код отправлен."]
    lines.append("Введите его кнопками ниже — не отправляйте код сообщением, Telegram его аннулирует.")
    if notice:
        lines += ["", notice]
    total = sent.length or max(entered, 5)
    lines += ["", "Код: " + " ".join("●" if i < entered else "○" for i in range(total))]
    return "\n".join(lines)


def format_day(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def export_started(day: date) -> str:
    return f"⏳ Выгружаю переписки за {format_day(day)}…\nНа больших аккаунтах это может занять несколько минут."


def export_caption(account_name: str, day: date, conversations: int, messages: int) -> str:
    return (
        f"📦 <b>{escape(account_name)}</b> — {format_day(day)}\n"
        f"Чатов: {conversations}, сообщений: {messages}"
    )


def export_summary(
    account_name: str,
    day: date,
    conversations: int,
    messages: int,
    exported_at: datetime,
    from_cache: bool,
    timezone: ZoneInfo,
) -> str:
    if messages == 0:
        text = f"За {format_day(day)} в аккаунте <b>{escape(account_name)}</b> сообщений нет."
    else:
        text = f"✅ Готово: чатов {conversations}, сообщений {messages}."
    if from_cache:
        text += f"\nДанные на {exported_at.astimezone(timezone):%H:%M} (из кеша)."
    return text


def account_connected(account: TelegramAccount) -> str:
    return f"✅ Аккаунт <b>{escape(account.display_name)}</b> подключён."


def account_card(account: TelegramAccount) -> str:
    lines = [f"<b>{escape(account.display_name)}</b>"]
    if account.username:
        lines.append(f"@{escape(account.username)}")
    if account.status is AccountStatus.REVOKED:
        lines += ["", "⚠️ Сессия завершена в Telegram. Подключите аккаунт заново."]
    return "\n".join(lines)


def logout_confirm(account: TelegramAccount) -> str:
    return (
        f"Отключить аккаунт <b>{escape(account.display_name)}</b>?\n\n"
        "Сессия бота будет завершена, выгрузки станут недоступны до повторного подключения."
    )


def account_logged_out() -> str:
    return "Аккаунт отключён."


def error_text(exc: Exception) -> str | None:
    """Текст для пользователя или None, если ошибка неожиданная."""
    match exc:
        case AccountNotFound():
            return "Аккаунт не найден."
        case AccountRevoked():
            return (
                "Сессия аккаунта завершена в Telegram (например, из «Устройств»). "
                "Подключите аккаунт заново."
            )
        case InvalidExportDay():
            return "Этот день ещё не наступил."
        case ExportTooLarge():
            return "Выгрузка за этот день слишком большая для отправки через Telegram."
        case AccountOwnedByAnotherUser():
            return "Этот Telegram-аккаунт уже подключён другим пользователем бота."
        case InvalidPhoneNumber():
            return "Не похоже на номер телефона. Пример: <code>+380501234567</code>."
        case PhoneNumberRejected():
            return "Telegram не принял этот номер. Проверьте его и попробуйте ещё раз."
        case InvalidCode():
            return "Неверный код, попробуйте ещё раз."
        case CodeExpired():
            return "Код истёк. Нажмите «Отправить код повторно»."
        case CodeResendUnavailable():
            return (
                "Telegram исчерпал способы отправки кода. Дождитесь уже отправленного "
                "кода или попробуйте через 12–24 часа."
            )
        case InvalidPassword():
            return "Неверный пароль, попробуйте ещё раз."
        case TooManyAttempts(retry_after_seconds=seconds) if seconds:
            return f"Слишком много попыток. Попробуйте через {_duration(seconds)}."
        case TooManyAttempts():
            return "Слишком много попыток. Попробуйте позже."
        case LoginNotStarted():
            return LOGIN_EXPIRED
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
