"""initial schema

Revision ID: 20260219_001
Revises:
Create Date: 2026-02-19 12:00:00.000000

"""

from alembic import op
from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "20260219_001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create tables
    # papers
    op.execute("""
        CREATE TABLE papers (
            id               SERIAL PRIMARY KEY,
            arxiv_id         VARCHAR(20) UNIQUE NOT NULL,
            title            TEXT NOT NULL,
            abstract         TEXT NOT NULL,
            authors          TEXT[] NOT NULL,
            pdf_url          TEXT,
            primary_category VARCHAR(10) NOT NULL,
            all_categories   TEXT[],
            published_at     TIMESTAMPTZ NOT NULL,
            embedding        vector(1536),

            -- L1 metadata
            matched_queries  INTEGER[] DEFAULT '{}',

            -- L2 results
            best_category_id INTEGER,
            max_score        FLOAT,
            hit_count        INTEGER,
            importance_score FLOAT,
            all_scores       JSONB,

            -- L3 results
            is_relevant      BOOLEAN,
            category_id      INTEGER,
            confidence       FLOAT,
            importance       SMALLINT CHECK (importance BETWEEN 1 AND 5),
            summary_ja       TEXT,
            reasoning        TEXT,
            detail_review    JSONB,

            -- Timestamps
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW()
        );
        COMMENT ON TABLE papers IS '論文メタデータ + L1/L2/L3 処理結果';
    """)

    # anchors
    op.execute("""
        CREATE TABLE anchors (
            id              SERIAL PRIMARY KEY,
            category_id     INTEGER UNIQUE NOT NULL,
            category_name   VARCHAR(100) NOT NULL,
            definition_en   TEXT NOT NULL,
            definition_ja   TEXT,
            embedding       vector(1536) NOT NULL,
            is_active       BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
        COMMENT ON TABLE anchors IS 'ベクトル選別用アンカー定義';
    """)

    # users
    op.execute("""
        CREATE TABLE users (
            id              SERIAL PRIMARY KEY,
            cognito_sub     VARCHAR(36) UNIQUE NOT NULL,
            email           VARCHAR(255) UNIQUE NOT NULL,
            display_name    VARCHAR(100),
            auth_provider   VARCHAR(20) NOT NULL CHECK (
                                auth_provider IN ('email', 'google', 'apple')
                            ),
            language        VARCHAR(5) DEFAULT 'ja' CHECK (language IN ('ja', 'en')),
            default_level   SMALLINT DEFAULT 2 CHECK (default_level BETWEEN 1 AND 3),
            is_active       BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
        COMMENT ON TABLE users IS 'Cognito連携ユーザー情報';
    """)

    # bookmarks
    op.execute("""
        CREATE TABLE bookmarks (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            paper_id    INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, paper_id)
        );
        COMMENT ON TABLE bookmarks IS 'ユーザーのお気に入り論文';
    """)

    # paper_views
    op.execute("""
        CREATE TABLE paper_views (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            paper_id    INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            viewed_at   TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, paper_id)
        );
        COMMENT ON TABLE paper_views IS 'ユーザーの論文閲覧履歴';
    """)

    # paper_figures
    op.execute("""
        CREATE TABLE paper_figures (
            id              SERIAL PRIMARY KEY,
            paper_id        INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            figure_index    SMALLINT NOT NULL,
            s3_key          TEXT NOT NULL,
            s3_url          TEXT NOT NULL,
            width           INTEGER,
            height          INTEGER,
            file_size_bytes INTEGER,
            caption         TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(paper_id, figure_index)
        );
        COMMENT ON TABLE paper_figures IS 'PDFから抽出した論文図表';
    """)

    # batch_logs
    op.execute("""
        CREATE TABLE batch_logs (
            id              SERIAL PRIMARY KEY,
            execution_date  DATE NOT NULL,
            date_range      JSONB NOT NULL,
            l1_raw_count    INTEGER,
            l1_dedup_count  INTEGER,
            l2_input_count  INTEGER,
            l2_passed_count INTEGER,
            l2_pass_rate    FLOAT,
            l3_input_count  INTEGER,
            l3_relevant_count INTEGER,
            l3_relevance_rate FLOAT,
            l3_input_tokens   INTEGER,
            l3_output_tokens  INTEGER,
            l3_cost_usd       FLOAT,
            figures_extracted INTEGER,
            errors          JSONB DEFAULT '[]',
            processing_time_sec INTEGER,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
        COMMENT ON TABLE batch_logs IS '日次バッチ処理の実行ログ';
    """)

    # 3. Create Indexes
    # vector index
    op.execute("""
        CREATE INDEX idx_papers_embedding
        ON papers USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # other indexes
    op.execute(
        """
        CREATE INDEX idx_papers_published ON papers (published_at DESC)
        WHERE is_relevant = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX idx_papers_category ON papers (category_id, published_at DESC)
        WHERE is_relevant = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX idx_papers_unprocessed_l2 ON papers (created_at)
        WHERE max_score IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX idx_papers_unprocessed_l3 ON papers (importance_score DESC)
        WHERE max_score IS NOT NULL AND is_relevant IS NULL
        """
    )
    op.execute("CREATE INDEX idx_bookmarks_user ON bookmarks (user_id, created_at DESC)")
    op.execute("CREATE INDEX idx_paper_views_user_paper ON paper_views (user_id, paper_id)")
    op.execute("CREATE INDEX idx_paper_figures_paper ON paper_figures (paper_id, figure_index)")
    op.execute("CREATE INDEX idx_batch_logs_date ON batch_logs (execution_date DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS paper_figures CASCADE")
    op.execute("DROP TABLE IF EXISTS paper_views CASCADE")
    op.execute("DROP TABLE IF EXISTS bookmarks CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS anchors CASCADE")
    op.execute("DROP TABLE IF EXISTS papers CASCADE")
    # We might want to keep the extension enabled,
    # but strictly speaking downgrade should reverse it.
    # op.execute("DROP EXTENSION IF EXISTS vector")
