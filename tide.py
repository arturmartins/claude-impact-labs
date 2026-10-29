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


def cmd_install(args: argparse.Namespace) -> int:
    raise NotImplementedError("install")


def cmd_uninstall(args: argparse.Namespace) -> int:
    raise NotImplementedError("uninstall")


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
