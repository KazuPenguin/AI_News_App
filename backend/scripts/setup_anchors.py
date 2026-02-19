"""アンカーデータをデータベースに初期投入するスクリプト。

PGVector を有効化したデータベースに対して、6カテゴリのアンカーベクトルを生成し、
`anchors` テーブルに挿入する。
"""

import os
from typing import TypedDict

import psycopg
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_research"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


class AnchorDef(TypedDict):
    id: int
    category_name: str
    definition_en: str
    definition_ja: str


ANCHORS: list[AnchorDef] = [
    {
        "id": 1,
        "category_name": "基盤モデル & アーキテクチャ",
        "definition_en": "State-of-the-art model architectures for large language models, including Transformer alternatives (Mamba, RWKV, SSM), Mixture of Experts (MoE), multimodal models, and reasoning-specialized models.",
        "definition_ja": "大規模言語モデルの最新アーキテクチャ、Transformer代替モデル(Mamba, RWKV)、MoE、マルチモーダル、推論特化型モデルなど。",
    },
    {
        "id": 2,
        "category_name": "学習 & チューニング",
        "definition_en": "Training and fine-tuning methods to improve model capability and adaptability: post-training (RLHF, DPO), Chain of Thought reasoning, and efficient adaptation (LoRA, QLoRA, Model Merging).",
        "definition_ja": "モデル能力向上のための学習手法：RLHF, DPO, CoT, LoRA, QLoRA, モデルマージなど。",
    },
    {
        "id": 3,
        "category_name": "アプリケーションエンジニアリング",
        "definition_en": "Applied LLM engineering: Retrieval-Augmented Generation (RAG, GraphRAG, Hybrid Search), autonomous agents, multi-agent systems, and prompt optimization (DSPy).",
        "definition_ja": "LLM応用エンジニアリング：RAG, GraphRAG, AIエージェント, マルチエージェント, プロンプト最適化(DSPy)。",
    },
    {
        "id": 4,
        "category_name": "インフラ & 推論最適化",
        "definition_en": "Infrastructure and inference optimization for large language models: high-throughput serving (vLLM, TGI), memory management (PagedAttention, KV Cache), quantization, edge AI deployment, and distributed training systems.",
        "definition_ja": "LLMインフラと推論最適化：vLLM, TGI, PagedAttention, 量子化, エッジAI, 分散学習。",
    },
    {
        "id": 5,
        "category_name": "評価 & 安全性",
        "definition_en": "Evaluation and safety of language models: benchmarks, leaderboards, jailbreak attacks and defenses, hallucination detection, bias assessment, and safety alignment.",
        "definition_ja": "LLMの評価と安全性：ベンチマーク, ジェイルブレイク攻撃, ハルシネーション検出, バイアス評価, アライメント。",
    },
    {
        "id": 6,
        "category_name": "規制 & ビジネス",
        "definition_en": "AI regulation, policy, and business impact: EU AI Act, copyright issues, training data rights, watermarking techniques, and societal implications of AI.",
        "definition_ja": "AI規制とビジネス：AI法規制, 著作権, 学習データ権利, ウォーターマーク, 社会的影響。",
    },
]


def main() -> None:
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        return

    print(f"Connecting to database: {DATABASE_URL}...")

    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Check connection
                cur.execute("SELECT 1")
                print("Database connected successfully.")

                for anchor in ANCHORS:
                    print(f"Processing Anchor {anchor['id']}: {anchor['category_name']}...")

                    # Generate embedding
                    response = client.embeddings.create(
                        input=anchor["definition_en"], model="text-embedding-3-small"
                    )
                    embedding = response.data[0].embedding

                    # Upsert anchor
                    cur.execute(
                        """
                        INSERT INTO anchors (id, category_id, category_name, definition_en, definition_ja, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category_id) DO UPDATE SET
                            category_name = EXCLUDED.category_name,
                            definition_en = EXCLUDED.definition_en,
                            definition_ja = EXCLUDED.definition_ja,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW();
                        """,
                        (
                            anchor["id"],
                            anchor["id"],  # category_id = id
                            anchor["category_name"],
                            anchor["definition_en"],
                            anchor["definition_ja"],
                            str(
                                embedding
                            ),  # pgvector requires explicit casting or string format with psycopg v3 if not registered adapter
                        ),
                    )
            conn.commit()
            print("All anchors inserted/updated successfully.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
