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
from app.services.location_matcher import match_locations
from app.services.nominatim_client import search_nominatim, upsert_nominatim_location
from app.services.parser import parse_message_text


def collect_unmatched_candidates(hours: int, limit: int) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    session = SessionLocal()
    try:
        rows = session.scalars(
            select(RawMessage)
            .options(selectinload(RawMessage.events))
            .where(RawMessage.message_date >= cutoff)
            .order_by(RawMessage.message_date.desc())
        ).all()

        collected: list[str] = []
        seen: set[str] = set()
        for row in rows:
            parsed = parse_message_text(row.message_text)
            if parsed is None or not parsed.candidate_locations:
                continue

            matches = match_locations(session, parsed.candidate_locations)
            for candidate in matches.unmatched:
                if candidate in seen:
                    continue
                seen.add(candidate)
                collected.append(candidate)
                if len(collected) >= limit:
                    return collected
        return collected
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode unmatched Lebanon locations with Nominatim and upsert them into SQLite.")
    parser.add_argument("--hours", type=int, default=72, help="Look back this many hours in raw messages")
    parser.add_argument("--limit", type=int, default=25, help="Maximum unmatched names to geocode in one run")
    parser.add_argument("--name", action="append", default=[], help="Specific village name to geocode; may be provided multiple times")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        names = list(args.name)
        if not names:
            names = collect_unmatched_candidates(hours=args.hours, limit=args.limit)

        if not names:
            print("No unmatched names found to geocode.")
            return

        resolved = 0
        unresolved = 0
        for name in names:
            result = search_nominatim(name)
            if result is None:
                print(f"UNRESOLVED {name}")
                unresolved += 1
                continue

            location = upsert_nominatim_location(session, result)
            session.commit()
            print(
                f"RESOLVED {name} -> {location.name_ar} "
                f"({location.latitude:.5f}, {location.longitude:.5f}) "
                f"[{location.governorate or 'unknown'}]"
            )
            resolved += 1

        print(f"Done. Resolved {resolved}, unresolved {unresolved}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
