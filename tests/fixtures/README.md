# Test fixtures

Notification hook input, one JSON object per file.

| File | Source |
| --- | --- |
| `permission_prompt.json` | Synthetic, from the documented schema. Replace with a recording. |
| `idle_prompt.json` | Synthetic, from the documented schema. Replace with a recording. |
| `auth_success.json` | Synthetic. Used only as a type that is not batched. |

Record real ones with `scripts/record-hook.sh` (see `CLAUDE.md`, step 1). The tests overwrite `session_id`, `cwd` and `transcript_path` with temporary values, so recorded files can be committed as they are once you have checked they hold nothing private.
