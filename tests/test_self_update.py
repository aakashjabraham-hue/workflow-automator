"""Tests for self-update mechanics (install/update/uninstall) and the
cross-platform executor branches.  Hermetic: downloads and subprocesses are
mocked; HOME/XDG are isolated into tmp dirs."""

import io
import os
import shutil
import sys
import tarfile
import types

import pytest

import src.self_update as su
from src.engine import executor as exc_mod


def _make_tarball(path: str, version: str, launcher: str = "launcher-body") -> None:
    """Build a fake GitHub-style tarball: <name>-<ver>/{src/__init__.py, launcher.py}."""
    with tarfile.open(path, "w:gz") as tf:
        for name, content in [
            (f"wa-{version}/src/__init__.py", f'__version__ = "{version}"\n'),
            (f"wa-{version}/launcher.py", launcher),
        ]:
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def _isolate(tmp_path, monkeypatch):
    """Point all app paths at tmp dirs via HOME / XDG_DATA_HOME."""
    home = str(tmp_path / "home")
    data = str(tmp_path / "data")
    os.makedirs(home)
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("XDG_DATA_HOME", data)


class _FakeResult:
    returncode = 0
    stdout = ""
    stderr = ""


def test_fetch_and_seed_swaps_current(tmp_path, monkeypatch):
    tarball = str(tmp_path / "wa.tgz")
    _make_tarball(tarball, "9.9.9")
    _isolate(tmp_path, monkeypatch)

    calls = {}

    def fake_download(url, dest):
        calls["url"] = url
        shutil.copy(tarball, dest)
        return True

    monkeypatch.setattr(su, "_download", fake_download)
    version = su._fetch_and_seed()

    assert version == "9.9.9"
    cur = su.current_dir()
    assert os.path.isfile(os.path.join(cur, "launcher.py"))
    init = os.path.join(cur, "src", "__init__.py")
    assert open(init).read().strip() == '__version__ = "9.9.9"'
    # old copy should be cleaned up
    assert not os.path.isdir(os.path.join(su.app_base_dir(), "old"))
    assert su.REPO in calls["url"]


def test_fetch_and_seed_download_failure(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(su, "_download", lambda url, dest: False)
    assert su._fetch_and_seed() is None
    assert not os.path.isdir(su.current_dir())


def test_write_shim_posix(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    cur = su.current_dir()
    os.makedirs(os.path.join(cur, "src"), exist_ok=True)
    open(os.path.join(cur, "src", "__init__.py"), "w").write('__version__ = "0.2.0"\n')
    open(os.path.join(cur, "launcher.py"), "w").write("")

    path = su._write_shim()
    content = open(path).read()
    assert os.access(path, os.X_OK)
    assert cur in content
    assert "from src.main import main" in content


def test_update_already_current(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(su, "running_from_checkout", lambda: None)
    monkeypatch.setattr(su, "_fetch_and_seed", lambda: su.current_version())
    su.cmd_update()
    assert "Already on the latest version" in capsys.readouterr().out


def test_update_dev_checkout_uses_git_pull(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(su, "running_from_checkout", lambda: "/fake/checkout")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(su.subprocess, "run", fake_run)
    su.cmd_update()
    out = capsys.readouterr().out
    assert seen["cmd"][:2] == ["git", "-C"]
    assert "/fake/checkout" in seen["cmd"]
    assert "Pulled the latest code" in out


def test_uninstall_removes_files_keeps_db(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    os.makedirs(su.current_dir())
    open(su.current_dir() + "/launcher.py", "w").write("x")
    os.makedirs(os.path.dirname(su.default_db_path()), exist_ok=True)
    open(su.default_db_path(), "w").write("db")
    monkeypatch.setattr(su, "uninstall_daemon", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    su.cmd_uninstall(confirm=True)

    assert not os.path.exists(su.current_dir())
    assert not os.path.exists(su.shim_path())
    assert os.path.exists(su.default_db_path())  # kept
    assert "uninstalled" in capsys.readouterr().out.lower()


def test_running_from_checkout_detects_repo():
    checkout = su.running_from_checkout()
    assert checkout is not None
    assert checkout.endswith("workflow-automator")


def test_real_launcher_runs_from_any_cwd(tmp_path):
    launcher = str(os.path.join(os.path.dirname(os.path.dirname(__file__)), "launcher.py"))
    out = os.popen(f'cd "{tmp_path}" && {sys.executable} "{launcher}" version').read()
    assert "workflow-automator v" in out


# ---------------------------------------------------------------------------
# Executor cross-platform branches
# ---------------------------------------------------------------------------

def _media_action():
    return types.SimpleNamespace(type="media", command="spotify|Play", args=[], enabled=True)


def test_media_action_linux_only(monkeypatch):
    monkeypatch.setattr(exc_mod.sys, "platform", "darwin")
    result = exc_mod.ActionExecutor().execute(_media_action())
    assert result["success"] is False
    assert "Linux-only" in result["error"]


@pytest.mark.parametrize(
    "platform,expected_bin",
    [("linux", "notify-send"), ("darwin", "osascript"), ("win32", "powershell")],
)
def test_notify_uses_platform_backend(monkeypatch, platform, expected_bin):
    monkeypatch.setattr(exc_mod.sys, "platform", platform)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _FakeResult()

    monkeypatch.setattr(exc_mod.subprocess, "run", fake_run)
    action = types.SimpleNamespace(
        type="notify", command="Hello", args=["World"], enabled=True
    )
    result = exc_mod.ActionExecutor().execute(action)
    assert result["success"] is True
    assert seen["cmd"][0] == expected_bin