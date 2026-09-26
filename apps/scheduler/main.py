import asyncio


async def main() -> None:
    while True:
        print("scheduler heartbeat (skeleton)")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
