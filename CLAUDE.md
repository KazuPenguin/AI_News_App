# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Research OS — arXiv論文を自動収集・キュレーション・多角的解説する日本語モバイルアプリ。3段階フィルタリングパイプライン (L1: arXiv API キーワード → L2: pgvector 類似度選別 → L3: Gemini LLM分析) で論文を選別し、AI/数学/ビジネスの3視点で解説を生成する。

## Architecture

**3層構成: frontend / backend / infra**

- **frontend/**: React Native (Expo) モバイルアプリ。現在スキャフォールド段階。
- **backend/**: Python 3.13、FastAPI ベース。`uv` でパッケージ管理。
  - `api/handler.py` — API Lambda エントリーポイント (API Gateway proxy統合)。Mangum でFastAPIをLambdaアダプタ。
  - `batch/handler.py` — バッチ Lambda エントリーポイント (EventBridge トリガー、平日 UTC 21:00)。arXiv取得→L2→L3→図表抽出。
  - `tests/` — pytest テスト。
- **infra/**: AWS CDK (TypeScript) による IaC。6スタック構成:

**CDK スタック依存関係:**
```
NetworkStack (VPC, SG) ─→ DatabaseStack (RDS PostgreSQL 16 + pgvector)
      │                         │
      ├─────────────────────────┼──→ BatchStack (Lambda + EventBridge)
      │                         │
      └─→ ApiStack (Lambda + API Gateway + Cognito Authorizer)
                                      ↑
StorageStack (S3 + CloudFront) ──→ BatchStack
AuthStack (Cognito User Pool)  ──→ ApiStack
```

- API Lambda は Docker イメージデプロイ (`backend/Dockerfile`)
- バッチ Lambda は `backend/batch/` を直接 zip デプロイ
- リージョン: `ap-northeast-1`

## Commands

### Backend (Python)

```bash
# 依存インストール
cd backend && uv sync

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Format チェック (CI用)
uv run ruff format --check .

# 型チェック (strict mode)
uv run mypy .

# テスト全実行
uv run pytest

# 単一テスト実行
uv run pytest tests/test_api_handler.py
uv run pytest tests/test_api_handler.py::TestHealthEndpoint::test_returns_200
```

### Infra (CDK / TypeScript)

```bash
cd infra

# 依存インストール
npm ci

# TypeScript 型チェック
npx tsc --noEmit

# テスト
npm test

# CDK synth (全スタック検証)
npx cdk synth --all --quiet
```

### Frontend (Expo)

```bash
cd frontend
npm install
npm start
```

## Code Style

- **Python**: ruff (line-length=100, target py313)。ルールは `ruff.toml` 参照。mypy strict mode。
- **TypeScript**: strict mode (`tsconfig.json`)。module: NodeNext。
- **設計ドキュメント**: `設計/` ディレクトリに日本語で記載。コード内コメントも日本語。

## Key Design Documents

設計ドキュメントは `設計/` に集約。CDKスタック内のコメントから各設計書を参照している:
- `api_specification.md` — REST API 12エンドポイント定義
- `database_schema.md` — DB物理設計、pgvector HNSW インデックス
- `security_architecture.md` — 認証 (Cognito OAuth 2.0 + PKCE)、暗号化、IAM
- `LLM_Refinement.md` — L3 LLM分析設計
- `agent_design.md` — Gemini エージェント設計
- `設計計画.md` (ルート) — 開発ロードマップ (Phase 1-6)
