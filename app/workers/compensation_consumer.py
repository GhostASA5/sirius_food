import asyncio
import logging

from app.workers.consumer import run_consumer


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_consumer("compensation"))
