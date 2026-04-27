"""
agent_service.py — LlamaIndex ReActAgent implementation.

Captures structured Thought / Act events via stream_events() so the frontend
can render a clean step-by-step reasoning trace.
"""

import asyncio
import os
import re
import subprocess
import sys
import traceback

from dotenv import load_dotenv
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.anthropic import Anthropic
from models import (
    AgentAnalyzeResponse,
    AgentEvent,
    AnalyzeRequest,
    ToolInvocation,
)

load_dotenv()

_EXECUTION_TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "60"))

# Common data science packages pre-installed at startup so the LLM never needs
# # subprocess calls for them.
# _PREINSTALLED_PACKAGES = [
#     "pandas", "numpy", "matplotlib", "scipy", "scikit-learn",
#     "yfinance", "seaborn", "statsmodels", "plotly", "requests",
#     "openpyxl", "xlrd", "beautifulsoup4", "lxml", "pyarrow",
# ]

# def _ensure_packages() -> None:
#     """Install common packages once at startup (no-op if already present)."""
#     import subprocess, sys
#     subprocess.run(
#         [sys.executable, "-m", "pip", "install", "--quiet"] + _PREINSTALLED_PACKAGES,
#         capture_output=True,
#     )

# _ensure_packages()

# Injected at the top of every code execution so the LLM never needs to write it.
_CODE_PREAMBLE = """\
import uuid, os
os.makedirs('./static/charts', exist_ok=True)
"""


def _decode_escape_sequences(code: str) -> str:
    """Character-by-character expansion of backslash escape sequences.

    json.loads wrapping fails whenever code contains double-quoted strings
    (the outer wrapper produces malformed JSON). This scanner is immune to
    that because it never wraps the whole string — it just walks each char.
    """
    if "\\" not in code:
        return code
    _SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}
    out: list[str] = []
    i = 0
    while i < len(code):
        if code[i] == "\\" and i + 1 < len(code):
            nxt = code[i + 1]
            if nxt in _SIMPLE:
                out.append(_SIMPLE[nxt])
                i += 2
            else:
                out.append(code[i])
                i += 1
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


def _code_interpreter(code: str, **kwargs) -> str:
    """Execute Python code and return stdout/stderr."""
    # Patch before decoding so we match the literal \n escape, not a real newline.
    code = re.sub(r'(print\(f?)"\\n', r'\1"', code)
    code = re.sub(r"(print\(f?)'\\n", r"\1'", code)
    #code = _decode_escape_sequences(code)
    # Remove any surviving double-escaped backslash line-continuations.
    code = re.sub(r'\\\\\n\s*', ' ', code)
    full_code = _CODE_PREAMBLE + code
    try:
        result = subprocess.run(
            [sys.executable, "-c", full_code],
            capture_output=True,
            timeout=_EXECUTION_TIMEOUT,
        )
        return f"StdOut:\n{result.stdout.decode()}\nStdErr:\n{result.stderr.decode()}"
    except subprocess.TimeoutExpired:
        return f"StdErr:\n[Timeout] Execution exceeded {_EXECUTION_TIMEOUT}s limit."


_code_interpreter_tools = [
    FunctionTool.from_defaults(fn=_code_interpreter, name="code_interpreter")
]

def _build_user_msg(request: AnalyzeRequest) -> str:
    """Return the user message, prepending file context when a file is attached."""
    if not request.file_path:
        return request.prompt
    ext = (request.file_path or "").rsplit(".", 1)[-1].lower()
    loader = "pd.read_excel" if ext in ("xlsx", "xls") else "pd.read_csv"
    return (
        f'The user has uploaded a file named "{request.file_name}".\n'
        f'Load it with: df = {loader}(r"{request.file_path}")\n\n'
        f'{request.prompt}'
    )


class ReactDataAgent:
    """React Agent for data analysis using LlamaIndex."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.llm = Anthropic(
            api_key=api_key,
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=8192,
            temperature=0.1,
        )

        code_interpreter_tools = _code_interpreter_tools

        system_prompt = """<role>
You are a Senior Data Scientist with 10+ years of experience across finance, healthcare, and tech. Your superpower is turning raw, messy data into crystal-clear visual stories that drive decisions.

Your approach follows a disciplined three-phase method:
  1. EXPLORE — understand the data's shape, quality, and distributions before drawing conclusions
  2. ANALYZE — apply the right statistical or ML technique for the question at hand
  3. COMMUNICATE — always pair findings with a well-labeled chart; a number without context is noise

Visual storytelling principles you live by:
  - Choose chart types deliberately: time trends → line charts, comparisons → bar charts, distributions → histograms/box plots, correlations → scatter/heatmaps
  - Every chart must have a descriptive title, labeled axes with units, and a legend when needed
  - Use color purposefully — highlight the key insight, not just make things pretty
  - Add annotations (reference lines, shaded regions, callout text) to draw the viewer's eye to what matters

You NEVER guess at numbers — every statistic, percentage, or metric you mention in your final answer was computed by the code interpreter and observed in its output. Your ONLY way to compute, analyze, and visualize anything is via the `code_interpreter` tool.
</role>

<react_format>
You MUST follow the ReAct loop exactly. Each reasoning step must use this precise format:

Thought: <explain what you are about to do and why>
Action: code_interpreter
Action Input: {"code": "<complete python code>"}

RULES:
- Never skip Action Input.
- Action Input MUST be a valid JSON object with exactly one key: "code".
- The "code" value must be a properly formatted multi-line Python string with real newlines — do NOT encode newlines as \\n.
- Never write raw code or computed values outside of a tool call.
- Complete ALL tasks from the user's prompt inside ONE single code block — never split across multiple tool calls.
</react_format>

<environment>
The following packages are pre-installed. Import them directly — never pip-install them:
  pandas, numpy, matplotlib, scipy, scikit-learn, yfinance, seaborn, plotly, requests

To install an unlisted package use exactly this one-liner (no backslashes, no sys.executable):
  import subprocess; subprocess.run(["pip", "install", "<pkg>"], check=True, capture_output=True)

Compatible library versions (write code that targets these):
  pandas>=2.2  |  numpy>=2.1  |  matplotlib>=3.9  |  scipy>=1.14
  yfinance>=1.2  |  seaborn>=0.13  |  fastapi>=0.115  |  pydantic>=2.11

Each tool call runs in a fresh interpreter — include ALL imports and redefine ALL variables every time.
</environment>

<coding_rules>
RULE 1 — yfinance always returns a MultiIndex DataFrame. ALWAYS flatten to a 1-D Series immediately after download:
  df = yf.download("TICKER", start="YYYY-MM-DD", end="YYYY-MM-DD", auto_adjust=True)
  close = df['Close'].squeeze()   # squeeze() converts single-column DataFrame → Series
  # Now close.mean(), close.std(), close.pct_change() all return scalars or 1-D Series.
  # NEVER do df['Close'].mean() directly — it returns a Series, not a scalar.

RULE 2 — Scalar extraction before ANY f-string format spec or arithmetic:
  returns = close.pct_change().dropna()           # returns is a 1-D Series
  mean_val = float(returns.mean())                # extract scalar FIRST
  std_val  = float(returns.std())
  # NEVER: float(df['Close'].mean())  — df['Close'] is a DataFrame, mean() → Series → TypeError
  # NEVER: (series_a.mean() - series_b.mean()).item() — arithmetic on Series → ValueError
  # ALWAYS extract both scalars first: diff = float(a.mean()) - float(b.mean())

RULE 3 — scipy.stats results are named tuples with numpy scalar attributes, NOT plain scalars:
  result = stats.ttest_ind(a, b)
  t_stat = float(result.statistic)   # use .statistic attribute, then float()
  p_val  = float(result.pvalue)      # use .pvalue attribute, then float()
  # NEVER: float(t_statistic) where t_statistic came from unpacking — it may be a 0-d array
  # NEVER: f"{t_statistic:.4f}" without float() wrapping

RULE 4 — pandas resample aliases
  NEVER use 'M' (deprecated). Use: 'ME' (month-end), 'QE' (quarter-end), 'YE' (year-end).

RULE 5 — String quoting inside code blocks:
  ALWAYS use double-quoted strings: print(f"text {var}")
  NEVER use single-quoted strings that contain variables or span logical lines: print(f'text {var}')
  For multi-line string literals use triple double-quotes: \"""...\"""
  This prevents unterminated f-string / SyntaxError when the code is transmitted.

RULE 6 — Complete all code in one block, never truncate:
  Write the ENTIRE script in a single code block. Never end mid-expression.
  All parentheses, brackets, and string quotes must be closed before submitting.

RULE 7 — VERY IMPORTANT Examples of how NOT to write print syntax in code:
    print("\n Something...") # Avoid leading newlines in print statements — they can break JSON parsing
    print(f"\n Something...") # Avoid leading newlines in print statements — they can break JSON parsing
</coding_rules>

<chart_rules>
When producing any matplotlib plot:
1. DO NOT call uuid.uuid4() or os.makedirs — they are already set up in the environment.
2. Save and announce the chart with these exact three lines (no plt.show()):
     _chart_path = f'./static/charts/{uuid.uuid4().hex}.png'
     plt.savefig(_chart_path, dpi=150, bbox_inches='tight')
     plt.close()
     print(f'CHART_SAVED:{_chart_path}')
</chart_rules>

<final_answer>
After the last Observation, write a concise plain-English summary of findings.
Make sure you create an analysis using chart and tell the user it has been rendered below.
Do NOT repeat raw numbers already visible in the Observation.
</final_answer>"""

        self.agent = ReActAgent(
            name="Data Analysis Agent",
            description="An AI agent specialized in data analysis using React approach",
            system_prompt=system_prompt,
            tools=code_interpreter_tools,
            llm=self.llm,
            streaming=False,
            verbose=False,
        )

    async def analyze_stream(self, request: AnalyzeRequest):
        """Async generator yielding SSE-formatted strings as the agent reasons step-by-step."""
        import json
        from llama_index.core.base.llms.types import ChatMessage, MessageRole

        try:
            chat_history = []
            for msg in request.history:
                role = (
                    MessageRole.USER if msg.role.lower() == "user" else MessageRole.ASSISTANT
                )
                chat_history.append(ChatMessage(role=role, content=msg.content))

            user_msg = _build_user_msg(request)
            run_kwargs = {"user_msg": user_msg}
            if chat_history:
                run_kwargs["chat_history"] = chat_history

            handler = self.agent.run(**run_kwargs, max_iterations=9)
            chart_urls: list[str] = []

            async for event in handler.stream_events():
                event_type = type(event).__name__

                if event_type == "AgentOutput":
                    response = getattr(event, "response", None)
                    if not response:
                        continue
                    blocks = getattr(response, "blocks", [])
                    for block in blocks:
                        text = getattr(block, "text", "") or ""
                        if "Thought:" not in text:
                            continue
                        thought = text
                        if thought.startswith("Thought:"):
                            thought = thought[len("Thought:"):].strip()
                        for marker in ("\nAction:", "\nAnswer:"):
                            if marker in thought:
                                thought = thought[: thought.index(marker)].strip()
                        if thought:
                            agent_event = AgentEvent(current_label="Think", content=thought)
                            yield f"data: {json.dumps({'type': 'step', 'event': agent_event.model_dump()})}\n\n"
                        break

                elif event_type == "ToolCall":
                    tool_name = getattr(event, "tool_name", "unknown")
                    tool_kwargs = getattr(event, "tool_kwargs", {})
                    act_event = AgentEvent(
                        current_label="Act",
                        tools=[
                            ToolInvocation(toolname=tool_name, queryparams=tool_kwargs, output=None)
                        ],
                    )
                    yield f"data: {json.dumps({'type': 'step', 'event': act_event.model_dump()})}\n\n"

                elif event_type == "ToolCallResult":
                    tool_output = getattr(event, "tool_output", None)
                    if tool_output is not None:
                        content = getattr(tool_output, "content", tool_output)
                        if isinstance(content, str):
                            output_str = content
                        elif isinstance(content, list):
                            output_str = "\n".join(
                                getattr(block, "text", str(block)) for block in content
                            )
                        else:
                            output_str = str(content)
                    else:
                        output_str = ""

                    for match in re.finditer(
                        r"CHART_SAVED:\./static/charts/([0-9a-f]+\.png)", output_str
                    ):
                        filename = match.group(1)
                        url = f"/charts/{filename}"
                        if url not in chart_urls:
                            chart_urls.append(url)
                    output_str = re.sub(
                        r"CHART_SAVED:\./static/charts/[0-9a-f]+\.png", "", output_str
                    )

                    yield f"data: {json.dumps({'type': 'step_result', 'output': output_str})}\n\n"

            result = await handler
            summary = str(result)
            yield f"data: {json.dumps({'type': 'done', 'summary': summary, 'charts': chart_urls})}\n\n"

        except Exception as e:
            print(f"[agent_stream] error: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    def analyze(self, request: AnalyzeRequest) -> AgentAnalyzeResponse:
        """Run the agent and return a structured event trace."""
        try:
            from llama_index.core.base.llms.types import ChatMessage, MessageRole

            chat_history = []
            for msg in request.history:
                role = (
                    MessageRole.USER
                    if msg.role.lower() == "user"
                    else MessageRole.ASSISTANT
                )
                chat_history.append(ChatMessage(role=role, content=msg.content))

            async def run_agent():
                run_kwargs = {"user_msg": _build_user_msg(request)}
                if chat_history:
                    run_kwargs["chat_history"] = chat_history
                handler = self.agent.run(**run_kwargs, max_iterations=7)

                agent_events: list[AgentEvent] = []
                chart_urls: list[str] = []
                # Index of the most recent Act event waiting for its tool result
                pending_act_idx: int | None = None

                async for event in handler.stream_events():
                    event_type = type(event).__name__

                    if event_type == "AgentOutput":
                        response = getattr(event, "response", None)
                        if not response:
                            continue
                        blocks = getattr(response, "blocks", [])
                        for block in blocks:
                            text = getattr(block, "text", "") or ""
                            if "Thought:" not in text:
                                continue
                            # Isolate the thought text
                            thought = text
                            if thought.startswith("Thought:"):
                                thought = thought[len("Thought:"):].strip()
                            # Trim trailing Action / Answer sections
                            for marker in ("\nAction:", "\nAnswer:"):
                                if marker in thought:
                                    thought = thought[: thought.index(marker)].strip()
                            if thought:
                                agent_events.append(
                                    AgentEvent(
                                        current_label="Think",
                                        content=thought,
                                    )
                                )
                            break

                    elif event_type == "ToolCall":
                        tool_name = getattr(event, "tool_name", "unknown")
                        tool_kwargs = getattr(event, "tool_kwargs", {})
                        act = AgentEvent(
                            current_label="Act",
                            tools=[
                                ToolInvocation(
                                    toolname=tool_name,
                                    queryparams=tool_kwargs,
                                    output=None,
                                )
                            ],
                        )
                        agent_events.append(act)
                        pending_act_idx = len(agent_events) - 1

                    elif event_type == "ToolCallResult":
                        tool_output = getattr(event, "tool_output", None)
                        if tool_output is not None:
                            content = getattr(tool_output, "content", tool_output)
                            # content may be a plain string, a list of blocks,
                            # or the ToolOutput object itself
                            if isinstance(content, str):
                                output_str = content
                            elif isinstance(content, list):
                                # Each block may have a .text attribute
                                output_str = "\n".join(
                                    getattr(block, "text", str(block))
                                    for block in content
                                )
                            else:
                                # Last resort: stringify the whole object
                                output_str = str(content)
                        else:
                            output_str = ""

                        # Extract any chart paths the code printed.
                        # Match only the UUID hex filename to avoid over-capture
                        # when the output contains literal \n escape sequences.
                        for match in re.finditer(
                            r"CHART_SAVED:\./static/charts/([0-9a-f]+\.png)",
                            output_str,
                        ):
                            filename = match.group(1)
                            url = f"/charts/{filename}"
                            print(f"[agent] chart detected → {url}")
                            if url not in chart_urls:
                                chart_urls.append(url)
                        # Strip the CHART_SAVED markers from the displayed output
                        output_str = re.sub(
                            r"CHART_SAVED:\./static/charts/[0-9a-f]+\.png",
                            "",
                            output_str,
                        )
                        print(f"[agent] tool output (first 300 chars): {output_str[:300]!r}")

                        # Attach result to the matching Act event
                        if pending_act_idx is not None:
                            act = agent_events[pending_act_idx]
                            if act.tools:
                                act.tools[-1].output = output_str
                        pending_act_idx = None

                result = await handler
                return str(result), agent_events, chart_urls

            summary, agent_events, chart_urls = asyncio.run(run_agent())

            return AgentAnalyzeResponse(
                summary=summary,
                events=agent_events,
                charts=chart_urls,
            )

        except Exception as e:
            error_msg = f"React agent error: {str(e)}\n{traceback.format_exc()}"
            return AgentAnalyzeResponse(
                summary=f"I encountered an error while processing your request: {str(e)}",
                error=error_msg,
            )


# Global agent instance
_agent_instance: ReactDataAgent | None = None


def get_react_agent() -> ReactDataAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReactDataAgent()
    return _agent_instance


def run_react_agent(request: AnalyzeRequest) -> AgentAnalyzeResponse:
    return get_react_agent().analyze(request)
