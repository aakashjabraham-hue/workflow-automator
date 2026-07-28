import subprocess
from typing import Any


class ActionExecutor:
    """Executes workflow actions of various types."""

    TIMEOUT = 30

    def execute(self, action: Any) -> dict:
        """Execute an action and return a result dict.

        Args:
            action: An object with attributes type, command, args, enabled.

        Returns:
            dict with keys: success (bool), output (str), error (str)
        """
        if not getattr(action, "enabled", True):
            return {"success": False, "output": "", "error": "Action is disabled"}

        action_type = getattr(action, "type", "")
        command = getattr(action, "command", "")
        args = getattr(action, "args", [])

        if action_type == "shell":
            return self._execute_shell(command, args)
        elif action_type == "launch":
            return self._execute_launch(command, args)
        elif action_type == "notify":
            return self._execute_notify(command, args)
        elif action_type == "dbus":
            return self._execute_dbus(command, args)
        else:
            return {
                "success": False,
                "output": "",
                "error": f"Unknown action type: {action_type}",
            }

    def _execute_shell(self, command: str, args: list) -> dict:
        """Run a shell command via subprocess.run with a timeout."""
        try:
            cmd = [command] + list(args)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return {"success": True, "output": output, "error": ""}
            return {
                "success": False,
                "output": output,
                "error": f"Command exited with code {result.returncode}",
            }
        except subprocess.TimeoutExpired as e:
            return {
                "success": False,
                "output": e.stdout or "" if isinstance(e.stdout, str) else "",
                "error": f"Command timed out after {self.TIMEOUT}s",
            }
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "output": e.stdout or "" if isinstance(e.stdout, str) else "",
                "error": f"Command failed with code {e.returncode}: {e.stderr or ''}",
            }
        except OSError as e:
            return {"success": False, "output": "", "error": str(e)}

    def _execute_launch(self, command: str, args: list) -> dict:
        """Launch a desktop app via subprocess.Popen (non-blocking)."""
        try:
            cmd = [command] + list(args)
            proc = subprocess.Popen(cmd)
            return {
                "success": True,
                "output": f"Launched {command} with PID {proc.pid}",
                "error": "",
            }
        except OSError as e:
            return {"success": False, "output": "", "error": str(e)}

    def _execute_notify(self, command: str, args: list) -> dict:
        """Send a desktop notification via notify-send."""
        try:
            cmd = ["notify-send", command] + list(args)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return {"success": True, "output": output, "error": ""}
            return {
                "success": False,
                "output": output,
                "error": f"notify-send exited with code {result.returncode}",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"notify-send timed out after {self.TIMEOUT}s",
            }
        except OSError as e:
            return {"success": False, "output": "", "error": str(e)}

    def _execute_dbus(self, command: str, args: list) -> dict:
        """Stub for D-Bus method calls."""
        return {
            "success": True,
            "output": f"dbus action not yet implemented for command={command}, args={args}",
            "error": "",
        }