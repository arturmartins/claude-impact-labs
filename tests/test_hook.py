"""R1-R3: the hook queues batched types, passes others through, and never breaks Claude Code."""
import json
import subprocess
import sys
import time

from conftest import TIDE


def test_batched_type_is_queued_not_delivered(tide):
    result = tide.hook(tide.event("permission_prompt"))

    assert result.returncode == 0, result.stderr
    queue = tide.queue()
    assert len(queue) == 1
    assert queue[0]["session_id"] == "s1"
    assert queue[0]["notification_type"] == "permission_prompt"
    assert isinstance(queue[0]["queued_at"], float)
    assert abs(queue[0]["queued_at"] - time.time()) < 30
    assert tide.notifications() == []


def test_batched_type_is_logged_as_caught(tide):
    tide.hook(tide.event("idle_prompt"))

    assert [e["event"] for e in tide.log()] == ["caught"]


def test_unbatched_type_is_delivered_now(tide):
    result = tide.hook(tide.event("auth_success"))

    assert result.returncode == 0, result.stderr
    assert tide.queue() == []
    sent = tide.notifications()
    assert len(sent) == 1
    assert "Authentication successful" in " ".join(sent[0])
    assert [e["event"] for e in tide.log()] == ["passthrough"]


def test_config_controls_which_types_are_batched(tide):
    tide.write_config('batch_types = ["idle_prompt"]\n')

    tide.hook(tide.event("permission_prompt", session="a"))
    tide.hook(tide.event("idle_prompt", session="b"))

    assert [q["session_id"] for q in tide.queue()] == ["b"]
    assert len(tide.notifications()) == 1


def test_bad_input_still_exits_zero(tide):
    for stdin in ["", "not json", "[]", '{"no": "fields"}']:
        result = tide.run("hook", stdin=stdin)
        assert result.returncode == 0, (stdin, result.stderr)


def test_hook_is_fast(tide):
    event = tide.event("idle_prompt")
    start = time.monotonic()
    tide.hook(event)
    assert time.monotonic() - start < 2.0


def test_parallel_hooks_do_not_corrupt_the_queue(tide):
    procs = [
        subprocess.Popen(
            [sys.executable, str(TIDE), "hook"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=tide.env,
        )
        for _ in range(20)
    ]
    for i, proc in enumerate(procs):
        proc.communicate(json.dumps(tide.event("idle_prompt", session=f"s{i}")), timeout=20)

    queue = tide.queue()
    assert len(queue) == 20
    assert {q["session_id"] for q in queue} == {f"s{i}" for i in range(20)}
