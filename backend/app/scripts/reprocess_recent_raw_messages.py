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
from app.services.event_service import build_events_for_raw_message
from app.services.location_matcher import match_locations
from app.services.parser import parse_message_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Reprocess recent raw Telegram messages into events")
    parser.add_argument("--hours", type=int, default=24, help="How far back to reprocess raw messages")
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Also reprocess raw messages that already have events",
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    session = SessionLocal()

    try:
        rows = session.scalars(
            select(RawMessage)
            .options(selectinload(RawMessage.events))
            .where(RawMessage.message_date >= cutoff)
            .order_by(RawMessage.message_date.asc(), RawMessage.ingested_at.asc())
        ).all()

        scanned = 0
        changed_messages = 0
        created_events = 0
        updated_events = 0

        for row in rows:
            scanned += 1
            if row.events and not args.include_existing:
                continue

            if row.events and args.include_existing:
                for existing_event in list(row.events):
                    session.delete(existing_event)
                session.flush()

            parsed = parse_message_text(row.message_text)
            if parsed is None or parsed.event_type is None:
                continue

            matches = match_locations(session, parsed.candidate_locations)
            events = build_events_for_raw_message(
                session,
                raw_message=row,
                parsed_message=parsed,
                location_matches=matches,
            )
            if not events:
                continue

            new_count = sum(1 for event in events if event.id is None)
            created_events += new_count
            updated_events += len(events) - new_count
            changed_messages += 1
            session.flush()

        session.commit()
        print(
            f"Scanned {scanned} raw messages, changed {changed_messages}, "
            f"created {created_events} events, updated {updated_events} events."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
