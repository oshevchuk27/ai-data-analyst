"""
executor.py — Sandboxed Python code execution.

Runs LLM-generated code in a subprocess with:
  - Configurable timeout (default 15s)
  - Captured stdout/stderr
  - Base64-encoded PNG capture for matplotlib figures
  - Basic input validation to block dangerous operations
"""

import base64
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from models import ExecutionResult

TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "15"))
MAX_OUTPUT = int(os.getenv("MAX_OUTPUT_CHARS", "8000"))

# Patterns that are never allowed in generated code
BLOCKED_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bshutil\.rmtree\b",
    r"\bopen\s*\([^)]*['\"]w['\"]",   # open(..., "w") file writes outside plots
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"import\s+socket",
    r"import\s+requests",              # network calls from generated code
]


def is_safe(code: str) -> tuple[bool, str]:
    """Return (safe, reason). Reject code that matches blocked patterns."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, f"Blocked pattern detected: {pattern}"
    return True, ""


def execute(code: str) -> ExecutionResult:
    """
    Execute code in a subprocess.  Returns stdout, stderr, success flag,
    and any matplotlib plots as base64-encoded PNG strings.
    """
    safe, reason = is_safe(code)
    if not safe:
        return ExecutionResult(
            stdout="",
            stderr=f"[Safety check failed] {reason}",
            success=False,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        plot_dir = Path(tmpdir) / "plots"
        plot_dir.mkdir()

        # Inject preamble: redirect plot saves into tmpdir and set non-GUI backend
        preamble = textwrap.dedent(f"""
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import os, pathlib

            _PLOT_DIR = pathlib.Path(r"{plot_dir}")
            _plot_counter = [0]

            _orig_savefig = plt.savefig
            def _patched_savefig(fname, *args, **kwargs):
                _plot_counter[0] += 1
                dest = _PLOT_DIR / f"plot_{{_plot_counter[0]}}.png"
                _orig_savefig(dest, *args, **kwargs)
            plt.savefig = _patched_savefig
        """)

        script = preamble + "\n" + code

        script_path = Path(tmpdir) / "script.py"
        script_path.write_text(script, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                cwd=tmpdir,
            )
            stdout = result.stdout[:MAX_OUTPUT]
            stderr = result.stderr[:MAX_OUTPUT]
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout="",
                stderr=f"[Timeout] Execution exceeded {TIMEOUT}s limit.",
                success=False,
            )
        except Exception as exc:
            return ExecutionResult(
                stdout="",
                stderr=f"[Executor error] {exc}",
                success=False,
            )

        # Collect plots
        plots: list[str] = []
        for png in sorted(plot_dir.glob("*.png")):
            plots.append(base64.b64encode(png.read_bytes()).decode())

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            success=success,
            plots=plots,
        )
