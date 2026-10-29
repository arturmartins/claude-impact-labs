"""R6, R8: install merges the hook safely; uninstall removes only Tide's entry."""
import json

EXISTING = {
    "model": "opus",
    "hooks": {
        "PostToolUse": [
            {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "prettier --write"}]}
        ],
        "Notification": [
            {"matcher": "", "hooks": [{"type": "command", "command": "say hello"}]}
        ],
    },
}


def write_settings(tide, data):
    tide.settings.parent.mkdir(parents=True, exist_ok=True)
    tide.settings.write_text(json.dumps(data, indent=2))


def read_settings(tide):
    return json.loads(tide.settings.read_text())


def notification_commands(settings):
    return [
        h["command"]
        for group in settings.get("hooks", {}).get("Notification", [])
        for h in group.get("hooks", [])
    ]


def tide_commands(settings):
    return [c for c in notification_commands(settings) if "tide.py hook" in c]


def test_install_adds_hook_and_keeps_everything_else(tide):
    write_settings(tide, EXISTING)

    result = tide.run("install")

    assert result.returncode == 0, result.stderr
    settings = read_settings(tide)
    assert settings["model"] == "opus"
    assert settings["hooks"]["PostToolUse"] == EXISTING["hooks"]["PostToolUse"]
    assert "say hello" in notification_commands(settings)
    assert len(tide_commands(settings)) == 1
    assert str(tide.home / "tide.py") in tide_commands(settings)[0]


def test_install_backs_up_settings_first(tide):
    write_settings(tide, EXISTING)
    tide.run("install")

    backup = tide.settings.with_name(tide.settings.name + ".tide-backup")
    assert json.loads(backup.read_text()) == EXISTING


def test_install_copies_itself_into_tide_home(tide):
    tide.run("install")

    assert (tide.home / "tide.py").is_file()


def test_install_is_idempotent(tide):
    write_settings(tide, EXISTING)
    tide.run("install")
    tide.run("install")

    assert len(tide_commands(read_settings(tide))) == 1


def test_install_creates_missing_settings(tide):
    result = tide.run("install")

    assert result.returncode == 0, result.stderr
    assert len(tide_commands(read_settings(tide))) == 1


def test_install_lists_other_notification_hooks(tide):
    write_settings(tide, EXISTING)

    result = tide.run("install")

    assert "say hello" in result.stdout


def test_uninstall_removes_only_tide(tide):
    write_settings(tide, EXISTING)
    tide.run("install")
    settings = read_settings(tide)
    settings["theme"] = "dark"  # a change made after install must survive uninstall
    write_settings(tide, settings)

    result = tide.run("uninstall")

    assert result.returncode == 0, result.stderr
    after = read_settings(tide)
    assert tide_commands(after) == []
    assert "say hello" in notification_commands(after)
    assert after["theme"] == "dark"
    assert after["hooks"]["PostToolUse"] == EXISTING["hooks"]["PostToolUse"]


def test_installed_hook_command_actually_works(tide):
    """The command written to settings must run and queue an event end to end."""
    import shlex
    import subprocess

    tide.run("install")
    command = tide_commands(read_settings(tide))[0]

    result = subprocess.run(
        shlex.split(command),
        input=json.dumps(tide.event("idle_prompt")),
        capture_output=True,
        text=True,
        env=tide.env,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert len(tide.queue()) == 1
