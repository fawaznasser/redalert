from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from sqlalchemy import cast, Integer, select

from app.config import settings
from app.db import SessionLocal
from app.models.raw_message import RawMessage
from app.services.event_service import ingest_message

logger = logging.getLogger(__name__)


def _build_session(session_value: str):
    if session_value.startswith("string:"):
        return StringSession(session_value.removeprefix("string:"))
    if len(session_value) > 80 and "/" not in session_value and "\\" not in session_value:
        return StringSession(session_value)
    return session_value


class TelegramListener:
    def __init__(self) -> None:
        self.client: TelegramClient | None = None
        self._runner_task: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None
        self._last_seen_message_id: int = 0

    async def start(self) -> None:
        if not settings.telegram_is_configured:
            logger.info("Telegram listener is disabled or missing configuration")
            return

        if self._runner_task is not None and not self._runner_task.done():
            return

        self._runner_task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram listener failed; retrying in 5 seconds")
                await asyncio.sleep(5)

    async def _connect_and_listen(self) -> None:
        assert settings.telegram_session is not None
        assert settings.telegram_api_id is not None
        assert settings.telegram_api_hash is not None
        assert settings.telegram_channel is not None

        session = _build_session(settings.telegram_session)
        client = TelegramClient(session, settings.telegram_api_id, settings.telegram_api_hash)
        self.client = client
        await client.start()
        channel = await client.get_entity(settings.telegram_channel)
        channel_name = getattr(channel, "title", None) or settings.telegram_channel or "telegram"
        self._last_seen_message_id = await asyncio.to_thread(self._load_last_seen_message_id, channel_name)

        await self._sync_recent_messages(client, channel, channel_name)
        self._sync_task = asyncio.create_task(self._poll_recent_messages(client, channel, channel_name))

        async def persist_event_message(message) -> None:  # type: ignore[no-untyped-def]
            payload = json.loads(message.to_json())
            await asyncio.to_thread(
                self._persist_message,
                telegram_message_id=message.id,
                channel_name=channel_name,
                message_text=message.message or getattr(message, "raw_text", "") or "",
                message_date=message.edit_date or message.date,
                raw_payload=payload,
            )
            self._record_seen_message_id(message.id)

        @client.on(events.NewMessage(chats=channel))
        async def handle_new_message(event) -> None:  # type: ignore[no-untyped-def]
            await persist_event_message(event.message)

        @client.on(events.MessageEdited(chats=channel))
        async def handle_message_edit(event) -> None:  # type: ignore[no-untyped-def]
            await persist_event_message(event.message)

        logger.info("Telegram listener started for channel %s", settings.telegram_channel)
        try:
            await client.run_until_disconnected()
        finally:
            if self._sync_task is not None:
                self._sync_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._sync_task
                self._sync_task = None
            await client.disconnect()
            if self.client is client:
                self.client = None

    async def _sync_recent_messages(self, client: TelegramClient, channel, channel_name: str) -> None:  # type: ignore[no-untyped-def]
        if settings.telegram_history_backfill_limit <= 0 and settings.telegram_edit_sync_limit <= 0:
            return

        recent_messages = [message async for message in client.iter_messages(channel, limit=settings.telegram_history_backfill_limit)]
        await self._ingest_messages(channel_name, recent_messages)

    async def _poll_recent_messages(self, client: TelegramClient, channel, channel_name: str) -> None:  # type: ignore[no-untyped-def]
        while True:
            await asyncio.sleep(max(1, settings.telegram_poll_interval_seconds))
            await self._sync_new_messages(client, channel, channel_name)
            await self._sync_recent_edits(client, channel, channel_name)

    async def _sync_new_messages(self, client: TelegramClient, channel, channel_name: str) -> None:  # type: ignore[no-untyped-def]
        if self._last_seen_message_id <= 0:
            return

        new_messages = [
            message
            async for message in client.iter_messages(
                channel,
                min_id=self._last_seen_message_id,
                limit=settings.telegram_history_backfill_limit,
            )
        ]
        await self._ingest_messages(channel_name, new_messages)

    async def _sync_recent_edits(self, client: TelegramClient, channel, channel_name: str) -> None:  # type: ignore[no-untyped-def]
        if settings.telegram_edit_sync_limit <= 0:
            return

        recent_messages = [message async for message in client.iter_messages(channel, limit=settings.telegram_edit_sync_limit)]
        await self._ingest_messages(channel_name, recent_messages)

    async def _ingest_messages(self, channel_name: str, messages: list) -> None:  # type: ignore[no-untyped-def]
        for message in reversed(messages):
            payload = json.loads(message.to_json())
            await asyncio.to_thread(
                self._persist_message,
                telegram_message_id=message.id,
                channel_name=channel_name,
                message_text=message.message or getattr(message, "raw_text", "") or "",
                message_date=message.edit_date or message.date,
                raw_payload=payload,
            )
            self._record_seen_message_id(message.id)

    def _record_seen_message_id(self, message_id: int | None) -> None:
        if message_id is None:
            return
        self._last_seen_message_id = max(self._last_seen_message_id, int(message_id))

    def _load_last_seen_message_id(self, channel_name: str) -> int:
        session = SessionLocal()
        try:
            last_seen = session.scalar(
                select(cast(RawMessage.telegram_message_id, Integer))
                .where(
                    RawMessage.channel_name == channel_name,
                    RawMessage.telegram_message_id.is_not(None),
                )
                .order_by(cast(RawMessage.telegram_message_id, Integer).desc())
                .limit(1)
            )
            return int(last_seen or 0)
        finally:
            session.close()

    def _persist_message(
        self,
        *,
        telegram_message_id: int | None,
        channel_name: str,
        message_text: str,
        message_date,
        raw_payload: dict,
    ) -> None:
        session = SessionLocal()
        try:
            ingest_message(
                session,
                telegram_message_id=telegram_message_id,
                channel_name=channel_name,
                message_text=message_text,
                message_date=message_date,
                raw_payload=raw_payload,
            )
        except Exception:
            session.rollback()
            logger.exception("Failed to ingest Telegram message %s", telegram_message_id)
        finally:
            session.close()

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.disconnect()

        if self._runner_task is None:
            return

        self._runner_task.cancel()
        try:
            await self._runner_task
        except asyncio.CancelledError:
            pass
        logger.info("Telegram listener stopped")
