"""R4, R5, R9: flush drops what you already handled, keeps one item per session, sends one digest."""
import json


def body_of(notification: list[str]) -> str:
    assert notification[0] == "Tide"
    return notification[1]


def test_one_digest_for_several_sessions(tide):
    for session, folder, kind in [
        ("a", "api-gateway", "permission_prompt"),
        ("b", "depsguard", "idle_prompt"),
        ("c", "docs-site", "idle_prompt"),
    ]:
        tide.hook(tide.event(kind, session=session, folder=folder))

    result = tide.run("flush")

    assert result.returncode == 0, result.stderr
    sent = tide.notifications()
    assert len(sent) == 1
    body = body_of(sent[0])
    assert body.startswith("3 agents waiting:")
    assert "api-gateway (permission)" in body
    assert "depsguard (idle)" in body
    assert "docs-site (idle)" in body
    assert tide.queue() == []


def test_digest_is_written_to_file(tide):
    tide.hook(tide.event("permission_prompt", folder="api-gateway"))
    tide.run("flush")

    digest = (tide.home / "last-digest.md").read_text()
    assert "api-gateway" in digest
    assert "permission" in digest
    assert "Claude needs your permission" in digest


def test_single_agent_is_singular(tide):
    tide.hook(tide.event("idle_prompt", folder="depsguard"))
    tide.run("flush")

    assert body_of(tide.notifications()[0]).startswith("1 agent waiting:")


def test_item_already_handled_is_dropped(tide):
    event = tide.event("permission_prompt")
    tide.hook(event)
    tide.touch_transcript(event, seconds_from_now=10)

    tide.run("flush")

    assert tide.notifications() == []
    assert tide.queue() == []
    assert "dropped" in [e["event"] for e in tide.log()]


def test_only_newest_item_per_session_is_kept(tide):
    tide.hook(tide.event("idle_prompt", session="a", folder="api-gateway"))
    tide.hook(tide.event("permission_prompt", session="a", folder="api-gateway"))

    tide.run("flush")

    body = body_of(tide.notifications()[0])
    assert body.startswith("1 agent waiting:")
    assert "(permission)" in body
    assert "(idle)" not in body


def test_missing_transcript_is_kept(tide):
    event = tide.event("idle_prompt", folder="docs-site")
    event["transcript_path"] = str(tide.tmp / "does-not-exist.jsonl")
    tide.hook(event)

    tide.run("flush")

    assert "docs-site" in body_of(tide.notifications()[0])


def test_empty_queue_sends_nothing(tide):
    result = tide.run("flush")

    assert result.returncode == 0, result.stderr
    assert tide.notifications() == []
    assert "digest" not in [e["event"] for e in tide.log()]


def test_digest_is_logged(tide):
    tide.hook(tide.event("idle_prompt", session="a"))
    tide.hook(tide.event("idle_prompt", session="b"))
    tide.run("flush")

    digests = [e for e in tide.log() if e["event"] == "digest"]
    assert len(digests) == 1


def test_now_flushes_like_flush(tide):
    tide.hook(tide.event("idle_prompt", folder="depsguard"))

    result = tide.run("now")

    assert result.returncode == 0, result.stderr
    assert len(tide.notifications()) == 1
    assert tide.queue() == []


def test_items_queued_after_flush_wait_for_next_flush(tide):
    tide.hook(tide.event("idle_prompt", session="a"))
    tide.run("flush")
    tide.hook(tide.event("idle_prompt", session="b"))

    assert [q["session_id"] for q in tide.queue()] == ["b"]
    assert len(tide.notifications()) == 1
    json.dumps(tide.queue())  # still valid JSON lines


def test_sessions_in_the_same_folder_get_a_session_suffix(tide):
    tide.hook(tide.event("permission_prompt", session="aaaa1111", folder="proj"))
    tide.hook(tide.event("idle_prompt", session="bbbb2222", folder="proj"))
    tide.hook(tide.event("idle_prompt", session="cccc3333", folder="other"))

    tide.run("flush")

    body = body_of(tide.notifications()[0])
    assert "proj#aaaa (permission)" in body
    assert "proj#bbbb (idle)" in body
    assert "other (idle)" in body
    digest = (tide.home / "last-digest.md").read_text()
    assert "proj#aaaa (permission)" in digest
