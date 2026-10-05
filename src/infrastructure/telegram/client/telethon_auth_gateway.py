"""Авторизация Telegram-аккаунтов через Telethon.

Незавершённые входы живут в памяти процесса: между шагами (телефон → код →
пароль) Telethon-клиент должен оставаться подключённым, поэтому бот работает
в одном экземпляре. После перезапуска начатые входы теряются.
"""
import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from telethon import TelegramClient, errors, utils
from telethon.sessions import StringSession
from telethon.tl import types
from telethon.tl.custom.qrlogin import QRLogin
from telethon.tl.functions.auth import ResendCodeRequest

from application.dto.login import (
    AuthorizedSession,
    CodeDelivery,
    CodeSent,
    LoginCancelled,
    LoginTimedOut,
    PasswordRequired,
    QrChallenge,
    QrRefreshed,
    QrWaitOutcome,
    SignInOutcome,
)
from application.errors import (
    ApplicationError,
    CodeExpired,
    CodeResendUnavailable,
    InvalidCode,
    InvalidPassword,
    LoginNotStarted,
    PhoneNumberRejected,
    TelegramUnavailable,
    TooManyAttempts,
)
from domain.value_objects.phone_number import PhoneNumber
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession

logger = logging.getLogger(__name__)

_CODE_DELIVERY = {
    types.auth.SentCodeTypeApp: CodeDelivery.APP,
    types.auth.SentCodeTypeSms: CodeDelivery.SMS,
    types.auth.SentCodeTypeCall: CodeDelivery.CALL,
    types.auth.SentCodeTypeFlashCall: CodeDelivery.FLASH_CALL,
    types.auth.SentCodeTypeMissedCall: CodeDelivery.MISSED_CALL,
    types.auth.SentCodeTypeEmailCode: CodeDelivery.EMAIL,
    types.auth.SentCodeTypeFragmentSms: CodeDelivery.FRAGMENT,
}


@dataclass
class _PendingLogin:
    client: TelegramClient
    started_at: float = field(default_factory=time.monotonic)
    phone: str | None = None
    phone_code_hash: str | None = None
    qr: QRLogin | None = None
    qr_deadline: float = 0.0
    waiter: asyncio.Task | None = None


@dataclass(frozen=True)
class DeviceInfo:
    """Как сессия бота выглядит в «Настройки → Устройства» у владельца аккаунта."""

    device_model: str = "tg-exporter"
    system_version: str = "server"
    app_version: str = "1.0"


class TelethonAuthGateway:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        *,
        device: DeviceInfo = DeviceInfo(),
        login_ttl_seconds: float = 600,
        qr_ttl_seconds: float = 180,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._device = device
        self._login_ttl = login_ttl_seconds
        self._qr_ttl = qr_ttl_seconds
        self._pending: dict[int, _PendingLogin] = {}

    # --- QR ----------------------------------------------------------------

    async def start_qr(self, login_id: int) -> QrChallenge:
        await self.cancel(login_id)
        client = await self._connect()
        try:
            qr = await client.qr_login()
        except Exception as exc:
            await _disconnect(client)
            raise _translate(exc) from exc
        self._pending[login_id] = _PendingLogin(
            client, qr=qr, qr_deadline=time.monotonic() + self._qr_ttl
        )
        return QrChallenge(qr.url)

    async def wait_qr(self, login_id: int) -> QrWaitOutcome:
        pending = self._get(login_id)
        if pending.qr is None:
            raise LoginNotStarted()
        qr = pending.qr

        timeout = max(1.0, (qr.expires - datetime.now(timezone.utc)).total_seconds())
        waiter = asyncio.create_task(qr.wait(timeout))
        pending.waiter = waiter
        try:
            await asyncio.wait({waiter})
        finally:
            pending.waiter = None

        if waiter.cancelled():
            return LoginCancelled()
        exc = waiter.exception()
        if exc is None:
            return await self._finish(login_id, pending, waiter.result())
        if isinstance(exc, TimeoutError):
            if time.monotonic() >= pending.qr_deadline:
                await self._drop(login_id, pending)
                return LoginTimedOut()
            try:
                await qr.recreate()
            except Exception as recreate_exc:
                await self._drop(login_id, pending)
                raise _translate(recreate_exc) from recreate_exc
            return QrRefreshed(qr.url)
        if isinstance(exc, errors.SessionPasswordNeededError):
            pending.qr = None
            return PasswordRequired()
        await self._drop(login_id, pending)
        raise _translate(exc) from exc

    # --- телефон и код -----------------------------------------------------

    async def start_phone(self, login_id: int, phone: PhoneNumber) -> CodeSent:
        await self.cancel(login_id)
        client = await self._connect()
        try:
            sent = await client.send_code_request(phone.value)
        except Exception as exc:
            await _disconnect(client)
            raise _translate(exc) from exc
        self._pending[login_id] = _PendingLogin(
            client, phone=phone.value, phone_code_hash=sent.phone_code_hash
        )
        return _code_sent(sent)

    async def resend_code(self, login_id: int) -> CodeSent:
        pending = self._get_phone_login(login_id)
        try:
            sent = await pending.client(ResendCodeRequest(pending.phone, pending.phone_code_hash))
        except errors.SendCodeUnavailableError as exc:
            raise CodeResendUnavailable() from exc
        except Exception as exc:
            raise _translate(exc) from exc
        pending.phone_code_hash = sent.phone_code_hash
        return _code_sent(sent)

    async def submit_code(self, login_id: int, code: str) -> SignInOutcome:
        pending = self._get_phone_login(login_id)
        try:
            user = await pending.client.sign_in(
                pending.phone, code, phone_code_hash=pending.phone_code_hash
            )
        except (errors.PhoneCodeInvalidError, errors.PhoneCodeEmptyError) as exc:
            raise InvalidCode() from exc
        except errors.PhoneCodeExpiredError as exc:
            # вход не сбрасываем: можно запросить код повторно
            raise CodeExpired() from exc
        except errors.SessionPasswordNeededError:
            return PasswordRequired()
        except Exception as exc:
            if not isinstance(exc, errors.FloodWaitError):
                await self._drop(login_id, pending)
            raise _translate(exc) from exc
        return await self._finish(login_id, pending, user)

    async def submit_password(self, login_id: int, password: str) -> SignInOutcome:
        pending = self._get(login_id)
        try:
            user = await pending.client.sign_in(password=password)
        except errors.PasswordHashInvalidError as exc:
            raise InvalidPassword() from exc
        except Exception as exc:
            raise _translate(exc) from exc
        return await self._finish(login_id, pending, user)

    # --- общее -------------------------------------------------------------

    async def cancel(self, login_id: int) -> None:
        pending = self._pending.pop(login_id, None)
        if pending is None:
            return
        if pending.waiter is not None:
            pending.waiter.cancel()
        await _disconnect(pending.client)

    async def log_out(self, session: TelegramSession) -> None:
        client = self._new_client(session.value)
        try:
            await client.connect()
            if await client.is_user_authorized():
                await client.log_out()
        except Exception as exc:
            raise _translate(exc) from exc
        finally:
            await _disconnect(client)

    async def run_cleanup(self, interval_seconds: float = 60) -> None:
        """Фоновая задача: закрывает брошенные на полпути входы."""
        while True:
            await asyncio.sleep(interval_seconds)
            now = time.monotonic()
            for login_id, pending in list(self._pending.items()):
                if pending.waiter is None and now - pending.started_at > self._login_ttl:
                    logger.info("Abandoned login expired: user=%s", login_id)
                    await self._drop(login_id, pending)

    async def close(self) -> None:
        for login_id in list(self._pending):
            await self.cancel(login_id)

    # --- внутреннее --------------------------------------------------------

    def _new_client(self, session: str | None = None) -> TelegramClient:
        return TelegramClient(
            StringSession(session),
            self._api_id,
            self._api_hash,
            device_model=self._device.device_model,
            system_version=self._device.system_version,
            app_version=self._device.app_version,
            # FloodWait отдаём пользователю, а не засыпаем внутри обработчика
            flood_sleep_threshold=0,
        )

    async def _connect(self) -> TelegramClient:
        client = self._new_client()
        try:
            await client.connect()
        except Exception as exc:
            await _disconnect(client)
            raise _translate(exc) from exc
        return client

    def _get(self, login_id: int) -> _PendingLogin:
        pending = self._pending.get(login_id)
        if pending is None:
            raise LoginNotStarted()
        return pending

    def _get_phone_login(self, login_id: int) -> _PendingLogin:
        pending = self._get(login_id)
        if pending.phone is None:
            raise LoginNotStarted()
        return pending

    async def _finish(
        self, login_id: int, pending: _PendingLogin, user: types.User
    ) -> AuthorizedSession:
        session = TelegramSession(pending.client.session.save())
        profile = TelegramProfile(
            telegram_user_id=user.id,
            display_name=utils.get_display_name(user) or str(user.id),
            username=user.username,
        )
        await self._drop(login_id, pending)
        return AuthorizedSession(profile, session)

    async def _drop(self, login_id: int, pending: _PendingLogin) -> None:
        if self._pending.get(login_id) is pending:
            del self._pending[login_id]
        await _disconnect(pending.client)


async def _disconnect(client: TelegramClient) -> None:
    with contextlib.suppress(Exception):
        await client.disconnect()


def _code_sent(sent: types.auth.SentCode) -> CodeSent:
    return CodeSent(
        delivery=_CODE_DELIVERY.get(type(sent.type), CodeDelivery.OTHER),
        length=getattr(sent.type, "length", None),
    )


def _translate(exc: BaseException) -> ApplicationError:
    """Ошибки Telethon → ошибки приложения. Подробности остаются в логах."""
    if isinstance(exc, ApplicationError):
        return exc
    if isinstance(exc, errors.FloodWaitError):
        return TooManyAttempts(exc.seconds)
    if isinstance(exc, (errors.PhoneNumberFloodError, errors.PhonePasswordFloodError)):
        return TooManyAttempts()
    if isinstance(
        exc,
        (
            errors.PhoneNumberInvalidError,
            errors.PhoneNumberBannedError,
            errors.PhoneNumberUnoccupiedError,
        ),
    ):
        return PhoneNumberRejected()
    logger.error("Telegram auth error: %s", type(exc).__name__, exc_info=exc)
    return TelegramUnavailable()
