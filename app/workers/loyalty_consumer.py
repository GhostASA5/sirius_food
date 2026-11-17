import asyncio
import logging

from app.workers.consumer import run_consumer


async def main():
    await asyncio.gather(
        run_consumer("loyalty_earn"),
        run_consumer("loyalty_cancel"),
        run_consumer("promo_restore"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
