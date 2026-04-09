# System Architecture

## Overview

AI Data Analyst is a full-stack agentic AI application. Users submit natural language data analysis requests; the system autonomously generates Python code, executes it, self-corrects on errors, and returns results with charts and a plain-English summary.

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser                               │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  ChatWindow  │   │  CodeBlock   │   │   ChartOutput    │  │
│  │  (history)   │   │ (highlight)  │   │  (base64 PNG)    │  │
│  └──────┬───────┘   └──────────────┘   └──────────────────┘  │
│         │ POST /api/analyze                                   │
└─────────┼────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────┐
│                    FastAPI Backend                            │
│                                                              │
│  main.py          agent.py              executor.py          │
│  ┌──────────┐    ┌─────────────────┐   ┌──────────────────┐  │
│  │  /api/   │───▶│ 1. Build msgs   │   │ subprocess run   │  │
│  │ analyze  │    │ 2. Call LLM     │──▶│ + timeout 15s    │  │
│  │          │    │ 3. Parse code   │   │ + stdout capture │  │
│  │ /health  │    │ 4. Execute      │◀──│ + PNG base64     │  │
│  └──────────┘    │ 5. Self-correct │   └──────────────────┘  │
│                  │ 6. Interpret    │                          │
│                  └────────┬────────┘                          │
└───────────────────────────┼──────────────────────────────────┘
                            │ HTTPS
                 ┌──────────▼──────────┐
                 │   Anthropic API     │
                 │  claude-sonnet-4    │
                 │  (2 calls/request)  │
                 └─────────────────────┘
```

---

## Request Lifecycle

### Single analysis request (happy path)

```
User types prompt
      │
      ▼
Frontend: POST /api/analyze
  { prompt, history[] }
      │
      ▼
Backend — agent.py::run()
  │
  ├─ Step 1: Build message list (system prompt + history + new prompt)
  │
  ├─ Step 2: Call Anthropic API → get response with <code> and <summary>
  │
  ├─ Step 3: Parse code block from response
  │
  ├─ Step 4: executor.py::execute(code)
  │     ├─ Safety check (blocked patterns)
  │     ├─ Inject matplotlib preamble (Agg backend, patched savefig)
  │     ├─ Write script to tempfile
  │     ├─ subprocess.run(..., timeout=15)
  │     └─ Collect stdout, stderr, PNG files → base64
  │
  ├─ Step 5: If execution failed → self-correction
  │     ├─ Build correction prompt with error message
  │     ├─ Call Anthropic API again → corrected code
  │     └─ Re-execute corrected code
  │
  ├─ Step 6: Interpret results
  │     ├─ Build interpretation prompt with stdout/stderr
  │     └─ Call Anthropic API → final <summary>
  │
  └─ Return AnalyzeResponse
        { code, output, error, summary, plots[] }
      │
      ▼
Frontend renders:
  ├─ CodeBlock (syntax highlighted Python)
  ├─ stdout box (monospace green text)
  ├─ Error box if self-correction triggered (shown for transparency)
  ├─ ChartOutput (base64 PNG images)
  └─ Summary bubble (natural language interpretation)
```

### Self-correction path

```
Execute(code) → stderr non-empty, returncode != 0
      │
      ▼
Build correction_prompt:
  "The code produced an error: {stderr}
   Please fix the code and try again."
      │
      ▼
LLM call → corrected <code> block
      │
      ▼
Execute(corrected_code) → success (or surface final error)
      │
      ▼
Proceed to interpretation step
```

---

## LLM Call Strategy

| Call | Purpose | Input | Output |
|------|---------|-------|--------|
| 1 | Code generation | System prompt + conversation history + user prompt | `<code>` + initial `<summary>` |
| 2 (conditional) | Self-correction | + error message | Corrected `<code>` |
| 2 or 3 | Result interpretation | + stdout/stderr from execution | Final `<summary>` |

---

## System Prompt Design Rationale

The system prompt enforces four properties:

1. **Structured output** — `<code>` and `<summary>` XML tags allow reliable regex parsing without brittle markdown fences
2. **Executable code** — explicit library allowlist prevents imports that aren't available in the sandbox
3. **Capturable output** — `plt.savefig()` requirement and `print()` mandate ensure all results flow through stdout/files
4. **Non-technical summaries** — the interpretation step produces audience-appropriate explanations separate from raw output

---

## Security Model

| Threat | Mitigation |
|--------|-----------|
| Dangerous shell commands | Regex blocklist (`os.system`, `subprocess`, etc.) checked before execution |
| Infinite loops | 15-second subprocess timeout |
| Filesystem writes | Code runs in `tempfile.TemporaryDirectory()`, deleted after execution |
| API key exposure | Stored in `.env`, never returned to frontend, not logged |
| Prompt injection | Input validation rejects prompts with known destructive keywords |

**Note:** This prototype uses subprocess sandboxing. For production, replace with Docker or E2B for full isolation.

---

## Data Flow for Plots

```
LLM generates:  plt.savefig("plot.png")
                        │
Executor injects preamble that patches plt.savefig
→ redirects all saves to tempdir/plots/plot_N.png
                        │
After subprocess exits, read all *.png files
→ base64-encode each
→ return in AnalyzeResponse.plots[]
                        │
Frontend renders: <img src="data:image/png;base64,{b64}" />
```
