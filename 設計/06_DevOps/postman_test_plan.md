# Postman API テスト計画書

AI Research OS のフロントエンド向け API (全11エンドポイント) を Postman で検証するための手引きです。

## 1. 事前準備 (環境変数の設定)

Postman 上で新しい **Environment** (例: `AI Research OS Dev`) を作成し、以下の変数を登録してください。

| 変数名 | 初期値や取得元 |
|:---|:---|
| `API_URL` | ローカル: `http://127.0.0.1:8000/api/v1` <br> 本番: `https://xxxx.execute-api.../prod/api/v1` |
| `ID_TOKEN` | アプリからのログイン後、または AWS CLI で取得した Cognito の ID トークン |
| `ARXIV_ID` | テストに利用する実在の arxiv_id (例: `2402.12345`) |
| `BOOKMARK_ID` | お気に入り登録テスト等で返ってきた ID |

### 💡 (参考) Cognito ID トークンの手動取得方法
```bash
aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id <COGNITO_CLIENT_ID> \
    --auth-parameters USERNAME="<EMAIL>",PASSWORD="<PASSWORD>" \
    --query "AuthenticationResult.IdToken" \
    --output text
```

---

## 2. 共通設定 (Authorization)

`ヘルスチェックAPI` を除くすべてのリクエストについて、Postman の **Authorization** タブで以下を設定します。
- **Type**: `Bearer Token`
- **Token**: `{{ID_TOKEN}}`

---

## 3. テスト項目一覧

### 0. ヘルスチェック (認証不要)
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/health`
- **期待値**: `200 OK`, `{"status": "ok"}`

### 1. 論文一覧の取得
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/papers`
- **クエリ (例)**: `?limit=5&category_id=4&importance=4`
- **期待値**: `200 OK`, 論文リスト(`data`) と `pagination` 情報が含まれていること

### 2. 論文詳細の取得
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/papers/{{ARXIV_ID}}`
- **期待値**: `200 OK`, 論文の基礎情報に加え、[detail](file:///Users/suenagakazuya/Documents/AI_News_App/backend/tests/test_api_papers.py#105-145) に3視点解説やレベル別テキストが含まれていること

### 3. 図表一覧の取得
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/papers/{{ARXIV_ID}}/figures`
- **期待値**: `200 OK`, `s3_url` などを含む図表の配列であること

### 4. 閲覧記録の送信
- **メソッド**: `POST`
- **URL**: `{{API_URL}}/papers/{{ARXIV_ID}}/view`
- **期待値**: `201 Created` 又は `200 OK` (日時情報が返る)

### 5. カテゴリ一覧の取得
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/categories`
- **期待値**: `200 OK`, 全6カテゴリの情報と `paper_count` (論文数) を含む配列

### 6. お気に入り追加
- **メソッド**: `POST`
- **URL**: `{{API_URL}}/bookmarks`
- **ボディ (JSON)**:
  ```json
  {
      "arxiv_id": "{{ARXIV_ID}}"
  }
  ```
- **期待値**: `201 Created` (※ここで返るIDを `BOOKMARK_ID` 変数に入れておきます), 再度同リクエストを送ると `409 Conflict` が返ること

### 7. お気に入り一覧
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/bookmarks`
- **期待値**: `200 OK`, 先ほど追加した論文情報が含まれていること

### 8. お気に入り削除
- **メソッド**: `DELETE`
- **URL**: `{{API_URL}}/bookmarks/{{BOOKMARK_ID}}`
- **期待値**: `204 No Content`, 再度同じIDで削除すると `404 Not Found` またはエラーになること

### 9. ユーザー情報取得
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/users/me`
- **期待値**: `200 OK`, 自分のメールアドレスやデフォルト設定情報が返ること

### 10. ユーザー統計取得
- **メソッド**: `GET`
- **URL**: `{{API_URL}}/users/me/stats`
- **期待値**: `200 OK`, `papers_viewed` や `bookmarks_count` の集計結果が返ること。閲覧やお気に入りを追加した分が反映されているか確認

### 11. ユーザー設定の更新
- **メソッド**: `PUT`
- **URL**: `{{API_URL}}/users/me/settings`
- **ボディ (JSON)**:
  ```json
  {
      "display_name": "Postman User",
      "default_level": 3
  }
  ```
- **期待値**: `200 OK`, 指定した表示名とレベルに変更されたユーザー情報が返ること
