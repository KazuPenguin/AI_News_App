# AWS インフラストラクチャ実装仕様書

> **最終更新**: 2026-02-20
> **対象**: CDK 実装コード (`infra/lib/*.ts`) に基づく、現在デプロイされている AWS リソースの実装仕様

---

## 1. 概要

本プロジェクト「AI Research OS」のインフラは **AWS CDK (TypeScript)** で IaC 管理されている。
6 つの CDK スタックに分割し、依存関係に基づく順序デプロイを行う。
リージョンは `ap-northeast-1` (東京) 固定。

### スタック一覧

| # | スタック名 | 役割 | 依存先 |
|:--|:--|:--|:--|
| 1 | **NetworkStack** | VPC / サブネット / NAT / SG / 踏み台 | なし |
| 2 | **DatabaseStack** | RDS PostgreSQL 16 + pgvector | NetworkStack |
| 3 | **StorageStack** | S3 (図表) + CloudFront CDN | なし |
| 4 | **AuthStack** | Cognito User Pool + OAuth | なし |
| 5 | **BatchStack** | バッチ Lambda + EventBridge | Network, Database, Storage |
| 6 | **ApiStack** | API Lambda + API Gateway + Cognito Authorizer | Network, Database, Auth |

### デプロイ順序

```
1. NetworkStack ─┬─→ 2. DatabaseStack ─┬─→ 5. BatchStack
                 │                      └─→ 6. ApiStack
3. StorageStack ─────────────────────────→ 5. BatchStack
4. AuthStack ────────────────────────────→ 6. ApiStack
```

> StorageStack / AuthStack は NetworkStack と並行デプロイ可能。

---

## 2. NetworkStack

**ソース**: `infra/lib/network-stack.ts` (157 行)

### 2.1 VPC

| 項目 | 値 | 備考 |
|:--|:--|:--|
| CIDR | `10.0.0.0/16` | 65,536 IP |
| AZ 数 | 2 | `maxAzs: 2` → ap-northeast-1a / 1c |
| Public サブネット | 2 (各 AZ に 1) | `cidrMask: 24`、NAT GW / IGW 配置 |
| Private サブネット | 2 (各 AZ に 1) | `PRIVATE_WITH_EGRESS`、Lambda / RDS / Bastion 配置 |
| NAT Gateway | **1** | コスト対策 (~$32/月)。1 AZ のみ |
| Internet Gateway | CDK 自動作成 | Public サブネット付随 |

### 2.2 踏み台 (Bastion Host)

| 項目 | 値 |
|:--|:--|
| リソース | `ec2.BastionHostLinux` |
| インスタンスタイプ | `t4g.nano` |
| 配置 | Private サブネット (`PRIVATE_WITH_EGRESS`) |
| 用途 | SSM Session Manager 経由でのポートフォワーディング (DB マイグレーション / シード投入) |

### 2.3 セキュリティグループ

全 SG で `allowAllOutbound: false` を設定し、明示的なルールのみ許可。

#### sg-lambda (API Lambda 用)

| 方向 | ポート | 対象 | 用途 |
|:--|:--|:--|:--|
| Egress | TCP 443 | `0.0.0.0/0` | HTTPS (AWS サービス / 外部 API) |
| Egress | TCP 5432 | sg-rds | PostgreSQL 接続 |
| Ingress | — | — | なし (API GW → Lambda は VPC 外から invoke) |

#### sg-batch (バッチ Lambda 用)

| 方向 | ポート | 対象 | 用途 |
|:--|:--|:--|:--|
| Egress | TCP 443 | `0.0.0.0/0` | HTTPS (arXiv / OpenAI / Gemini API) |
| Egress | TCP 5432 | sg-rds | PostgreSQL 接続 |
| Ingress | — | — | なし (EventBridge → Lambda は VPC 外から invoke) |

#### sg-rds (RDS 用)

| 方向 | ポート | 対象 | 用途 |
|:--|:--|:--|:--|
| Ingress | TCP 5432 | sg-lambda | API Lambda からの DB 接続 |
| Ingress | TCP 5432 | sg-batch | Batch Lambda からの DB 接続 |
| Ingress | TCP 5432 | Bastion SG | 踏み台からの DB 接続 |
| Egress | — | — | なし |

### 2.4 CloudFormation Outputs

| Output 名 | Export 名 | 内容 |
|:--|:--|:--|
| `VpcId` | `AiResearch-VpcId` | VPC ID |
| `SgLambdaId` | `AiResearch-SgLambdaId` | API Lambda 用 SG ID |
| `SgBatchId` | `AiResearch-SgBatchId` | Batch Lambda 用 SG ID |
| `SgRdsId` | `AiResearch-SgRdsId` | RDS 用 SG ID |
| `BastionInstanceId` | `AiResearch-BastionInstanceId` | 踏み台 EC2 インスタンス ID |

---

## 3. DatabaseStack

**ソース**: `infra/lib/database-stack.ts` (130 行)

### 3.1 RDS PostgreSQL

| 項目 | 値 | 備考 |
|:--|:--|:--|
| エンジン | PostgreSQL 16 | pgvector 拡張対応 |
| インスタンスタイプ | `db.t4g.micro` | 開発環境向け (2 vCPU, 1 GB RAM) |
| 配置 | Private サブネット (`PRIVATE_WITH_EGRESS`) | |
| セキュリティグループ | sg-rds | |
| データベース名 | `ai_research` | |
| マスターユーザー名 | `postgres` | |

### 3.2 認証情報

| 項目 | 値 |
|:--|:--|
| 管理方法 | `rds.Credentials.fromGeneratedSecret('postgres')` |
| Secret 名 | `ai-research/rds-credentials` |
| 保管先 | AWS Secrets Manager (自動生成パスワード) |

### 3.3 ストレージ

| 項目 | 値 |
|:--|:--|
| 初期容量 | 20 GB |
| オートスケーリング上限 | 50 GB |
| ストレージタイプ | gp3 |
| 暗号化 | AES-256 (AWS KMS マネージドキー) |

### 3.4 可用性・バックアップ

| 項目 | 値 | 備考 |
|:--|:--|:--|
| Multi-AZ | **false** | 開発環境。本番は true に変更 |
| バックアップ保持期間 | 7 日 | |
| バックアップウィンドウ | UTC 18:00-18:30 | JST 03:00 (低負荷時間帯) |
| メンテナンスウィンドウ | 日曜 UTC 19:00-19:30 | JST 月曜 04:00 |
| 削除保護 | false | 開発環境。本番は true |
| RemovalPolicy | DESTROY | 開発環境。本番は RETAIN |

### 3.5 モニタリング

| 項目 | 値 |
|:--|:--|
| Performance Insights | 有効 (7 日保持 / 無料枠) |
| CloudWatch ログエクスポート | `postgresql` ログ |

### 3.6 カスタムパラメータグループ

| パラメータ | 値 | 用途 |
|:--|:--|:--|
| `maintenance_work_mem` | `256000` (256 MB) | pgvector HNSW インデックス構築 |
| `log_min_duration_statement` | `1000` (1 秒) | スロークエリログ |

### 3.7 CloudFormation Outputs

| Output 名 | Export 名 | 内容 |
|:--|:--|:--|
| `DbEndpoint` | `AiResearch-DbEndpoint` | RDS エンドポイント |
| `DbPort` | `AiResearch-DbPort` | RDS ポート (5432) |
| `DbSecretArn` | `AiResearch-DbSecretArn` | Secrets Manager ARN |
| `DbInstanceId` | `AiResearch-DbInstanceId` | RDS インスタンス識別子 |

---

## 4. StorageStack

**ソース**: `infra/lib/storage-stack.ts` (107 行)

### 4.1 S3 バケット (論文図表)

| 項目 | 値 |
|:--|:--|
| バケット名 | `ai-research-figures-{ACCOUNT_ID}` |
| 暗号化 | SSE-S3 |
| パブリックアクセス | 完全ブロック (`BLOCK_ALL`) |
| バージョニング | 無効 |
| RemovalPolicy | **RETAIN** (誤削除防止) |

#### ライフサイクルルール

| ルール名 | 条件 | アクション |
|:--|:--|:--|
| `TransitionToIA` | 90 日経過 | S3 Standard → S3 Infrequent Access へ移行 |

#### CORS 設定

| 項目 | 値 |
|:--|:--|
| 許可メソッド | `GET` |
| 許可オリジン | `*` (モバイルアプリからの画像直接表示) |
| 許可ヘッダー | `*` |
| max-age | 3,600 秒 |

### 4.2 CloudFront ディストリビューション

| 項目 | 値 |
|:--|:--|
| オリジンアクセス | OAC (Origin Access Control) |
| ビューワープロトコル | HTTPS リダイレクト |
| 最低 TLS | TLS 1.2 (2021 ポリシー) |
| HTTP バージョン | HTTP/2 + HTTP/3 |

#### キャッシュポリシー (`AiResearch-FigureCache`)

| 項目 | 値 |
|:--|:--|
| デフォルト TTL | 30 日 |
| 最大 TTL | 365 日 |
| 最小 TTL | 1 日 |

### 4.3 CloudFormation Outputs

| Output 名 | Export 名 | 内容 |
|:--|:--|:--|
| `FigureBucketName` | `AiResearch-FigureBucketName` | S3 バケット名 |
| `FigureBucketArn` | `AiResearch-FigureBucketArn` | S3 バケット ARN |
| `CdnDomainName` | `AiResearch-CdnDomainName` | CloudFront ドメイン |
| `CdnDistributionId` | `AiResearch-CdnDistributionId` | CloudFront ディストリビューション ID |

---

## 5. AuthStack

**ソース**: `infra/lib/auth-stack.ts` (154 行)

### 5.1 Cognito User Pool

| 項目 | 値 |
|:--|:--|
| User Pool 名 | `ai-research-user-pool` |
| セルフサインアップ | 有効 |
| サインインエイリアス | メールアドレス |
| メール自動検証 | 有効 |
| アカウント復旧 | メールのみ |
| RemovalPolicy | **RETAIN** |

#### パスワードポリシー

| 項目 | 値 |
|:--|:--|
| 最小長 | 8 文字 |
| 小文字必須 | あり |
| 大文字必須 | あり |
| 数字必須 | あり |
| 記号必須 | **なし** |

#### ユーザー属性

| 属性 | 必須 | 変更可能 | 備考 |
|:--|:--|:--|:--|
| `email` | はい | はい | 標準属性 |
| `name` (fullname) | いいえ | はい | 標準属性 |
| `custom:auth_provider` | — | いいえ | カスタム属性 (不変) |

#### メール送信

| 項目 | 値 | 備考 |
|:--|:--|:--|
| 送信元 | Cognito デフォルト | 本番では SES に切り替え推奨 |

### 5.2 ソーシャルログイン (未有効化)

以下のプロバイダはコード上にコメントアウトで定義済み。OAuth クレデンシャル取得後に有効化する。

| プロバイダ | 状態 | スコープ |
|:--|:--|:--|
| Google | **コメントアウト** | openid, email, profile |
| Apple | **コメントアウト** | openid, email, name |

### 5.3 App Client

| 項目 | 値 |
|:--|:--|
| クライアント名 | `ai-research-mobile-app` |
| OAuth フロー | Authorization Code Grant |
| 認証フロー | SRP (Secure Remote Password) |
| スコープ | openid, email, profile |
| コールバック URL | `myapp://callback` |
| ログアウト URL | `myapp://signout` |
| ID Token 有効期限 | 1 時間 |
| Access Token 有効期限 | 1 時間 |
| Refresh Token 有効期限 | 30 日 |
| ユーザー存在エラー防止 | 有効 (`preventUserExistenceErrors`) |
| サポート IdP | Cognito (Google / Apple は追加予定) |

### 5.4 Hosted UI

| 項目 | 値 |
|:--|:--|
| ドメインプレフィックス | `ai-research-os` |
| URL | `https://ai-research-os.auth.ap-northeast-1.amazoncognito.com` |

### 5.5 CloudFormation Outputs

| Output 名 | Export 名 | 内容 |
|:--|:--|:--|
| `UserPoolId` | `AiResearch-UserPoolId` | User Pool ID |
| `UserPoolArn` | `AiResearch-UserPoolArn` | User Pool ARN |
| `AppClientId` | `AiResearch-AppClientId` | App Client ID |
| `CognitoDomainUrl` | `AiResearch-CognitoDomainUrl` | Hosted UI URL |

---

## 6. BatchStack

**ソース**: `infra/lib/batch-stack.ts` (141 行)

### 6.1 バッチ Lambda 関数

| 項目 | 値 |
|:--|:--|
| 関数タイプ | `DockerImageFunction` |
| Dockerfile | `backend/Dockerfile.batch` |
| ベースイメージ | `public.ecr.aws/lambda/python:3.13` |
| メモリ | 1,024 MB |
| タイムアウト | 15 分 (Lambda 最大) |
| 配置 | Private サブネット + sg-batch |
| ハンドラー | `batch.handler.main` |

#### 環境変数

| 変数名 | 値 / ソース |
|:--|:--|
| `DB_SECRET_ARN` | DatabaseStack の `dbSecret.secretArn` |
| `FIGURE_BUCKET` | StorageStack の `figureBucket.bucketName` |
| `OPENAI_SECRET_ARN` | `arn:aws:secretsmanager:{region}:{account}:secret:ai-research/openai-api-key` |
| `GEMINI_SECRET_ARN` | `arn:aws:secretsmanager:{region}:{account}:secret:ai-research/gemini-api-key` |

#### IAM 権限

| 権限 | リソース | 備考 |
|:--|:--|:--|
| `secretsmanager:GetSecretValue` | `ai-research/rds-credentials` | `dbSecret.grantRead()` |
| `secretsmanager:GetSecretValue` | `ai-research/openai-api-key*` | ワイルドカード (サフィックス自動付与のため) |
| `secretsmanager:GetSecretValue` | `ai-research/gemini-api-key*` | 同上 |
| `s3:PutObject` 等 | `ai-research-figures-{ACCOUNT_ID}/figures/*` | `grantWrite('figures/*')` |

#### ログ

| 項目 | 値 |
|:--|:--|
| ロググループ | `BatchHandlerLogGroup` |
| 保持期間 | 14 日 |
| RemovalPolicy | DESTROY |

### 6.2 EventBridge ルール

| 項目 | 値 |
|:--|:--|
| ルール名 | `ai-research-daily-batch` |
| スケジュール | `cron(0 21 ? * MON-FRI *)` |
| 実行時刻 | 毎日 UTC 21:00 (JST 06:00)、月曜〜金曜 |
| リトライ回数 | 2 |

> arXiv は UTC 20:00 頃に更新されるため、1 時間後の UTC 21:00 に実行。

### 6.3 CloudFormation Outputs

| Output 名 | Export 名 | 内容 |
|:--|:--|:--|
| `BatchFunctionName` | `AiResearch-BatchFunctionName` | Lambda 関数名 |
| `BatchFunctionArn` | `AiResearch-BatchFunctionArn` | Lambda 関数 ARN |
| `EventBridgeRuleName` | `AiResearch-EventBridgeRuleName` | EventBridge ルール名 |

---

## 7. ApiStack

**ソース**: `infra/lib/api-stack.ts` (182 行)

### 7.1 API Lambda 関数

| 項目 | 値 |
|:--|:--|
| 関数タイプ | `DockerImageFunction` |
| Dockerfile | `backend/Dockerfile` |
| ベースイメージ | `public.ecr.aws/lambda/python:3.13` |
| メモリ | 512 MB |
| タイムアウト | 30 秒 |
| 配置 | Private サブネット + sg-lambda |
| ハンドラー | `api.handler.main` (Mangum で FastAPI をラップ) |

#### 環境変数

| 変数名 | 値 / ソース |
|:--|:--|
| `DB_SECRET_ARN` | DatabaseStack の `dbSecret.secretArn` |

#### IAM 権限

| 権限 | リソース |
|:--|:--|
| `secretsmanager:GetSecretValue` | `ai-research/rds-credentials` |

#### ログ

| 項目 | 値 |
|:--|:--|
| ロググループ | `ApiHandlerLogGroup` |
| 保持期間 | 14 日 |
| RemovalPolicy | DESTROY |

### 7.2 API Gateway (REST API)

| 項目 | 値 |
|:--|:--|
| API 名 | `ai-research-api` |
| ステージ名 | `v1` |
| スロットリング (レート) | 100 リクエスト/秒 |
| スロットリング (バースト) | 200 リクエスト |
| ログレベル | INFO |
| データトレース | 無効 (リクエストボディのログ無効化) |
| メトリクス | 有効 |

#### CORS 設定

| 項目 | 値 |
|:--|:--|
| 許可オリジン | `*` (全オリジン) |
| 許可メソッド | 全メソッド |
| 許可ヘッダー | `Content-Type`, `Authorization` |
| max-age | 1 時間 |

### 7.3 Cognito Authorizer

| 項目 | 値 |
|:--|:--|
| 名前 | `ai-research-cognito-authorizer` |
| IdentitySource | `method.request.header.Authorization` |
| 対象 User Pool | AuthStack の `userPool` |

### 7.4 エンドポイント定義

全エンドポイントは Lambda Proxy 統合 (`proxy: true`)。`/health` を除き Cognito 認証必須。

| パス | メソッド | 認証 | 説明 |
|:--|:--|:--|:--|
| `/papers` | GET | Cognito | 論文一覧 (フィルタ / ページネーション) |
| `/papers/{arxiv_id}` | GET | Cognito | 論文詳細 (3 視点解説 / レベル別テキスト) |
| `/papers/{arxiv_id}/figures` | GET | Cognito | 図表一覧 |
| `/papers/{arxiv_id}/view` | POST | Cognito | 閲覧記録 |
| `/categories` | GET | Cognito | カテゴリ一覧 |
| `/bookmarks` | GET | Cognito | お気に入り一覧 |
| `/bookmarks` | POST | Cognito | お気に入り追加 |
| `/bookmarks/{id}` | DELETE | Cognito | お気に入り削除 |
| `/users/me` | GET | Cognito | ユーザー情報 |
| `/users/me/settings` | PUT | Cognito | ユーザー設定更新 |
| `/users/me/stats` | GET | Cognito | ユーザー統計 |
| `/health` | GET | なし | ヘルスチェック |

### 7.5 CloudFormation Outputs

| Output 名 | Export 名 | 内容 |
|:--|:--|:--|
| `ApiUrl` | `AiResearch-ApiUrl` | API Gateway エンドポイント URL |
| `ApiId` | `AiResearch-ApiId` | REST API ID |
| `ApiFunctionName` | `AiResearch-ApiFunctionName` | API Lambda 関数名 |

---

## 8. Secrets Manager 一覧

| シークレット名 | 用途 | 管理方法 |
|:--|:--|:--|
| `ai-research/rds-credentials` | RDS 接続情報 (host, port, username, password, dbname) | CDK 自動生成 |
| `ai-research/openai-api-key` | OpenAI API キー (L2 Embedding) | 手動登録 |
| `ai-research/gemini-api-key` | Gemini API キー (L3 / Post-L3) | 手動登録 |

---

## 9. CI/CD パイプライン (GitHub Actions)

### 9.1 ワークフロー一覧

| ワークフロー | ファイル | トリガー | 内容 |
|:--|:--|:--|:--|
| **CI** | `.github/workflows/ci.yml` | PR / main push | Backend lint + type check + test, CDK synth |
| **Deploy** | `.github/workflows/deploy.yml` | main push (`infra/**`, `backend/**`) | CDK diff → 手動承認 → CDK deploy |
| **Security** | `.github/workflows/security.yml` | PR / main push | trufflehog シークレットスキャン |
| **Frontend CI** | `.github/workflows/frontend.yml` | main push / PR (`frontend/**`) | type-check, lint, test |

### 9.2 CI ワークフロー詳細

| ジョブ | ランナー | ステップ |
|:--|:--|:--|
| `cdk-check` | ubuntu-latest (Node 22) | `npm ci` → `tsc --noEmit` → `npm test` → `cdk synth --all --quiet` |
| `backend-check` | ubuntu-latest (uv) | `uv sync` → `ruff check` → `ruff format --check` → `mypy` → `pytest` |

### 9.3 Deploy ワークフロー詳細

| ジョブ | 条件 | ステップ |
|:--|:--|:--|
| `cdk-diff` | 自動 | AWS OIDC 認証 → `cdk diff --all` → GitHub Summary に出力 |
| `deploy` | `cdk-diff` 後 + **手動承認** (GitHub Environments: `production`) | AWS OIDC 認証 → `cdk deploy --all --require-approval never` |

### 9.4 AWS 認証方式

| 項目 | 値 |
|:--|:--|
| 方式 | **OIDC (OpenID Connect)** |
| ロール ARN | `secrets.AWS_ROLE_ARN` (GitHub Secrets に保管) |
| 権限 | `id-token: write` (OIDC トークン取得) |

---

## 10. Docker ビルド構成

### 10.1 API Lambda (`backend/Dockerfile`)

```dockerfile
FROM public.ecr.aws/lambda/python:3.13
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml
COPY api/ ${LAMBDA_TASK_ROOT}/api/
COPY utils/ ${LAMBDA_TASK_ROOT}/utils/
CMD [ "api.handler.main" ]
```

### 10.2 Batch Lambda (`backend/Dockerfile.batch`)

```dockerfile
FROM public.ecr.aws/lambda/python:3.13
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml
COPY batch/ ${LAMBDA_TASK_ROOT}/batch/
COPY utils/ ${LAMBDA_TASK_ROOT}/utils/
CMD [ "batch.handler.main" ]
```

> 両方とも `uv` で依存解決。`--no-dev` は Batch Dockerfile では省略されている（API 側も同様）。

---

## 11. コスト概算 (開発環境)

| リソース | 月額概算 | 備考 |
|:--|:--|:--|
| NAT Gateway | ~$32 | 1 AZ, $0.045/h + データ転送 |
| RDS db.t4g.micro | ~$12 | 単一 AZ, gp3 20GB |
| Bastion t4g.nano | ~$3 | $0.0042/h |
| S3 | ~$1 | 年間 ~10GB |
| CloudFront | ~$1 | 低トラフィック想定 |
| Lambda (API) | ~$1 | リクエスト数に依存 |
| Lambda (Batch) | ~$1 | 1 日 1 回, ~5-10 分 |
| Secrets Manager | ~$2 | 3 シークレット × $0.40 + API コール |
| API Gateway | ~$1 | リクエスト数に依存 |
| Cognito | 無料 | 50,000 MAU まで無料 |
| CloudWatch | ~$1 | ログ保持 14 日 |
| **合計** | **~$55/月** | |

---

## 12. 本番環境に向けた変更点

| 項目 | 現状 (開発) | 本番推奨 |
|:--|:--|:--|
| NAT Gateway 数 | 1 | 2 (各 AZ に 1 つ) |
| RDS Multi-AZ | false | true |
| RDS インスタンスタイプ | db.t4g.micro | db.t4g.small 以上 |
| RDS 削除保護 | false | true |
| RDS RemovalPolicy | DESTROY | RETAIN |
| Cognito メール送信 | Cognito デフォルト | SES |
| Google / Apple ログイン | コメントアウト | 有効化 |
| VPC Flow Logs | 未設定 | 有効化 |
| VPC Endpoints | 未設定 | S3, Secrets Manager 等に追加 |
| API Gateway データトレース | false | false (維持) |
| CORS 許可オリジン | `*` | 特定ドメインに制限 |
| CloudFront WAF | 未設定 | 有効化推奨 |

---

## 13. CloudFormation Outputs 一覧 (全スタック)

デプロイ後に取得可能な全出力値をまとめる。

| Export 名 | スタック | 内容 |
|:--|:--|:--|
| `AiResearch-VpcId` | NetworkStack | VPC ID |
| `AiResearch-SgLambdaId` | NetworkStack | API Lambda SG ID |
| `AiResearch-SgBatchId` | NetworkStack | Batch Lambda SG ID |
| `AiResearch-SgRdsId` | NetworkStack | RDS SG ID |
| `AiResearch-BastionInstanceId` | NetworkStack | Bastion EC2 Instance ID |
| `AiResearch-DbEndpoint` | DatabaseStack | RDS エンドポイント |
| `AiResearch-DbPort` | DatabaseStack | RDS ポート |
| `AiResearch-DbSecretArn` | DatabaseStack | DB Secret ARN |
| `AiResearch-DbInstanceId` | DatabaseStack | RDS インスタンス ID |
| `AiResearch-FigureBucketName` | StorageStack | S3 バケット名 |
| `AiResearch-FigureBucketArn` | StorageStack | S3 バケット ARN |
| `AiResearch-CdnDomainName` | StorageStack | CloudFront ドメイン |
| `AiResearch-CdnDistributionId` | StorageStack | CloudFront ディストリビューション ID |
| `AiResearch-UserPoolId` | AuthStack | Cognito User Pool ID |
| `AiResearch-UserPoolArn` | AuthStack | Cognito User Pool ARN |
| `AiResearch-AppClientId` | AuthStack | Cognito App Client ID |
| `AiResearch-CognitoDomainUrl` | AuthStack | Cognito Hosted UI URL |
| `AiResearch-BatchFunctionName` | BatchStack | Batch Lambda 関数名 |
| `AiResearch-BatchFunctionArn` | BatchStack | Batch Lambda 関数 ARN |
| `AiResearch-EventBridgeRuleName` | BatchStack | EventBridge ルール名 |
| `AiResearch-ApiUrl` | ApiStack | API Gateway URL |
| `AiResearch-ApiId` | ApiStack | REST API ID |
| `AiResearch-ApiFunctionName` | ApiStack | API Lambda 関数名 |
