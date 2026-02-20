# L3 設計書：LLM 最終判定 & 構造化データ生成

## 1. 概要
L2（ベクトル選別）を通過した論文に対してのみLLMを呼び出し、以下を行う。

1. **適合判定:** 本当に6大カテゴリに合致するか最終チェック
2. **カテゴリ分類:** 正確なカテゴリIDの付与
3. **日本語要約:** エンジニア向けの技術的1行要約
4. **重要度判定:** 5段階の重要度ランク

L2を通さない論文にはLLMを使わない → **トークンコスト最小化（KGI）**の中核。

---

## 2. モデル選定

| 候補 | 入力コスト | 出力コスト | 速度 | 判定 |
|:---|:---|:---|:---|:---|
| **Gemini 2.0 Flash** | $0.10 / 1Mトークン | $0.40 / 1Mトークン | 非常に速い | **✅ 採用** |
| gpt-4o-mini | $0.15 / 1Mトークン | $0.60 / 1Mトークン | 速い | △ コスト微増 |
| Claude 3.5 Haiku | $0.80 / 1Mトークン | $4.00 / 1Mトークン | 速い | ✗ 高コスト |

**選定理由:** Gemini 2.0 Flash は最安クラスかつ JSON Mode（構造化出力）に対応。日次バッチ用途に最適。

---

## 3. 入力設計

### 3.1 L2からの引き継ぎデータ

```python
l2_output = {
    "arxiv_id": "2402.12345",
    "title": "Efficient KV Cache Compression for Long-Context LLM Serving",
    "abstract": "We propose a novel method for compressing KV cache...",
    "authors": ["Alice Smith", "Bob Chen"],
    "pdf_url": "https://arxiv.org/pdf/2402.12345",
    "published_at": "2026-02-11",

    # L2 結果
    "best_category_id": 4,        # インフラ & 推論最適化
    "max_score": 0.62,
    "hit_count": 2,               # カテゴリ4と1でヒット
    "importance_score": 0.57,
    "all_scores": {
        "1": 0.41, "2": 0.28, "3": 0.33,
        "4": 0.62, "5": 0.19, "6": 0.12
    }
}
```

### 3.2 LLMへの入力トークン見積もり

| 要素 | トークン数 |
|:---|:---|
| システムプロンプト | ~500 |
| Title + Abstract | ~300 |
| L2コンテキスト（スコア等） | ~100 |
| **合計（入力）** | **~900** |
| **出力（JSON）** | **~300** |

---

## 4. プロンプト設計

### 4.1 システムプロンプト

```
You are an expert AI/ML research curator specializing in systems engineering and infrastructure. Your task is to evaluate whether an academic paper is relevant to practitioners working on LLM systems, and if so, classify and summarize it.

## Categories
1. Foundation Models & Architecture — Model architectures (Transformer, Mamba, MoE, multimodal)
2. Training & Tuning — RLHF, DPO, LoRA, efficient training methods
3. Application Engineering — RAG, agents, multi-agent systems, prompt optimization
4. Infrastructure & Inference Optimization — Serving (vLLM, TGI), KV Cache, quantization, edge AI, distributed training [HIGHEST PRIORITY]
5. Evaluation & Safety — Benchmarks, jailbreak, hallucination, bias
6. Regulation & Business — AI policy, copyright, watermarking

## Evaluation Criteria
- The paper must contain ACTIONABLE technical insights for LLM engineers
- Pure linguistics, cognitive science, or social science papers should be marked as NOT relevant
- Papers about traditional ML (non-LLM) should be marked as NOT relevant unless they directly apply to LLM infrastructure
- Infrastructure papers (Category 4) should have a LOWER threshold for relevance — include if there is any systems-level insight

## Output Rules
- summary_ja: Write a single-line Japanese summary focusing on the TECHNICAL contribution (what method, what improvement, what result). Max 100 characters.
- importance: Rate 1-5 based on novelty and practical impact for LLM engineers
```

### 4.2 ユーザープロンプトテンプレート

```
## Paper
Title: {title}
Abstract: {abstract}

## Pre-filter Context
Best matching category: {best_category_id} ({category_name})
Similarity score: {max_score}
Categories hit (score >= 0.40): {hit_count}/6

Please evaluate this paper.
```

---

## 5. 出力仕様（JSON Schema）

### 5.1 JSON Schema 定義

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["is_relevant", "category_id", "confidence", "importance", "summary_ja", "reasoning"],
  "properties": {
    "is_relevant": {
      "type": "boolean",
      "description": "Whether the paper is relevant to LLM engineering practitioners"
    },
    "category_id": {
      "type": "integer",
      "enum": [1, 2, 3, 4, 5, 6],
      "description": "Primary category ID (1-6)"
    },
    "secondary_category_ids": {
      "type": "array",
      "items": { "type": "integer", "enum": [1, 2, 3, 4, 5, 6] },
      "description": "Optional secondary categories"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Confidence in the relevance judgment (0.0-1.0)"
    },
    "importance": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "Importance for LLM engineers: 1=marginal, 2=minor, 3=notable, 4=significant, 5=breakthrough"
    },
    "summary_ja": {
      "type": "string",
      "maxLength": 150,
      "description": "One-line Japanese summary of the technical contribution"
    },
    "reasoning": {
      "type": "string",
      "maxLength": 200,
      "description": "Brief English reasoning for the judgment (for debugging/audit)"
    }
  }
}
```

### 5.2 出力例

**合格例（is_relevant = true）:**
```json
{
  "is_relevant": true,
  "category_id": 4,
  "secondary_category_ids": [1],
  "confidence": 0.92,
  "importance": 4,
  "summary_ja": "KV Cacheを動的に圧縮し、長文コンテキストでのvLLMスループットを2.3倍改善する手法を提案",
  "reasoning": "Direct contribution to inference optimization with quantitative speedup results on production-grade serving system."
}
```

**不合格例（is_relevant = false）:**
```json
{
  "is_relevant": false,
  "category_id": 3,
  "secondary_category_ids": [],
  "confidence": 0.78,
  "importance": 1,
  "summary_ja": "対話分析における言語学的特徴量の影響を調査（LLMインフラとは無関係）",
  "reasoning": "Paper studies dialogue analysis from a linguistics perspective. While using an LLM as a tool, no systems-level or engineering contribution."
}
```

---

## 6. コスト見積もり

### 6.1 日次コスト（Gemini 2.0 Flash）

| 項目 | 値 |
|:---|:---|
| L2通過見込み | 50〜100件/日 |
| 1論文あたり入力 | ~900トークン |
| 1論文あたり出力 | ~300トークン |
| **日次入力トークン** | 45,000〜90,000 |
| **日次出力トークン** | 15,000〜30,000 |
| **日次コスト** | $0.005〜$0.02 |
| **月次コスト** | **$0.15〜$0.60** |

### 6.2 全パイプライン月次コストサマリ

| フェーズ | 月次コスト | 備考 |
|:---|:---|:---|
| L1（arXiv API） | $0.00 | 無料 |
| L2（Embedding） | ~$0.04 | text-embedding-3-small |
| **L3（LLM判定）** | **~$0.40** | Gemini 2.0 Flash |
| **合計** | **~$0.44/月** | ☕ コーヒー1杯以下 |

---

## 7. 処理フロー

```
L2通過論文（50-100件/日）
    │
    ▼
┌──────────────────────────────┐
│  1. プロンプト構築             │
│     - Title + Abstract       │
│     - L2スコア情報            │
│     - システムプロンプト      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  2. Gemini 2.0 Flash 呼び出し │
│     - JSON Mode (強制)       │
│     - temperature: 0.1       │
│     - max_output_tokens: 500 │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  3. レスポンス検証            │
│     - JSON Schema バリデーション│
│     - 必須フィールド確認       │
│     - 不正値チェック           │
└──────────┬──────────┬────────┘
           │          │
     valid │          │ invalid
           ▼          ▼
    ┌──────────┐  ┌──────────────┐
    │ 4a. DB   │  │ 4b. リトライ  │
    │   UPDATE │  │   (最大2回)   │
    └──────────┘  └──────────────┘
           │
           ▼
    ┌──────────────────────────┐
    │ 5. is_relevant=true のみ │
    │    アプリ配信キューへ     │
    └──────────────────────────┘
```

---

## 8. DB更新仕様

L3の結果を `papers` テーブルに UPDATE する。

```sql
UPDATE papers
SET
    is_relevant      = :is_relevant,
    category_id      = :category_id,
    summary_ja       = :summary_ja,
    detail_review    = :full_json_response,  -- L3の全JSON出力をJSONB保存
    updated_at       = NOW()
WHERE arxiv_id = :arxiv_id;
```

---

## 9. エラーハンドリング

| エラー種別 | 対応策 |
|:---|:---|
| API 429 (Rate Limit) | 指数バックオフ（1秒 → 2秒 → 4秒）、最大3回リトライ |
| API 500/503 | 5分後にリトライ、2回失敗で当日スキップ → 翌日再処理 |
| JSON パースエラー | リトライ1回。それでも不正なら `is_relevant = NULL` で保存し手動確認 |
| Schema バリデーション失敗 | reasoningのみ欠損なら許容。それ以外はリトライ |
| タイムアウト (30秒) | リトライ1回 |

---

## 10. 並列実行設計

| パラメータ | 値 | 根拠 |
|:---|:---|:---|
| **同時リクエスト数** | 5 | Gemini API のレートリミットに余裕を持たせる |
| **リクエスト間隔** | 200ms | バースト制限の回避 |
| **全体処理時間** | ~2〜4分 | 100件 ÷ 5並列 × 1秒/件 |

```python
import asyncio
from aiohttp import ClientSession

CONCURRENCY = 5
semaphore = asyncio.Semaphore(CONCURRENCY)

async def process_paper(paper, session):
    async with semaphore:
        prompt = build_prompt(paper)
        response = await call_gemini(prompt, session)
        validated = validate_schema(response)
        await update_db(paper["arxiv_id"], validated)

async def run_l3(papers):
    async with ClientSession() as session:
        tasks = [process_paper(p, session) for p in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

---

## 11. ログ出力仕様

```json
{
  "phase": "L3",
  "execution_date": "2026-02-12",
  "input_count": 72,
  "relevant_count": 23,
  "rejected_count": 49,
  "relevance_rate": "31.9%",
  "total_input_tokens": 64800,
  "total_output_tokens": 21600,
  "estimated_cost_usd": 0.015,
  "errors": [],
  "processing_time_sec": 142,
  "importance_distribution": {
    "5_breakthrough": 1,
    "4_significant": 5,
    "3_notable": 9,
    "2_minor": 6,
    "1_marginal": 2
  },
  "category_distribution": {
    "1_基盤モデル": 5,
    "2_学習": 3,
    "3_エンジニアリング": 6,
    "4_インフラ": 7,
    "5_評価": 1,
    "6_規制": 1
  }
}
```

---

## 12. L3 通過後のパイプライン連携

L3で `is_relevant = true` と判定された論文（10〜30件/日）は、後段の**PDF全文分析**（Gemini 2.0 Flash）へ渡される。

| 次工程 | 処理内容 | 設計書 |
|:---|:---|:---|
| PDF全文分析 | PDFを丸ごとGeminiに投入し、3視点解説・レベル別テキスト・図表分析を一括生成 | `agent_design.md` |
| 図表抽出 | PyMuPDFでPDFから画像を抽出しS3に保存（PDF分析と並列実行） | `agent_design.md` |

> **設計上の分離:** L3は「フィルタリング＋軽量な1行要約」に特化し、重いPDF全文分析は別プロセスで非同期実行する。これにより、L3のコストとレイテンシを最小に保つ。
