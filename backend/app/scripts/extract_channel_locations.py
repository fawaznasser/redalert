from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
import sys

from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.db import SessionLocal
from app.services.location_matcher import match_locations
from app.services.parser import parse_message_text, parse_secondary_channel_incursion_message


def normalize_channel_name(value: str) -> str:
    channel = value.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if channel.startswith(prefix):
            channel = channel[len(prefix):]
            break
    return channel.removeprefix("@")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Extract location mentions from a Telegram channel")
    parser.add_argument("--channel", required=True, help="Telegram channel username or t.me link")
    parser.add_argument("--session", help="Optional Telethon session file path")
    parser.add_argument("--limit", type=int, default=0, help="Optional history limit; 0 means full history")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write extracted summary JSON",
    )
    args = parser.parse_args()

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("Telegram API credentials are missing in backend/.env")

    session_value = args.session or settings.telegram_session
    if not session_value:
        raise RuntimeError("Telegram session is missing in backend/.env")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    channel_name = normalize_channel_name(args.channel)
    client = TelegramClient(session_value, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start()
    session = SessionLocal()

    try:
        entity = await client.get_entity(channel_name)
        total_messages = 0
        parsed_messages = 0
        candidate_counter: Counter[str] = Counter()
        matched_counter: Counter[str] = Counter()
        unmatched_counter: Counter[str] = Counter()

        async for message in client.iter_messages(entity, limit=args.limit or None):
            total_messages += 1
            text = (message.message or getattr(message, "raw_text", "") or "").strip()
            if not text:
                continue

            parsed = parse_message_text(text) or parse_secondary_channel_incursion_message(text)
            if parsed is None:
                continue

            parsed_messages += 1
            if not parsed.candidate_locations:
                continue

            for candidate in parsed.candidate_locations:
                candidate_counter[candidate] += 1

            result = match_locations(session, parsed.candidate_locations)
            for matched in result.matches:
                matched_counter[matched.location.name_ar] += 1
            for unmatched in result.unmatched:
                unmatched_counter[unmatched] += 1

            if total_messages % 1000 == 0:
                print(
                    f"processed={total_messages} parsed={parsed_messages} "
                    f"unique_candidates={len(candidate_counter)} unmatched={len(unmatched_counter)}",
                    flush=True,
                )

        payload = {
            "channel": channel_name,
            "total_messages": total_messages,
            "parsed_messages": parsed_messages,
            "unique_candidates": len(candidate_counter),
            "candidates": candidate_counter.most_common(),
            "matched_locations": matched_counter.most_common(),
            "unmatched_locations": unmatched_counter.most_common(),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"completed channel={channel_name} messages={total_messages} parsed={parsed_messages} "
            f"unique_candidates={len(candidate_counter)} unmatched={len(unmatched_counter)} output={output_path}",
            flush=True,
        )
    finally:
        session.close()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
