"""
AI Research OS — Pydantic データモデル

パイプライン各段 (L1/L2/L3/Post-L3) で受け渡すデータを型安全に定義する。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# L1: arXiv API 収集結果
# ---------------------------------------------------------------------------
class ArxivPaper(BaseModel):
    """arXiv API から取得した論文メタデータ。"""

    arxiv_id: str = Field(description="arXiv ID (例: 2402.12345)")
    title: str
    abstract: str
    authors: list[str]
    pdf_url: str | None = None
    primary_category: str = Field(description="主カテゴリ (例: cs.CL)")
    all_categories: list[str] = Field(default_factory=list)
    published_at: datetime
    matched_queries: list[int] = Field(
        default_factory=list,
        description="ヒットしたクエリカテゴリID群",
    )


# ---------------------------------------------------------------------------
# L2: pgvector 選別結果
# ---------------------------------------------------------------------------
class L2Result(BaseModel):
    """L2ベクトル選別の結果。ArxivPaperに付与される。"""

    arxiv_id: str
    max_score: float = Field(description="最高コサイン類似度")
    best_category_id: int = Field(description="最も近いカテゴリID")
    hit_count: int = Field(description="閾値超えアンカー数")
    importance_score: float = Field(description="重要度スコア")
    all_scores: dict[str, float] = Field(description="全アンカーとのスコア")
    passed: bool = Field(description="L2通過判定")


class L2Paper(ArxivPaper):
    """L2選別を通過した論文。L2結果を含む。"""

    best_category_id: int = 0
    max_score: float = 0.0
    hit_count: int = 0
    importance_score: float = 0.0
    all_scores: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# L3: LLM 分析結果
# ---------------------------------------------------------------------------
class L3Response(BaseModel):
    """Gemini L3分析のJSON出力スキーマ。"""

    is_relevant: bool
    category_id: int = Field(ge=1, le=6)
    secondary_category_ids: list[int] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    importance: int = Field(ge=1, le=5)
    summary_ja: str
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Post-L3: 詳細解説
# ---------------------------------------------------------------------------
class Section(BaseModel):
    """論文解説のセクション。"""

    section_id: str
    title_ja: str
    content_ja: str


class Perspectives(BaseModel):
    """3視点の解説。"""

    ai_engineer: str
    mathematician: str
    business: str


class Levels(BaseModel):
    """3レベルの解説。"""

    beginner: str
    intermediate: str
    expert: str


class FigureAnalysis(BaseModel):
    """図表分析。"""

    figure_ref: str
    description_ja: str
    is_key_figure: bool = False


class DetailReview(BaseModel):
    """Post-L3 PDF全文分析の出力。papers.detail_review に JSONB で保存。"""

    sections: list[Section]
    perspectives: Perspectives
    levels: Levels
    figure_analysis: list[FigureAnalysis] = Field(default_factory=list)
    one_line_takeaway: str = ""


# ---------------------------------------------------------------------------
# 図表抽出
# ---------------------------------------------------------------------------
class ExtractedFigure(BaseModel):
    """PyMuPDF で抽出した図表情報。"""

    figure_index: int
    s3_key: str
    s3_url: str
    width: int
    height: int
    file_size_bytes: int
    caption: str | None = None


# ---------------------------------------------------------------------------
# バッチログ
# ---------------------------------------------------------------------------
class BatchLogEntry(BaseModel):
    """batch_logs テーブルに記録する1回分のバッチ実行ログ。"""

    execution_date: str
    date_range: dict[str, str]
    l1_raw_count: int = 0
    l1_dedup_count: int = 0
    l2_input_count: int = 0
    l2_passed_count: int = 0
    l2_pass_rate: float = 0.0
    l3_input_count: int = 0
    l3_relevant_count: int = 0
    l3_relevance_rate: float = 0.0
    l3_input_tokens: int = 0
    l3_output_tokens: int = 0
    l3_cost_usd: float = 0.0
    figures_extracted: int = 0
    errors: list[str] = Field(default_factory=list)
    processing_time_sec: int = 0
