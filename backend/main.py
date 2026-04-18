"""
main.py — FastAPI application entry point.
"""

import os
import uuid

import agent
import agent_service
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from models import AnalyzeRequest, AnalyzeResponse, AgentAnalyzeRequest, AgentAnalyzeResponse

load_dotenv()

# Ensure required directories exist before mounting
os.makedirs("static/charts", exist_ok=True)
UPLOADS_DIR = os.path.abspath("uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(
    title="AI Data Analyst API",
    description="AI-powered data analysis backend (CISC 520 Final Project)",
    version="0.1.0",
)

# Serve saved chart images at /charts/<filename>
app.mount("/charts", StaticFiles(directory="static/charts"), name="charts")

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

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept a CSV/Excel file, persist it, and return its server-side path."""
    allowed = {".csv", ".xlsx", ".xls"}
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in allowed:
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported.")

    safe_name = f"{uuid.uuid4().hex}{ext.lower()}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    return {"file_path": file_path, "file_name": file.filename}


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
        return agent_service.run_react_agent(analyze_request)
    except Exception as exc:
        # Log the full error for debugging
        import traceback
        print(f"Error in /api/agent_analyse: {exc}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/agent_analyse/stream")
async def agent_analyse_stream(request: AgentAnalyzeRequest):
    """
    Streaming SSE endpoint. Emits each Think/Act step as it happens so the
    frontend can render the reasoning trace in real-time.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    blocked_keywords = ["rm -rf", "drop table", "delete from", "format c:"]
    if any(kw in request.prompt.lower() for kw in blocked_keywords):
        raise HTTPException(status_code=400, detail="Prompt contains disallowed content.")

    analyze_request = AnalyzeRequest(
        prompt=request.prompt,
        history=request.history,
        file_path=request.file_path,
        file_name=request.file_name,
    )

    async def generate():
        async for chunk in agent_service.get_react_agent().analyze_stream(analyze_request):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
