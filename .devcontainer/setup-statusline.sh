#!/bin/sh
# postCreateCommand から呼ばれ、コンテナ内ユーザースコープに statusLine を配備する。
# - ~/.claude/statusline-command.sh を、リポジトリ内スクリプトへの symlink として作成
#   (リポジトリ側を編集すれば即反映され、コンテナ再ビルド不要)
# - ~/.claude/settings.json に statusLine キーを jq でマージ(既存設定は保持)
set -e

CLAUDE_DIR="$HOME/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"
STATUSLINE_SRC="/workspaces/cc-dev-container/.devcontainer/statusline-command.sh"
STATUSLINE_DST="$CLAUDE_DIR/statusline-command.sh"

mkdir -p "$CLAUDE_DIR"

ln -sfn "$STATUSLINE_SRC" "$STATUSLINE_DST"

STATUSLINE_JSON='{"type":"command","command":"bash ~/.claude/statusline-command.sh"}'
if [ -f "$SETTINGS" ]; then
  tmp=$(mktemp)
  jq --argjson sl "$STATUSLINE_JSON" '.statusLine = $sl' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"
else
  jq -n --argjson sl "$STATUSLINE_JSON" '{statusLine: $sl}' > "$SETTINGS"
fi

echo "statusLine setup complete: $STATUSLINE_DST -> $STATUSLINE_SRC"
