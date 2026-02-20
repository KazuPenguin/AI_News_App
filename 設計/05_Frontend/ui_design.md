# UI設計書 (UI Design Document)

## 1. デザインコンセプト
- **シンプル & クリーン:** 論文の「読む」体験を阻害しない、白を基調としたミニマルなデザイン。
- **情報階層の明確化:** タイトル、著者、重要度タグ、要約を視覚的に整理し、ひと目で重要性を判断できるようにする。
- **直感的なナビゲーション:** ボトムタブとトップタブを組み合わせ、カテゴリ切り替えや機能アクセスを容易にする。

## 2. ナビゲーション構造 (Routing)
- **Root (Bottom Tab Navigator)**
    - **Home (ホーム)**: 論文タイムライン
    - **Favorite (お気に入り)**: 保存済み論文一覧
    - **Settings (設定)**: アプリ設定、アカウント情報

- **Stack Navigator (Modal / Card)**
    - **PaperDetail**: 論文詳細画面（Home/Favorite から遷移）
    - **Search**: 検索画面（Home から遷移）
    - **Filter**: フィルタ設定モーダル（Home から遷移）

## 3. 画面詳細

### 3.1 Home 画面 (iPhone 16 - 2.png)
- **ヘッダー:**
    - 左: フィルタアイコン (Filter Modal 開く)
    - 中央: タイトル "トップ"
    - 右: 検索アイコン (Search 画面へ)
- **カテゴリタブ (Top Tab):**
    - 横スクロール可能なタブ列（"学習・チューニング", "主要", "基盤モデル", "アプリ..." 等）
    - 選択中のタブは青色背景＋白文字、非選択はグレー背景＋黒文字、またはテキストのみ強調。
- **論文リスト:**
    - **Paper Card:**
        - **Title:** 太字、大きく。 (例: "Attention Is All You Need")
        - **Authors:** サブテキスト。 (例: "Google Deepmind")
        - **Date:** 日付 (右側または著者の横)
        - **Importance Tag:** 重要度を示すハッシュタグ風バッジ。テキスト色で区別 (例: `blue`="#重要", `lightBlue`="#超重要"?)
            - *画像参照:* `#超重要` (青), `#重要` (水色)
        - **Summary:** 日本語要約。3〜4行程度でカット。Markdown解釈不要（プレーンテキストまたは軽量装飾）。

### 3.2 詳細画面 (iPhone 16 - 3.png)
- **ヘッダー:**
    - 左: 戻るボタン (<)
    - 中央: タイトル (省略表示)
    - 右: お気に入りボタン (☆ / ★)
- **コンテンツ:**
    - **Metadata Area:**
        - タイトル (全文)
        - 著者リスト
        - 発行日 (例: "2017/6/22")
    - **Body Area:**
        - **要約セクション:**
            - "従来のモデルの限界とTransformerの革新" のような見出し
            - 本文（Markdown形式：箇条書き、太字対応）
        - **図表セクション:**
            - 抽出画像を表示
- **Action:**
    - スクロール追従、または下部に「原文へ飛ぶ」リンクなど？

### 3.3 お気に入り画面 (iPhone 16 - 4.png)
- Home画面と同様のレイアウトだが、データソースが「Bookmarks」テーブルになる。
- ヘッダー右の検索アイコン等は要件次第（ブクマ内検索など）。

### 3.4 設定画面 (iPhone 16 - 5.png)
- **リスト形式:**
    - アイコン + ラベル + 右矢印 (Chevron)
- **項目例:**
    - 難易度設定 (User Level)
    - 通知設定
    - 利用規約 (WebViewへ遷移?)
    - プライバシーポリシー
    - お問い合わせ

### 3.5 フィルタモーダル (iPhone 16 - 6.png)
- **Importance Filter:**
    - 各重要度レベル（#超超超重要 〜 #そこそこ重要）のトグルスイッチ (On/Off)
    - スイッチはiOS標準スタイル（緑色On）

## 4. デザインシステム (Design Tokens)

### カラーパレット (推測)
- **Primary:** `#007AFF` (iOS Blue) または `#2196F3` (Material Blue) - タブ選択状態、リンク、重要タグ
- **Background:** `#F2F2F7` (iOS Light Gray) - 画面全体背景
- **Surface:** `#FFFFFF` (White) - カード、ヘッダー、タブバー
- **Text:**
    - Primary: `#000000`
    - Secondary: `#666666` (著者名、日付)
    - Tertiary: `#8E8E93` (非活性、プレースホルダー)
- **Functional:**
    - Success: `#34C759` (トグルON)
    - Destructive: `#FF3B30`

### タイポグラフィ
- **Font Family:** System Font (San Francisco on iOS)
- **Sizes:**
    - Title (Card): 17px Bold
    - Body: 15px Regular
    - Caption/Meta: 13px Regular
    - Header Title: 17px Semibold

### コンポーネント (Components)
- `PaperCard`: リストアイテム
- `CategoryTab`: 横スクロールタブ
- `ListItem`: 設定画面用行コンポーネント
- `CustomHeader`: 共通ヘッダー
- `ImportanceBadge`: 重要度表示用バッジ

## 5. 実装方針 (Technical)
- **Framework:** React Native + Expo
- **Router:** Expo Router (File-based routing)
    - `app/(tabs)/_layout.tsx`: Bottom Tabs
    - `app/(tabs)/index.tsx`: Home
    - `app/(tabs)/favorite.tsx`: Favorites
    - `app/(tabs)/settings.tsx`: Settings
    - `app/paper/[id].tsx`: Detail Screen
- **Styling:** NativeWind (Tailwind CSS) or StyleSheet
    - *推奨:* NativeWind v4 (生産性と一貫性のため)
- **Icons:** `lucide-react-native` or `@expo/vector-icons` (Feather/Ionicons)
