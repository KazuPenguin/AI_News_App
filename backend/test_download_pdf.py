import asyncio
from batch.post_l3_reviewer import download_pdf


async def test_pdf_download() -> None:
    # URL 1: A valid arXiv PDF URL (Attention Is All You Need)
    url1 = "https://arxiv.org/pdf/1706.03762"
    print(f"Testing valid PDF download: {url1}")
    result1 = await download_pdf(url1)
    if result1:
        print(f"Success! Downloaded {len(result1)} bytes.")
    else:
        print("Failed!")

    print("-" * 30)

    # URL 2: An invalid URL
    url2 = "https://arxiv.org/pdf/invalid_pdf_id_999999"
    print(f"Testing invalid PDF download: {url2}")
    result2 = await download_pdf(url2)
    if result2:
        print(f"Success?! Downloaded {len(result2)} bytes. (This shouldn't happen)")
    else:
        print("Failed as expected.")


if __name__ == "__main__":
    asyncio.run(test_pdf_download())
