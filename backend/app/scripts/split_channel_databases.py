from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


def _normalize_channel(value: str) -> str:
    text = (value or "").strip().lower()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.removeprefix("@").strip()


def _prune_database(target_path: Path, keep_channels: set[str]) -> tuple[int, int]:
    connection = sqlite3.connect(target_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        rows = connection.execute("SELECT id, channel_name FROM raw_messages").fetchall()
        drop_ids = [row[0] for row in rows if _normalize_channel(str(row[1] or "")) not in keep_channels]
        if drop_ids:
            placeholders = ",".join("?" for _ in drop_ids)
            connection.execute(
                f"DELETE FROM raw_messages WHERE id IN ({placeholders})",
                drop_ids,
            )
        connection.commit()
        connection.execute("VACUUM")
        raw_count = connection.execute("SELECT COUNT(*) FROM raw_messages").fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return raw_count, event_count
    finally:
        connection.close()


def split_databases(source: Path, redalerts_target: Path, firemonitor_target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Source database not found: {source}")

    redalerts_target.parent.mkdir(parents=True, exist_ok=True)
    firemonitor_target.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source, redalerts_target)
    shutil.copy2(source, firemonitor_target)

    redalerts_raw, redalerts_events = _prune_database(
        redalerts_target,
        keep_channels={_normalize_channel("redlinkleb")},
    )
    firemonitor_raw, firemonitor_events = _prune_database(
        firemonitor_target,
        keep_channels={
            _normalize_channel("RNN_Alerts_AR_Lebanon"),
            _normalize_channel("t.me/alichoeib1970"),
        },
    )

    print(
        f"Created {redalerts_target} with {redalerts_raw} raw messages and {redalerts_events} events",
    )
    print(
        f"Created {firemonitor_target} with {firemonitor_raw} raw messages and {firemonitor_events} events",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Split the mixed Red Alert database into channel-specific databases.")
    parser.add_argument("--source", default="data/red_alert.db")
    parser.add_argument("--redalerts-target", default="data/redalerts.db")
    parser.add_argument("--firemonitor-target", default="data/firemonitor.db")
    args = parser.parse_args()

    split_databases(
        source=Path(args.source).resolve(),
        redalerts_target=Path(args.redalerts_target).resolve(),
        firemonitor_target=Path(args.firemonitor_target).resolve(),
    )


if __name__ == "__main__":
    main()
