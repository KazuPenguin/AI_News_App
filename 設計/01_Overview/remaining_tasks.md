# 📌 AI Research OS: 残タスク一覧 (Remaining Tasks)

これまでに作成されたロードマップ(`設計計画.md`)と、運用開始へ向けたタスク(`あとでやること.md`)から、**現在未完了(`[ ]`)**となっているタスクを全て抽出・整理しました。
デプロイ準備や将来的な改善など、フェーズとカテゴリごとに分類しています。

---

## 1. 🚀 直近のデプロイ・稼働確認 (Immediate Actions)

まずはインフラをAWSにデプロイし、パイプラインとAPIを正常稼働させるためのステップです。

### 1-1. インフラのデプロイ
- [ ] **バッチ基盤デプロイ**: `cd infra && npx cdk deploy BatchStack` を実行し、ECR へのイメージプッシュと Lambda 更新
- [ ] **API基盤デプロイ**: `cd infra && npx cdk deploy ApiStack` を実行し、API Gateway と Lambda を更新
- [ ] **フロントエンドのAPI向き先変更**: デプロイされた API Gateway URL を `.env` の `EXPO_PUBLIC_API_URL` に設定

### 1-2. DBマイグレーションとデータ初期化
先日作成した `operations_guide.md` に従い、踏み台を経由して実施します。
- [ ] **Alembic実行**: ローカルポートフォワード経由で `uv run alembic upgrade head` を実行
- [ ] **アンカーデータ投入**: `uv run python -m scripts.setup_anchors` 実行
- [ ] **シードデータ投入**: `uv run python -m scripts.seed_papers` 実行

### 1-3. 動作テスト(結合テスト)
- [ ] APIの全エンドポイント疎通確認 (SwaggerまたはPostmanコレクションを使用)
- [ ] `aws lambda invoke` 等でのバッチ手動実行と CloudWatch Logs の確認
- [ ] アプリからの API呼び出し (ホーム、詳細、お気に入り、設定) 動作確認
- [ ] EventBridge ルールの日次スケジュールでの発火テスト

---

## 2. ⚙️ 品質向上・チューニング (Quality & Tuning)

システム稼働後、実際のデータを見ながらシステム精度の向上を目指すステップです。

### 2-1. キュレーションパイプライン評価
- [ ] **L2 閾値調整**: 通過率(30〜50%) を目標に `L2_THRESHOLD` (初期値:0.40) を調整
- [ ] **L3・出力品質確認**:
  - `is_relevant=true` の論文が本当に有用か目視確認
  - `detail_review` JSON (日本語品質、セクション選択の妥当性) を確認
  - バッチ失敗時の通知用 DLQ (Dead Letter Queue) 追加
- [ ] **RAG精度評価 (Eval)**: 代表的な論文での日本語・英語の要約出力形式と精度検証
- [ ] 1日あたりのトークン消費量の計測とコスト最適化

### 2-2. 追加機能実装 (パーソナライズ)
- [ ] ユーザーの「興味タグ」に基づく推薦・フィルタロジックの実装
- [ ] 言語設定 (`ja`/`en`) に応じたエージェント出力の切り替え

---

## 3. 🛡️ 本番環境への移行 (Production Readiness)

ユーザーへの公開（ストア連携を含む）に向けて、非機能要件を高めるステップです。

### 3-1. AWS CDK: 本番向けリソース設定の変更
- [ ] **DB保護・高可用化**: `removalPolicy=RETAIN`, `multiAz=true`, `deletionProtection=true`
- [ ] **DBスペックUP**: インスタンスタイプを `db.t4g.small` 以上に
- [ ] **ネットワーク可用化**: VPC の `natGateways` を `2` に変更
- [ ] **APIセキュリティ強化**: CORSの `allowOrigins` を限定、`dataTraceEnabled=false` に変更しリクエストログを消音
- [ ] **認証メール強化**: Cognito デフォルト送信から AWS SES へ切り替え（送信上限の緩和）

### 3-2. ネットワーク・セキュリティ強化
- [ ] VPC Endpoints (S3, ECR等) の追加による NAT Gateway 通信費の削減
- [ ] API Gateway / CloudFront へのカスタムドメイン設定 (`api.example.com` 等) と ACM 証明書の取得
- [ ] AWS WAF (Web ACL) の導入
- [ ] API キーの発行と Usage Plan によるクライアントアプリ単位のスロットリング設定

### 3-3. CI/CDフェーズの完成
- [ ] フロントエンド(Web版)用ホスティング環境 (S3 + CloudFront) をインフラスタックに追加
- [ ] GitHub Actions にフロントエンド Web の Build & Deploy ジョブを追加
- [ ] EAS (Expo Application Services) プロジェクトの初期化とモバイルCI/CDフローの構築
- [ ] E2Eテストツールの導入 (Playwright など)

---

## 4. 📝 公開準備 (Release & Docs)

- [ ] **ドキュメントの完備**: README.md の最終更新、ADRの整理
- [ ] **法的準備**: プライバシーポリシー・利用規約の作成
- [ ] **アプリ審査準備**: Fastlane を用いた TestFlight (iOS) / Google Play (Android) への配信設定
