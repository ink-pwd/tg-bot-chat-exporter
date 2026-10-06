"""Хранилище расписаний автовыгрузки в MySQL."""
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.export_schedule import ExportSchedule
from infrastructure.persistence.sqlalchemy_models import ExportScheduleModel


class MySqlExportScheduleRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get(self, owner_id: int) -> ExportSchedule | None:
        async with self._session_factory() as db:
            row = await db.get(ExportScheduleModel, owner_id)
            return _to_entity(row) if row else None

    async def list_enabled(self) -> list[ExportSchedule]:
        async with self._session_factory() as db:
            rows = await db.scalars(
                select(ExportScheduleModel).where(ExportScheduleModel.enabled.is_(True))
            )
            return [_to_entity(row) for row in rows]

    async def save(self, schedule: ExportSchedule) -> None:
        async with self._session_factory.begin() as db:
            row = await db.get(ExportScheduleModel, schedule.owner_id)
            if row is None:
                row = ExportScheduleModel(owner_id=schedule.owner_id)
                db.add(row)
            row.local_time = schedule.local_time
            row.enabled = schedule.enabled
            row.last_run_day = schedule.last_run_day

    async def mark_done(self, owner_id: int, day: date) -> None:
        await self._update(owner_id, last_run_day=day)

    async def disable(self, owner_id: int) -> None:
        await self._update(owner_id, enabled=False)

    async def _update(self, owner_id: int, **values) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(
                update(ExportScheduleModel)
                .where(ExportScheduleModel.owner_id == owner_id)
                .values(**values)
            )


def _to_entity(row: ExportScheduleModel) -> ExportSchedule:
    return ExportSchedule(
        owner_id=row.owner_id,
        local_time=row.local_time,
        enabled=row.enabled,
        last_run_day=row.last_run_day,
    )
