# Test fixtures

Notification hook input, one JSON object per file.

| File | Source |
| --- | --- |
| `permission_prompt.json` | Recorded from a real Claude Code session on 2026-10-29 with `scripts/record-hook.sh`. |
| `idle_prompt.json` | Recorded from a real Claude Code session on 2026-10-29 with `scripts/record-hook.sh`. |
| `auth_success.json` | Synthetic. Used only as a type that is not batched. |

Recordings also carry `scratchpad_dir` and `prompt_id`, which are not in the documented schema; Tide ignores them. Record real ones with `scripts/record-hook.sh` (see `CLAUDE.md`, step 1). The tests overwrite `session_id`, `cwd` and `transcript_path` with temporary values, so recorded files can be committed as they are once you have checked they hold nothing private.
