# CI/CD・自動化構成案 (CI/CD Specification)

## 1. 概要
本プロジェクト（AI Research OS）における、品質保証とデリバリー速度を最大化するためのCI/CDパイプライン設計を示す。
GitHub Actionsをメインのオーケストレーターとし、AWS CDKによるインフラ管理、Fastlane/EASによるモバイルアプリ配信を組み合わせる。

## 2. 全体戦略 (Workflow Strategy)

### 2.1 ブランチ戦略
*   **`main`**: 常にデプロイ可能な状態を保つプロダクションブランチ。
*   **`feature/*`**: 機能開発用ブランチ。`main`へのPR作成時にテストが実行される。
*   **`release/*` または Tag**: 本番環境（アプリストア/AWS本番環境）へのデプロイ・リリーストリガー。

### 2.2 パイプライン構成
| 対象 | タイミング | 実行内容 |
| :--- | :--- | :--- |
| **Backend** | PR作成時 | Lint (`ruff`), Test (`pytest`), Type Check (`mypy`) |
| | `main`マージ時 | Docker Image Build, ECR Push, Lambda Update (Dev) |
| | Release Tag | Production Deploy |
| **Frontend** | PR作成時 | Lint (`eslint`), Test (`jest`), Build Check |
| | `main`マージ時 | OTA Update (Expo Updates) - *Optional* |
| | Release Tag | Native Build (IPA/APK), Store Upload (TestFlight/Google Play Console) |
| **Infra** | PR作成時 | `cdk synth`, `cdk diff` (変更差分確認) |
| | `main`マージ時 | `cdk deploy` (自動適用) |

---

## 3. Backend Pipeline (Python / FastAPI)

### 3.1 ワークフロー詳細
*   **Linter & Formatter**: `ruff` を使用し、高速な静的解析を行う。
*   **Type Checking**: `mypy` による型安全性チェック。
*   **Testing**: `pytest` による単体テスト・結合テスト実行。
*   **Container**: `Dockerfile` のビルドチェック。

### 3.2 GitHub Actions 定義案 (`.github/workflows/backend.yml`)
1.  **Lint & Test Job**
    *   `python -m pip install poetry`
    *   `poetry install`
    *   `poetry run ruff check .`
    *   `poetry run mypy .`
    *   `poetry run pytest`
2.  **Deploy Job (CD)**
    *   *Conditions: Push to main*
    *   Configure AWS Credentials (OIDC)
    *   Login to Amazon ECR
    *   Build & Push Docker Image
    *   Update Lambda Function Code

---

## 4. Frontend Pipeline (React Native / Expo)

### 4.1 ワークフロー詳細
*   **Linter**: `eslint` (with Prettier)
*   **Testing**: `jest` (Unit Test), `maestro` (E2E Test - *Future Scope*)
*   **Build**: Expo Application Services (EAS) または Fastlane を使用。

### 4.2 GitHub Actions 定義案 (`.github/workflows/frontend.yml`)
1.  **Check Job**
    *   `npm ci`
    *   `npm run lint`
    *   `npm run test`
    *   `npm run type-check` (TypeScript)
2.  **Preview Deploy (Optional)**
    *   PR毎に Expo Go で確認可能なQRコードを発行コメント（`expo-github-action`利用）。
3.  **Production Build (Release)**
    *   *Conditions: Tag push (v*)*
    *   `eas build --platform all --profile production`
    *   または `fastlane android deploy` / `fastlane ios deploy`

---

## 5. Infrastructure Pipeline (AWS CDK)

### 5.1 ワークフロー詳細 (IaC)
インフラ変更の安全性確認を自動化する。

### 5.2 GitHub Actions 定義案 (`.github/workflows/infra.yml`)
1.  **Diff Job (PR)**
    *   `npm ci` (CDK dependencies)
    *   `npx cdk synth`
    *   `npx cdk diff`
    *   結果をPRへコメント通知（変更リソースの可視化）。
2.  **Deploy Job (Main)**
    *   *Conditions: Push to main*
    *   `npx cdk deploy --require-approval never`

---

## 6. セキュリティと認証

### 6.1 AWS認証 (OIDC)
*   AWS Access Key / Secret Key をGitHub Secretsに直接保存**しない**。
*   **OpenID Connect (OIDC)** を使用し、GitHub Actionsが一時的な認証トークンを取得する構成とする（セキュリティベストプラクティス）。

### 6.2 Secret管理
*   `DATABASE_URL` や API Key などの機密情報は GitHub Secrets に格納し、Actions 実行時に環境変数として注入する。

---

## 7. 今後の拡張 (Roadmap)
*   **E2E自動テスト**: Maestro 等を用いたUI操作の自動テスト組み込み。
*   **コスト通知**: AWSコストが予算を超過しそうな場合のSlack通知連携。
*   **依存パッケージ脆弱性スキャン**: Dependabot / Renovate の導入。
