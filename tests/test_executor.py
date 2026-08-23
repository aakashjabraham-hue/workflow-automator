import subprocess
from unittest.mock import patch, MagicMock

import pytest

from src.engine.executor import ActionExecutor


def _make_action(action_type, command="", args=None, enabled=True):
    """Create a simple mock action object."""
    action = MagicMock()
    action.type = action_type
    action.command = command
    action.args = args or []
    action.enabled = enabled
    return action


class TestActionExecutor:
    def setup_method(self):
        self.executor = ActionExecutor()

    def test_shell_action_runs_command(self):
        """Execute a shell action that runs `echo hello` → success=True, output contains 'hello'."""
        with patch("src.engine.executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hello\n", stderr="")
            action = _make_action("shell", command="echo", args=["hello"])
            result = self.executor.execute(action)

        assert result["success"] is True
        assert "hello" in result["output"]
        assert result["error"] == ""

    def test_shell_action_timeout(self):
        """Command that sleeps longer than timeout → success=False."""
        with patch("src.engine.executor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["sleep", "60"], timeout=30
            )
            action = _make_action("shell", command="sleep", args=["60"])
            result = self.executor.execute(action)

        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_launch_action(self):
        """Verify Popen is called with correct command."""
        with patch("src.engine.executor.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc
            action = _make_action("launch", command="spotify", args=[])
            result = self.executor.execute(action)

        assert result["success"] is True
        # Popen now receives env (session vars for GUI apps); check the command.
        mock_popen.assert_called_once()
        assert mock_popen.call_args[0][0] == ["spotify"]

    def test_notify_action(self):
        """Verify notify-send is called with correct args."""
        with patch("src.engine.executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            action = _make_action("notify", command="Hello Title", args=["Body text"])
            result = self.executor.execute(action)

        assert result["success"] is True
        mock_run.assert_called_once_with(
            ["notify-send", "Hello Title", "Body text"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_dbus_action_returns_stub(self):
        """Returns success=True with 'not yet implemented' message."""
        action = _make_action("dbus", command="org.freedesktop.DBus.CallMethod", args=[])
        result = self.executor.execute(action)

        assert result["success"] is True
        assert "not yet implemented" in result["output"].lower()

    def test_disabled_action_returns_failure(self):
        """Disabled actions return success=False."""
        action = _make_action("shell", command="echo", args=["hi"], enabled=False)
        result = self.executor.execute(action)

        assert result["success"] is False
        assert result["error"] == "Action is disabled"

    def test_unknown_action_type(self):
        """Unknown action type returns failure."""
        action = _make_action("unknown", command="test")
        result = self.executor.execute(action)

        assert result["success"] is False
        assert "Unknown action type" in result["error"]