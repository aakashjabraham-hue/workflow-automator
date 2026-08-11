"""Tests for the CLI command surface (subcommands, version helpers)."""

import pytest

from src.main import build_parser
from src.self_update import is_newer, read_version, version_key


def test_parser_accepts_all_subcommands():
    parser = build_parser()
    for cmd in ["dashboard", "daemon", "install", "update", "uninstall", "version"]:
        args = parser.parse_args([cmd])
        assert args.command == cmd


def test_parser_preserves_backward_compat_flags():
    args = build_parser().parse_args(["--daemon", "--foreground", "--verbose"])
    assert args.daemon is True
    assert args.foreground is True
    assert args.verbose is True


def test_parser_db_and_skip_download():
    args = build_parser().parse_args(
        ["install", "--skip-download", "--db", "/tmp/x.db"]
    )
    assert args.command == "install"
    assert args.skip_download is True
    assert args.db == "/tmp/x.db"


def test_parser_version_flag_exits():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0


def test_version_key_ordering():
    assert version_key("0.1.0") < version_key("0.2.0")
    assert version_key("0.2.0") == version_key("0.2.0")
    assert version_key("1.0.0") > version_key("0.9.9")
    # Non-numeric segments must not crash
    assert version_key("dev") == (0,)
    assert version_key("") == (0,)


def test_is_newer():
    assert is_newer("0.2.0", "0.1.0") is True
    assert is_newer("0.1.0", "0.2.0") is False
    assert is_newer("0.2.0", "0.2.0") is False


def test_read_version_from_init(tmp_path):
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "__init__.py").write_text('__version__ = "1.2.3"\n')
    assert read_version(str(tree)) == "1.2.3"


def test_read_version_falls_back_to_pyproject(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "pyproject.toml").write_text(
        '[project]\nname = "workflow-automator"\nversion = "0.4.2"\n'
    )
    assert read_version(str(tree)) == "0.4.2"


def test_read_version_unknown(tmp_path):
    assert read_version(str(tmp_path / "missing")) == "0.0.0"


def test_main_version_command_prints(capsys):
    from src.main import main

    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "workflow-automator v" in out