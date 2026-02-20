import asyncio
from batch.post_l3_reviewer import download_pdf, extract_and_upload_figures

async def test():
    # A known arXiv PDF URL
    url = "https://arxiv.org/pdf/2402.12345.pdf"
    print(f"Downloading {url}...")
    pdf_bytes = await download_pdf(url)
    if not pdf_bytes:
        print("Failed to download PDF.")
        return
        
    print(f"Downloaded {len(pdf_bytes)} bytes. Extracting figures...")
    figs = await extract_and_upload_figures("2402.12345", pdf_bytes)
    print(f"Extracted {len(figs)} figures.")

if __name__ == "__main__":
    asyncio.run(test())
