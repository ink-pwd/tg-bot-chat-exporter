from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from domain.errors import AccountOwnedByAnotherUser
from domain.value_objects.telegram_profile import TelegramProfile
from infrastructure.persistence.models import TelegramAccountModel


class SqlTelegramAccountRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_owned(self, owner_id: int) -> list[TelegramAccount]:
        async with self._session_factory() as db:
            rows = await db.scalars(
                select(TelegramAccountModel)
                .where(TelegramAccountModel.owner_id == owner_id)
                .order_by(TelegramAccountModel.id)
            )
            return [_to_entity(row) for row in rows]

    async def get_owned(self, account_id: int, owner_id: int) -> TelegramAccount | None:
        async with self._session_factory() as db:
            row = await db.scalar(
                select(TelegramAccountModel).where(
                    TelegramAccountModel.id == account_id,
                    TelegramAccountModel.owner_id == owner_id,
                )
            )
            return _to_entity(row) if row else None

    async def save_authorized(self, owner_id: int, profile: TelegramProfile) -> TelegramAccount:
        try:
            async with self._session_factory.begin() as db:
                row = await db.scalar(
                    select(TelegramAccountModel)
                    .where(TelegramAccountModel.telegram_user_id == profile.telegram_user_id)
                    .with_for_update()
                )
                if row is None:
                    row = TelegramAccountModel(
                        owner_id=owner_id, telegram_user_id=profile.telegram_user_id
                    )
                    db.add(row)
                elif row.owner_id != owner_id:
                    raise AccountOwnedByAnotherUser()
                row.display_name = profile.display_name[:255]
                row.username = profile.username
                row.status = AccountStatus.ACTIVE
            return _to_entity(row)
        except IntegrityError:
            # параллельный вход в тот же аккаунт: уникальный telegram_user_id уже занят
            raise AccountOwnedByAnotherUser() from None

    async def delete_owned(self, account_id: int, owner_id: int) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(
                delete(TelegramAccountModel).where(
                    TelegramAccountModel.id == account_id,
                    TelegramAccountModel.owner_id == owner_id,
                )
            )


def _to_entity(row: TelegramAccountModel) -> TelegramAccount:
    return TelegramAccount(
        id=row.id,
        owner_id=row.owner_id,
        telegram_user_id=row.telegram_user_id,
        display_name=row.display_name,
        username=row.username,
        status=AccountStatus(row.status),
    )
