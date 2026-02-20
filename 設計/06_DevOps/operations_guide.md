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

## 3. データベースの初期化とマイグレーション (踏み台経由)

インフラデプロイにより構築されたRDS (PostgreSQL) に対して、テーブルの作成と拡張機能(pgvector)の有効化を行います。
本環境は完全にプライベートなVPC内にあるため、セキュリティの観点から **SSM (Systems Manager) を用いた踏み台ポートフォワーディング** を利用してローカルのターミナルから操作を行います。

### 3.1 事前準備: Session Manager Plugin のインストール
Mac(ローカルPC)上でポートフォワーディングを行うために、以下のプラグインをインストールします。
```bash
brew install awscli session-manager-plugin
```

### 3.2 踏み台を経由したポートのトンネル接続
CDKのデプロイで作成された踏み台(Bastion Host) のインスタンスIDと、RDSのエンドポイントを使い、トンネルを開通させます。（ターミナルを立ち上げっぱなしにします）

```bash
aws ssm start-session \
    --target <BASTION_INSTANCE_ID> \
    --document-name AWS-StartPortForwardingSessionToRemoteHost \
    --parameters '{"host":["<RDS_ENDPOINT>"],"portNumber":["5432"],"localPortNumber":["15432"]}'
```
※ `<BASTION_INSTANCE_ID>` はCDKの出力 `AiResearch-BastionInstanceId` に表示されます。
※ `<RDS_ENDPOINT>` はCDKの出力 `AiResearch-DbEndpoint` に表示されます。

### 3.3 Alembic によるマイグレーション実行
**別のターミナル**を開き、`host`を `localhost`、ポートを先ほどフォワードした `15432` に設定してマイグレーションを実行します。

```bash
cd backend

# DATABASE_URL環境変数にローカルPCあてのポートフォワードURLを設定
# パスワードはAWS Secrets Managerで確認、またはAWSコンソールで初期設定したもの
export DATABASE_URL="postgresql://postgres:PASSWORD@localhost:15432/ai_research"

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

デプロイされたバックエンドの情報をフロントエンドの [.env](file:///Users/suenagakazuya/Documents/AI_News_App/frontend/.env) (または `.env.local`, `.env.production`) に設定します。

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
4. 数分後、CloudWatch Logs にてエラーなく [run_pipeline](file:///Users/suenagakazuya/Documents/AI_News_App/backend/batch/pipeline.py#23-192) が完了しているか確認

---

## 7. 最終動作確認 (E2E チェック)

アプリを立ち上げ、以下の主要機能にアクセスできるか確認して完了です。
- [ ] ログイン/新規登録ができること
- [ ] ホーム画面に先ほどシードした論文リストが表示されること
- [ ] 論文をタップし、要約や図表が表示されること（閲覧履歴としてカウントされること）
- [ ] お気に入り登録・解除ができること
- [ ] 設定画面で統計データ（閲覧数など）が表示されること

---

## 8. 運用における監視ポイント (Operations & Monitoring)

AI処理や外部APIへの依存が多い本アプリケーションでは、AWS運用時に以下のポイントを重点的に監視（CloudWatch Logs / Metrics）する必要があります。

### 1. Batch Pipeline (Lambda) の実行状況
日次バッチ（`BatchStack-PipelineLambda`）は外部API(arXiv, Gemini)を大量に呼び出します。以下のエラーやメトリクスに注意が必要です。
* **Lambda Timeout (実行時間の超過)**
  * PDFのダウンロード(httpx)やGemini APIの生成待ちでハングするリスクがあります。Lambdaの最大実行時間（通常15分等）に達していないか監視します。
* **CloudWatch Logs の特定エラー文字列の監視 (Metric Filters)**
  以下の文字列をCloudWatch上でアラート設定しておくことを推奨します。
  * `"PDF download failed"` : arXivのサーバーダウンや一時的なアクセス制限。
  * `"Post-L3 paper processing timed out"` : PDF分析時の無限ハングを強制終了したケース。頻発する場合はタイムアウト値(`70.0`, `300`秒)の見直しが必要です。
  * `"L3 API error, retrying" / "Post-L3 API error, retrying"` : Gemini APIの503エラーやレートリミット(429)。
  * `"ValidationError"` : Geminiがシステムプロンプトやスキーマ(`L3Response` / `DetailReview`)に従わず、想定外のJSONを返却したケース。プロンプトの調整が必要になります。

### 2. 外部APIの利用制限 (Rate Limit / Quotas)
* **arXiv API / PDF Download**
  * arXivは連続アクセスに厳しく、`httpx.get`時にIPブロック(403 Forbiddenなど)を受けるとバッチが全滅します。エラーログが増加した場合、`L1_REQUEST_INTERVAL_MS` や `L3_CONCURRENCY` などの並列度・間隔調整が必要です。
* **Gemini (Google AI Studio)**
  * Google AI Studioのダッシュボードで、**RPM (Requests per minute)**, **TPM (Tokens per minute)**, **RPD (Requests per day)** が上限に達していないかを定期監視します。上限にあたる場合は有償プランへの移行を検討します。

### 3. Database (Amazon RDS / PostgreSQL)
* **データベース接続数 (DatabaseConnections)**
  * 非同期処理(`asyncio.gather`)で大量のタスクを並列化しているため、Lambdaからの非同期コネクション(`psycopg.AsyncConnection`)が急増してRDSの「Too many connections」にならないか監視します。
* **ストレージ容量 (FreeStorageSpace)**
  * `pgvector`によるベクトルデータ(`embedding`列)や、Markdownによる全文分析(`detail_review`)はテキスト/ベクトルデータサイズが大きくなりがちです。日次でデータが蓄積していくため、ストレージアラート(例: 残り20%以下)を設定します。

### 4. Amazon S3 (図表抽出画像)
* PyMuPDFで抽出した大量の図表画像がS3(`FIGURE_BUCKET`)に日次でアップロードされます。
* 不要になった過去論文の画像を消すライフサイクルルール(例: 1年経過したプレフィックスを自動削除)を設定しないと、ストレージコストが増大する点に留意してください。
