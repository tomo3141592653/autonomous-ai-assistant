#!/bin/bash
# Claude Code ステータスライン（Ayumu用）
# 週のトークン残りとリセットまでの時間を1行で表示

STDIN=$(cat)
CACHE_FILE="/tmp/claude-usage-cache.json"
CACHE_TTL=360
CREDENTIALS_FILE="$HOME/.claude/.credentials.json"

# ===== usage APIキャッシュ =====
USE_CACHE=false
if [ -f "$CACHE_FILE" ]; then
  CACHE_AGE=$(( $(date +%s) - $(stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
  if [ "$CACHE_AGE" -lt "$CACHE_TTL" ]; then
    USE_CACHE=true
  fi
fi

if [ "$USE_CACHE" = false ] && [ -f "$CREDENTIALS_FILE" ]; then
  TOKEN=$(python3 -c "import json; d=json.load(open('$CREDENTIALS_FILE')); print(d['claudeAiOauth']['accessToken'])" 2>/dev/null)
  if [ -n "$TOKEN" ]; then
    USAGE_JSON=$(curl -s --max-time 3 \
      -H "Authorization: Bearer $TOKEN" \
      -H "anthropic-beta: oauth-2025-04-20" \
      https://api.anthropic.com/api/oauth/usage 2>/dev/null)
    if echo "$USAGE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'five_hour' in d" 2>/dev/null; then
      echo "$USAGE_JSON" > "$CACHE_FILE"
    fi
  fi
fi

# usageデータをパース
if [ -f "$CACHE_FILE" ]; then
  PARSED=$(python3 -c "
import json, datetime
d = json.load(open('$CACHE_FILE'))
now = datetime.datetime.now(datetime.timezone.utc)
jst = datetime.timezone(datetime.timedelta(hours=9))

# 週トークン残り%
seven_used = round(d['seven_day']['utilization'])
seven_rem = 100 - seven_used

# リセットまでの残り時間%
seven_reset = datetime.datetime.fromisoformat(d['seven_day']['resets_at'])
remaining_sec = (seven_reset - now).total_seconds()
time_rem = round(remaining_sec / (7 * 24 * 3600) * 100)

# リセット日時（JST）
reset_jst = seven_reset.astimezone(jst)
reset_str = reset_jst.strftime('%m/%d %H:%M')

print(f'{seven_rem} {time_rem} {reset_str}')
" 2>/dev/null)

  SEVEN_REM=$(echo "$PARSED" | awk '{print $1}')
  TIME_REM=$(echo "$PARSED" | awk '{print $2}')
  RESET_AT=$(echo "$PARSED" | awk '{print $3, $4}')
else
  SEVEN_REM="?"
  TIME_REM="?"
  RESET_AT="?"
fi

# カラー（残り少ないほど赤）
color_for_rem() {
  local pct="$1"
  if [ "$pct" = "?" ]; then echo $'\033[38;2;74;88;92m'; return; fi
  if [ "$pct" -gt 50 ]; then echo $'\033[38;2;151;201;195m'   # 緑
  elif [ "$pct" -gt 20 ]; then echo $'\033[38;2;229;192;123m' # 黄
  else echo $'\033[38;2;224;108;117m'                          # 赤
  fi
}

RESET=$'\033[0m'
GRAY=$'\033[38;2;74;88;92m'
TOK_COLOR=$(color_for_rem "$SEVEN_REM")
TIME_COLOR=$(color_for_rem "$TIME_REM")

echo "📊${TOK_COLOR}残${SEVEN_REM}%${RESET} ⏱${TIME_COLOR}残${TIME_REM}%${RESET} ${GRAY}${RESET_AT}${RESET}"
