# 🗓️ AI Insight Hub 開発ロードマップ (Backend First)

ユーザーの要望に基づき、**バックエンド開発を先行**して一気に進める計画に変更しました。
APIとデータパイプラインを先に完成させ、その後Flutterアプリを一気に実装します。

## 📅 全体スケジュール概要

| フェーズ | 期間 | テーマ | 主なゴール |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Week 1-2 | **Backend Foundation & Core** | DB構築、Arxiv論文収集・要約APIの完成 |
| **Phase 2** | Week 3 | **Backend Expansion** | SNS/ニュース/金融データの収集・分析API完成 |
| **Phase 3** | Week 4-5 | **Mobile App Implementation** | Flutterアプリ構築、全APIとの連携、UI実装 |
| **Phase 4** | Week 6 | **Polish & Deploy** | 通知機能、全体テスト、本番デプロイ |

---

## 🚀 詳細ロードマップ

### Phase 1: Backend Foundation & Core (Week 1-2)
**目的**: 開発環境を整え、最重要機能である「論文要約」のAPIを完成させる。

- **Infrastructure & Base**
    - [ ] プロジェクト作成 (FastAPI + Poetry)
    - [ ] Docker環境構築 (App + DB)
    - [ ] Supabase接続設定 & Migration (Users, Articles, Images)
    - [ ] ユーザー認証API (Supabase Auth Wrapper)
- **Feature: Arxiv Insight**
    - [ ] Arxiv API クライアント実装
    - [ ] PDF取得 & PyMuPDFによる画像抽出処理
    - [ ] OpenAI API (Vision) 連携 & プロンプトエンジニアリング
    - [ ] 論文データ保存・取得API (CRUD)

### Phase 2: Backend Expansion (Week 3)
**目的**: 残りのデータソース（トレンド、ビジネス、金融）のAPIを一気に作り切る。

- **Feature: Trend & Business**
    - [ ] SNSデータ収集 (Tweepy/Serper)
    - [ ] ニューススクレイピング (BeautifulSoup/Firecrawl)
    - [ ] 感情分析・重要度スコアリングロジック (LangChain)
    - [ ] トレンド/ニュース取得API
- **Feature: Finance**
    - [ ] yfinance データ取得API
    - [ ] 銘柄データキャッシュ機構
    - [ ] 株価データ取得API

### Phase 3: Mobile App Implementation (Week 4-5)
**目的**: 完成したAPIを利用して、Flutterアプリを一気に組み上げる。

- **Foundation**
    - [ ] Flutterプロジェクト作成 & ディレクトリ構成
    - [ ] Riverpod + Dio + GoRouter 設定
    - [ ] APIクライアントコード生成 (OpenAPI Generator等検討)
- **UI Implementation**
    - [ ] 認証画面 (Login/Signup)
    - [ ] **Arxiv**: フィード画面 & 詳細画面 (画像表示)
    - [ ] **Trend/Biz**: ニュースリスト & タイムライン
    - [ ] **Finance**: 株価チャート (fl_chart)
    - [ ] ナビゲーション & 画面遷移 (Hero Animation)

### Phase 4: Polish & Deploy (Week 6)
**目的**: 統合テストとデプロイを行う。

- **Common**
    - [ ] プッシュ通知実装 (FCM) - バックエンド側トリガー実装含む
    - [ ] エラーハンドリング & ロギング強化
- **Deployment**
    - [ ] Backend: Render または Google Cloud Run へデプロイ
    - [ ] Mobile: 実機ビルド (TestFlight / APK)

---

## 🎯 次のアクション (Phase 1 Start)
バックエンド開発に集中するため、以下の順序で進めます。

1. **FastAPI プロジェクトセットアップ** (Docker含む)
2. **Supabase データベース設計 & 構築**
3. **Arxiv API & PDF解析ロジックの実装**
