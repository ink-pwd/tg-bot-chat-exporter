from datetime import date

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.export_schedule import ExportSchedule
from infrastructure.persistence.models import ExportScheduleModel, TelegramAccountModel


class SqlExportScheduleRepository:
    """owner_id берётся из telegram_accounts — в самой таблице расписаний его нет."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get_owned(self, account_id: int, owner_id: int) -> ExportSchedule | None:
        async with self._session_factory() as db:
            row = (
                await db.execute(
                    _with_owner().where(
                        ExportScheduleModel.account_id == account_id,
                        TelegramAccountModel.owner_id == owner_id,
                    )
                )
            ).first()
        return _to_entity(*row) if row else None

    async def list_owned(self, owner_id: int) -> list[ExportSchedule]:
        async with self._session_factory() as db:
            rows = await db.execute(_with_owner().where(TelegramAccountModel.owner_id == owner_id))
            return [_to_entity(*row) for row in rows]

    async def list_enabled(self) -> list[ExportSchedule]:
        async with self._session_factory() as db:
            rows = await db.execute(_with_owner().where(ExportScheduleModel.enabled.is_(True)))
            return [_to_entity(*row) for row in rows]

    async def save(self, schedule: ExportSchedule) -> None:
        async with self._session_factory.begin() as db:
            owned = await db.scalar(
                select(TelegramAccountModel.id).where(
                    TelegramAccountModel.id == schedule.account_id,
                    TelegramAccountModel.owner_id == schedule.owner_id,
                )
            )
            if owned is None:
                return
            row = await db.get(ExportScheduleModel, schedule.account_id)
            if row is None:
                row = ExportScheduleModel(account_id=schedule.account_id)
                db.add(row)
            row.local_time = schedule.local_time
            row.enabled = schedule.enabled
            row.last_run_day = schedule.last_run_day

    async def mark_done(self, account_id: int, day: date) -> None:
        await self._update(ExportScheduleModel.account_id == account_id, last_run_day=day)

    async def disable(self, account_id: int) -> None:
        await self._update(ExportScheduleModel.account_id == account_id, enabled=False)

    async def disable_all_owned(self, owner_id: int) -> None:
        owned_accounts = select(TelegramAccountModel.id).where(
            TelegramAccountModel.owner_id == owner_id
        )
        await self._update(ExportScheduleModel.account_id.in_(owned_accounts), enabled=False)

    async def _update(self, condition, **values) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(update(ExportScheduleModel).where(condition).values(**values))


def _with_owner() -> Select:
    return select(ExportScheduleModel, TelegramAccountModel.owner_id).join(
        TelegramAccountModel, TelegramAccountModel.id == ExportScheduleModel.account_id
    )


def _to_entity(row: ExportScheduleModel, owner_id: int) -> ExportSchedule:
    return ExportSchedule(
        account_id=row.account_id,
        owner_id=owner_id,
        local_time=row.local_time,
        enabled=row.enabled,
        last_run_day=row.last_run_day,
    )
