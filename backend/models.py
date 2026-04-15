from pydantic import BaseModel
from typing import Optional


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


class AnalyzeResponse(BaseModel):
    code: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    summary: str
    plots: list[str] = []  # base64 PNGs
    raw_llm_response: Optional[str] = None


class AgentAnalyzeRequest(BaseModel):
    prompt: str
    history: list[Message] = []


class AgentAnalyzeResponse(BaseModel):
    summary: str
    raw_llm_response: Optional[str] = None
    error: Optional[str] = None
