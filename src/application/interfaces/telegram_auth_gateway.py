from typing import Protocol

from application.dto.login import CodeSent, QrChallenge, QrWaitOutcome, SignInOutcome
from domain.value_objects.phone_number import PhoneNumber
from domain.value_objects.telegram_session import TelegramSession


class TelegramAuthGateway(Protocol):
    """Пошаговая авторизация Telegram-аккаунта.

    login_id связывает шаги одного входа (у пользователя бота одновременно
    не больше одного незавершённого входа). Новый start_* отменяет предыдущий.
    Ошибки Telegram переводятся в application.errors.
    """

    async def start_qr(self, login_id: int) -> QrChallenge: ...

    async def wait_qr(self, login_id: int) -> QrWaitOutcome: ...

    async def start_phone(self, login_id: int, phone: PhoneNumber) -> CodeSent: ...

    async def resend_code(self, login_id: int) -> CodeSent: ...

    async def submit_code(self, login_id: int, code: str) -> SignInOutcome: ...

    async def submit_password(self, login_id: int, password: str) -> SignInOutcome: ...

    async def cancel(self, login_id: int) -> None: ...

    async def log_out(self, session: TelegramSession) -> None:
        """Завершает сессию на стороне Telegram (устройство пропадает из списка)."""
        ...
