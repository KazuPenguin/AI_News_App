import asyncio
from dotenv import load_dotenv
from batch.post_l3_reviewer import _generate_detail_review, extract_and_upload_figures
from google import genai
from utils.models import L2Paper
from utils.secrets import get_gemini_api_key
from datetime import datetime


async def test() -> None:
    load_dotenv()
    paper = L2Paper(
        arxiv_id="1234.5678",
        title="Test Paper about LLMs",
        abstract="We introduce a new Transformer architecture that improves KV cache.",
        authors=["Alice", "Bob"],
        primary_category="cs.CL",
        published_at=datetime.now(),
        best_category_id=4,
        max_score=0.85,
        hit_count=3,
    )
    client = genai.Client(api_key=get_gemini_api_key())

    # create a dummy pdf
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 24 Tf\n100 100 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000224 00000 n \n0000000312 00000 n \ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n405\n%%EOF"

    print("Testing detail review...")
    res = await _generate_detail_review(client, paper, pdf_bytes, "テスト要約")
    if res:
        print("Success generation!")
    else:
        print("Failed generation.")

    print("Testing figure extraction...")
    figs = await extract_and_upload_figures(paper.arxiv_id, pdf_bytes)
    print(f"Extracted {len(figs)} figures")


if __name__ == "__main__":
    asyncio.run(test())
