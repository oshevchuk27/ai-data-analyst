"""
agent_service.py — LlamaIndex ReActAgent implementation.

Captures structured Thought / Act events via stream_events() so the frontend
can render a clean step-by-step reasoning trace.
"""

import asyncio
import os
import re
import traceback

from dotenv import load_dotenv

load_dotenv()

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.anthropic import Anthropic
from llama_index.tools.code_interpreter import CodeInterpreterToolSpec

_code_spec = CodeInterpreterToolSpec()

# Common data science packages pre-installed at startup so the LLM never needs
# subprocess calls for them.
_PREINSTALLED_PACKAGES = [
    "pandas", "numpy", "matplotlib", "scipy", "scikit-learn",
    "yfinance", "seaborn", "statsmodels", "plotly", "requests",
    "openpyxl", "xlrd", "beautifulsoup4", "lxml", "pyarrow",
]

def _ensure_packages() -> None:
    """Install common packages once at startup (no-op if already present)."""
    import subprocess, sys
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet"] + _PREINSTALLED_PACKAGES,
        capture_output=True,
    )

_ensure_packages()

# Injected at the top of every code execution so the LLM never needs to write it.
_CODE_PREAMBLE = """\
import uuid, os
os.makedirs('./static/charts', exist_ok=True)
"""


def _code_interpreter(code: str, **kwargs) -> str:
    """Execute Python code and return stdout/stderr."""
    # If the code arrived as a single flat line (no real newlines), the JSON
    # string was not decoded — escape sequences like \n, \", \\ are still raw.
    # Decode the whole thing as a JSON string to restore all of them at once.
    if "\n" not in code:
        import json
        try:
            code = json.loads(f'"{code}"')
        except json.JSONDecodeError:
            code = code.replace("\\n", "\n")
    # LLMs sometimes double-escape backslash line-continuations (\\\n → \\+newline).
    # A literal \\ at end of line is never valid Python here; convert to a space
    # so the expression stays on one logical line and avoids SyntaxError.
    code = re.sub(r'\\\\\n\s*', ' ', code)
    return _code_spec.code_interpreter(code=_CODE_PREAMBLE + code)


_code_interpreter_tools = [
    FunctionTool.from_defaults(fn=_code_interpreter, name="code_interpreter")
]

from models import (
    AgentAnalyzeResponse,
    AgentEvent,
    AnalyzeRequest,
    ToolInvocation,
)


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
            max_tokens=2048,
            temperature=0.1,
        )

        code_interpreter_tools = _code_interpreter_tools

        system_prompt = """You are an experienced Data Scientist. You MUST use the code_interpreter tool to run any computation — never write code or results directly in your Answer.

## Tool usage — MANDATORY format
Every time you need to run code you MUST emit exactly:

Thought: <what you plan to do>
Action: code_interpreter
Action Input: {"code": "<your python code with \\n for newlines>"}

Do NOT put code in the Answer. Do NOT skip Action Input. The Action Input value MUST be a valid JSON object with a "code" key.

## Coding rules
- Each execution starts with a fresh environment — include ALL imports and redefine ALL variables in every code block.
- The following packages are ALREADY INSTALLED — import them directly, never pip-install them:
  pandas, numpy, matplotlib, scipy, scikit-learn, yfinance, seaborn, statsmodels, plotly, requests, openpyxl, xlrd, beautifulsoup4, lxml, pyarrow
- If you need a package NOT in the list above, install it with EXACTLY this one-liner (single line, no backslashes, no sys.executable): `import subprocess; subprocess.run(["pip", "install", "<package>"], check=True, capture_output=True)` then import it below.
- Every task mentioned in the user's prompt MUST be completed in a single code block. Never split the work across multiple tool calls — if the user asks for data fetching, analysis, and plotting, all of it goes in one code block.
- When using f-string format specifiers (e.g. `:.2f`, `:.4%`), the value MUST be a Python scalar. Always use `.iloc[0]` or `.item()` to extract a scalar from a Series or array before formatting — never wrap a Series in `float()`.

## Chart rules — follow exactly when producing any plot
- DO NOT import uuid or call os.makedirs — they are already set up for you.
- Save the chart and print the marker with these exact lines (NO plt.show()):
    _chart_path = f'./static/charts/{uuid.uuid4().hex}.png'
    plt.savefig(_chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'CHART_SAVED:{_chart_path}')

## Final answer
After observing the tool output, write a clear summary for the user. Tell the user the chart has been rendered below if one was produced.
"""

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
        finally:
            if request.file_path and os.path.exists(request.file_path):
                os.remove(request.file_path)

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
