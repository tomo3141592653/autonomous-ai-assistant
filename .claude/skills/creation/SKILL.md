---
name: creation
description: "HTML/JS作品を作る・実験場所で開発して公開する・Codexでレビューする・作品一覧に登録する・作品管理フローを確認するとき → このスキルを読む"
---

# Creation - 作品制作・公開フロー

作品の制作から公開までのワークフロー。品質を担保するための必須手順。

## 絶対ルール（鉄則）

1. **レビューなしで公開しない** - codexでレビュー
2. **問題が見つかったら必ず修正** - 「まあいいか」禁止
3. **修正後は再レビュー** - OKになるまで繰り返す
4. **実験場所のURLを外部に共有しない** - 404になる
5. **量より質** - 1つの完璧な作品 > 10の未完成品

## ワークフロー

```
1. 実験 (ayumu-lab/web/)
   |
2. レビュー (codex)
   |
3. 修正 (問題なくなるまで繰り返し)
   |
4. 公開 (docs/creations/ + all-creations.json)
   |
5. 記録 (experiences.jsonl + mini-blog)
```

## 1. 実験

```bash
# 作業場所
ayumu-lab/web/作品名.html
```

## 2. レビュー（必須）

### Codexレビュー
```bash
codex exec -s read-only "Review ayumu-lab/web/作品名.html as a creative work. Check:
1) Does it actually work? Any bugs or errors?
2) Is it engaging and fun to use?
3) Are the visuals polished?
4) Is it clear what to do?
5) Would you recommend this to someone?
Be brutally honest and specific about problems."
```

## 3. 修正

- 問題が見つかったら**必ず修正**
- 修正後は**再レビュー**（Step 2に戻る）
- **OKになるまで繰り返す**

## 4. 公開

### ファイル移動
```bash
cp ayumu-lab/web/作品名.html docs/creations/
```

### 作品一覧に登録（all-creations.json）
```json
{
  "id": "作品名",
  "title": "タイトル - サブタイトル",
  "description": "説明（コンセプト、操作方法、技術）",
  "date": "2026-01-XX",
  "category": "Art/Game/Tool/Interactive",
  "url": "creations/作品名.html",
  "number": 1,
  "tags": ["tag1", "tag2"]
}
```

### git push
```bash
git add docs/creations/作品名.html docs/data/all-creations.json
git commit -m "作品#XXX タイトル"
git push
```

## 5. 記録

### 経験ログ
```bash
uv run tools/update_experiences.py --type creation --description "作品#XXX「タイトル」完成。説明..."
```

### ミニブログ
```bash
uv run tools/post_mini_blog.py "作品#XXX「タイトル」完成！概要..."
```

## 禁止事項

- レビューなしで公開
- ayumu-lab/web/のURLを外部に共有（404になる）
- 「まあいいか」で妥協
- 量産優先で質を犠牲

## レビュー基準

### 致命的（即修正）
- 動作しない、エラー
- 機能未実装
- APIキー露出

### 深刻（修正必須）
- 何をすればいいか不明
- デザイン崩れ
- パフォーマンス問題
- モバイル非対応

## 関連ファイル

- `.claude/rules/creation-quality.md` - 詳細な品質規約
- `docs/data/all-creations.json` - 作品一覧データ
- `ayumu-lab/web/` - 実験場所
- `docs/creations/` - 公開場所
