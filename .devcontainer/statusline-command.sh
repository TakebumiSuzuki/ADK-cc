#!/bin/sh
input=$(cat)

eval $(echo "$input" | python3 -c "
import sys, json
from datetime import datetime, timezone
d = json.load(sys.stdin)

def pct(val):
    if val is None:
        return '--'
    return str(int(val))

def fmt_time(epoch, fmt, miss):
    if not epoch:
        return miss
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone().strftime(fmt)

cwd = d.get('cwd', '')
model = (d.get('model') or {}).get('display_name', '...')

ctx = d.get('context_window') or {}
ctx_pct = pct(ctx.get('used_percentage'))

rl_obj = d.get('rate_limits') or {}
rl = rl_obj.get('five_hour') or {}
rl_pct = pct(rl.get('used_percentage'))
rl_time = fmt_time(rl.get('resets_at'), '%H:%M', '--:--')

rl7 = rl_obj.get('seven_day') or {}
rl7_pct = pct(rl7.get('used_percentage'))
rl7_time = fmt_time(rl7.get('resets_at'), '%-m/%-d %H:%M', '--')

cost_val = (d.get('cost') or {}).get('total_cost_usd')
cost = cost_val if cost_val is not None else None

def esc(s):
    return s.replace('\"','\\\"')

print('CWD=\"{}\"'.format(esc(cwd)))
print('MODEL=\"{}\"'.format(esc(model)))
print('CTX_PCT=\"{}\"'.format(ctx_pct))
print('RL_PCT=\"{}\"'.format(rl_pct))
print('RL_TIME=\"{}\"'.format(rl_time))
print('RL7_PCT=\"{}\"'.format(rl7_pct))
print('RL7_TIME=\"{}\"'.format(rl7_time))
if cost is None:
    print('COST=\"--\"')
else:
    print('COST=\"{:.4f}\"'.format(cost))
")

# Git branch
branch=$(git -C "$CWD" symbolic-ref --short HEAD 2>/dev/null)

# Colors
RESET='\033[0m'
CYAN='\033[36m'
MAGENTA='\033[35m'
GREEN='\033[32m'
ORANGE='\033[38;5;208m'
RED='\033[31m'
YELLOW='\033[33m'
GRAY='\033[90m'

# Context color (handle "--" sentinel for not-yet-available data)
if [ "$CTX_PCT" = "--" ]; then
  CTX_COLOR=$GRAY
elif [ "$CTX_PCT" -ge 80 ]; then
  CTX_COLOR=$RED
elif [ "$CTX_PCT" -ge 50 ]; then
  CTX_COLOR=$ORANGE
else
  CTX_COLOR=$GREEN
fi

# Rate limit color (5h)
if [ "$RL_PCT" = "--" ]; then
  RL_COLOR=$GRAY
elif [ "$RL_PCT" -ge 80 ]; then
  RL_COLOR=$RED
elif [ "$RL_PCT" -ge 50 ]; then
  RL_COLOR=$ORANGE
else
  RL_COLOR=$GRAY
fi

# Rate limit color (7d)
if [ "$RL7_PCT" = "--" ]; then
  RL7_COLOR=$GRAY
elif [ "$RL7_PCT" -ge 80 ]; then
  RL7_COLOR=$RED
elif [ "$RL7_PCT" -ge 50 ]; then
  RL7_COLOR=$ORANGE
else
  RL7_COLOR=$GRAY
fi

# Build output
out="🤖 ${MAGENTA}${MODEL}${RESET}"
if [ -n "$branch" ]; then
  out="${out}  ⎇ ${CYAN}${branch}${RESET}"
fi
out="${out}  📊 ctx:${CTX_COLOR}${CTX_PCT}%${RESET}"
out="${out}  ⏱ 5h:${RL_COLOR}${RL_PCT}%${RESET}(→${RL_TIME}) 7d:${RL7_COLOR}${RL7_PCT}%${RESET}(→${RL7_TIME})"
if [ "$COST" = "--" ]; then
  out="${out}  💰 ${GRAY}\$--${RESET}"
else
  out="${out}  💰 ${YELLOW}\$${COST}${RESET}"
fi

printf "%b" "$out"
