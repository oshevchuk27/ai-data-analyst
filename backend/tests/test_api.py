"""
tests/test_api.py — Integration tests for FastAPI routes.
Mocks the agent to avoid real LLM calls.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")

from main import app
from models import AnalyzeResponse

client = TestClient(app)

MOCK_RESPONSE = AnalyzeResponse(
    code="print('hello')",
    output="hello\n",
    summary="The code printed 'hello' successfully.",
    plots=[],
)


class TestHealth:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAnalyze:
    @patch("main.agent.run", return_value=MOCK_RESPONSE)
    def test_basic_request(self, mock_run):
        r = client.post("/api/analyze", json={"prompt": "print hello world"})
        assert r.status_code == 200
        body = r.json()
        assert body["summary"] == "The code printed 'hello' successfully."
        assert body["code"] == "print('hello')"

    def test_empty_prompt_rejected(self):
        r = client.post("/api/analyze", json={"prompt": "   "})
        assert r.status_code == 400

    def test_blocked_prompt_rejected(self):
        r = client.post("/api/analyze", json={"prompt": "rm -rf everything"})
        assert r.status_code == 400

    @patch("main.agent.run", return_value=MOCK_RESPONSE)
    def test_history_passed_through(self, mock_run):
        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]
        r = client.post("/api/analyze", json={
            "prompt": "follow up question",
            "history": history,
        })
        assert r.status_code == 200
        call_args = mock_run.call_args[0][0]
        assert len(call_args.history) == 2

    @patch("main.agent.run", side_effect=Exception("LLM timeout"))
    def test_agent_error_returns_500(self, mock_run):
        r = client.post("/api/analyze", json={"prompt": "do something"})
        assert r.status_code == 500
        assert "LLM timeout" in r.json()["detail"]
