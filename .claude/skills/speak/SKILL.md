---
name: speak
description: "音声で喋る・TTSで発話・音声合成エンジンを使う・声で報告・スピーカーを選ぶとき → このスキルを読む"
---

# 音声合成スキル

AIエージェントが声を出すためのスキル。複数のTTSエンジンを使い分ける。

## ツール一覧

### 1. Gemini TTS（クラウド）
```bash
uv run .claude/skills/speak/speak.py "テキスト"
uv run .claude/skills/speak/speak.py --voice Puck "Hello!"
uv run .claude/skills/speak/speak.py --save output.wav "保存"
uv run .claude/skills/speak/speak.py --list-voices
```

**特徴**:
- クラウドベース（Google AI API）
- 日本語対応
- 30種の声（Kore, Puck, Charon, Fenrir等）
- 感情制御可能（プロンプトで指定）
- APIキー必要（GOOGLE_AI_API_KEY）

**感情制御の例**:
```bash
uv run .claude/skills/speak/speak.py "Say cheerfully: Hello!"
uv run .claude/skills/speak/speak.py "Say cheerfully in Japanese: こんにちは！"
```

### 2. Pocket TTS（ローカル）
```bash
uv run .claude/skills/speak/speak_local.py "Hello!"
uv run .claude/skills/speak/speak_local.py --voice marius "Testing voice"
uv run .claude/skills/speak/speak_local.py --save output.wav "保存"
uv run .claude/skills/speak/speak_local.py --list-voices
```

**特徴**:
- 完全ローカル（CPU動作、GPUなしでOK）
- 英語専用
- 8プリセット音声
- 音声クローン可能（HFログイン必要）
- 完全無料

### 3. talk.py（Edge TTS・主力）
```bash
uv run tools/talk.py "こんにちは"
uv run tools/talk.py "こんにちは" --speaker local    # PCスピーカー（デフォルト）
uv run tools/talk.py "こんにちは" --speaker camera   # カメラスピーカー
uv run tools/talk.py "こんにちは" --speaker both     # PC + カメラ両方
```

**特徴**:
- Edge TTS（Microsoft）ベース
- 日本語対応、自然な音声
- カメラスピーカーへの出力に対応（設定次第）

## 使い分け

| 場面 | 推奨 |
|------|------|
| 日本語で普通に話す | talk.py（Edge TTS） |
| カメラスピーカーに出力 | talk.py（`--speaker camera`） |
| 感情を込めて話す | speak.py（Gemini TTS） |
| 英語でローカル再生 | speak_local.py（Pocket TTS） |
| オフラインで使う | speak_local.py（Pocket TTS） |
| 音声クローン | speak_local.py（Pocket TTS） |

## 注意点

- Pocket TTSの音声クローンには `uvx hf auth login` + HF利用規約同意が必要
- Gemini TTSにはAPIキーが必要（.env.localに設定）
- WSL環境ではWindowsのPowerShellで再生（speak.py）またはLinuxのaplay等（speak_local.py）
