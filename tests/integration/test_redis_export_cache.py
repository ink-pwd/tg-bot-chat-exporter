import json
import os
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from redis.asyncio import Redis

from application.dto.export import CachedExport
from domain.value_objects.day_range import DayRange
from infrastructure.cache.redis_export_cache import RedisExportCache

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_REDIS_URL, reason="TEST_REDIS_URL не задан"),
]

DAY = DayRange(date(2026, 10, 4), ZoneInfo("Europe/Kyiv"))
EXPORT = CachedExport("file-1", 3, 42, datetime(2026, 10, 5, 9, 0, tzinfo=UTC))


@pytest.fixture
async def redis():
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def cache(redis):
    return RedisExportCache(redis)


async def test_roundtrip_with_ttl(cache, redis):
    await cache.put(1, DAY, EXPORT, timedelta(hours=24))

    assert await cache.get(1, DAY) == EXPORT
    assert 0 < await redis.ttl("export:1:2026-10-04:Europe/Kyiv") <= 24 * 3600


async def test_keys_are_separated_by_account_and_timezone(cache):
    await cache.put(1, DAY, EXPORT, timedelta(hours=1))

    assert await cache.get(2, DAY) is None
    assert await cache.get(1, DayRange(DAY.day, ZoneInfo("UTC"))) is None


async def test_empty_day_without_file(cache):
    empty = CachedExport(None, 0, 0, EXPORT.exported_at)

    await cache.put(1, DAY, empty, timedelta(hours=1))

    assert await cache.get(1, DAY) == empty


async def test_delete(cache):
    await cache.put(1, DAY, EXPORT, timedelta(hours=1))

    await cache.delete(1, DAY)

    assert await cache.get(1, DAY) is None


async def test_only_reference_and_counters_are_stored(cache, redis):
    await cache.put(1, DAY, EXPORT, timedelta(hours=1))

    stored = json.loads(await redis.get("export:1:2026-10-04:Europe/Kyiv"))

    assert set(stored) == {"file_id", "conversations_count", "messages_count", "exported_at"}
