"""Shared test harness. Runs tide.py as a subprocess with every path redirected into tmp_path."""
from __future__ import annotations

import json
import os
import pathlib
import shlex
import subprocess
import sys
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
TIDE = REPO / "tide.py"
FIXTURES = REPO / "tests" / "fixtures"


class Tide:
    def __init__(self, tmp_path: pathlib.Path):
        self.tmp = tmp_path
        self.home = tmp_path / "tide-home"
        self.settings = tmp_path / "claude" / "settings.json"
        self.notified = tmp_path / "notified.jsonl"

        notifier = tmp_path / "notify.py"
        notifier.write_text(
            "import json, sys\n"
            f"with open({str(self.notified)!r}, 'a') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        )
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()

        self.env = {
            **os.environ,
            "HOME": str(fake_home),
            "TIDE_HOME": str(self.home),
            "TIDE_CLAUDE_SETTINGS": str(self.settings),
            "TIDE_NOTIFY_CMD": f"{shlex.quote(sys.executable)} {shlex.quote(str(notifier))}",
            "TIDE_NO_SCHEDULE": "1",
        }

    def run(self, *args: str, stdin: str | None = None, timeout: float = 10) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TIDE), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=timeout,
        )

    def event(self, fixture: str, session: str = "s1", folder: str = "proj", transcript_age: float = 100) -> dict:
        """A fixture with its paths pointed into tmp_path. The transcript was last written `transcript_age` seconds ago."""
        data = json.loads((FIXTURES / f"{fixture}.json").read_text())
        cwd = self.tmp / "projects" / folder
        cwd.mkdir(parents=True, exist_ok=True)
        transcript = self.tmp / "transcripts" / f"{session}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        if not transcript.exists():
            transcript.write_text("{}\n")
        t = time.time() - transcript_age
        os.utime(transcript, (t, t))
        data.update(session_id=session, cwd=str(cwd), transcript_path=str(transcript))
        return data

    def hook(self, event: dict) -> subprocess.CompletedProcess:
        return self.run("hook", stdin=json.dumps(event))

    def touch_transcript(self, event: dict, seconds_from_now: float = 10) -> None:
        t = time.time() + seconds_from_now
        os.utime(event["transcript_path"], (t, t))

    @staticmethod
    def _jsonl(path: pathlib.Path) -> list:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def queue(self) -> list[dict]:
        return self._jsonl(self.home / "queue.jsonl")

    def log(self) -> list[dict]:
        return self._jsonl(self.home / "log.jsonl")

    def notifications(self) -> list[list[str]]:
        return self._jsonl(self.notified)

    def write_config(self, text: str) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "config.toml").write_text(text)


@pytest.fixture
def tide(tmp_path: pathlib.Path) -> Tide:
    return Tide(tmp_path)
