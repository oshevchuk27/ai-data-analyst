"""
main.py — FastAPI application entry point.
"""

import os

import agent
import agent_service
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import AnalyzeRequest, AnalyzeResponse, AgentAnalyzeRequest, AgentAnalyzeResponse

load_dotenv()

app = FastAPI(
    title="AI Data Analyst API",
    description="AI-powered data analysis backend (CISC 520 Final Project)",
    version="0.1.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    """
    Main endpoint.  Accepts a user prompt + conversation history,
    runs the full agentic pipeline, and returns structured results.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    # Basic input validation — reject obviously harmful requests
    blocked_keywords = ["rm -rf", "drop table", "delete from", "format c:"]
    lower = request.prompt.lower()
    if any(kw in lower for kw in blocked_keywords):
        raise HTTPException(
            status_code=400,
            detail="Prompt contains disallowed content.",
        )

    try:
        result = agent.run(request)
    except Exception as exc:
        # Log the full error for debugging
        import traceback
        print(f"Error in /api/analyze: {exc}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))

    return result


@app.post("/api/agent_analyse", response_model=AgentAnalyzeResponse)
def agent_analyse(request: AgentAnalyzeRequest):
    """
    React Agent endpoint. Accepts a user prompt + conversation history,
    runs the React agent pipeline using LlamaIndex, and returns structured results.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    # Basic input validation — reject obviously harmful requests
    blocked_keywords = ["rm -rf", "drop table", "delete from", "format c:"]
    lower = request.prompt.lower()
    if any(kw in lower for kw in blocked_keywords):
        raise HTTPException(
            status_code=400,
            detail="Prompt contains disallowed content.",
        )

    try:
        # Convert AgentAnalyzeRequest to AnalyzeRequest for compatibility
        analyze_request = AnalyzeRequest(
            prompt=request.prompt,
            history=request.history
        )
        result = agent_service.run_react_agent(analyze_request)
        
        # Convert AnalyzeResponse to AgentAnalyzeResponse
        return AgentAnalyzeResponse(
            summary=result.summary,
            raw_llm_response=result.raw_llm_response,
            error=result.error
        )
    except Exception as exc:
        # Log the full error for debugging
        import traceback
        print(f"Error in /api/agent_analyse: {exc}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))
