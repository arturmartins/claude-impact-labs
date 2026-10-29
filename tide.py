#!/usr/bin/env python3
"""Tide: batch Claude Code notifications into one digest per interval.

See CLAUDE.md for the CLI contract and docs/PRD.md for the spec.
Standard library only. Python 3.11+.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
import traceback
from pathlib import Path

DEFAULT_BATCH_TYPES = [
    "idle_prompt",
    "permission_prompt",
    "agent_needs_input",
    "agent_completed",
    "elicitation_dialog",
]


def tide_home() -> Path:
    return Path(os.environ.get("TIDE_HOME") or Path.home() / ".tide")


def log_error(message: str) -> None:
    try:
        home = tide_home()
        home.mkdir(parents=True, exist_ok=True)
        with open(home / "error.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def load_config() -> dict:
    config = {"interval_minutes": 30, "batch_types": list(DEFAULT_BATCH_TYPES)}
    try:
        with open(tide_home() / "config.toml", "rb") as f:
            config.update(tomllib.load(f))
    except FileNotFoundError:
        pass
    except (OSError, tomllib.TOMLDecodeError):
        log_error("bad config.toml, using defaults\n" + traceback.format_exc())
    return config


def append_line(path: Path, record: dict) -> None:
    """Append one JSON line under an exclusive lock, so parallel writers never interleave."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(record) + "\n")
        f.flush()


def log_event(event: str, **fields) -> None:
    append_line(tide_home() / "log.jsonl", {"ts": time.time(), "event": event, **fields})


def deliver(title: str, body: str) -> None:
    """Show a desktop notification. Failure is logged, never raised: last-digest.md is the fallback."""
    try:
        custom = os.environ.get("TIDE_NOTIFY_CMD")
        if custom:
            cmd = [*shlex.split(custom), title, body]
        elif sys.platform == "darwin":
            script = f"display notification {json.dumps(body)} with title {json.dumps(title)}"
            cmd = ["osascript", "-e", script]
        elif shutil.which("notify-send"):
            cmd = ["notify-send", title, body]
        else:
            log_error("no notifier available (osascript / notify-send)")
            return
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
    except Exception:
        log_error("delivery failed\n" + traceback.format_exc())


def cmd_hook(args: argparse.Namespace) -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("hook input is not a JSON object")
        ntype = event.get("notification_type")
        if ntype in load_config()["batch_types"]:
            append_line(tide_home() / "queue.jsonl", {**event, "queued_at": time.time()})
            log_event("caught", notification_type=ntype, session_id=event.get("session_id"))
        else:
            deliver("Claude Code", str(event.get("message") or ntype or "Notification"))
            log_event("passthrough", notification_type=ntype, session_id=event.get("session_id"))
    except Exception:
        log_error("hook failed\n" + traceback.format_exc())
    return 0


REASONS = {
    "permission_prompt": "permission",
    "idle_prompt": "idle",
    "agent_completed": "finished",
    "agent_needs_input": "needs input",
    "elicitation_dialog": "form",
}
STALE_AFTER = 2.0


def take_queue() -> list[dict]:
    """Read and empty the queue under an exclusive lock, so no hook line is lost or read twice."""
    path = tide_home() / "queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    items = []
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        for line in f.read().splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                log_error(f"skipped bad queue line: {line[:200]}")
                continue
            if isinstance(item, dict):
                items.append(item)
        f.truncate(0)
    return items


def is_stale(item: dict) -> bool:
    try:
        modified = os.stat(item["transcript_path"]).st_mtime
    except (KeyError, TypeError, OSError):
        return False
    return modified - float(item.get("queued_at", 0)) > STALE_AFTER


def digest_line(item: dict) -> str:
    folder = os.path.basename(str(item.get("cwd") or "").rstrip("/")) or "unknown"
    ntype = item.get("notification_type")
    return f"{folder} ({REASONS.get(ntype, ntype)})"


def cmd_flush(args: argparse.Namespace) -> int:
    newest: dict[str, dict] = {}
    for item in take_queue():
        key = str(item.get("session_id"))
        if key not in newest or item.get("queued_at", 0) >= newest[key].get("queued_at", 0):
            newest[key] = item

    kept = []
    for item in newest.values():
        if is_stale(item):
            log_event("dropped", session_id=item.get("session_id"), notification_type=item.get("notification_type"))
        else:
            kept.append(item)
    if not kept:
        return 0

    kept.sort(key=lambda i: i.get("queued_at", 0), reverse=True)
    n = len(kept)
    body = f"{n} agent{'s' if n != 1 else ''} waiting: " + ", ".join(digest_line(i) for i in kept)
    lines = [f"# Tide digest, {time.strftime('%Y-%m-%d %H:%M')}", ""]
    for item in kept:
        queued = time.strftime("%H:%M:%S", time.localtime(item.get("queued_at", 0)))
        lines.append(f"- **{digest_line(item)}**: {item.get('message', '')} (queued {queued})")
    (tide_home() / "last-digest.md").write_text("\n".join(lines) + "\n")

    deliver("Tide", body)
    log_event("digest", count=n)
    return 0


def read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    records = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def cmd_status(args: argparse.Namespace) -> int:
    home = tide_home()
    queued = len(read_jsonl(home / "queue.jsonl"))
    today = time.localtime()[:3]
    events = [
        e.get("event")
        for e in read_jsonl(home / "log.jsonl")
        if isinstance(e.get("ts"), (int, float)) and time.localtime(e["ts"])[:3] == today
    ]
    caught, digests = events.count("caught"), events.count("digest")
    print(f"{queued} queued")
    print(f"today: {caught} caught, {digests} digest{'s' if digests != 1 else ''}")
    return 0


HOOK_MARKER = re.compile(r"tide\.py['\"]? hook")
PLIST_LABEL = "ai.tide.flush"
CRON_TAG = "# tide"


def settings_path() -> Path:
    return Path(os.environ.get("TIDE_CLAUDE_SETTINGS") or Path.home() / ".claude" / "settings.json")


def is_tide_hook(hook: dict) -> bool:
    return bool(HOOK_MARKER.search(str(hook.get("command", ""))))


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def save_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tide-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def notification_hooks(settings: dict) -> list[dict]:
    groups = settings.get("hooks", {}).get("Notification", [])
    return [h for g in groups if isinstance(g, dict) for h in g.get("hooks", []) if isinstance(h, dict)]


def schedule_times(interval: int) -> tuple[list[tuple[int | None, int]], str]:
    """(launchd Hour/Minute pairs, cron time fields) for an interval that divides the hour or the day."""
    if interval < 60 and 60 % interval == 0:
        return [(None, m) for m in range(0, 60, interval)], f"*/{interval} * * * *"
    if interval % 60 == 0 and 24 % (interval // 60) == 0:
        step = interval // 60
        return [(h, 0) for h in range(0, 24, step)], f"0 */{step} * * *"
    raise ValueError(f"interval_minutes = {interval} must divide an hour or a day evenly")


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def install_schedule(interval: int) -> str:
    pairs, cron_time = schedule_times(interval)
    script = tide_home() / "tide.py"
    if sys.platform == "darwin":
        calendar = [{k: v for k, v in (("Hour", h), ("Minute", m)) if not (k == "Hour" and v is None)} for h, m in pairs]
        plist = {
            "Label": PLIST_LABEL,
            "ProgramArguments": ["/usr/bin/env", "python3", str(script), "flush"],
            "StartCalendarInterval": calendar,
            "StandardErrorPath": str(tide_home() / "launchd.err"),
        }
        path = plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        launchctl("bootout", f"gui/{os.getuid()}", str(path))  # makes re-install idempotent
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        result = launchctl("bootstrap", f"gui/{os.getuid()}", str(path))
        if result.returncode != 0:
            return f"wrote {path} but launchctl bootstrap failed: {result.stderr.strip()}"
        return f"launchd agent {PLIST_LABEL} loaded, every {interval} min"
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [ln for ln in existing.stdout.splitlines() if not ln.rstrip().endswith(CRON_TAG)]
    lines.append(f"{cron_time} python3 {script} flush {CRON_TAG}")
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
    return f"crontab entry added, every {interval} min"


def uninstall_schedule() -> str:
    if sys.platform == "darwin":
        path = plist_path()
        launchctl("bootout", f"gui/{os.getuid()}", str(path))
        if path.exists():
            path.unlink()
            return f"removed launchd agent {PLIST_LABEL}"
        return "no launchd agent to remove"
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = existing.stdout.splitlines()
    kept = [ln for ln in lines if not ln.rstrip().endswith(CRON_TAG)]
    if len(kept) == len(lines):
        return "no crontab entry to remove"
    subprocess.run(["crontab", "-"], input="\n".join(kept) + "\n" if kept else "", text=True, check=True)
    return "removed crontab entry"


def cmd_install(args: argparse.Namespace) -> int:
    home, path = tide_home(), settings_path()
    try:
        settings = load_settings(path)
    except (ValueError, OSError) as e:
        print(f"tide: cannot read {path}: {e}. Nothing changed.", file=sys.stderr)
        return 1

    home.mkdir(parents=True, exist_ok=True)
    target = home / "tide.py"
    if Path(__file__).resolve() != target.resolve():
        shutil.copy2(__file__, target)
    command = f"python3 {target} hook"

    others = [h.get("command", "") for h in notification_hooks(settings) if not is_tide_hook(h)]
    groups = settings.setdefault("hooks", {}).setdefault("Notification", [])
    ours = [h for g in groups if isinstance(g, dict) for h in g.get("hooks", []) if isinstance(h, dict) and is_tide_hook(h)]
    if ours:
        changed = any(h.get("command") != command for h in ours)
        for h in ours:
            h["command"] = command
    else:
        groups.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
        changed = True
    if changed:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".tide-backup"))
        save_settings(path, settings)
    print(f"Hook {'updated' if ours else 'added'} in {path}: {command}")
    for other in others:
        print(f"Other Notification hook still active: {other}")

    if os.environ.get("TIDE_NO_SCHEDULE") == "1":
        print("Schedule skipped (TIDE_NO_SCHEDULE=1)")
        return 0
    try:
        print(install_schedule(int(load_config()["interval_minutes"])))
    except Exception as e:
        print(f"tide: hook installed but the schedule was not: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    path = settings_path()
    try:
        settings = load_settings(path)
    except (ValueError, OSError) as e:
        print(f"tide: cannot read {path}: {e}. Nothing changed.", file=sys.stderr)
        return 1

    groups = settings.get("hooks", {}).get("Notification")
    if isinstance(groups, list):
        removed = 0
        for g in groups:
            if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                before = len(g["hooks"])
                g["hooks"] = [h for h in g["hooks"] if not (isinstance(h, dict) and is_tide_hook(h))]
                removed += before - len(g["hooks"])
        if removed:
            settings["hooks"]["Notification"] = [g for g in groups if not (isinstance(g, dict) and g.get("hooks") == [])]
            if not settings["hooks"]["Notification"]:
                del settings["hooks"]["Notification"]
            if not settings["hooks"]:
                del settings["hooks"]
            save_settings(path, settings)
        print(f"Removed {removed} Tide hook{'s' if removed != 1 else ''} from {path}")

    if os.environ.get("TIDE_NO_SCHEDULE") != "1":
        try:
            print(uninstall_schedule())
        except Exception as e:
            print(f"tide: schedule not removed: {e}", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tide", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hook", help="read one Notification event from stdin").set_defaults(func=cmd_hook)
    sub.add_parser("flush", help="send the digest for everything queued").set_defaults(func=cmd_flush)
    sub.add_parser("now", help="same as flush").set_defaults(func=cmd_flush)
    sub.add_parser("status", help="show what is queued and today's counts").set_defaults(func=cmd_status)
    sub.add_parser("install", help="add the hook and the schedule").set_defaults(func=cmd_install)
    sub.add_parser("uninstall", help="remove the hook and the schedule").set_defaults(func=cmd_uninstall)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
