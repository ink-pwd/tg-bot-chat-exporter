class ApplicationError(Exception):
    """Ошибка сценария, понятная пользователю (переводится в текст в presentation)."""


class TooManyAttempts(ApplicationError):
    def __init__(self, retry_after_seconds: int | None = None) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class TelegramUnavailable(ApplicationError):
    """Прочие сбои Telegram API — подробности только в логах."""


class CachedFileUnavailable(ApplicationError):
    """Ранее отправленный файл больше нельзя переслать по file_id."""


class ExportTooLarge(ApplicationError):
    """Выгрузка не помещается в лимит Telegram на размер файла даже в сжатом виде."""


class RecipientUnavailable(ApplicationError):
    """Пользователь заблокировал бота или удалил чат — отправить ему ничего нельзя."""
