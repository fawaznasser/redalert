from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import sys

from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.db import SessionLocal
from app.services.event_service import ingest_message
from app.services.telegram_listener import _build_session


def parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def normalize_channel_name(value: str) -> str:
    channel = value.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if channel.startswith(prefix):
            channel = channel[len(prefix):]
            break
    return channel.removeprefix("@")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Telegram channel history into raw_messages/events")
    parser.add_argument("--since", required=True, help="Inclusive start date in YYYY-MM-DD format")
    parser.add_argument("--until", help="Inclusive end date in YYYY-MM-DD format")
    args = parser.parse_args()

    if not settings.telegram_is_configured:
        raise RuntimeError("Telegram is not fully configured in backend/.env")

    since = parse_day(args.since)
    until = parse_day(args.until) + timedelta(days=1) - timedelta(microseconds=1) if args.until else None

    client = TelegramClient(_build_session(settings.telegram_session), settings.telegram_api_id, settings.telegram_api_hash)
    await client.start()
    try:
        total_ingested = 0
        for configured_channel in settings.telegram_channels:
            channel = await client.get_entity(configured_channel)
            channel_name = normalize_channel_name(configured_channel)

            matched_messages = []
            async for message in client.iter_messages(channel):
                message_time = (message.edit_date or message.date)
                if message_time.tzinfo is None:
                    message_time = message_time.replace(tzinfo=timezone.utc)
                else:
                    message_time = message_time.astimezone(timezone.utc)

                if message_time < since:
                    break
                if until is not None and message_time > until:
                    continue
                matched_messages.append(message)

            ingested = 0
            for message in reversed(matched_messages):
                session = SessionLocal()
                try:
                    ingest_message(
                        session,
                        telegram_message_id=message.id,
                        channel_name=channel_name,
                        message_text=message.message or getattr(message, "raw_text", "") or "",
                        message_date=message.edit_date or message.date,
                        raw_payload=json.loads(message.to_json()),
                    )
                    ingested += 1
                finally:
                    session.close()

            total_ingested += ingested
            print(
                f"Backfilled {ingested} Telegram messages from {channel_name} "
                f"from {args.since}" + (f" to {args.until}" if args.until else "")
            )

        print(f"Backfilled {total_ingested} total Telegram messages across {len(settings.telegram_channels)} channels")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
