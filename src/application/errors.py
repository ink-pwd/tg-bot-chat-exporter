class ApplicationError(Exception):
    """Ошибка сценария, понятная пользователю (переводится в текст в presentation)."""


class LoginNotStarted(ApplicationError):
    """Нет начатого входа: истёк по времени, отменён или бот перезапускался."""


class InvalidCode(ApplicationError):
    pass


class CodeExpired(ApplicationError):
    pass


class CodeResendUnavailable(ApplicationError):
    """Telegram исчерпал способы повторной отправки кода."""


class InvalidPassword(ApplicationError):
    pass


class PhoneNumberRejected(ApplicationError):
    """Telegram не принял номер: неверный, заблокирован или не зарегистрирован."""


class TooManyAttempts(ApplicationError):
    def __init__(self, retry_after_seconds: int | None = None) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class TelegramUnavailable(ApplicationError):
    """Прочие сбои Telegram API — подробности только в логах."""
