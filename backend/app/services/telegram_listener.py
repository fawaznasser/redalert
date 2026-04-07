from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.utils import get_peer_id
from sqlalchemy import cast, Integer, select

from app.config import settings
from app.db import SessionLocal
from app.models.raw_message import RawMessage
from app.services.event_service import ingest_message
from app.services.ocr_service import detect_attack_side_from_image_bytes, extract_ocr_text_from_bytes

logger = logging.getLogger(__name__)
_OCR_MEANINGFUL_CHAR_RE = re.compile(r"[0-9A-Za-z\u0600-\u06FF]")


@dataclass(slots=True)
class ChannelContext:
    entity: object
    channel_name: str


@dataclass(slots=True)
class OCRJob:
    channel_name: str
    telegram_message_id: int
    message_marker: str
    message_date: datetime | None
    message: object
    message_text: str
    raw_payload: dict
    media_kind: str
    job_key: str


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
        self._ocr_worker_tasks: list[asyncio.Task] = []
        self._ocr_queue: asyncio.Queue[OCRJob] | None = None
        self._last_seen_message_ids: dict[str, int] = {}
        self._last_processed_edit_markers: dict[str, dict[int, str]] = {}
        self._latest_observed_message_markers: dict[str, dict[int, str]] = {}
        self._pending_ocr_job_keys: set[str] = set()

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
        channel_lookup = self._build_channel_lookup(channel_contexts)
        self._start_ocr_workers(client)

        for context in channel_contexts:
            self._last_seen_message_ids[context.channel_name] = await asyncio.to_thread(
                self._load_last_seen_message_id,
                context.channel_name,
            )
            self._last_processed_edit_markers.setdefault(context.channel_name, {})
            self._latest_observed_message_markers.setdefault(context.channel_name, {})
            await self._sync_recent_messages(client, context)
            self._sync_tasks.append(asyncio.create_task(self._poll_recent_messages(client, context)))

        async def persist_event_message(message) -> None:  # type: ignore[no-untyped-def]
            channel_context = channel_lookup.get(getattr(message, "chat_id", None))
            if channel_context is None:
                return
            await self._persist_message_without_ocr(channel_context.channel_name, message)
            await self._enqueue_ocr_job(client, channel_context.channel_name, message)

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
            for task in self._ocr_worker_tasks:
                task.cancel()
            for task in self._ocr_worker_tasks:
                with suppress(asyncio.CancelledError):
                    await task
            self._ocr_worker_tasks.clear()
            self._ocr_queue = None
            self._pending_ocr_job_keys.clear()
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

    def _build_channel_lookup(self, channel_contexts: list[ChannelContext]) -> dict[int, ChannelContext]:
        lookup: dict[int, ChannelContext] = {}
        for context in channel_contexts:
            entity_id = getattr(context.entity, "id", None)
            if entity_id is not None:
                lookup[int(entity_id)] = context

            try:
                lookup[int(get_peer_id(context.entity))] = context
            except Exception:
                logger.debug("Unable to derive peer id for %s", context.channel_name, exc_info=True)

        return lookup

    async def _sync_recent_messages(self, client: TelegramClient, channel_context: ChannelContext) -> None:  # type: ignore[no-untyped-def]
        if settings.telegram_history_backfill_limit <= 0 and settings.telegram_edit_sync_limit <= 0:
            return

        recent_messages = [
            message async for message in client.iter_messages(channel_context.entity, limit=settings.telegram_history_backfill_limit)
        ]
        await self._ingest_messages(channel_context.channel_name, recent_messages)

    async def _poll_recent_messages(self, client: TelegramClient, channel_context: ChannelContext) -> None:  # type: ignore[no-untyped-def]
        while True:
            try:
                await asyncio.sleep(max(1, settings.telegram_poll_interval_seconds))
                await self._sync_new_messages(client, channel_context)
                await self._sync_recent_edits(client, channel_context)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to poll Telegram updates for %s; continuing", channel_context.channel_name)
                await asyncio.sleep(1)

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
        recent_edit_markers = self._last_processed_edit_markers.setdefault(channel_context.channel_name, {})
        edited_messages = []
        seen_recent_ids: set[int] = set()

        for message in recent_messages:
            message_id = getattr(message, "id", None)
            edit_date = getattr(message, "edit_date", None)
            if message_id is None:
                continue
            seen_recent_ids.add(int(message_id))
            if edit_date is None:
                continue
            marker = edit_date.isoformat()
            if recent_edit_markers.get(int(message_id)) == marker:
                continue
            edited_messages.append(message)

        # Keep only recent edited message markers so the cache stays bounded.
        stale_ids = [message_id for message_id in recent_edit_markers if message_id not in seen_recent_ids]
        for message_id in stale_ids:
            recent_edit_markers.pop(message_id, None)

        if edited_messages:
            await self._ingest_messages(channel_context.channel_name, edited_messages)

    async def _ingest_messages(self, channel_name: str, messages: list) -> None:  # type: ignore[no-untyped-def]
        for message in reversed(messages):
            await self._persist_message_without_ocr(channel_name, message)
            await self._enqueue_ocr_job(self.client, channel_name, message)

    def _message_text_is_meaningful(self, message_text: str) -> bool:
        return len(_OCR_MEANINGFUL_CHAR_RE.findall(message_text or "")) >= settings.ocr_min_trigger_chars

    def _message_supports_ocr(self, message) -> bool:  # type: ignore[no-untyped-def]
        if getattr(message, "photo", None) is not None:
            return True

        file_info = getattr(message, "file", None)
        mime_type = str(getattr(file_info, "mime_type", "") or "").lower()
        is_sticker = bool(getattr(message, "sticker", None))
        return is_sticker or mime_type.startswith("image/")

    def _message_marker(self, message) -> str:  # type: ignore[no-untyped-def]
        marker_source = getattr(message, "edit_date", None) or getattr(message, "date", None)
        if isinstance(marker_source, datetime):
            return marker_source.isoformat()
        return ""

    def _media_kind(self, message) -> str:
        return "sticker" if bool(getattr(message, "sticker", None)) else "image"

    def _current_message_text(self, message) -> str:  # type: ignore[no-untyped-def]
        return (message.message or getattr(message, "raw_text", "") or "").strip()

    def _start_ocr_workers(self, client: TelegramClient) -> None:
        worker_count = max(0, int(settings.ocr_worker_concurrency))
        if not settings.ocr_enabled or worker_count <= 0:
            self._ocr_queue = None
            self._ocr_worker_tasks.clear()
            return

        queue_size = max(1, int(settings.ocr_queue_max_size))
        self._ocr_queue = asyncio.Queue(maxsize=queue_size)
        self._ocr_worker_tasks = [
            asyncio.create_task(self._ocr_worker(client, worker_index))
            for worker_index in range(worker_count)
        ]

    async def _persist_message_without_ocr(self, channel_name: str, message) -> None:  # type: ignore[no-untyped-def]
        payload = json.loads(message.to_json())
        message_text = self._current_message_text(message)
        self._annotate_ocr_skip(payload, message)
        await asyncio.to_thread(
            self._persist_message,
            telegram_message_id=message.id,
            channel_name=channel_name,
            message_text=message_text,
            message_date=message.edit_date or message.date,
            raw_payload=payload,
        )
        self._record_seen_message_id(channel_name, message.id)
        self._record_edit_marker(channel_name, message)
        self._record_latest_marker(channel_name, message)

    def _annotate_ocr_skip(self, payload: dict, message) -> None:  # type: ignore[no-untyped-def]
        if not settings.ocr_enabled or not self._message_supports_ocr(message):
            return

        file_info = getattr(message, "file", None)
        file_size = int(getattr(file_info, "size", 0) or 0)
        if file_size and file_size > settings.ocr_max_media_size_bytes:
            payload["_ocr"] = {"skipped": True, "reason": "file_too_large", "size": file_size}

    async def _enqueue_ocr_job(self, client: TelegramClient | None, channel_name: str, message) -> None:  # type: ignore[no-untyped-def]
        if client is None or self._ocr_queue is None or not settings.ocr_enabled:
            return
        if not self._message_supports_ocr(message):
            return

        file_info = getattr(message, "file", None)
        file_size = int(getattr(file_info, "size", 0) or 0)
        if file_size and file_size > settings.ocr_max_media_size_bytes:
            return

        message_id = getattr(message, "id", None)
        if message_id is None:
            return

        message_marker = self._message_marker(message)
        job_key = f"{channel_name}:{int(message_id)}:{message_marker}"
        if job_key in self._pending_ocr_job_keys:
            return

        payload = json.loads(message.to_json())
        job = OCRJob(
            channel_name=channel_name,
            telegram_message_id=int(message_id),
            message_marker=message_marker,
            message_date=getattr(message, "edit_date", None) or getattr(message, "date", None),
            message=message,
            message_text=self._current_message_text(message),
            raw_payload=payload,
            media_kind=self._media_kind(message),
            job_key=job_key,
        )

        try:
            self._ocr_queue.put_nowait(job)
            self._pending_ocr_job_keys.add(job_key)
        except asyncio.QueueFull:
            logger.warning(
                "OCR queue full; skipping Telegram media OCR for %s message %s",
                channel_name,
                message_id,
            )

    async def _ocr_worker(self, client: TelegramClient, worker_index: int) -> None:
        assert self._ocr_queue is not None
        while True:
            job = await self._ocr_queue.get()
            try:
                await self._process_ocr_job(client, job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "OCR worker %s failed while processing Telegram message %s",
                    worker_index,
                    job.telegram_message_id,
                )
            finally:
                self._pending_ocr_job_keys.discard(job.job_key)
                self._ocr_queue.task_done()

    def _message_marker_is_current(self, channel_name: str, message_id: int, marker: str) -> bool:
        latest_marker = self._latest_observed_message_markers.get(channel_name, {}).get(int(message_id))
        if latest_marker is None:
            return True
        return latest_marker == marker

    async def _process_ocr_job(self, client: TelegramClient, job: OCRJob) -> None:
        if not self._message_marker_is_current(job.channel_name, job.telegram_message_id, job.message_marker):
            return

        message_text = await self._resolve_message_text_with_ocr(client, job.message, job.raw_payload, job.message_text)

        if not self._message_marker_is_current(job.channel_name, job.telegram_message_id, job.message_marker):
            return

        await asyncio.to_thread(
            self._persist_message,
            telegram_message_id=job.telegram_message_id,
            channel_name=job.channel_name,
            message_text=message_text,
            message_date=job.message_date,
            raw_payload=job.raw_payload,
        )

    async def _resolve_message_text_with_ocr(self, client: TelegramClient | None, message, payload: dict, message_text: str) -> str:  # type: ignore[no-untyped-def]
        message_text = (message.message or getattr(message, "raw_text", "") or "").strip()
        if client is None or not settings.ocr_enabled:
            return message_text
        if not self._message_supports_ocr(message):
            return message_text

        file_info = getattr(message, "file", None)
        file_size = int(getattr(file_info, "size", 0) or 0)
        if file_size and file_size > settings.ocr_max_media_size_bytes:
            payload["_ocr"] = {"skipped": True, "reason": "file_too_large", "size": file_size}
            return message_text

        try:
            media_bytes = await asyncio.wait_for(
                client.download_media(message, file=bytes),
                timeout=max(1.0, float(settings.ocr_download_timeout_seconds)),
            )
        except asyncio.TimeoutError:
            payload["_ocr"] = {"skipped": True, "reason": "download_timeout"}
            logger.warning("Telegram media OCR download timed out (message=%s)", getattr(message, "id", None))
            return message_text
        except Exception:
            logger.exception("Failed to download Telegram media for OCR (message=%s)", getattr(message, "id", None))
            return message_text

        if not media_bytes:
            return message_text

        media_kind = self._media_kind(message)
        if self._message_text_is_meaningful(message_text):
            label_color, attack_side = await asyncio.wait_for(
                asyncio.to_thread(detect_attack_side_from_image_bytes, media_bytes),
                timeout=max(1.0, float(settings.ocr_processing_timeout_seconds)),
            )
            if label_color or attack_side:
                ocr_payload = {
                    "engine": "color-detector",
                    "media_kind": media_kind,
                }
                if label_color:
                    ocr_payload["label_color"] = label_color
                if attack_side:
                    ocr_payload["attack_side"] = attack_side
                payload["_ocr"] = ocr_payload
            return message_text

        if media_kind == "sticker" and not settings.ocr_extract_text_from_stickers:
            label_color, attack_side = await asyncio.wait_for(
                asyncio.to_thread(detect_attack_side_from_image_bytes, media_bytes),
                timeout=max(1.0, float(settings.ocr_processing_timeout_seconds)),
            )
            if label_color or attack_side:
                ocr_payload = {
                    "engine": "color-detector",
                    "media_kind": media_kind,
                    "skipped_text": True,
                }
                if label_color:
                    ocr_payload["label_color"] = label_color
                if attack_side:
                    ocr_payload["attack_side"] = attack_side
                payload["_ocr"] = ocr_payload
            return message_text

        try:
            ocr_result = await asyncio.wait_for(
                asyncio.to_thread(extract_ocr_text_from_bytes, media_bytes),
                timeout=max(1.0, float(settings.ocr_processing_timeout_seconds)),
            )
        except asyncio.TimeoutError:
            payload["_ocr"] = {"skipped": True, "reason": "processing_timeout", "media_kind": media_kind}
            logger.warning("Telegram media OCR processing timed out (message=%s)", getattr(message, "id", None))
            return message_text
        if ocr_result is None:
            return message_text

        ocr_payload = {
            "engine": ocr_result.engine,
            "media_kind": media_kind,
        }
        if ocr_result.text and ocr_result.text.strip():
            ocr_payload["text"] = ocr_result.text.strip()
        if ocr_result.label_color:
            ocr_payload["label_color"] = ocr_result.label_color
        if ocr_result.attack_side:
            ocr_payload["attack_side"] = ocr_result.attack_side
        payload["_ocr"] = ocr_payload

        if not ocr_result.text or not ocr_result.text.strip():
            return message_text

        logger.info("OCR extracted text for Telegram message %s", getattr(message, "id", None))
        return ocr_result.text.strip()

    def _record_seen_message_id(self, channel_name: str, message_id: int | None) -> None:
        if message_id is None:
            return
        self._last_seen_message_ids[channel_name] = max(self._last_seen_message_ids.get(channel_name, 0), int(message_id))

    def _record_edit_marker(self, channel_name: str, message) -> None:  # type: ignore[no-untyped-def]
        message_id = getattr(message, "id", None)
        edit_date = getattr(message, "edit_date", None)
        if message_id is None or edit_date is None:
            return
        self._last_processed_edit_markers.setdefault(channel_name, {})[int(message_id)] = edit_date.isoformat()

    def _record_latest_marker(self, channel_name: str, message) -> None:  # type: ignore[no-untyped-def]
        message_id = getattr(message, "id", None)
        if message_id is None:
            return
        self._latest_observed_message_markers.setdefault(channel_name, {})[int(message_id)] = self._message_marker(message)

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

        for task in self._ocr_worker_tasks:
            task.cancel()
        for task in self._ocr_worker_tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._ocr_worker_tasks.clear()
        self._ocr_queue = None
        self._pending_ocr_job_keys.clear()

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
