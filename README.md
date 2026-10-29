# Tide

[![tests](https://github.com/arturmartins/claude-impact-labs/actions/workflows/test.yml/badge.svg)](https://github.com/arturmartins/claude-impact-labs/actions/workflows/test.yml)

Tide batches Claude Code notifications into one digest every 30 minutes. For developers running several agents at once.

**Not one of the six hackathon examples.** AI made each task faster, so we run more of them, and their interruptions now arrive one by one. That is compression burnout: the gaps between tasks used to be breaks, and now the next agent fills them. Tide gives the gaps back.

## Install

Requires Python 3.11+ on macOS or Linux. No accounts, no API keys, no dependencies.

```bash
git clone https://github.com/arturmartins/claude-impact-labs && cd claude-impact-labs && ./install.sh
```

This adds one Notification hook to `~/.claude/settings.json` (backed up first) and schedules a flush at :00 and :30.

## What happens

Your agents keep working. When one needs you, Tide holds the notification. Every 30 minutes you get one notification instead:

```
Tide
1 agent waiting: claude-impact-labs (idle)
```

That is the notification from a real run on the author's Mac. Two events recorded from a real Claude Code session (a permission prompt, then an idle prompt) went through the installed hook. Tide kept the newest one for the session and sent a single digest. `~/.tide/last-digest.md` holds the same digest with each message and the time it was queued.

Anything you already answered before the digest is dropped, so it never sends you to a session that has moved on.

## Commands

| Command | Does |
| --- | --- |
| `python3 ~/.tide/tide.py status` | What is waiting, and today's notifications caught versus digests sent |
| `python3 ~/.tide/tide.py now` | Send the digest now, for when you sit down between blocks |
| `python3 ~/.tide/tide.py uninstall` | Remove Tide's hook and schedule; nothing else changes |

## How it gives time back

- It removes interruptions. It adds no prompts, alerts or dashboards.
- Nothing to remember: once installed, it runs on its own.
- Measured from its own log on our machine tonight:

```
$ python3 ~/.tide/tide.py status
0 queued
today: 2 caught, 1 digest
```

Two notifications caught, one digest sent. These are the counts from that run, read from `~/.tide/log.jsonl`.

## Configure

Optional `~/.tide/config.toml`:

```toml
interval_minutes = 30
batch_types = ["idle_prompt", "permission_prompt", "agent_needs_input", "agent_completed", "elicitation_dialog"]
```

Types not listed are delivered straight away.

## Limits

- **Agents can wait up to one interval for you.** That is the point, but if a stalled permission prompt costs you more than the interruption, remove `permission_prompt` from `batch_types`.
- Claude Code's own built-in notification, and any other Notification hooks you have, still run. `install` lists the other hooks it finds. To turn the built-in one off, set `"preferredNotifChannel": "notifications_disabled"` in `~/.claude/settings.json` ([settings reference](https://code.claude.com/docs/en/settings-reference#preferrednotifchannel)). By default Claude Code sends its own desktop notification in iTerm2, Ghostty and Kitty. Tide does not change this setting for you.
- macOS: `osascript` sends notifications through the built-in Script Editor app. Without notification permission the command fails silently, and macOS does not prompt for it, so Tide cannot tell that the digest did not show. Run `osascript -e 'display notification "test"'` once, then open System Settings > Notifications, find Script Editor and turn on Allow Notifications ([Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide#get-notified-when-claude-needs-input)). Linux: needs `notify-send` and a notification daemon. The digest is always written to `~/.tide/last-digest.md` too.
- No Windows support yet.

## Tests

```bash
pytest -q
```

CI runs them on Ubuntu and macOS. The `permission_prompt` and `idle_prompt` fixtures in `tests/fixtures/` are hook JSON recorded from a real Claude Code session; `auth_success` is synthetic (see `tests/fixtures/README.md`).

## Spec

[`docs/PRD.md`](docs/PRD.md)

## Licence

MIT
