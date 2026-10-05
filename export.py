#!/usr/bin/env python3
"""Выгрузка сообщений из всех чатов Telegram за сутки в JSON.

Аккаунты перечисляются в .env: ACCOUNTS=personal,work
Вход в аккаунт (один раз):   python export.py --login personal
Выгрузка всех аккаунтов:     python export.py
Только один аккаунт:         python export.py --account work
Другой день:                 python export.py --date 2026-10-01

По умолчанию выгружает вчерашний день (00:00–24:00 по локальному времени).
"""
import argparse
import asyncio
import getpass
import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

try:
    from telethon import TelegramClient, utils
except ModuleNotFoundError:
    # запущено не из .venv — перезапускаемся через его python
    venv = Path(__file__).resolve().parent / ".venv"
    venv_python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    if venv_python.exists() and Path(sys.executable) != venv_python:
        os.execv(venv_python, [str(venv_python), *sys.argv])
    sys.exit("Нет библиотеки telethon. Выполните: pip install -r requirements.txt")
from telethon.errors import (PhoneCodeExpiredError, PhoneCodeInvalidError,
                             SendCodeUnavailableError, SessionPasswordNeededError)
from telethon.tl.functions.auth import ResendCodeRequest
from telethon.tl.types import Channel, Chat, User

BASE = Path(__file__).resolve().parent
OUT = BASE / "exports"
SESSIONS = BASE / "sessions"


def load_env():
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def chat_type(entity):
    if isinstance(entity, User):
        return "bot" if entity.bot else "private"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        return "supergroup" if entity.megagroup else "channel"
    return "unknown"


def media_type(m):
    if not m.media:
        return None
    for attr in ("photo", "video", "voice", "video_note", "audio", "sticker", "gif", "document", "contact", "geo", "poll"):
        if getattr(m, attr, None):
            return attr
    return type(m.media).__name__


def serialize(m):
    return {
        "id": m.id,
        "date": m.date.astimezone().isoformat(),
        "edit_date": m.edit_date.astimezone().isoformat() if m.edit_date else None,
        "from_id": m.sender_id,
        "from": utils.get_display_name(m.sender) if m.sender else None,
        "out": m.out,
        "text": m.message or "",
        "reply_to": m.reply_to_msg_id,
        "forwarded_from": (m.fwd_from.from_name or utils.get_peer_id(m.fwd_from.from_id))
        if m.fwd_from and (m.fwd_from.from_name or m.fwd_from.from_id) else None,
        "media": media_type(m),
        "action": type(m.action).__name__ if m.action else None,
    }


async def export_day(client, day, out_dir):
    tz = datetime.now().astimezone().tzinfo
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)

    chats = []
    async for dialog in client.iter_dialogs():
        # диалоги без сообщений после начала суток пропускаем сразу
        if dialog.date is None or dialog.date < start:
            continue
        messages = []
        async for m in client.iter_messages(dialog.entity, offset_date=end):
            if m.date < start:
                break
            messages.append(serialize(m))
        if not messages:
            continue
        messages.reverse()
        chats.append({
            "id": dialog.id,
            "name": dialog.name,
            "type": chat_type(dialog.entity),
            "messages": messages,
        })
        print(f"  {dialog.name}: {len(messages)}")

    me = await client.get_me()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{day.isoformat()}.json"
    tmp = out_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "date": day.isoformat(),
        "account": {"id": me.id, "name": utils.get_display_name(me),
                    "username": me.username, "phone": me.phone},
        "exported_at": datetime.now().astimezone().isoformat(),
        "chats": chats,
    }, ensure_ascii=False, indent=2))
    tmp.replace(out_file)
    total = sum(len(c["messages"]) for c in chats)
    print(f"{out_file}: {len(chats)} чатов, {total} сообщений")


def make_client(account, api_id, api_hash):
    SESSIONS.mkdir(mode=0o700, exist_ok=True)
    return TelegramClient(str(SESSIONS / account), api_id, api_hash, flood_sleep_threshold=300)


CODE_TYPES = {
    "SentCodeTypeApp": "в приложение Telegram (чат «Telegram» на другом вашем устройстве)",
    "SentCodeTypeSms": "по SMS",
    "SentCodeTypeCall": "звонком (код продиктуют)",
    "SentCodeTypeFlashCall": "сбросом звонка (код — последние цифры номера)",
    "SentCodeTypeMissedCall": "пропущенным звонком (код — последние цифры номера)",
    "SentCodeTypeEmailCode": "на почту, привязанную к аккаунту",
    "SentCodeTypeFragmentSms": "через Fragment",
}


def describe_code(sent):
    where = CODE_TYPES.get(type(sent.type).__name__, type(sent.type).__name__)
    length = getattr(sent.type, "length", None)
    return f"Код отправлен {where}" + (f", цифр: {length}" if length else "")


async def login(account, api_id, api_hash):
    client = make_client(account, api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            phone = input("Телефон (в формате +380...): ").strip().replace(" ", "")
            if not phone.startswith("+"):
                phone = "+" + phone
            sent = await client.send_code_request(phone)
            print(describe_code(sent))
            while True:
                code = input("Код (Enter — отправить повторно другим способом): ").strip()
                if not code:
                    try:
                        sent = await client(ResendCodeRequest(phone, sent.phone_code_hash))
                        print(describe_code(sent))
                    except SendCodeUnavailableError:
                        print("Telegram исчерпал способы отправки кода на этот номер. "
                              "Дождитесь кода, который уже отправлен, или повторите вход через 12–24 часа.")
                    except Exception as e:
                        print(f"Повторно отправить не удалось: {e}")
                    continue
                try:
                    await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
                    break
                except PhoneCodeInvalidError:
                    print("Неверный код, попробуйте ещё раз.")
                except PhoneCodeExpiredError:
                    sent = await client.send_code_request(phone)
                    print("Код истёк. " + describe_code(sent))
                except SessionPasswordNeededError:
                    await client.sign_in(password=getpass.getpass("Пароль двухэтапной проверки: "))
                    break
        me = await client.get_me()
    finally:
        await client.disconnect()
    (SESSIONS / f"{account}.session").chmod(0o600)
    print(f"{account}: вошли как {utils.get_display_name(me)} (+{me.phone})")


async def export_account(account, api_id, api_hash, day):
    client = make_client(account, api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(f"нет входа, выполните: python export.py --login {account}")
        print(f"[{account}]")
        await export_day(client, day, OUT / account)
    finally:
        await client.disconnect()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat,
                        default=date.today() - timedelta(days=1),
                        help="день для выгрузки, YYYY-MM-DD (по умолчанию вчера)")
    parser.add_argument("--account", help="выгрузить только этот аккаунт")
    parser.add_argument("--login", metavar="ACCOUNT", help="войти в аккаунт (интерактивно)")
    args = parser.parse_args()

    load_env()
    try:
        api_id = int(os.environ["API_ID"])
        api_hash = os.environ["API_HASH"]
    except (KeyError, ValueError):
        sys.exit("Заполните API_ID и API_HASH в .env (см. .env.example)")
    accounts = [a.strip() for a in os.environ.get("ACCOUNTS", "me").split(",") if a.strip()]

    if args.login:
        await login(args.login, api_id, api_hash)
        return

    if args.account:
        accounts = [args.account]
    failed = []
    for account in accounts:
        try:
            await export_account(account, api_id, api_hash, args.date)
        except Exception as e:
            print(f"[{account}] ошибка: {e}", file=sys.stderr)
            failed.append(account)
    if failed:
        sys.exit(f"не удалось выгрузить: {', '.join(failed)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit("\nПрервано")
