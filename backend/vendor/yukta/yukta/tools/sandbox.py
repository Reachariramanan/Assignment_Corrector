"""
sandbox.py — Subprocess-based isolation for untrusted tool functions.

Tools marked with trust_level="sandbox" are executed in a child process so that
they cannot access or mutate the parent process's environment, memory, or globals.
"""

import json
import subprocess
import sys
import textwrap
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_RUNNER_SCRIPT = textwrap.dedent("""\
    import sys, json, importlib, importlib.util, os

    payload = json.loads(sys.argv[1])
    module_path = payload["module_path"]
    function_name = payload["function_name"]
    args = payload["args"]

    spec = importlib.util.spec_from_file_location("_sandbox_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, function_name)
    result = fn(**args)
    print(json.dumps(result if isinstance(result, dict) else {"result": result}))
""")


class ToolSandbox:
    """
    Executes a tool function inside a subprocess for isolation.

    The child process:
    - Has no access to parent in-memory state
    - Is killed on timeout
    - Cannot affect parent environment variables or globals

    Usage::

        sandbox = ToolSandbox()
        result = sandbox.execute_callable(fn, args, timeout=10.0)
        # or by module path:
        result = sandbox.execute(module_path="/path/to/module.py",
                                  function_name="my_tool", args={...})
    """

    def execute(
        self,
        module_path: str,
        function_name: str,
        args: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Load *module_path* in a subprocess, call *function_name*(**args), return result.

        Args:
            module_path: Absolute path to the Python module file.
            function_name: Name of the function to call inside that module.
            args: Keyword arguments to pass to the function.
            timeout: Maximum seconds before the subprocess is killed.

        Returns:
            Dict with tool result, or an error dict on failure/timeout.
        """
        payload = json.dumps({
            "module_path": module_path,
            "function_name": function_name,
            "args": args,
        })
        try:
            proc = subprocess.run(
                [sys.executable, "-c", _RUNNER_SCRIPT, payload],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or f"exit code {proc.returncode}"
                logger.warning("Sandbox subprocess error for %s.%s: %s", module_path, function_name, err)
                return {"error": f"Sandbox execution failed: {err}"}
            return json.loads(proc.stdout.strip())
        except subprocess.TimeoutExpired:
            logger.warning("Sandbox timeout (%ss) for %s.%s", timeout, module_path, function_name)
            return {"error": f"Sandbox execution timed out after {timeout}s"}
        except json.JSONDecodeError as exc:
            return {"error": f"Sandbox returned non-JSON output: {exc}"}
        except Exception as exc:
            return {"error": f"Sandbox launch failed: {type(exc).__name__}: {exc}"}

    def execute_callable(
        self,
        fn: Callable,
        args: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Execute a plain Python callable inside a subprocess by serialising it via cloudpickle.

        Falls back to direct execution if cloudpickle is unavailable (with a warning).

        Args:
            fn: The callable to execute.
            args: Keyword arguments to pass.
            timeout: Timeout in seconds.

        Returns:
            Dict with tool result, or an error dict on failure/timeout.
        """
        try:
            import cloudpickle
        except ImportError:
            logger.warning(
                "cloudpickle not installed; sandbox cannot isolate in-memory callables. "
                "Falling back to direct execution. Install cloudpickle for full isolation."
            )
            try:
                result = fn(**args)
                return result if isinstance(result, dict) else {"result": result}
            except Exception as exc:
                return {"error": f"Direct execution failed: {type(exc).__name__}: {exc}"}

        _PICKLE_RUNNER = textwrap.dedent("""\
            import sys, json, pickle, base64
            fn_bytes = base64.b64decode(sys.argv[1])
            args = json.loads(sys.argv[2])
            import cloudpickle
            fn = cloudpickle.loads(fn_bytes)
            result = fn(**args)
            print(json.dumps(result if isinstance(result, dict) else {"result": result}))
        """)

        import base64
        fn_b64 = base64.b64encode(cloudpickle.dumps(fn)).decode()
        args_json = json.dumps(args)

        try:
            proc = subprocess.run(
                [sys.executable, "-c", _PICKLE_RUNNER, fn_b64, args_json],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or f"exit code {proc.returncode}"
                return {"error": f"Sandbox execution failed: {err}"}
            return json.loads(proc.stdout.strip())
        except subprocess.TimeoutExpired:
            return {"error": f"Sandbox execution timed out after {timeout}s"}
        except json.JSONDecodeError as exc:
            return {"error": f"Sandbox returned non-JSON output: {exc}"}
        except Exception as exc:
            return {"error": f"Sandbox launch failed: {type(exc).__name__}: {exc}"}
