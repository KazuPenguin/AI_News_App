# AI Research OS - 運用開始・デプロイ手順書

本ドキュメントは、ローカル開発環境からAWSの本番（またはステージング）環境へデプロイし、実際にアプリケーションを稼働させるまでの手順をまとめたものです。

## 1. 準備段階 (環境変数の設定)

デプロイ前に、AWS Systems Manager (Secrets Manager) にAPIキーを登録する必要があります。
現在、Backendのバッチ処理やAPIはこれらのシークレットを参照して動作します。

```bash
# OpenAI APIキー (L2 Embedding用)
aws secretsmanager create-secret \
    --name ai-research/openai-api-key \
    --secret-string '{"api_key":"sk-xxx"}'

# Gemini APIキー (L3/Post-L3 分析用)
aws secretsmanager create-secret \
    --name ai-research/gemini-api-key \
    --secret-string '{"api_key":"xxx"}'
```

※ Google OAuth連携やApple Sign Inなどを使用する場合は、追って同様にSecretとして登録し、CDKの `auth-stack.ts` で有効化する必要があります。

---

## 2. インフラのデプロイ (AWS CDK)

GitHub ActionsによるCI/CDパイプラインが自動で行いますが、初回や手動デプロイの場合は以下の手順を実行します。

```bash
cd infra

# ライブラリのインストール
npm install

# AWS環境のブートストラップ (未実行の場合のみ)
npx cdk bootstrap

# 全スタックのデプロイ
npx cdk deploy --all --require-approval never
```

デプロイが完了すると、コンソール上に以下の情報が出力されるため、メモしておきます。
* **API Gateway URL** (Frontendの接続先)
* **Cognito User Pool ID / Client ID**
* **RDS Database Endpoint**

---

## 3. データベースの初期化とマイグレーション

インフラデプロイにより構築されたRDS (PostgreSQL) に対して、テーブルの作成と拡張機能(pgvector)の有効化を行います。

### 3.1 RDS への接続情報の取得
AWS Secrets Manager に自動生成された `ai-research/db-credentials` の値、もしくはAWSコンソールからRDSのエンドポイントとパスワードを取得します。

### 3.2 Alembic によるマイグレーション実行
ローカルPCからAWSのDBへ直接繋ぐか、デプロイ済みのLambda環境等を利用してAlembicを実行します。今回はローカルPCから（踏み台などを経由して）実行する想定のコマンドです。

```bash
cd backend

# DATABASE_URL環境変数にRDSの接続文字列を設定
export DATABASE_URL="postgresql://postgres:PASSWORD@RDS_ENDPOINT:5432/ai_research"

# マイグレーション実行 (テーブル・pgvectorの作成)
uv run alembic upgrade head
```

---

## 4. 初期データの投入 (シード作成)

初回起動直後にアプリが空にならないよう、初期データを投入します。

### 4.1 アンカーデータの投入 (L2ベクトル初期化)
ベクトル検索(L2)の比較基準となるアンカーデータを投入します。
※実行には `DATABASE_URL` と `OPENAI_API_KEY` 環境変数が必要です。

```bash
cd backend
uv run python -m scripts.setup_anchors
```

### 4.2 有名論文のシードデータ投入
アプリ上に即座に表示させるため、著名なAI論文（Transformer, ResNetなど）をArxiv APIから強制取得してDBに書き込みます。

```bash
cd backend
# 関連度の高い過去の論文をカテゴリ毎に100件ずつ強制取得＆LLM分析
uv run python -m scripts.seed_papers
```
※ この処理にはGemini 2.0 FlashとOpenAIのAPIコールが含まれるため、数分〜10分程度かかります。

---

## 5. フロントエンドの環境変数設定 & ビルド

デプロイされたバックエンドの情報をフロントエンドの `.env` (または `.env.local`, `.env.production`) に設定します。

```env
# frontend/.env
EXPO_PUBLIC_API_URL=https://xxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/api/v1
EXPO_PUBLIC_COGNITO_USER_POOL_ID=ap-northeast-1_xxxxxxxxx
EXPO_PUBLIC_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxx
```

設定後、EAS (Expo Application Services) などを用いてアプリをビルドします（もしくはローカルでプレビュー）。

```bash
cd frontend
npm install

# ローカルでの動作確認
npm start
```

---

## 6. バッチ処理の確認

毎日動作する「論文自動キュレーションバッチ」が正常に動くか手動でテストします。

1. AWS Console > Lambda へ移動
2. `BatchStack` に含まれる関数 (例: `BatchStack-PipelineLambda...`) を選択
3. 「テスト」タブから空イベント `{}` で実行をクリック
4. 数分後、CloudWatch Logs にてエラーなく `run_pipeline` が完了しているか確認

---

## 7. 最終動作確認 (E2E チェック)

アプリを立ち上げ、以下の主要機能にアクセスできるか確認して完了です。
- [ ] ログイン/新規登録ができること
- [ ] ホーム画面に先ほどシードした論文リストが表示されること
- [ ] 論文をタップし、要約や図表が表示されること（閲覧履歴としてカウントされること）
- [ ] お気に入り登録・解除ができること
- [ ] 設定画面で統計データ（閲覧数など）が表示されること
