# Tide: instructions for the coding agent

Tide batches Claude Code `Notification` hook events into one digest per interval, so developers running several agent sessions are not interrupted one by one. The full spec is `docs/PRD.md`. This file is how to build it.

This is a 2-hour hackathon build, judged by an agent that reads the README and code. Working, honest and small beats clever.

## Hard rules

- **One file:** all logic lives in `tide.py`. Python 3.11+, standard library only. No third-party imports in `tide.py`.
- **Never touch the real home directory in tests.** Every path comes from these environment variables, with these defaults:
  - `TIDE_HOME`, default `~/.tide`
  - `TIDE_CLAUDE_SETTINGS`, default `~/.claude/settings.json`
  - `TIDE_NOTIFY_CMD`, default unset. When set, deliver by running `$TIDE_NOTIFY_CMD "<title>" "<body>"` instead of `osascript` / `notify-send`.
  - `TIDE_NO_SCHEDULE=1` makes `install` and `uninstall` skip launchd and cron.
- **Nothing faked.** No hardcoded counts, sample digests or demo numbers in code or README. README output must be pasted from a real run.
- **The hook must never break Claude Code.** `tide.py hook` always exits 0, even on bad input, and returns in well under a second. Errors go to `$TIDE_HOME/error.log`.
- **Do not edit `tests/` to make them pass.** If a test looks wrong, stop and say why. You may add tests.
- Commit after each step below, with a short message naming the step.

## CLI contract

| Command | Does |
| --- | --- |
| `tide.py hook` | Reads one Notification JSON from stdin. If `notification_type` is in `batch_types`, appends it to `$TIDE_HOME/queue.jsonl` with `queued_at` (epoch seconds, float) and logs `caught`. Otherwise delivers it at once and logs `passthrough`. |
| `tide.py flush` | Takes the queue under an exclusive lock and empties it. Drops items whose `transcript_path` file was modified more than 2 s after `queued_at` (logs `dropped`). Keeps the newest item per `session_id`. If any remain, delivers one notification, writes `$TIDE_HOME/last-digest.md`, logs `digest`. If none remain, delivers nothing. |
| `tide.py now` | Same as `flush`. |
| `tide.py status` | Prints `<n> queued` and today's counts as `<n> caught` and `<m> digests` (singular `digest` for 1). "Today" is local time. |
| `tide.py install` | Copies itself to `$TIDE_HOME/tide.py`. Backs up the settings file (if it exists) to `<settings>.tide-backup`, adds Tide's Notification hook (`python3 <TIDE_HOME>/tide.py hook`, matcher `""`) without touching anything else, and is idempotent. Creates the settings file if missing. Prints the command of each other Notification hook it finds. Sets up the schedule unless `TIDE_NO_SCHEDULE=1`. |
| `tide.py uninstall` | Removes only Tide's hook entry and the schedule. Leaves every other setting as it is now. |

Logs are JSON lines in `$TIDE_HOME/log.jsonl`: `{"ts": <epoch>, "event": "caught" | "passthrough" | "dropped" | "digest", ...}`.

Config is optional, `$TIDE_HOME/config.toml`, read with `tomllib`:

```toml
interval_minutes = 30
batch_types = ["idle_prompt", "permission_prompt", "agent_needs_input", "agent_completed", "elicitation_dialog"]
```

**Tide's hook entry** is any hook whose `command` contains `tide.py hook`. `install` and `uninstall` find it that way.

**Digest text.** Title `Tide`. Body: `1 agent waiting: <folder> (<reason>)` or `3 agents waiting: <folder> (<reason>), ...`, newest first, where folder is the basename of `cwd` and reason maps `permission_prompt` → permission, `idle_prompt` → idle, `agent_completed` → finished, `agent_needs_input` → needs input, `elicitation_dialog` → form, anything else → the raw type. `last-digest.md` lists each item with folder, reason, message and time queued.

**Schedule.** macOS: a launchd agent `~/Library/LaunchAgents/ai.tide.flush.plist` with `StartCalendarInterval` at minutes 0 and 30. Linux: one user crontab line `*/30 * * * * python3 <TIDE_HOME>/tide.py flush # tide`. Derive the minutes from `interval_minutes`.

## Order of work

Run `pytest -q` after each step. Each step should turn more tests green.

1. **Real fixtures.** The files in `tests/fixtures/` are synthetic, built from the documented schema. Run `scripts/record-hook.sh on`, then ask the human to open a second terminal in this repo, start `claude`, trigger a permission prompt and wait 10 s, then leave it idle for 70 s. Run `scripts/record-hook.sh split` and `scripts/record-hook.sh off`. Keep the recorded `permission_prompt.json` and `idle_prompt.json` (tests only rely on the documented fields), and update `tests/fixtures/README.md` to say which are recorded. If the recorded JSON differs from the contract above, stop and tell the human.
2. **`hook`:** `tests/test_hook.py`.
3. **`flush` and `now`:** `tests/test_flush.py`.
4. **`status`:** `tests/test_status.py`.
5. **`install` and `uninstall`:** `tests/test_install.py`. Then the schedule code (not unit tested; test it by hand on this machine).
6. **README:** fill every `TODO(real-run)` with output from a real run on this machine.

## Definition of done

- `pytest -q` passes locally, and CI is green on Ubuntu and macOS.
- `./install.sh` works on this machine, and a real digest has arrived.
- No `TODO` left in `README.md`.
