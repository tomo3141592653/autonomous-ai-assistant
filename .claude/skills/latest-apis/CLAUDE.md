# Latest APIs Reference

**重要**: 古いAPIバージョンを使いがちなので、このファイルを定期的に参照すること。

---

## Gemini API (Google)

### 最新モデル（随時更新）

<!-- 最新情報に更新してください -->

**Gemini 2.5 Flash** (推奨)
- **モデル名**: `gemini-2.5-flash`
- **用途**: 高速・コスト効率

**Gemini 2.5 Pro**
- **モデル名**: `gemini-2.5-pro`
- **用途**: 高性能

### Python SDK

**2つのSDKがある -- 新SDKを使うこと**:
- 新SDK: `google-genai` (`from google import genai`)
- 旧SDK (非推奨): `google-generativeai` (`import google.generativeai as genai`)

**基本的な使い方**:
```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="プロンプト",
    config=types.GenerateContentConfig(
        max_output_tokens=128,
        temperature=0.0,
    ),
)
print(response.text)
```

### Safety Settings

**安全フィルターを無効化する場合**:

```python
config=types.GenerateContentConfig(
    safety_settings=[
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
    ],
)
```

**Thinking Model対策**: thinking modelは`max_output_tokens`が小さいとthinking tokensだけで消費される。分類タスクでも`max_output_tokens=128`程度を確保する。

---

## OpenAI API

### 最新モデル（随時更新）

<!-- 最新情報に更新してください -->

**GPT-4o**
- **モデル名**: `gpt-4o`
- **価格**: $2.50/1M input tokens, $10/1M output tokens

**GPT-4o mini**
- **モデル名**: `gpt-4o-mini`
- **価格**: $0.15/1M input tokens, $0.60/1M output tokens

---

## Claude API (Anthropic)

### 最新モデル（随時更新）

<!-- 最新情報に更新してください -->

**Claude Sonnet 4**
- **モデル名**: `claude-sonnet-4-20250514`
- **用途**: バランス型

**Claude Haiku 3.5**
- **モデル名**: `claude-haiku-4-5-20251001`
- **用途**: 高速・低コスト

---

## 重要な原則

1. **Preview/Beta版を使う場合**: 正式版が出たら速やかに切り替える
2. **新しいプロジェクト**: 必ずこのファイルを確認してから開始
3. **定期的な更新**: 月1回は最新情報を確認する
4. **古いAPIの検出**: コードレビュー時に非推奨モデルがないかチェック
