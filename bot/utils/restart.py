import asyncio
import logging
import sys

async def graceful_crash():
    logging.error("Bot crashed. Restarting in 10 seconds...")

    for i in range(10, 0, -1):
        logging.error(f"Restarting in {i}...")
        await asyncio.sleep(1)

    sys.exit(1)
