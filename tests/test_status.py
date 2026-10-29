"""R7: status shows what is queued and today's caught-versus-sent counts."""
import re


def count(pattern: str, text: str) -> int:
    match = re.search(pattern, text)
    assert match, f"{pattern!r} not found in:\n{text}"
    return int(match.group(1))


def test_status_on_a_fresh_install(tide):
    result = tide.run("status")

    assert result.returncode == 0, result.stderr
    assert count(r"(\d+) queued", result.stdout) == 0
    assert count(r"(\d+) caught", result.stdout) == 0
    assert count(r"(\d+) digests?\b", result.stdout) == 0


def test_status_counts_caught_and_digests(tide):
    tide.hook(tide.event("idle_prompt", session="a"))
    tide.hook(tide.event("permission_prompt", session="b"))
    tide.run("flush")
    tide.hook(tide.event("idle_prompt", session="c"))

    out = tide.run("status").stdout

    assert count(r"(\d+) queued", out) == 1
    assert count(r"(\d+) caught", out) == 3
    assert count(r"(\d+) digests?\b", out) == 1


def test_passthrough_is_not_counted_as_caught(tide):
    tide.hook(tide.event("auth_success"))

    assert count(r"(\d+) caught", tide.run("status").stdout) == 0
