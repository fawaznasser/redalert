from __future__ import annotations

import asyncio
import logging

from app.services.telegram_listener import TelegramListener


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


async def main() -> None:
    listener = TelegramListener()

    await listener.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
