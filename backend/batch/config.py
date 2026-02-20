"""
AI Research OS — バッチ処理設定定数

全フェーズ (L1/L2/L3/Post-L3) の閾値・並列数・モデル名・クエリテンプレートを集約。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# arXiv API (L1)
# ---------------------------------------------------------------------------
ARXIV_BASE_URL = "http://export.arxiv.org/api/query"
ARXIV_RATE_LIMIT_SEC = 3.0
ARXIV_TIMEOUT_SEC = 30
ARXIV_MAX_RETRIES = 3
ARXIV_MAX_PAGES_PER_QUERY = 3

# カテゴリ別クエリテンプレート
# {start}, {end} は YYYYMMDDTTTT 形式の日付で置換
ARXIV_QUERIES: list[dict[str, str | int]] = [
    {
        "category_id": 1,
        "category_name": "基盤モデル",
        "query": (
            "%28cat:cs.CL+OR+cat:cs.LG%29"
            "+AND+"
            "%28abs:%22Foundation+Model%22+OR+abs:%22Large+Language+Model%22"
            "+OR+abs:GPT+OR+abs:Llama+OR+abs:Gemini+OR+abs:Claude"
            "+OR+abs:Mistral+OR+abs:MoE+OR+abs:Mamba+OR+abs:SSM"
            "+OR+abs:RWKV+OR+abs:Transformer%29"
        ),
        "max_results": 500,
    },
    {
        "category_id": 2,
        "category_name": "学習・調整",
        "query": (
            "%28cat:cs.LG+OR+cat:cs.AI%29"
            "+AND+"
            "%28abs:RLHF+OR+abs:RLAIF"
            "+OR+abs:%22Direct+Preference+Optimization%22+OR+abs:DPO"
            "+OR+abs:%22Chain+of+Thought%22"
            "+OR+abs:PEFT+OR+abs:LoRA+OR+abs:QLoRA"
            "+OR+abs:%22Model+Merging%22%29"
        ),
        "max_results": 300,
    },
    {
        "category_id": 3,
        "category_name": "エンジニアリング",
        "query": (
            "%28cat:cs.SE+OR+cat:cs.CL%29"
            "+AND+"
            "%28abs:%22Retrieval-Augmented+Generation%22+OR+abs:RAG"
            "+OR+abs:GraphRAG"
            "+OR+abs:%22Autonomous+Agent%22+OR+abs:%22Multi-Agent%22"
            "+OR+abs:%22Prompt+Engineering%22+OR+abs:DSPy%29"
        ),
        "max_results": 300,
    },
    {
        "category_id": 4,
        "category_name": "インフラ・最適化",
        "query": (
            "%28cat:cs.DC+OR+cat:cs.AR%29"
            "+AND+"
            "%28abs:vLLM+OR+abs:TGI+OR+abs:TensorRT"
            "+OR+abs:%22KV+Cache%22+OR+abs:%22Speculative+Decoding%22"
            "+OR+abs:Quantization+OR+abs:AWQ+OR+abs:GPTQ"
            "+OR+abs:%22On-Device%22+OR+abs:%22Edge+AI%22"
            "+OR+abs:%22GPU+optimization%22%29"
        ),
        "max_results": 200,
    },
    {
        "category_id": 5,
        "category_name": "評価・安全性",
        "query": (
            "%28cat:cs.CL+OR+cat:cs.CR%29"
            "+AND+"
            "%28abs:%22LLM+Evaluation%22+OR+abs:Leaderboard"
            "+OR+abs:Hallucination+OR+abs:Jailbreak"
            "+OR+abs:%22Adversarial+Attack%22+OR+abs:Bias"
            "+OR+abs:%22Safety+Alignment%22%29"
        ),
        "max_results": 200,
    },
    {
        "category_id": 6,
        "category_name": "規制・社会",
        "query": (
            "cat:cs.CY"
            "+AND+"
            "%28abs:%22AI+Regulation%22+OR+abs:%22EU+AI+Act%22"
            "+OR+abs:Copyright+OR+abs:Watermarking%29"
        ),
        "max_results": 100,
    },
]

# ---------------------------------------------------------------------------
# Embedding / pgvector (L2)
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
L2_THRESHOLD = 0.40  # コサイン類似度の通過閾値
ANCHOR_COUNT = 6

# importance_score の重み付け
IMPORTANCE_WEIGHT_MAX_SCORE = 0.6
IMPORTANCE_WEIGHT_HIT_COUNT = 0.3
IMPORTANCE_WEIGHT_MATCHED_QUERIES = 0.1

# ---------------------------------------------------------------------------
# Gemini L3 分析
# ---------------------------------------------------------------------------
GEMINI_MODEL = "gemini-2.5-flash"
L3_CONCURRENCY = 5
L3_REQUEST_INTERVAL_MS = 200
L3_TEMPERATURE = 0.1
L3_MAX_OUTPUT_TOKENS = 500
L3_MAX_RETRIES = 3
L3_TIMEOUT_SEC = 30

# カテゴリID → カテゴリ名マッピング
CATEGORY_NAMES: dict[int, str] = {
    1: "Foundation Models & Architecture",
    2: "Training & Tuning",
    3: "Application Engineering",
    4: "Infrastructure & Inference Optimization",
    5: "Evaluation & Safety",
    6: "Regulation & Business",
}

# L3 システムプロンプト
L3_SYSTEM_PROMPT = """You are an expert AI/ML research curator specializing in systems engineering and infrastructure. Your task is to evaluate whether an academic paper is relevant to practitioners working on LLM systems, and if so, classify and summarize it.

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
- importance: Rate 1-5 based on novelty and practical impact for LLM engineers"""  # noqa: E501

# L3 ユーザープロンプトテンプレート
L3_USER_PROMPT_TEMPLATE = """## Paper
Title: {title}
Abstract: {abstract}

## Pre-filter Context
Best matching category: {best_category_id} ({category_name})
Similarity score: {max_score}
Categories hit (score >= 0.40): {hit_count}/6

Please evaluate this paper."""

# ---------------------------------------------------------------------------
# Post-L3: PDF全文分析
# ---------------------------------------------------------------------------
POST_L3_CONCURRENCY = 3
POST_L3_TEMPERATURE = 0.3
POST_L3_MAX_OUTPUT_TOKENS = 4096
POST_L3_TIMEOUT_SEC = 60
POST_L3_MAX_RETRIES = 3

# Post-L3 システムプロンプト
POST_L3_SYSTEM_PROMPT = """You are an expert AI research analyst who produces detailed, multi-perspective paper reviews for a mobile learning app. Your audience ranges from beginners to senior engineers.

## Your Task
Given a full academic paper (PDF) and its metadata, generate a structured review with:
1. Automatic section selection — choose the most relevant sections for this paper
2. Three expert perspectives — AI Engineering, Mathematical Theory, and Business Impact
3. Three difficulty levels — Beginner, Intermediate, and Expert
4. Figure analysis — describe key figures/tables from the paper

## Section Candidates
Choose 3-5 of the following sections, based on what is most informative for THIS paper:
- research_background: Why this research matters, prior work
- overview: Core idea in 2-3 sentences
- novelty: What is new compared to existing approaches
- technical_details: Architecture, algorithms, key equations
- theoretical_basis: Mathematical foundations, proofs
- experimental_results: Benchmarks, ablation studies, key numbers
- business_impact: Industry applications, market implications

## Writing Guidelines
- Write ALL content in Japanese (日本語)
- Be specific: cite actual numbers, model names, and dataset names from the paper
- For mathematical content: use plain-language explanations, avoid raw LaTeX
- Each perspective should add UNIQUE value, not repeat the same content
- Beginner level: use analogies and avoid jargon
- Expert level: include specific hyperparameters, training details, and limitations"""  # noqa: E501

# Post-L3 ユーザープロンプトテンプレート
POST_L3_USER_PROMPT_TEMPLATE = """## Paper Metadata
- Title: {title}
- arXiv ID: {arxiv_id}
- Category: {category_name} (ID: {category_id})
- L2 Importance Score: {importance_score}
- L3 Quick Summary: {summary_ja}

## Instructions
Please analyze the attached PDF and generate a detailed review."""

# ---------------------------------------------------------------------------
# 図表抽出 (PyMuPDF)
# ---------------------------------------------------------------------------
FIGURE_MIN_WIDTH = 100  # 最小幅 (px) — アイコンなどを除外
FIGURE_MIN_HEIGHT = 100  # 最小高さ (px)
FIGURE_S3_PREFIX = "figures/"

# ---------------------------------------------------------------------------
# Gemini API バックオフ設定
# ---------------------------------------------------------------------------
BACKOFF_BASE_SEC = 1.0
BACKOFF_MAX_SEC = 32.0
