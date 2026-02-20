import asyncio
from dotenv import load_dotenv
from batch.pipeline import run_pipeline


async def test() -> None:
    load_dotenv()
    await run_pipeline()


if __name__ == "__main__":
    asyncio.run(test())
