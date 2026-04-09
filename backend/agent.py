"""
agent.py — LLM orchestration layer.

Responsibilities:
  1. Build the system prompt (data analysis agent persona + output format)
  2. Call Anthropic API with conversation history
  3. Parse the structured response (code block + summary)
  4. Execute the code via executor.py
  5. Self-correct on execution errors (retry once with error context)
  6. Call the LLM a second time to interpret execution results
  7. Return a structured AnalyzeResponse
"""

import os
import re
from typing import Optional

import anthropic

from executor import execute
from models import AnalyzeRequest, AnalyzeResponse, ExecutionResult, Message

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

SYSTEM_PROMPT = """You are DataAgent, an expert data analysis assistant. Your job is to help users explore and analyze data through natural language.

## How you work

When the user asks for data analysis, you ALWAYS:
1. Generate clean, executable Python code in a <code> block
2. After the user shows you execution results, interpret them in a <summary>

## Code requirements

- Use ONLY these libraries: pandas, numpy, matplotlib, scipy, yfinance, math, random, statistics
- Save ALL plots with plt.savefig("plot.png") — never use plt.show()
- Print ALL numerical results explicitly so they appear in stdout
- Always add plt.close() after saving each figure
- Keep code concise (under 40 lines when possible)
- Add brief inline comments explaining each major step

## Output format

Your response must follow this exact structure:

<code>
# your Python code here
</code>

<summary>
Your interpretation here (written for a non-technical audience).
Include: what was computed, what the key findings are, and any notable patterns.
</summary>

## Self-correction

If you are shown an error message from code execution, analyze the error, fix the code, and respond with a corrected <code> block and a <summary> explaining what went wrong and how you fixed it.

## Style

- Be concise and precise
- Highlight surprising or important findings
- Use plain language in summaries — avoid jargon
- If the user asks a follow-up question, maintain context from the conversation
"""


client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _parse_code(text: str) -> Optional[str]:
    m = re.search(r"<code>([\s\S]*?)</code>", text)
    return m.group(1).strip() if m else None


def _parse_summary(text: str) -> str:
    m = re.search(r"<summary>([\s\S]*?)</summary>", text)
    return m.group(1).strip() if m else text.strip()


def _call_llm(messages: list[dict]) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def _build_messages(request: AnalyzeRequest) -> list[dict]:
    msgs = [{"role": m.role, "content": m.content} for m in request.history]
    msgs.append({"role": "user", "content": request.prompt})
    return msgs


def _interpret_results(
    msgs: list[dict],
    llm_response: str,
    exec_result: ExecutionResult,
) -> str:
    """Ask the LLM to interpret execution output and return the final summary."""
    stdout_section = exec_result.stdout or "(no stdout)"
    stderr_section = exec_result.stderr or "(none)"
    status = "SUCCESS" if exec_result.success else "ERROR"

    interpretation_prompt = (
        f"Execution status: {status}\n\n"
        f"stdout:\n{stdout_section}\n\n"
        f"stderr:\n{stderr_section}\n\n"
        "Please provide a <summary> interpreting these results for the user."
    )

    followup_msgs = msgs + [
        {"role": "assistant", "content": llm_response},
        {"role": "user", "content": interpretation_prompt},
    ]
    interpretation = _call_llm(followup_msgs)
    return _parse_summary(interpretation)


def run(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Full agentic pipeline:
      user prompt → LLM → code → execute → (retry on error) → interpret → response
    """
    msgs = _build_messages(request)

    # ── Step 1: Generate code ──────────────────────────────────────────────
    llm_response = _call_llm(msgs)
    code = _parse_code(llm_response)

    if not code:
        # No code block — LLM gave a plain text answer
        return AnalyzeResponse(
            summary=_parse_summary(llm_response),
            raw_llm_response=llm_response,
        )

    # ── Step 2: Execute ────────────────────────────────────────────────────
    exec_result = execute(code)

    # ── Step 3: Self-correction (one retry on failure) ─────────────────────
    if not exec_result.success:
        correction_prompt = (
            f"The code produced an error:\n\n{exec_result.stderr}\n\n"
            "Please fix the code and try again. Respond with a corrected <code> block."
        )
        correction_msgs = msgs + [
            {"role": "assistant", "content": llm_response},
            {"role": "user", "content": correction_prompt},
        ]
        llm_response = _call_llm(correction_msgs)
        corrected_code = _parse_code(llm_response)

        if corrected_code:
            code = corrected_code
            exec_result = execute(code)

    # ── Step 4: Interpret results ──────────────────────────────────────────
    summary = _interpret_results(msgs, llm_response, exec_result)

    return AnalyzeResponse(
        code=code,
        output=exec_result.stdout or None,
        error=exec_result.stderr if not exec_result.success else None,
        summary=summary,
        plots=exec_result.plots,
        raw_llm_response=llm_response,
    )
