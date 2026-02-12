# L2 設計書：pgvector ベクトル選別

## 1. 概要
L1（arXiv API）で取得した論文の Title + Abstract をベクトル化し、事前定義した6本の**アンカーベクトル**とのコサイン類似度で選別する。
キーワードは一致しても文脈が異なるノイズ（言語学、電力系Transformer等）をここで除外する。

---

## 2. Embedding モデル

| 項目 | 値 |
|:---|:---|
| **モデル** | OpenAI `text-embedding-3-small` |
| **次元数** | 1,536 |
| **コスト** | $0.02 / 1Mトークン |
| **入力** | `Title + " " + Abstract`（英語のまま） |

### コスト見積もり
- 1論文あたり平均 ~300トークン（Title + Abstract）
- 日次 200件 × 300トークン = 60,000トークン/日
- **月額: ~$0.04**（ほぼ無視できるコスト）

---

## 3. アンカーベクトル定義

以下の6つの定義文を**英語で**ベクトル化し、アンカーとして保持する。

> **なぜ英語か:** 論文のAbstractは英語。同一言語でEmbeddingした方がコサイン類似度の精度が高い。

| ID | カテゴリ名 | アンカー定義文（英語） |
| :--- | :--- | :--- |
| **1** | **基盤モデル & アーキテクチャ** | State-of-the-art model architectures for large language models, including Transformer alternatives (Mamba, RWKV, SSM), Mixture of Experts (MoE), multimodal models, and reasoning-specialized models. |
| **2** | **学習 & チューニング** | Training and fine-tuning methods to improve model capability and adaptability: post-training (RLHF, DPO), Chain of Thought reasoning, and efficient adaptation (LoRA, QLoRA, Model Merging). |
| **3** | **アプリケーションエンジニアリング** | Applied LLM engineering: Retrieval-Augmented Generation (RAG, GraphRAG, Hybrid Search), autonomous agents, multi-agent systems, and prompt optimization (DSPy). |
| **4** | **インフラ & 推論最適化** | Infrastructure and inference optimization for large language models: high-throughput serving (vLLM, TGI), memory management (PagedAttention, KV Cache), quantization, edge AI deployment, and distributed training systems. |
| **5** | **評価 & 安全性** | Evaluation and safety of language models: benchmarks, leaderboards, jailbreak attacks and defenses, hallucination detection, bias assessment, and safety alignment. |
| **6** | **規制 & ビジネス** | AI regulation, policy, and business impact: EU AI Act, copyright issues, training data rights, watermarking techniques, and societal implications of AI. |

---

## 4. 類似度判定

### 4.1 距離関数
**コサイン類似度**（pgvector の `<=>` 演算子、cosine distance）

### 4.2 閾値設計

| パラメータ | 値 | 根拠 |
|:---|:---|:---|
| **通過閾値** | **0.40** | `text-embedding-3-small` で意味的に関連する文書間のスコアは 0.3〜0.6 が一般的。0.40 はRecall寄りの設定 |

> **チューニング方針:** 運用開始後1週間のデータで L2通過率を測定。
> - 通過率 > 50% → 閾値を 0.45 に引き上げ
> - 通過率 < 20% → 閾値を 0.35 に引き下げ
> - 目標通過率: **30〜50%**（L3に渡す件数: 50〜100件/日）

### 4.3 スコアリングロジック
各論文に対して6本のアンカーとの類似度を全て計算し、以下の指標を出力する。

```python
scores = [cosine_sim(paper_vec, anchor_vec) for anchor_vec in anchors]

result = {
    "max_score": max(scores),                          # 最高類似度
    "best_category_id": argmax(scores) + 1,            # 最も近いカテゴリ
    "hit_count": sum(1 for s in scores if s >= 0.40),  # 閾値超えアンカー数
    "all_scores": dict(zip(category_ids, scores)),     # 全スコア（デバッグ用）
    "passed": max(scores) >= 0.40                      # L2通過判定
}
```

### 4.4 重要度スコアの算出
L2では「関連度」だけでなく「重要度」も推定し、L3へ渡す。

```python
importance_score = (
    0.6 * max_score                      # 専門性の深さ（最高類似度）
  + 0.3 * (hit_count / 6)               # 分野横断性（複数カテゴリにヒット = 注目度高）
  + 0.1 * (matched_queries_count / 6)   # L1での複数クエリヒット数
)
```

| スコア帯 | 解釈 | 期待される例 |
|:---|:---|:---|
| 0.7〜1.0 | **最重要** — 深い専門性 + 分野横断的 | vLLMの新アーキテクチャ論文 |
| 0.5〜0.7 | **重要** — 特定領域で高い関連性 | LoRAの新手法 |
| 0.4〜0.5 | **参考** — 閾値付近、L3で最終判定 | 間接的にLLMに言及する論文 |

---

## 5. pgvector インデックス設計

### 5.1 インデックス方式: **HNSW**

| 項目 | 設定値 | 根拠 |
|:---|:---|:---|
| **方式** | HNSW | データ量 < 100万件で精度重視。IVFFlatは不要 |
| **`m`** | 16 | 近傍グラフの接続数。デフォルト推奨値 |
| **`ef_construction`** | 64 | 構築時の探索幅。精度と構築速度のバランス |

### 5.2 テーブル設計

```sql
-- 論文テーブル
CREATE TABLE papers (
    id              SERIAL PRIMARY KEY,
    arxiv_id        VARCHAR(20) UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    abstract        TEXT NOT NULL,
    authors         TEXT[] NOT NULL,
    pdf_url         TEXT,
    published_at    TIMESTAMPTZ NOT NULL,
    embedding       vector(1536),

    -- L2 結果
    best_category_id INTEGER,
    max_score        FLOAT,
    hit_count        INTEGER,
    importance_score FLOAT,
    all_scores       JSONB,

    -- L3 結果（後段で更新）
    is_relevant      BOOLEAN,
    category_id      INTEGER,
    summary_ja       TEXT,
    detail_review    JSONB,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ベクトルインデックス
CREATE INDEX idx_papers_embedding ON papers
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- アンカーテーブル
CREATE TABLE anchors (
    id              SERIAL PRIMARY KEY,
    category_id     INTEGER UNIQUE NOT NULL,
    category_name   VARCHAR(100) NOT NULL,
    definition_text TEXT NOT NULL,
    embedding       vector(1536) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.3 クエリ例（L2選別）

```sql
-- 全アンカーとの類似度を計算（6本のアンカーに対して全スキャン）
SELECT
    p.arxiv_id,
    p.title,
    a.category_id,
    a.category_name,
    1 - (p.embedding <=> a.embedding) AS cosine_similarity
FROM papers p
CROSS JOIN anchors a
WHERE p.max_score IS NULL  -- まだL2未処理の論文
ORDER BY p.arxiv_id, cosine_similarity DESC;
```

---

## 6. ログ出力仕様

```json
{
  "phase": "L2",
  "execution_date": "2026-02-12",
  "input_count": 198,
  "passed_count": 72,
  "rejected_count": 126,
  "pass_rate": "36.4%",
  "score_distribution": {
    "0.6+": 8,
    "0.5-0.6": 22,
    "0.4-0.5": 42,
    "below_0.4": 126
  },
  "category_hits": {
    "1_基盤モデル": 28,
    "2_学習": 15,
    "3_エンジニアリング": 18,
    "4_インフラ": 12,
    "5_評価": 9,
    "6_規制": 4
  }
}
```