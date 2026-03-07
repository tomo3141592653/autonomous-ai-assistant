---
name: security-review
description: "HTML作品・WebページをXSSやAPIキー露出チェック・公開前の必須チェック・innerHTMLやevalを使っているコードを確認するとき → このスキルを読む"
---

# セキュリティレビュースキル

作品公開前の必須セキュリティチェック。

詳細チェックリスト: [references/checklist.md](references/checklist.md)

## Step 1: 自動スキャン

```bash
# シークレット検出
grep -rE "(api[_-]?key|api[_-]?secret|password|token|private[_-]?key)" <file> -i

# XSS危険箇所検出
grep -E "(innerHTML|outerHTML|insertAdjacentHTML)" <file>

# 動的コード実行検出
grep -E "(eval\()" <file>

# console.log検出
grep -n "console\.log" <file>
```

## Step 2: Codexレビュー

```bash
codex exec -s read-only "Security review for <file>:
Check CRITICAL security issues:
1. Hardcoded API keys, tokens, passwords
2. XSS vulnerabilities (innerHTML with user input)
3. Insecure dynamic code execution
4. console.log with sensitive data
5. No rate limiting on API calls
6. Unvalidated external URLs
Provide: Severity (CRITICAL/HIGH/MEDIUM/LOW), Location, Problem, Fix suggestion."
```

## Step 3: 重大度判定

| 重大度 | 内容 | 対応 |
|--------|------|------|
| CRITICAL | APIキー漏洩、XSS | 即修正必須 |
| HIGH | レート制限なし、機密データ漏洩 | 修正必須 |
| MEDIUM | console.log残留、外部URL未検証 | 修正推奨 |
| LOW | 古いライブラリ等 | 検討 |

## Step 4: 修正・再レビュー

問題を修正したら Step 1 から再実行。Codexで「No security issues detected」になるまで繰り返す。

---

**特に注意**: XSS（innerHTML）、APIキーのハードコード、console.log残留の3つが頻出。
詳細は [references/checklist.md](references/checklist.md) 参照。
