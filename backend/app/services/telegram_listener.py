from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from sqlalchemy import cast, Integer, select

from app.config import settings
from app.db import SessionLocal
from app.models.raw_message import RawMessage
from app.services.event_service import ingest_message

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChannelContext:
    entity: object
    channel_name: str


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
        self._sync_tasks: list[asyncio.Task] = []
        self._last_seen_message_ids: dict[str, int] = {}

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
        assert settings.telegram_channels

        session = _build_session(settings.telegram_session)
        client = TelegramClient(session, settings.telegram_api_id, settings.telegram_api_hash)
        self.client = client
        await client.start()
        channel_contexts = await self._resolve_channels(client)
        channel_lookup = {getattr(context.entity, "id", None): context for context in channel_contexts}

        for context in channel_contexts:
            self._last_seen_message_ids[context.channel_name] = await asyncio.to_thread(
                self._load_last_seen_message_id,
                context.channel_name,
            )
            await self._sync_recent_messages(client, context)
            self._sync_tasks.append(asyncio.create_task(self._poll_recent_messages(client, context)))

        async def persist_event_message(message) -> None:  # type: ignore[no-untyped-def]
            channel_context = channel_lookup.get(getattr(message, "chat_id", None))
            if channel_context is None:
                return
            payload = json.loads(message.to_json())
            await asyncio.to_thread(
                self._persist_message,
                telegram_message_id=message.id,
                channel_name=channel_context.channel_name,
                message_text=message.message or getattr(message, "raw_text", "") or "",
                message_date=message.edit_date or message.date,
                raw_payload=payload,
            )
            self._record_seen_message_id(channel_context.channel_name, message.id)

        @client.on(events.NewMessage(chats=[context.entity for context in channel_contexts]))
        async def handle_new_message(event) -> None:  # type: ignore[no-untyped-def]
            await persist_event_message(event.message)

        @client.on(events.MessageEdited(chats=[context.entity for context in channel_contexts]))
        async def handle_message_edit(event) -> None:  # type: ignore[no-untyped-def]
            await persist_event_message(event.message)

        logger.info("Telegram listener started for channels %s", ", ".join(context.channel_name for context in channel_contexts))
        try:
            await client.run_until_disconnected()
        finally:
            for task in self._sync_tasks:
                task.cancel()
            for task in self._sync_tasks:
                with suppress(asyncio.CancelledError):
                    await task
            self._sync_tasks.clear()
            await client.disconnect()
            if self.client is client:
                self.client = None

    async def _resolve_channels(self, client: TelegramClient) -> list[ChannelContext]:
        contexts: list[ChannelContext] = []
        for configured_channel in settings.telegram_channels:
            entity = await client.get_entity(configured_channel)
            contexts.append(
                ChannelContext(
                    entity=entity,
                    channel_name=self._normalize_channel_name(configured_channel),
                )
            )
        return contexts

    def _normalize_channel_name(self, value: str) -> str:
        channel = value.strip()
        for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
            if channel.startswith(prefix):
                channel = channel[len(prefix):]
                break
        return channel.removeprefix("@")

    async def _sync_recent_messages(self, client: TelegramClient, channel_context: ChannelContext) -> None:  # type: ignore[no-untyped-def]
        if settings.telegram_history_backfill_limit <= 0 and settings.telegram_edit_sync_limit <= 0:
            return

        recent_messages = [
            message async for message in client.iter_messages(channel_context.entity, limit=settings.telegram_history_backfill_limit)
        ]
        await self._ingest_messages(channel_context.channel_name, recent_messages)

    async def _poll_recent_messages(self, client: TelegramClient, channel_context: ChannelContext) -> None:  # type: ignore[no-untyped-def]
        while True:
            await asyncio.sleep(max(1, settings.telegram_poll_interval_seconds))
            await self._sync_new_messages(client, channel_context)
            await self._sync_recent_edits(client, channel_context)

    async def _sync_new_messages(self, client: TelegramClient, channel_context: ChannelContext) -> None:  # type: ignore[no-untyped-def]
        last_seen_message_id = self._last_seen_message_ids.get(channel_context.channel_name, 0)
        if last_seen_message_id <= 0:
            return

        new_messages = [
            message
            async for message in client.iter_messages(
                channel_context.entity,
                min_id=last_seen_message_id,
                limit=settings.telegram_history_backfill_limit,
            )
        ]
        await self._ingest_messages(channel_context.channel_name, new_messages)

    async def _sync_recent_edits(self, client: TelegramClient, channel_context: ChannelContext) -> None:  # type: ignore[no-untyped-def]
        if settings.telegram_edit_sync_limit <= 0:
            return

        recent_messages = [
            message async for message in client.iter_messages(channel_context.entity, limit=settings.telegram_edit_sync_limit)
        ]
        await self._ingest_messages(channel_context.channel_name, recent_messages)

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
            self._record_seen_message_id(channel_name, message.id)

    def _record_seen_message_id(self, channel_name: str, message_id: int | None) -> None:
        if message_id is None:
            return
        self._last_seen_message_ids[channel_name] = max(self._last_seen_message_ids.get(channel_name, 0), int(message_id))

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
        for task in self._sync_tasks:
            task.cancel()
        for task in self._sync_tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._sync_tasks.clear()

        if self.client is not None:
            with suppress(Exception):
                await self.client.disconnect()
            self.client = None

        if self._runner_task is not None:
            self._runner_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._runner_task
            self._runner_task = None
        logger.info("Telegram listener stopped")
