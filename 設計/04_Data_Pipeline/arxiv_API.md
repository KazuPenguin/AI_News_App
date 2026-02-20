# L1 設計書：arXiv API データ収集

## 1. 概要
arXiv API を用いて、6大カテゴリに関連する論文メタデータを毎日自動取得する。
キーワード検索で**広めに**収集し、後段の L2（ベクトル）/ L3（LLM）で絞り込む「ファンネル型」の入口。

---

## 2. arXiv API 仕様サマリ

| 項目 | 値 |
|:---|:---|
| **Base URL** | `http://export.arxiv.org/api/query` |
| **メソッド** | GET / POST |
| **レスポンス形式** | Atom XML |
| **ページネーション** | `start`（0-based）+ `max_results` |
| **1リクエスト上限** | 推奨 1,000件、ハードリミット ~50,000件 |
| **レートリミット** | 3秒間隔を推奨（連続リクエスト時） |
| **日付フィルタ** | `submittedDate:[YYYYMMDDTTTT+TO+YYYYMMDDTTTT]`（GMT） |
| **検索フィールド** | `ti:`（タイトル）, `abs:`（要旨）, `au:`（著者）, `cat:`（カテゴリ）, `all:`（全文） |
| **Boolean演算子** | `AND`, `OR`, `ANDNOT` |
| **URLエスケープ** | `(` → `%28`, `)` → `%29`, `"` → `%22`, スペース → `+` |

---

## 3. 日次取得件数の見積もり

### 3.1 arXiv 投稿統計（2024年実績）

| 月 | CS全体 新規投稿数 | 日平均（営業日ベース ~22日） |
|:---|:---|:---|
| 2024/01 | 7,341 | ~334 |
| 2024/05 | 9,624 | ~437 |
| 2024/07 | 10,005 | ~455 |
| 2024/10 | 11,690 | ~531 |

### 3.2 対象カテゴリ別の推定日次件数

| カテゴリ | arXiv Code | 推定 日次件数 | 備考 |
|:---|:---|:---|:---|
| 基盤モデル | `cs.CL`, `cs.LG` | 80–150 | cs.CL + cs.LG は CS最大。ただしキーワードで絞るため実際は一部 |
| 学習・調整 | `cs.LG`, `cs.AI` | 30–60 | cs.LG と重複あり |
| エンジニアリング | `cs.SE`, `cs.CL` | 20–40 | RAG/Agent 関連は cs.CL にも多い |
| インフラ・最適化 | `cs.DC`, `cs.AR` | 10–30 | ニッチだが高品質 |
| 評価・安全性 | `cs.CL`, `cs.CR` | 15–30 | |
| 規制・社会 | `cs.CY` | 5–15 | 最小規模 |
| **合計（重複除外後）** | | **100–250件/日** | カテゴリ横断の重複を除外した推定値 |

### 3.3 ファンネル通過率の目標

```
L1（キーワード取得）: 100–250件/日
    ↓ L2 通過率 30–50%
L2（ベクトル選別）: 30–125件/日
    ↓ L3 通過率 30–50%
L3（LLM最終判定）: 10–50件/日 → アプリ配信
```

**L3到達率目標: 全体の10%以下** → 250件中25件以下が理想

---

## 4. クエリ設計

### 4.1 クエリ構成方針
- カテゴリ（`cat:`）とキーワード（`abs:` or `all:`）を `AND` で組み合わせる
- 6カテゴリを **個別クエリとして実行**し、結果をマージ後に重複排除する
  - 理由: 1本の巨大OR結合クエリはAPI仕様上不安定になる可能性がある

### 4.2 各カテゴリのクエリテンプレート

#### カテゴリ1: 基盤モデル
```
search_query=
  %28cat:cs.CL+OR+cat:cs.LG%29
  +AND+
  %28abs:%22Foundation+Model%22+OR+abs:%22Large+Language+Model%22+OR+abs:GPT+OR+abs:Llama+OR+abs:Gemini+OR+abs:Claude+OR+abs:Mistral+OR+abs:MoE+OR+abs:Mamba+OR+abs:SSM+OR+abs:RWKV+OR+abs:Transformer%29
  +AND+
  submittedDate:[{start}+TO+{end}]
&start=0&max_results=500&sortBy=submittedDate&sortOrder=descending
```

#### カテゴリ2: 学習・調整
```
search_query=
  %28cat:cs.LG+OR+cat:cs.AI%29
  +AND+
  %28abs:RLHF+OR+abs:RLAIF+OR+abs:%22Direct+Preference+Optimization%22+OR+abs:DPO+OR+abs:%22Chain+of+Thought%22+OR+abs:PEFT+OR+abs:LoRA+OR+abs:QLoRA+OR+abs:%22Model+Merging%22%29
  +AND+
  submittedDate:[{start}+TO+{end}]
&start=0&max_results=300&sortBy=submittedDate&sortOrder=descending
```

#### カテゴリ3: エンジニアリング
```
search_query=
  %28cat:cs.SE+OR+cat:cs.CL%29
  +AND+
  %28abs:%22Retrieval-Augmented+Generation%22+OR+abs:RAG+OR+abs:GraphRAG+OR+abs:%22Autonomous+Agent%22+OR+abs:%22Multi-Agent%22+OR+abs:%22Prompt+Engineering%22+OR+abs:DSPy%29
  +AND+
  submittedDate:[{start}+TO+{end}]
&start=0&max_results=300&sortBy=submittedDate&sortOrder=descending
```

#### カテゴリ4: インフラ・最適化
```
search_query=
  %28cat:cs.DC+OR+cat:cs.AR%29
  +AND+
  %28abs:vLLM+OR+abs:TGI+OR+abs:TensorRT+OR+abs:%22KV+Cache%22+OR+abs:%22Speculative+Decoding%22+OR+abs:Quantization+OR+abs:AWQ+OR+abs:GPTQ+OR+abs:%22On-Device%22+OR+abs:%22Edge+AI%22+OR+abs:%22GPU+optimization%22%29
  +AND+
  submittedDate:[{start}+TO+{end}]
&start=0&max_results=200&sortBy=submittedDate&sortOrder=descending
```

#### カテゴリ5: 評価・安全性
```
search_query=
  %28cat:cs.CL+OR+cat:cs.CR%29
  +AND+
  %28abs:%22LLM+Evaluation%22+OR+abs:Leaderboard+OR+abs:Hallucination+OR+abs:Jailbreak+OR+abs:%22Adversarial+Attack%22+OR+abs:Bias+OR+abs:%22Safety+Alignment%22%29
  +AND+
  submittedDate:[{start}+TO+{end}]
&start=0&max_results=200&sortBy=submittedDate&sortOrder=descending
```

#### カテゴリ6: 規制・社会
```
search_query=
  cat:cs.CY
  +AND+
  %28abs:%22AI+Regulation%22+OR+abs:%22EU+AI+Act%22+OR+abs:Copyright+OR+abs:Watermarking%29
  +AND+
  submittedDate:[{start}+TO+{end}]
&start=0&max_results=100&sortBy=submittedDate&sortOrder=descending
```

### 4.3 日付パラメータ `{start}` / `{end}` の設計

arXivは**米国東部時間 (ET) 14:00** に当日分を締め切り、**20:00頃** に公開される。

```
実行タイミング: 毎日 JST 11:00（= UTC 02:00 = ET 21:00）
取得範囲: 前日の UTC 00:00 〜 当日の UTC 00:00（24時間幅）

例: JST 2026/2/12 11:00 に実行する場合
  start = 202602110000
  end   = 202602120000
```

> **注意:** arXiv の `submittedDate` は初回投稿日。更新(replacement)は含まれない。
> 取りこぼし防止のため、48時間幅に広げて重複排除するオプションも検討。

---

## 5. レスポンスパース仕様

Atom XMLから以下のフィールドを抽出する。

| XML要素 | 取得データ | 型 | 備考 |
|:---|:---|:---|:---|
| `<id>` | arXiv URL | `str` | `http://arxiv.org/abs/XXXX.XXXXX` → IDを抽出 |
| `<title>` | 論文タイトル | `str` | 改行・余分な空白を正規化 |
| `<summary>` | Abstract | `str` | L2でEmbedding対象 |
| `<author><name>` | 著者リスト | `list[str]` | 全著者を配列で保持 |
| `<published>` | 発行日 | `datetime` | ISO 8601形式 |
| `<updated>` | 更新日 | `datetime` | 初版と異なれば改訂あり |
| `<link>` (type=pdf) | PDF URL | `str` | `rel="related"` かつ `title="pdf"` |
| `<arxiv:primary_category>` | 主カテゴリ | `str` | `cs.CL` 等 |
| `<category>` | 全カテゴリ | `list[str]` | クロスリスト含む |

---

## 6. 重複排除ロジック

6本のクエリ結果をマージするため、重複が発生する。

```python
# 重複排除の方針
deduplicated = {}
for paper in all_results:
    arxiv_id = extract_id(paper["id"])  # "2401.12345" 形式に正規化
    if arxiv_id not in deduplicated:
        deduplicated[arxiv_id] = paper
    else:
        # 既存エントリにカテゴリ情報をマージ（どのクエリでヒットしたか記録）
        deduplicated[arxiv_id]["matched_queries"].extend(paper["matched_queries"])
```

**`matched_queries`** フィールドにより、「この論文はカテゴリ1と4の両方でヒットした」という情報をL2/L3に引き継ぐ。

---

## 7. エラーハンドリング & リトライ

| エラー種別 | 対応策 |
|:---|:---|
| HTTP 503 (Service Unavailable) | 指数バックオフ（3秒 → 9秒 → 27秒）、最大3回リトライ |
| HTTP 400 (Bad Request) | クエリ構文エラー → ログ出力してスキップ、管理者通知 |
| レスポンス 0件 | 正常扱い（その日は該当論文なし）。ただし全6クエリが0件なら異常として通知 |
| XMLパースエラー | 該当レスポンスをログ保存、スキップして次のクエリへ |
| タイムアウト (30秒) | リトライ1回、それでも失敗なら次のクエリへ |

---

## 8. ログ出力仕様

各実行で以下をログ出力する（フィルタ強度調整の根拠とする）。

```json
{
  "execution_date": "2026-02-12",
  "execution_time_utc": "2026-02-12T02:00:00Z",
  "date_range": { "start": "202602110000", "end": "202602120000" },
  "queries": [
    { "category": "基盤モデル", "raw_count": 142, "api_calls": 1 },
    { "category": "学習・調整", "raw_count": 38, "api_calls": 1 },
    { "category": "エンジニアリング", "raw_count": 27, "api_calls": 1 },
    { "category": "インフラ・最適化", "raw_count": 15, "api_calls": 1 },
    { "category": "評価・安全性", "raw_count": 22, "api_calls": 1 },
    { "category": "規制・社会", "raw_count": 8, "api_calls": 1 }
  ],
  "total_raw": 252,
  "after_dedup": 198,
  "passed_to_L2": 198,
  "errors": []
}
```

---

## 9. 実装時の注意事項

1. **`abs:` vs `all:` の選択:** `abs:` は Abstract のみを検索。`all:`（全フィールド）はノイズが増える。まずは `abs:` で開始し、Recallが低ければ `all:` へ切り替え。
2. **「Transformer」問題:** "Transformer" は電力変圧器の論文にもヒットする。`cat:` との AND 結合で制御するが、L2ベクトル選別で除外されることを期待する。
3. **ページング:** `max_results` 超過時は `start` をインクリメントして追加取得。1カテゴリあたり最大3ページ（1500件）をハードリミットとする。
4. **レートリミット遵守:** リクエスト間に最低3秒のスリープを入れる。6クエリ × ページング で最大でも ~60秒で完了。