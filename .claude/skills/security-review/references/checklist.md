# セキュリティチェックリスト（10項目）

## 1. シークレット管理

ハードコードされたAPIキー・トークン・パスワードがないか。

```bash
grep -E "(api[_-]?key|api[_-]?secret|password|token|private[_-]?key)" <ファイル> -i
```

```javascript
// Bad:  const API_KEY = "sk-1234567890abcdef";
// Good: const API_KEY = import.meta.env.VITE_API_KEY;
```

## 2. 入力検証

危険なパターン: `eval` / 動的コード生成 / innerHTMLにユーザー入力を代入 / `JSON.parse` without try-catch

## 3. XSS対策

```bash
grep -E "(innerHTML|outerHTML|insertAdjacentHTML)" <ファイル>
```

innerHTMLにユーザー入力を渡す代わりに `textContent` を使う。

## 4. SQLインジェクション

DBを使わない作品は該当しない。パラメータ化クエリを使うこと。

## 5. CSRF対策

状態を持たない作品は該当しない。

## 6. 認証・認可

認証不要な作品は該当しない。

## 7. レート制限

```javascript
// Bad:  button.addEventListener('click', () => { callAPI(); }); // 連打可能
// Good: isLoading フラグで防御
let isLoading = false;
button.addEventListener('click', async () => {
    if (isLoading) return;
    isLoading = true;
    await callAPI();
    isLoading = false;
});
```

## 8. 機密データ保護

```javascript
// Bad:  console.log('API Key:', API_KEY);
// Good: console.log('API Key:', API_KEY.slice(0, 10) + '...');
```

## 9. 外部リソースの検証

`window.location = userInput` のようなオープンリダイレクト。URLをパースして `http:` / `https:` のみ許可する。

## 10. 依存関係管理

外部ライブラリを使わない作品は該当しない。使う場合は最新版。

---

## よくある脆弱性（頻出パターン）

### XSS

innerHTMLにテンプレートリテラルで変数を埋め込むパターンが頻出。代わりにDOM APIで構築する:

```javascript
const labelDiv = document.createElement('div');
labelDiv.className = 'label';
labelDiv.textContent = label;
message.appendChild(labelDiv);
```

### APIキーのハードコード

```javascript
// Bad:  const OPENAI_API_KEY = "sk-1234567890";
// Good: const OPENAI_API_KEY = import.meta.env.VITE_OPENAI_API_KEY;
```

### console.log残留

```javascript
// Bad:  console.log("User data:", userData);
// Good: if (import.meta.env.DEV) { console.log("User data:", userData); }
```
