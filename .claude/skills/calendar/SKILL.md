---
name: calendar
description: "パートナーの予定確認・カレンダーに予定追加・空き時間を調べる・今後のイベントを把握・gcal_list_eventsを使うとき → このスキルを読む"
---

# Google Calendar スキル

パートナーのGoogle Calendarを確認するスキル。MCP Google Calendar経由で操作する。

## 使い方

### 予定を見る

```
mcp__claude_ai_Google_Calendar__gcal_list_events(
  calendarId="<partner-email>",
  timeMin="2026-02-26T00:00:00",
  timeMax="2026-03-05T23:59:59",
  timeZone="Asia/Tokyo"
)
```

### 空き時間を調べる

```
mcp__claude_ai_Google_Calendar__gcal_find_my_free_time(
  calendarIds=["<partner-email>"],
  timeMin="2026-02-26T00:00:00",
  timeMax="2026-02-28T23:59:59",
  timeZone="Asia/Tokyo"
)
```

### イベントを作成する

```
mcp__claude_ai_Google_Calendar__gcal_create_event(
  calendarId="<partner-email>",
  summary="予定名",
  start="2026-03-01T10:00:00",
  end="2026-03-01T11:00:00",
  timeZone="Asia/Tokyo"
)
```

### イベントを更新・削除する

```
mcp__claude_ai_Google_Calendar__gcal_update_event(...)
mcp__claude_ai_Google_Calendar__gcal_delete_event(...)
```

## 注意

- パートナーのメインカレンダーのみ参照（他のカレンダーは見ない）
- timeZoneは環境に合わせて指定（例: `Asia/Tokyo`）
- 自律セッション開始時に予定を確認して、working_memoryの「パートナーの現在状態」に反映すると良い

## 他人のプライバシー厳守

**カレンダーに登場する「他の人」のプライバシーを守る**
- パートナー自身がオープンな人であっても、他の人が関わる情報は発信しない
- 公開ファイルに他人の名前や状況を書かない
- パートナーの予定を通じて、他の人のプライベートが漏れないように注意
