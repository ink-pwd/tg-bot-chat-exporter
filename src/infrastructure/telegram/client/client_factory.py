from dataclasses import dataclass

from telethon import TelegramClient
from telethon.sessions import StringSession


@dataclass(frozen=True)
class DeviceInfo:
    """Как сессия бота выглядит в «Настройки → Устройства» у владельца аккаунта."""

    device_model: str = "tg-exporter"
    system_version: str = "server"
    app_version: str = "1.0"


class TelethonClientFactory:
    def __init__(self, api_id: int, api_hash: str, device: DeviceInfo = DeviceInfo()) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._device = device

    def create(self, session: str | None = None, *, flood_sleep_threshold: int = 0) -> TelegramClient:
        """flood_sleep_threshold: FloodWait короче этого Telethon переждёт сам, длиннее — бросит ошибку."""
        return TelegramClient(
            StringSession(session),
            self._api_id,
            self._api_hash,
            device_model=self._device.device_model,
            system_version=self._device.system_version,
            app_version=self._device.app_version,
            flood_sleep_threshold=flood_sleep_threshold,
        )
