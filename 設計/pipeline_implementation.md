# 論文キュレーション・パイプライン 実装記録

**実装日**: 2026-02-19
**対象**: 設計計画.md Phase 4 — パイプライン実装 + 詳細解説生成エンジン

---

## 実装ファイル一覧

### 基盤モジュール (utils/)

| ファイル | 内容 |
|---|---|
| `utils/models.py` | Pydantic データモデル — ArxivPaper, L2Paper, L2Result, L3Response, DetailReview, ExtractedFigure, BatchLogEntry |
| `utils/secrets.py` | Secrets Manager ラッパー — `@lru_cache` で DB接続情報・OpenAI/Gemini APIキーをキャッシュ取得 |
| `utils/db.py` | psycopg v3 同期/非同期接続管理 — Lambda 用1接続再利用パターン、`close_connections()` クリーンアップ |

### バッチ処理 (batch/)

| ファイル | 内容 |
|---|---|
| `batch/config.py` | 全設定定数 — 6クエリテンプレート、L2閾値(0.40)、importance重み、L3/Post-L3プロンプト、並列数 |
| `batch/l1_collector.py` | L1: arXiv API 収集 — 6クエリ順次実行、3秒間隔レートリミット、Atom XMLパース、arXiv ID重複排除 |
| `batch/l2_selector.py` | L2: pgvector 選別 — OpenAI バッチEmbedding、DB INSERT (ON CONFLICT)、コサイン類似度計算、importance算出 |
| `batch/l3_analyzer.py` | L3: Gemini LLM 分析 — 5並列 asyncio.Semaphore、200ms間隔、JSON Mode、指数バックオフ(3回リトライ) |
| `batch/post_l3_reviewer.py` | Post-L3: PDF全文分析 + 図表抽出 — 3並列、Gemini PDF入力、PyMuPDF画像抽出→S3、DB更新 |
| `batch/pipeline.py` | オーケストレーター — L1→L2→L3→Post-L3 を順次実行、fail-forward、batch_logs記録 |
| `batch/handler.py` | Lambda エントリーポイント — `asyncio.run(run_pipeline())` で非同期パイプライン実行 |

### デプロイ設定

| ファイル | 変更内容 |
|---|---|
| `backend/pyproject.toml` | 依存追加: google-genai, PyMuPDF, boto3, httpx, pytest-asyncio |
| `backend/Dockerfile.batch` | 新規作成: バッチLambda用 Docker イメージ (Python 3.13 Lambda base + uv) |
| `infra/lib/batch-stack.ts` | `lambda.Function` → `lambda.DockerImageFunction` に変更、Dockerfile.batch を参照 |

### テスト (53 tests 全パス)

| ファイル | テスト内容 | テスト数 |
|---|---|---|
| `tests/test_l1_collector.py` | XMLパース、arXiv ID抽出、重複排除、日付範囲計算 | 18 |
| `tests/test_l2_selector.py` | importance計算、閾値判定、重み係数検証 | 9 |
| `tests/test_l3_analyzer.py` | プロンプト構築、L3Response Pydanticバリデーション | 11 |
| `tests/test_pipeline.py` | オーケストレーション正常系、L1/L2エラー伝播、空パイプライン | 4 |
| `tests/test_batch_handler.py` | ハンドラー成功/失敗/レスポンス検証 (更新) | 3 |

---

## パイプライン実行フロー

```
EventBridge (UTC 21:00 Mon-Fri)
  → handler.main(event, context)
    → asyncio.run(pipeline.run_pipeline())
      → [SYNC]  L1: collect_papers()       6クエリ × 3秒間隔    → 100-250 papers
      → [SYNC]  L2: run_l2(papers)         バッチEmbed + SQL     → 30-125 passed
      → [ASYNC] L3: run_l3(l2_passed)      5並列 Gemini          → 10-30 relevant
      → [ASYNC] Post-L3: run_post_l3()     3並列 PDF+図表        → detail_review + figures
      → [SYNC]  batch_logs INSERT
    → close_connections()
```

---

## 設計判断

| 判断 | 選定 | 理由 |
|---|---|---|
| Gemini SDK | `google-genai` (新SDK) | async対応、PDF入力ネイティブサポート |
| HTTP client | `httpx` | async対応、PDF DLで使用 |
| PDF図表抽出 | `PyMuPDF` (`fitz`) | 高速、Lambdaで動作可能 |
| XMLパース | `xml.etree.ElementTree` | 標準ライブラリ、feedparser不要 |
| DB接続 | psycopg v3 sync/async | Lambda = 1接続再利用、プール不要 |
| バッチデプロイ | DockerImageFunction | PyMuPDF等のネイティブ依存をDockerで解決 |
| エラー戦略 | fail-forward | 各フェーズの例外をキャッチし次フェーズに空リストを渡す |

---

## 検証結果 (2026-02-19)

| チェック | 結果 |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 25 files already formatted |
| `uv run mypy .` | Success: no issues found in 26 source files |
| `uv run pytest -v` | 53 passed |
| `npx tsc --noEmit` (infra) | No errors |
| `npx cdk synth --all --quiet` | All stacks synthesized |
