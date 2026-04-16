from pydantic import BaseModel
from typing import Any, Optional


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AnalyzeRequest(BaseModel):
    prompt: str
    history: list[Message] = []


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    success: bool
    plots: list[str] = []  # base64-encoded PNG images


class ThinkingStep(BaseModel):
    type: str           # "thought" | "action" | "observation" | "response"
    content: str        # main text content
    tool_name: Optional[str] = None   # set when type == "action"
    tool_input: Optional[str] = None  # raw input string (may be code or JSON)
    is_code: bool = False             # True when tool_input contains Python code


class AnalyzeResponse(BaseModel):
    code: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    summary: str
    plots: list[str] = []  # base64 PNGs
    raw_llm_response: Optional[str] = None
    thinking: list[ThinkingStep] = []  # structured reasoning trace


class ToolInvocation(BaseModel):
    toolname: str
    queryparams: Optional[Any] = None  # dict of kwargs passed to the tool
    output: Optional[str] = None       # tool execution result


class AgentEvent(BaseModel):
    current_label: str                          # "Think" | "Act"
    content: Optional[str] = None              # reasoning text (Think)
    tools: Optional[list[ToolInvocation]] = None  # tool calls (Act)


class AgentAnalyzeRequest(BaseModel):
    prompt: str
    history: list[Message] = []


class AgentAnalyzeResponse(BaseModel):
    summary: str
    error: Optional[str] = None
    events: list[AgentEvent] = []  # structured ReAct reasoning trace
    charts: list[str] = []  # relative URLs to saved chart images, e.g. ["/charts/abc.png"]
