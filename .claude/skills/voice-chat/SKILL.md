---
name: voice-chat
description: "パートナーと音声で会話・VoiceModeで双方向対話・converse()を使う・ウェイクワード対応・listen.pyで発話を待つ・音声対話モードに入るとき → このスキルを読む"
---

# ボイスチャットスキル

VoiceMode MCP と既存の listen.py を組み合わせた双方向音声会話。

## 使い方

### 方法1: VoiceMode converse（推奨）

AIが話して、マイクで応答を待つ。一番シンプル。

```python
# 話しかけて応答を待つ
mcp__voicemode__converse(
    message="何か聞きたいことある？",
    voice="jf_alpha",         # 日本語女性音声
    tts_provider="kokoro",    # ローカルTTS
    wait_for_response=True
)
```

**ポイント**:
- `wait_for_response=True` でマイクが開く
- パートナーが喋り終わると自動で認識
- 認識結果がテキストで返る → AIが考えて次の発話

### 方法2: listen.py --poll → converse 応答

パートナーが先に話しかける場合。常時リスニングの発話を待つ。

```bash
# Step 1: 発話を待つ（最大60秒）
text=$(uv run tools/listen.py --poll 60)

# Step 2: 発話があったらconverseで応答
```

### 方法3: ボイスチャットループ

対話セッション中にボイスチャットモードに入る。

```
ループ:
  1. listen.py --poll で発話待ち
  2. 発話テキストを取得
  3. AIが応答を考える
  4. converse(message=応答, wait_for_response=False) で喋る
  5. 1に戻る
```

「終わり」「バイバイ」等の終了ワードでループを抜ける。

## VoiceMode設定

設定ファイル: `~/.voicemode/voicemode.env`

### 日本語音声

| 音声 | 性別 | 説明 |
|------|------|------|
| jf_alpha | 女性 | 標準（推奨） |
| jf_gongitsune | 女性 | ごん狐風 |
| jf_nezumi | 女性 | ねずみ風 |
| jm_kumo | 男性 | 蜘蛛風 |

### サービス管理

```python
# ステータス確認
mcp__voicemode__service(service_name="kokoro", action="status")
mcp__voicemode__service(service_name="whisper", action="status")

# 起動
mcp__voicemode__service(service_name="kokoro", action="start")
mcp__voicemode__service(service_name="whisper", action="start")
```

## 注意点

- **Kokoroが起動していないとローカルTTSが使えない**（OpenAI APIにフォールバック）
- **エコーキャンセル**: VoiceModeの再生中にlisten.pyが拾うと二重認識される
  - VoiceModeは自前でマイク管理するので、converseの`wait_for_response=True`なら問題なし
- **WSL**: PulseAudio経由のオーディオ。物理マイクはWindows ffmpeg経由

## 既存ツールとの使い分け

| 用途 | ツール |
|------|--------|
| 対話（双方向） | VoiceMode converse |
| 一方的に喋る | VoiceMode converse (wait_for_response=False) |
| 背景音を常時記録 | listen.py --on |
| 発話待ち | listen.py --poll |
| 高品質日本語TTS | speak.py (Gemini TTS) |
| 英語ローカルTTS | speak_local.py (Pocket TTS) |
