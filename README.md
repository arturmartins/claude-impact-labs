# Tide

[![tests](https://github.com/OWNER/tide/actions/workflows/test.yml/badge.svg)](https://github.com/OWNER/tide/actions/workflows/test.yml)

Tide batches Claude Code notifications into one digest every 30 minutes. For developers running several agents at once.

**Not one of the six hackathon examples.** AI made each task faster, so we run more of them, and their interruptions now arrive one by one. That is compression burnout: the gaps between tasks used to be breaks, and now the next agent fills them. Tide gives the gaps back.

## Install

Requires Python 3.11+ on macOS or Linux. No accounts, no API keys, no dependencies.

```bash
git clone https://github.com/OWNER/tide && cd tide && ./install.sh
```

This adds one Notification hook to `~/.claude/settings.json` (backed up first) and schedules a flush at :00 and :30.

## What happens

Your agents keep working. When one needs you, Tide holds the notification. Every 30 minutes you get one notification instead:

```
TODO(real-run): paste a real digest here
```

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
TODO(real-run): paste real `tide.py status` output here
```

## Configure

Optional `~/.tide/config.toml`:

```toml
interval_minutes = 30
batch_types = ["idle_prompt", "permission_prompt", "agent_needs_input", "agent_completed", "elicitation_dialog"]
```

Types not listed are delivered straight away.

## Limits

- **Agents can wait up to one interval for you.** That is the point, but if a stalled permission prompt costs you more than the interruption, remove `permission_prompt` from `batch_types`.
- Claude Code's own built-in notification, and any other Notification hooks you have, still run. `install` lists the other hooks it finds.
- macOS: `osascript` needs Script Editor to have notification permission. Linux: needs `notify-send`. The digest is always written to `~/.tide/last-digest.md` too.
- No Windows support yet.

## Tests

```bash
pytest -q
```

CI runs them on Ubuntu and macOS. Test fixtures in `tests/fixtures/` are hook JSON recorded from real Claude Code sessions.

## Spec

[`docs/PRD.md`](docs/PRD.md)

## Licence

MIT
