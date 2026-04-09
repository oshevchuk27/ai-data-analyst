"""
main.py — FastAPI application entry point.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

import agent
from models import AnalyzeRequest, AnalyzeResponse

app = FastAPI(
    title="DataAgent API",
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
        raise HTTPException(status_code=500, detail=str(exc))

    return result
