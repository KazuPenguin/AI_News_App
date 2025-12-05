# 📱 AI Insight Hub 要件定義書 (Ver 1.0)

## 1. プロジェクト概要

### 1.1 背景・目的
AI/LLM分野の急速な進展に伴い、情報のキャッチアップコストが増大している。本プロジェクトは、アカデミック（論文）、トレンド（SNS）、ビジネス、金融の4領域から情報を自動収集・要約し、マルチモーダル（テキスト＋画像）なUIで閲覧できるスマートフォンアプリを開発する。

また、本開発を通じて「モダンなアプリ開発（Flutter）」と「最新のPythonバックエンド/LLM開発」の実践的スキルを習得することを主目的とする。

### 1.2 ターゲットユーザー
- **プライマリ**: 開発者本人（コンピュータ科学専攻、LLMに関心がある）。
- **セカンダリ**: 多忙なAIエンジニア、投資家、テック系ビジネスパーソン。

---

## 2. システムアーキテクチャ

BFF (Backend for Frontend) パターンを採用し、クライアントとサーバーを疎結合にする。

- **クライアントサイド**: Flutter (iOS/Android)
- **サーバーサイド**: Python (FastAPI)
- **データベース**: Supabase (PostgreSQL + pgvector)
- **インフラ**: Docker, Render/Google Cloud Run (コンテナ運用)
- **LLMオーケストレーション**: LangChain

---

## 3. 機能要件 (Functional Requirements)

アプリは以下の4つの主要モジュールで構成される。

### 3.1 📚 Arxiv 論文インサイト機能 (Core Feature)
最新のCS系論文（cs.CL, cs.LGなど）を収集し、視覚的に要約する。

- **データ取得**: arxiv APIを使用。過去3日分（または指定期間）の論文を取得。
- **PDF解析・画像抽出**:
    - **ライブラリ**: PyMuPDF (fitz) または pdf2image。
    - **処理**: PDF内の図表（Figure 1など）を座標指定で切り出し、画像ファイルとして保存。
- **マルチモーダル要約**:
    - **LLM**: OpenAI API (gpt-4o-mini) 等のVision対応モデル。
    - **処理**: テキスト要約に加え、「抽出した図が何を表しているか」の解説を生成。
- **UI要件 (2段階表示)**:
    - **Level 1 (フィード)**: サムネイル画像（アーキテクチャ図）＋タイトル＋1行要約。
    - **Level 2 (詳細)**: 背景、新規性、手法、結果の構造化要約＋画像ギャラリー。

### 3.2 📢 Webトレンドモニタリング機能
Web上の最新トレンドや議論を収集し、重要なトピックを抽出する。

- **データ取得**: Serper Dev API (Google Search Results)。
- **フィルタリング**:
    - **キーワード**: "LLM", "Generative AI", "AI News" などの検索クエリ。
- **感情分析 (Sentiment Analysis)**:
    - LangChainを用い、単なる宣伝やスパムを除外。「技術的議論」や「速報」を優先スコアリング。

### 3.3 📈 AI金融インテリジェンス機能
AI関連銘柄の市場動向を可視化する。

- **データ取得**: yfinance ライブラリ。
- **対象**: 主要AI銘柄（NVDA, MSFT, GOOGL, PLTR等）。
- **表示**:
    - 株価チャート（fl_chart で描画）。
    - 株価変動に関連しそうなニュースの自動紐付け。

### 3.4 💼 ビジネス・サービスニュース機能
新サービスや資金調達情報を収集する。

- **データ取得**: BeautifulSoup4 または Firecrawl (Markdown変換スクレイピング)。
- **ソース**: TechCrunch, PR Times, Hacker Newsなど。
- **処理**: 重複記事の統合（De-duplication）。

### 3.5 🔔 通知・配信機能
- **定期配信**: 3日に1回、重要トピックをプッシュ通知（Firebase Cloud Messaging）。
- **オンデマンド**: アプリ起動時に最新情報をPullリフレッシュ。

---
s
## 4. データベース設計 (Schema Design)

Supabase (PostgreSQL) を利用。非構造化データへの対応と将来的なRAG（検索拡張生成）を見据える。

### テーブル構成概要

| テーブル名 | 概要 | 主要カラム |
| :--- | :--- | :--- |
| **users** | ユーザー管理 | `uuid`, `email`, `preferences` (興味タグ) |
| **articles** | 記事マスター | `id`, `category` (arxiv/web/finance/biz), `title`, `summary`, `published_at`, `source_url` |
| **article_images** | 記事画像 | `id`, `article_id`, `image_url`, `caption` (図の解説) |
| **embeddings** | ベクトルデータ | `id`, `article_id`, `vector` (記事内容の埋め込み表現) |
| **market_data** | 金融データ | `ticker`, `date`, `close_price`, `volume` |

---

## 5. UI/UX デザインガイドライン

- **コンセプト**: "Smart & Academic"
- **ナビゲーション**: ボトムタブバー（Home / Arxiv / Market / Trend）
- **カードUI**: 情報の塊をカードとして表現。スワイプ操作での「興味あり/なし」判定（将来的な学習データ用）を実装検討。
- **インタラクション**: 画面遷移にはHero Animation（画像が拡大して詳細画面に繋がる演出）を採用し、シームレスな体験を提供する。

---

## 6. 技術スタック・使用ライブラリ一覧

学習効果を高めるための選定。

| 領域 | 技術要素 | 学習ポイント |
| :--- | :--- | :--- |
| **Mobile** | Flutter (Dart)<br>Riverpod (状態管理), Dio (通信), GoRouter (ルーティング), fl_chart (グラフ) | モダンなアプリ開発、状態管理、チャート描画 |
| **Backend** | FastAPI (Python)<br>Pydantic (型定義), Asyncio (非同期処理) | 高速なAPIサーバー構築、非同期処理 |
| **LLM/AI** | LangChain<br>OpenAI API (gpt-4o-mini) / Anthropic API, Prompt Engineering, Function Calling | LLMオーケストレーション、プロンプトエンジニアリング |
| **PDF/Data** | PyMuPDF / yfinance | 非構造化データ処理, 金融データハンドリング |
| **DB/Auth** | Supabase<br>PostgreSQL, pgvector, Authentication | ベクトル検索、認証基盤 |
| **DevOps** | Docker / GitHub Actions | コンテナ化, CI/CDパイプライン |
