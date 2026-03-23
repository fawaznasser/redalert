from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from app.config import settings


async def main() -> None:
    api_id = settings.telegram_api_id
    api_hash = settings.telegram_api_hash

    if api_id is None:
        api_id = int(input("TELEGRAM_API_ID: ").strip())
    if not api_hash:
        api_hash = input("TELEGRAM_API_HASH: ").strip()

    phone = input("Phone number (international format): ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        sent_code = await client.send_code_request(phone)
        code = input("Telegram code: ").strip()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=sent_code.phone_code_hash)
        except SessionPasswordNeededError:
            password = input("Telegram password: ").strip()
            await client.sign_in(password=password)

        print("\nTELEGRAM_SESSION=")
        print(client.session.save())
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
