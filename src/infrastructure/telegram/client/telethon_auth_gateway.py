"""Авторизация Telegram-аккаунтов через Telethon.

Незавершённые входы живут в памяти процесса: между шагами (телефон → код →
пароль) Telethon-клиент должен оставаться подключённым, поэтому бот работает
в одном экземпляре. После перезапуска начатые входы теряются.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from telethon import TelegramClient, errors, utils
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
    CodeExpired,
    CodeResendUnavailable,
    InvalidCode,
    InvalidPassword,
    LoginNotStarted,
)
from domain.value_objects.phone_number import PhoneNumber
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession
from infrastructure.telegram.client.client_factory import TelethonClientFactory
from infrastructure.telegram.client.errors import disconnect_quietly, translate_error

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


class TelethonAuthGateway:
    def __init__(
        self,
        clients: TelethonClientFactory,
        *,
        login_ttl_seconds: float = 600,
        qr_ttl_seconds: float = 180,
    ) -> None:
        self._clients = clients
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
            await disconnect_quietly(client)
            raise translate_error(exc) from exc
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
                raise translate_error(recreate_exc) from recreate_exc
            return QrRefreshed(qr.url)
        if isinstance(exc, errors.SessionPasswordNeededError):
            pending.qr = None
            return PasswordRequired()
        await self._drop(login_id, pending)
        raise translate_error(exc) from exc

    # --- телефон и код -----------------------------------------------------

    async def start_phone(self, login_id: int, phone: PhoneNumber) -> CodeSent:
        await self.cancel(login_id)
        client = await self._connect()
        try:
            sent = await client.send_code_request(phone.value)
        except Exception as exc:
            await disconnect_quietly(client)
            raise translate_error(exc) from exc
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
            raise translate_error(exc) from exc
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
            raise translate_error(exc) from exc
        return await self._finish(login_id, pending, user)

    async def submit_password(self, login_id: int, password: str) -> SignInOutcome:
        pending = self._get(login_id)
        try:
            user = await pending.client.sign_in(password=password)
        except errors.PasswordHashInvalidError as exc:
            raise InvalidPassword() from exc
        except Exception as exc:
            raise translate_error(exc) from exc
        return await self._finish(login_id, pending, user)

    # --- общее -------------------------------------------------------------

    async def cancel(self, login_id: int) -> None:
        pending = self._pending.pop(login_id, None)
        if pending is None:
            return
        if pending.waiter is not None:
            pending.waiter.cancel()
        await disconnect_quietly(pending.client)

    async def log_out(self, session: TelegramSession) -> None:
        client = self._clients.create(session.value)
        try:
            await client.connect()
            if await client.is_user_authorized():
                await client.log_out()
        except Exception as exc:
            raise translate_error(exc) from exc
        finally:
            await disconnect_quietly(client)

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

    async def _connect(self) -> TelegramClient:
        # FloodWait отдаём пользователю, а не засыпаем внутри обработчика
        client = self._clients.create(flood_sleep_threshold=0)
        try:
            await client.connect()
        except Exception as exc:
            await disconnect_quietly(client)
            raise translate_error(exc) from exc
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
        await disconnect_quietly(pending.client)



def _code_sent(sent: types.auth.SentCode) -> CodeSent:
    return CodeSent(
        delivery=_CODE_DELIVERY.get(type(sent.type), CodeDelivery.OTHER),
        length=getattr(sent.type, "length", None),
    )
