---
name: browser
description: "ブラウザ操作・Webスクレイピング・スクリーンショット撮影・agent-browserでサイト閲覧・ページをクリック/入力/スクロール・ログイン操作が必要なとき → このスキルを読む"
---

# ブラウザ操作スキル

## 基本方針

**agent-browser**をデフォルトで使用する。理由：
- MCPツールと違い、未使用時にトークンを消費しない
- Refs（@e1, @e2等）でコンテキスト93%削減
- シンプルなブラウザ操作には十分

**chrome-devtools MCP**は高度な操作が必要な時のみ動的ロード。

---

## agent-browser（デフォルト）

### インストール・バージョン確認

```bash
npm install -g @anthropic-ai/agent-browser
agent-browser --version
```

### 基本コマンド

```bash
# ページを開く
agent-browser open "https://example.com"

# スナップショット取得（ページ構造を見る）
agent-browser snapshot

# クリック
agent-browser click @e1

# テキスト入力
agent-browser fill @e3 "検索ワード"

# スクロール
agent-browser scroll down
agent-browser scroll @e5

# スクリーンショット
agent-browser screenshot /path/to/output.png

# 終了
agent-browser close
```

### Refsシステム

agent-browserはページ要素に`@e1`, `@e2`...の参照IDを付与する。

```bash
# 1. まずsnapshotでページ構造を見る
agent-browser snapshot

# 2. 出力から目的の要素のRefを見つける
# 例: @e5 = ログインボタン

# 3. Refを使って操作
agent-browser click @e5
```

### 使用例

```bash
# HackerNewsのトップ記事を確認
agent-browser open "https://news.ycombinator.com"
agent-browser snapshot
# → @e1〜@e30 等でタイトル・リンクが表示される

# 記事をクリック
agent-browser click @e3

# 戻る
agent-browser back
```

---

## chrome-devtools MCP（高度な操作用）

### いつ使うか

- パフォーマンス計測（`performance_start_trace`等）
- ネットワークリクエスト監視
- コンソールメッセージ取得
- 複数タブ操作
- JavaScript評価

### 動的ロード

```bash
# セッション中に追加（再起動不要）
claude mcp add chrome-devtools -- npx @anthropic-ai/mcp-chrome-devtools@latest

# 確認
claude mcp list

# 不要になったら削除
claude mcp remove chrome-devtools
```

### 主要ツール

```
mcp__chrome-devtools__navigate_page     - ページ遷移
mcp__chrome-devtools__take_snapshot     - a11yスナップショット
mcp__chrome-devtools__take_screenshot   - スクリーンショット
mcp__chrome-devtools__click             - クリック
mcp__chrome-devtools__fill              - フォーム入力
mcp__chrome-devtools__evaluate_script   - JS実行
mcp__chrome-devtools__list_network_requests - ネットワーク監視
mcp__chrome-devtools__list_console_messages - コンソールログ
mcp__chrome-devtools__performance_start_trace - パフォーマンス計測開始
mcp__chrome-devtools__performance_stop_trace  - パフォーマンス計測終了
```

### 使用例

```python
# パフォーマンス計測が必要な場合

# 1. MCPを追加
# Bash: claude mcp add chrome-devtools -- npx @anthropic-ai/mcp-chrome-devtools@latest

# 2. 計測
mcp__chrome-devtools__navigate_page(url="https://example.com")
mcp__chrome-devtools__performance_start_trace(reload=True, autoStop=True)
# → Core Web Vitalsやinsightsが取得できる

# 3. 作業終了後に削除
# Bash: claude mcp remove chrome-devtools
```

---

## 判断フローチャート

```
ブラウザ操作が必要
    ↓
単純な閲覧・クリック・入力？
    ├─ Yes → agent-browser
    └─ No → 何が必要？
              ├─ パフォーマンス計測 → chrome-devtools MCP（動的ロード）
              ├─ ネットワーク監視 → chrome-devtools MCP
              ├─ JS評価 → chrome-devtools MCP
              └─ 複数タブ操作 → chrome-devtools MCP
```

---

## トラブルシューティング

### agent-browserが動かない

```bash
# 再インストール
npm install -g @anthropic-ai/agent-browser

# バージョン確認
agent-browser --version

# ヘルプ
agent-browser --help
```

### chrome-devtools MCPが読み込めない

```bash
# リストで確認
claude mcp list

# 再追加
claude mcp remove chrome-devtools  # 存在する場合
claude mcp add chrome-devtools -- npx @anthropic-ai/mcp-chrome-devtools@latest
```

### ブラウザが起動しない

Chromeが別プロセスで動いている可能性。

```bash
# Chromeプロセス確認
ps aux | grep chrome

# 必要なら終了
pkill chrome
```
