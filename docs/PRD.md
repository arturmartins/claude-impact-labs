# PRD: Tide, an agent notification batcher

Hackathon build, 29 October 2026. Living version: the Claude Doc this was exported from.

## Summary

Tide holds Claude Code's "I need you" notifications in a queue and delivers them as one digest every 30 minutes, so parallel agents stop interrupting you one at a time. It is a `Notification` hook, a small queue file and a scheduled flush, written as one stdlib-only Python file.

It is our own idea, not one of the six examples. It sits closest to the workload tracker, but where that shows the load, Tide removes some of it.

## Problem

Running agents in parallel turns one long task into many short interruptions. Each Claude Code session notifies you on its own clock: a permission prompt after about 6 seconds of waiting, an idle prompt about 60 seconds after it finishes ([hooks guide](https://code.claude.com/docs/en/hooks-guide)). With three or four sessions open, those land at random through the day.

This is compression burnout in its plainest form. The waiting time between tasks used to be a break. Now it is filled by the next agent asking for you.

## Who it's for

- **Primary:** developers who run two or more Claude Code sessions at once, on macOS or Linux desktop.
- **Not for:** single-session users, and on-call engineers who need alerts the moment they fire. Tide never touches pager or chat notifications.

## Goals

1. Replace one-by-one agent notifications with one digest per interval, 30 minutes by default.
2. Drop items you already dealt with, so a digest never sends you to a session that has moved on.
3. Install with one command and need nothing from you afterwards.
4. Show its own effect: notifications caught versus digests sent, from its own log.

## Non-goals

- Changing how Claude Code asks for permission. Tide only changes when you hear about it.
- Chat, email, pager or calendar notifications.
- Windows support tonight.
- Any hosted service, account or API key.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| R1 | `tide hook` reads the Notification JSON from stdin, appends one line to the queue and exits 0 in under 100 ms | Tonight |
| R2 | Types to batch are set in config. Default: `idle_prompt`, `permission_prompt`, `agent_needs_input`, `agent_completed`, `elicitation_dialog` | Tonight |
| R3 | Types not in the batch list pass straight through to a desktop notification | Tonight |
| R4 | `tide flush` keeps the newest item per session and drops any item whose session transcript changed after it was queued | Tonight |
| R5 | `tide flush` sends one desktop notification listing each waiting session by folder and reason, and writes the digest to `~/.tide/last-digest.md` | Tonight |
| R6 | `tide install` merges the hook into `~/.claude/settings.json` without removing other hooks, backs it up first, and sets up the schedule | Tonight |
| R7 | `tide status` shows what is queued and today's caught-versus-sent count | Tonight |
| R8 | `tide uninstall` removes Tide's hook and the schedule, leaving other settings as they are | Tonight |
| R9 | `tide now` flushes immediately | Should |
| R10 | Quiet hours: nothing delivered between set times; the queue waits until morning | Should |
| R11 | Interval aligned to the clock (:00 and :30) | Should |
| R12 | Windows support | Later |

## Technical design

See `CLAUDE.md` for the exact CLI contract the code must meet.

- **Hook input:** JSON on stdin with `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `message`, `notification_type`.
- **Queue:** `~/.tide/queue.jsonl`, appended under `fcntl.flock`.
- **Staleness:** at flush, drop an item if its transcript was modified more than 2 s after `queued_at`; keep the newest per `session_id`.
- **Schedule:** launchd on macOS, user crontab on Linux.
- **Delivery:** `osascript` or `notify-send`, plus `~/.tide/last-digest.md`.
- **Counting:** `~/.tide/log.jsonl`.

## Risks

| Risk | Mitigation |
| --- | --- |
| A batched permission prompt stalls an agent for up to 30 minutes | Documented; `permission_prompt` can be removed from `batch_types`; `tide now` |
| Claude Code's built-in notification still fires | Documented in the README: `preferredNotifChannel` = `notifications_disabled`. Not changed by `install` |
| Other Notification hooks still send popups | `install` lists them |
| Install breaks `settings.json` | Back up first, merge with `json`, test covers it |
| No notifier available | `last-digest.md` always written |
| Staleness drops a real item | Only drop on a transcript change after queuing; every drop is logged |
