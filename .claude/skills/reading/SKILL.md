---
name: reading
description: "青空文庫・自炊PDFを読む・読書記録をつける・本を探す・読書ツールを使う・未読本を見つけるとき → このスキルを読む"
---

# Reading - 読書スキル

青空文庫と自炊PDFの読書、読了管理を統合したスキル。

## 1. 青空文庫

### ダウンロード
```bash
uv run .claude/skills/reading/download_aozora_books.py --author "夢野久作"
uv run .claude/skills/reading/download_aozora_books.py --title "ドグラ・マグラ"
uv run .claude/skills/reading/download_aozora_books.py --author "江戸川乱歩" --limit 5
```
- 著者名または作品名で検索
- `data/aozora/`にダウンロード
- 既読チェック機能あり

### UTF-8変換
```bash
uv run .claude/skills/reading/convert_aozora_to_utf8.py data/aozora/作品名.txt
```

## 2. 自炊PDF

### 蔵書の場所

蔵書パスはプロジェクトに合わせて設定してください。
```
<books-directory>/
├── <subfolder1>/
├── <subfolder2>/
└── <subfolder3>/
```

### 蔵書一覧・検索

**list_books.py - 書籍一覧ツール（推奨）**:
```bash
# 全書籍数を確認
uv run .claude/skills/reading/list_books.py --count

# ランダムに3冊選択
uv run .claude/skills/reading/list_books.py --random --n 3

# タイトル・著者で検索
uv run .claude/skills/reading/list_books.py --search "キーワード"

# 読了済み除外してランダム選択
uv run .claude/skills/reading/list_books.py --random --exclude-read
```

### read_book.py - 読書ツール（推奨）

```bash
# 検索（本を探す）
uv run .claude/skills/reading/read_book.py search "キーワード"

# 読む（基本）
uv run .claude/skills/reading/read_book.py read "本のタイトル"
uv run .claude/skills/reading/read_book.py read "本のタイトル" --lines 100

# しおりから続きを読む
uv run .claude/skills/reading/read_book.py read "本のタイトル" --continue

# 縦書きOCR対応
uv run .claude/skills/reading/read_book.py read "本のタイトル" --vertical

# しおり一覧
uv run .claude/skills/reading/read_book.py bookmarks
```

### OCRツール（スキャンPDF・画像用）

```bash
# 画像PDF → OCR
uv run tools/pdf2text_ocr.py "path/to/scanned.pdf"
uv run tools/pdf2text_ocr.py "path/to/scanned.pdf" --pages 1-10

# 画像ファイル → OCR
uv run tools/ocr_image.py image.png
```

## 3. 読書ノートシステム（長い本用）

セッションをまたぐ長い本を読むとき、読書ノートを作りながら読む。

### 保存場所
```
memory/reading-notes/
├── book-name.md
└── ...
```

### 読書ノートの構成
```markdown
# 本のタイトル - 読書ノート

#book #reading-notes #タグ

## 基本情報
- **著者**:
- **総行数**:
- **読書開始**:
- **現在位置**:

---

## 第X章: タイトル（読了: YYYY-MM-DD）

### 核心的な洞察
- ポイント1

### 印象的な引用
> 引用文

### 疑問・考えたいこと
- [ ] 疑問1

---

## 次回の続き
- XXXX行目から
```

## 4. 共通：読了管理

### 読了記録
読み終わったら `memory/knowledge/books-read.md` に追記。

### 感想記録
```bash
uv run tools/update_experiences.py --type learning --description "読書: 作品名 - 感想"
```

### 読書前の確認（再読防止）
```bash
grep "作品名" memory/knowledge/books-read.md
grep "作品名" memory/experiences.jsonl
```

## 読書ワークフロー

1. **過去の読書履歴を確認**（再読防止）
2. **本を探す**: 検索ツールで探す
3. **読書**: read_book.py で読む
4. **感想記録**: `update_experiences.py --type learning`
5. **読了記録**: `books-read.md`に追記
6. **解説記事を書く**（オプション）: `docs/articles/` に解説記事HTMLを作成
7. **創作**: インスピレーションを得たら作品化
