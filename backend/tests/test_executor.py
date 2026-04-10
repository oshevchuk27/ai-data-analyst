"""
tests/test_executor.py — Unit tests for the code execution sandbox.
These tests do NOT require an Anthropic API key.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from executor import execute, is_safe


# ── Safety checks ──────────────────────────────────────────────────────────

class TestIsSafe:
    def test_allows_clean_code(self):
        code = "import pandas as pd\nprint(pd.Series([1,2,3]).mean())"
        safe, reason = is_safe(code)
        assert safe

    def test_blocks_os_system(self):
        safe, _ = is_safe("os.system('rm -rf /')")
        assert not safe

    def test_blocks_subprocess(self):
        safe, _ = is_safe("import subprocess; subprocess.run(['ls'])")
        assert not safe

    def test_blocks_eval(self):
        safe, _ = is_safe("eval('__import__(\"os\").system(\"ls\")')")
        assert not safe

    def test_blocks_exec(self):
        safe, _ = is_safe("exec('import os')")
        assert not safe

    def test_blocks_socket(self):
        safe, _ = is_safe("import socket")
        assert not safe


# ── Execution ──────────────────────────────────────────────────────────────

class TestExecute:
    def test_basic_print(self):
        result = execute("print('hello ai data analyst')")
        assert result.success
        assert "hello ai data analyst" in result.stdout

    def test_pandas_stats(self):
        code = """
import pandas as pd
s = pd.Series([10, 20, 30, 40, 50])
print(f"mean={s.mean()}")
print(f"std={s.std():.2f}")
"""
        result = execute(code)
        assert result.success
        assert "mean=30.0" in result.stdout

    def test_numpy_computation(self):
        code = """
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
print(arr.sum())
"""
        result = execute(code)
        assert result.success
        assert "15" in result.stdout

    def test_matplotlib_plot_captured(self):
        code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [4, 5, 6])
plt.savefig("plot.png")
plt.close()
"""
        result = execute(code)
        assert result.success
        assert len(result.plots) == 1  # one PNG captured
        assert len(result.plots[0]) > 100  # non-empty base64

    def test_syntax_error_captured(self):
        result = execute("def broken(\n    pass")
        assert not result.success
        assert result.stderr  # stderr contains the SyntaxError

    def test_timeout_enforced(self):
        import os
        original = os.environ.get("EXECUTION_TIMEOUT_SECONDS")
        os.environ["EXECUTION_TIMEOUT_SECONDS"] = "2"

        # Re-import to pick up new env value
        import importlib, executor
        importlib.reload(executor)

        result = executor.execute("import time\ntime.sleep(30)")
        assert not result.success
        assert "Timeout" in result.stderr

        # Restore
        if original:
            os.environ["EXECUTION_TIMEOUT_SECONDS"] = original
        else:
            del os.environ["EXECUTION_TIMEOUT_SECONDS"]
        importlib.reload(executor)

    def test_blocked_code_rejected(self):
        result = execute("import os\nos.system('ls')")
        assert not result.success
        assert "Safety check failed" in result.stderr
