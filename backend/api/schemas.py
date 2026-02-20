"""
AI Research OS — API レスポンス/リクエスト用 Pydantic モデル

設計/api_specification.md §6 の TypeScript Interface に1:1対応。
パイプライン用モデル (utils/models.py) とは分離。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 論文関連
# ---------------------------------------------------------------------------
class PaperSummary(BaseModel):
    """論文一覧用サマリー。"""

    arxiv_id: str
    title: str
    category_id: int | None = None
    category_name: str | None = None
    importance: int | None = None
    summary_ja: str | None = None
    one_line_takeaway: str | None = None
    authors: list[str] = Field(default_factory=list)
    published_at: datetime
    thumbnail_url: str | None = None
    is_bookmarked: bool = False
    is_viewed: bool = False


class Section(BaseModel):
    """論文解説セクション。"""

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


class PaperDetailData(BaseModel):
    """detail_review JSONB のパース先。"""

    one_line_takeaway: str = ""
    sections: list[Section] = Field(default_factory=list)
    perspectives: Perspectives | None = None
    levels: Levels | None = None
    figure_analysis: list[FigureAnalysis] = Field(default_factory=list)


class PaperDetail(BaseModel):
    """論文詳細レスポンス。"""

    arxiv_id: str
    title: str
    abstract: str
    authors: list[str] = Field(default_factory=list)
    pdf_url: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    importance: int | None = None
    published_at: datetime
    summary_ja: str | None = None
    detail: PaperDetailData | None = None
    is_bookmarked: bool = False
    is_viewed: bool = False


class PaperFigure(BaseModel):
    """論文図表。"""

    id: int
    figure_index: int
    s3_url: str
    width: int | None = None
    height: int | None = None
    caption: str | None = None


class ViewResponse(BaseModel):
    """閲覧記録レスポンス。"""

    viewed_at: datetime


# ---------------------------------------------------------------------------
# カテゴリ
# ---------------------------------------------------------------------------
class Category(BaseModel):
    """カテゴリ一覧用。"""

    id: int
    name: str
    paper_count: int = 0


# ---------------------------------------------------------------------------
# ブックマーク
# ---------------------------------------------------------------------------
class BookmarkPaper(BaseModel):
    """ブックマーク内の論文サマリー。"""

    arxiv_id: str
    title: str
    category_id: int | None = None
    category_name: str | None = None
    importance: int | None = None
    summary_ja: str | None = None


class Bookmark(BaseModel):
    """ブックマーク。"""

    bookmark_id: int
    bookmarked_at: datetime
    paper: BookmarkPaper


class CreateBookmarkRequest(BaseModel):
    """ブックマーク追加リクエスト。"""

    arxiv_id: str


# ---------------------------------------------------------------------------
# ユーザー
# ---------------------------------------------------------------------------
class UserProfile(BaseModel):
    """ユーザープロフィール。"""

    id: int
    email: str
    display_name: str | None = None
    auth_provider: str
    language: str = "ja"
    default_level: int = 2
    created_at: datetime


class UpdateSettingsRequest(BaseModel):
    """ユーザー設定更新リクエスト。"""

    display_name: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, pattern=r"^(ja|en)$")
    default_level: int | None = Field(default=None, ge=1, le=3)


class MostViewedCategory(BaseModel):
    """最多閲覧カテゴリ。"""

    id: int
    name: str
    count: int


class UserStats(BaseModel):
    """ユーザー統計。"""

    papers_viewed: int = 0
    bookmarks_count: int = 0
    most_viewed_category: MostViewedCategory | None = None
    member_since: datetime


# ---------------------------------------------------------------------------
# ページネーション
# ---------------------------------------------------------------------------
class Pagination(BaseModel):
    """カーソルベースページネーション。"""

    next_cursor: str | None = None
    has_next: bool = False
    total_count: int | None = None
