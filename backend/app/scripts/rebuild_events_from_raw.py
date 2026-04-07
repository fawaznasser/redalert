from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.models.raw_message import RawMessage
from app.services.event_service import (
    _apply_media_hints,
    _parse_message_for_channel,
    build_events_for_raw_message,
)
from app.services.location_matcher import match_locations


def parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Red Alert events from stored raw Telegram messages.")
    parser.add_argument("--since", required=True, help="Inclusive start date in YYYY-MM-DD format")
    parser.add_argument("--until", required=True, help="Inclusive end date in YYYY-MM-DD format")
    parser.add_argument("--channel", action="append", default=[], help="Optional channel filter; may be provided multiple times")
    parser.add_argument("--batch-size", type=int, default=100, help="How many raw messages to rebuild per transaction")
    args = parser.parse_args()

    since = parse_day(args.since)
    until = parse_day(args.until) + timedelta(days=1) - timedelta(microseconds=1)
    channel_filters = {value.strip() for value in args.channel if value.strip()}

    session = SessionLocal()
    try:
        stmt = (
            select(RawMessage.id)
            .where(RawMessage.message_date >= since, RawMessage.message_date <= until)
            .order_by(RawMessage.message_date.asc(), RawMessage.id.asc())
        )
        if channel_filters:
            stmt = stmt.where(RawMessage.channel_name.in_(sorted(channel_filters)))

        raw_ids = list(session.scalars(stmt))
    finally:
        session.close()

    total = len(raw_ids)
    rebuilt_events = 0
    empty_messages = 0

    print(
        f"Rebuilding events from {total} raw messages"
        f" between {args.since} and {args.until}"
        + (f" for channels {sorted(channel_filters)}" if channel_filters else ""),
        flush=True,
    )

    for start in range(0, total, max(1, args.batch_size)):
        batch_ids = raw_ids[start : start + max(1, args.batch_size)]
        session = SessionLocal()
        try:
            raws = list(
                session.scalars(
                    select(RawMessage)
                    .options(selectinload(RawMessage.events))
                    .where(RawMessage.id.in_(batch_ids))
                    .order_by(RawMessage.message_date.asc(), RawMessage.id.asc())
                )
            )

            batch_rebuilt = 0
            batch_empty = 0
            for raw in raws:
                for event in list(raw.events):
                    session.delete(event)
                session.flush()

                source_text = raw.message_text or ""
                parsed = _apply_media_hints(
                    raw.channel_name,
                    source_text,
                    _parse_message_for_channel(raw.channel_name, source_text),
                    raw.raw_json,
                )

                if parsed is None or parsed.event_type is None:
                    batch_empty += 1
                    continue

                location_matches = match_locations(session, parsed.candidate_locations)
                created_events = build_events_for_raw_message(
                    session,
                    raw_message=raw,
                    parsed_message=parsed,
                    location_matches=location_matches,
                )
                batch_rebuilt += len(created_events)

            session.commit()
            rebuilt_events += batch_rebuilt
            empty_messages += batch_empty
            print(
                f"processed={min(start + len(batch_ids), total)}/{total} "
                f"rebuilt_events={rebuilt_events} empty_messages={empty_messages}",
                flush=True,
            )
        finally:
            session.close()

    print(
        f"Finished rebuilding {rebuilt_events} events from {total} raw messages; "
        f"{empty_messages} messages currently produce no events.",
        flush=True,
    )


if __name__ == "__main__":
    main()
