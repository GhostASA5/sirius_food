import asyncio

from app.core.rabbitmq import declare_topology, open_channel


async def main():
    connection, channel = await open_channel()
    try:
        await declare_topology(channel)
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
