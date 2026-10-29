#!/usr/bin/env bash
# Record real Claude Code Notification hook input, for test fixtures.
#
# Usage:
#   scripts/record-hook.sh on    # register this script as a Notification hook for this repo only
#   (start `claude` in this repo; trigger a permission prompt and wait ~6 s;
#    then let it finish and leave it idle ~60 s)
#   scripts/record-hook.sh off   # remove the hook again
#   scripts/record-hook.sh split # write one fixture file per notification type
#
# When Claude Code runs it as a hook (no argument), it appends stdin to tests/fixtures/recorded.jsonl.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
out="$repo/tests/fixtures/recorded.jsonl"
local_settings="$repo/.claude/settings.local.json"

case "${1:-record}" in
  on)
    python3 - "$local_settings" "$repo/scripts/record-hook.sh" <<'PY'
import json, sys, pathlib
path, script = pathlib.Path(sys.argv[1]), sys.argv[2]
data = json.loads(path.read_text()) if path.exists() else {}
entry = {"matcher": "", "hooks": [{"type": "command", "command": script}]}
data.setdefault("hooks", {}).setdefault("Notification", [])
if entry not in data["hooks"]["Notification"]:
    data["hooks"]["Notification"].append(entry)
path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Recording hook on in {path}")
PY
    ;;
  off)
    python3 - "$local_settings" "$repo/scripts/record-hook.sh" <<'PY'
import json, sys, pathlib
path, script = pathlib.Path(sys.argv[1]), sys.argv[2]
if path.exists():
    data = json.loads(path.read_text())
    groups = data.get("hooks", {}).get("Notification", [])
    data.get("hooks", {})["Notification"] = [
        g for g in groups if not any(h.get("command") == script for h in g.get("hooks", []))
    ]
    path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Recording hook off in {path}")
PY
    ;;
  split)
    python3 - "$out" "$repo/tests/fixtures" <<'PY'
import json, sys, pathlib
src, dest = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
for line in src.read_text().splitlines():
    if line.strip():
        event = json.loads(line)
        name = event.get("notification_type", "unknown")
        (dest / f"{name}.json").write_text(json.dumps(event, indent=2) + "\n")
        print(f"wrote {name}.json")
PY
    ;;
  record)
    mkdir -p "$(dirname "$out")"
    { cat; echo; } >> "$out"
    ;;
  *)
    echo "usage: $0 [on|off|split]" >&2
    exit 1
    ;;
esac
