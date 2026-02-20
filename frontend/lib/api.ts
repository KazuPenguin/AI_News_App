/**
 * AI Research OS — API 型定義 + API 関数群
 *
 * api_specification.md §6 の TypeScript Interface に準拠。
 */

import { apiClient } from './api-client';

// ---------------------------------------------------------------------------
// 型定義
// ---------------------------------------------------------------------------
export interface PaperSummary {
    arxiv_id: string;
    title: string;
    category_id: number | null;
    category_name: string | null;
    importance: number | null;
    summary_ja: string | null;
    one_line_takeaway: string | null;
    authors: string[];
    published_at: string;
    thumbnail_url: string | null;
    is_bookmarked: boolean;
    is_viewed: boolean;
}

export interface Section {
    section_id: string;
    title_ja: string;
    content_ja: string;
}

export interface Perspectives {
    ai_engineer: string;
    mathematician: string;
    business: string;
}

export interface Levels {
    beginner: string;
    intermediate: string;
    expert: string;
}

export interface FigureAnalysis {
    figure_ref: string;
    description_ja: string;
    is_key_figure: boolean;
}

export interface PaperDetailData {
    one_line_takeaway: string;
    sections: Section[];
    perspectives: Perspectives | null;
    levels: Levels | null;
    figure_analysis: FigureAnalysis[];
}

export interface PaperDetail {
    arxiv_id: string;
    title: string;
    abstract: string;
    authors: string[];
    pdf_url: string | null;
    category_id: number | null;
    category_name: string | null;
    importance: number | null;
    published_at: string;
    summary_ja: string | null;
    detail: PaperDetailData | null;
    is_bookmarked: boolean;
    is_viewed: boolean;
}

export interface PaperFigure {
    id: number;
    figure_index: number;
    s3_url: string;
    width: number | null;
    height: number | null;
    caption: string | null;
}

export interface Category {
    id: number;
    name: string;
    paper_count: number;
}

export interface BookmarkPaper {
    arxiv_id: string;
    title: string;
    category_id: number | null;
    category_name: string | null;
    importance: number | null;
    summary_ja: string | null;
}

export interface Bookmark {
    bookmark_id: number;
    bookmarked_at: string;
    paper: BookmarkPaper;
}

export interface UserProfile {
    id: number;
    email: string;
    display_name: string | null;
    auth_provider: string;
    language: string;
    default_level: number;
    created_at: string;
}

export interface UserStats {
    papers_viewed: number;
    bookmarks_count: number;
    most_viewed_category: { id: number; name: string; count: number } | null;
    member_since: string;
}

export interface Pagination {
    next_cursor: string | null;
    has_next: boolean;
    total_count?: number;
}

export interface ApiResponse<T> {
    data: T;
    pagination?: Pagination;
}

export interface PapersQuery {
    category_id?: number;
    importance?: number;
    from_date?: string;
    to_date?: string;
    cursor?: string;
    limit?: number;
}

export interface UpdateSettingsRequest {
    display_name?: string;
    language?: 'ja' | 'en';
    default_level?: 1 | 2 | 3;
}

// ---------------------------------------------------------------------------
// API 関数
// ---------------------------------------------------------------------------

// 論文
export function fetchPapers(query: PapersQuery = {}) {
    return apiClient<ApiResponse<PaperSummary[]>>('/papers', {
        params: query as Record<string, string | number | undefined>,
    });
}

export function fetchPaperDetail(arxivId: string) {
    return apiClient<ApiResponse<PaperDetail>>(`/papers/${arxivId}`);
}

export function recordView(arxivId: string) {
    return apiClient<ApiResponse<{ viewed_at: string }>>(`/papers/${arxivId}/view`, {
        method: 'POST',
    });
}

export function fetchPaperFigures(arxivId: string) {
    return apiClient<ApiResponse<PaperFigure[]>>(`/papers/${arxivId}/figures`);
}

// カテゴリ
export function fetchCategories() {
    return apiClient<ApiResponse<Category[]>>('/categories');
}

// ブックマーク
export function fetchBookmarks(query: { cursor?: string; limit?: number } = {}) {
    return apiClient<ApiResponse<Bookmark[]>>('/bookmarks', {
        params: query as Record<string, string | number | undefined>,
    });
}

export function addBookmark(arxivId: string) {
    return apiClient<ApiResponse<{ bookmark_id: number; bookmarked_at: string }>>('/bookmarks', {
        method: 'POST',
        body: { arxiv_id: arxivId },
    });
}

export function removeBookmark(bookmarkId: number) {
    return apiClient<void>(`/bookmarks/${bookmarkId}`, {
        method: 'DELETE',
    });
}

// ユーザー
export function fetchUserProfile() {
    return apiClient<ApiResponse<UserProfile>>('/users/me');
}

export function updateUserSettings(settings: UpdateSettingsRequest) {
    return apiClient<ApiResponse<UserProfile>>('/users/me/settings', {
        method: 'PUT',
        body: settings,
    });
}

export function fetchUserStats() {
    return apiClient<ApiResponse<UserStats>>('/users/me/stats');
}
