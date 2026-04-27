# How We Guided AI

A chronicle of our interactions with Claude (Claude.ai and Claude Code) across three weeks of building the AI Data Analyst project — how we prompted, where we hit walls, how we broke through them, and what patterns made us most effective.

---

## Tools and How We Used Them

| Tool | Role |
|------|------|
| **Claude.ai** | Initial architecture design, full-stack code generation from scratch, deployment configuration, and debugging in Week 1 |
| **Claude Code** | Iterative feature development, bug fixes, refactoring, and documentation in Weeks 2 and 3 — operating directly in the terminal and editor |

The shift from Claude.ai to Claude Code was deliberate. Claude.ai is better for open-ended design conversations where you are still figuring out the architecture. Claude Code is better once the codebase exists and you need precise, contextual edits with immediate feedback from running tests and servers.

---

## Week 1 — Building from Scratch with Claude.ai

### Interaction 1 — Framing the implementation approach

The assignment required the agent to execute code and return real output — numbers, charts, summaries — not just generate code snippets for the user to run manually. The first conversation with Claude focused on *how* to implement that: what execution model to use, how to capture stdout and plot files, and how to feed results back to the LLM for interpretation. Claude recommended a subprocess-based executor with stdout capture and a separate interpretation call, which became the foundation of `executor.py` and `agent.py`.

**What worked:** Framing the first conversation around implementation approach rather than jumping straight to code generation gave us a shared understanding of the architecture before any files were created.

### Interaction 2 — Laying out the architecture

We described the goal — a web app where users type natural-language analysis requests and get results — and asked Claude to sketch a full-stack architecture. Claude proposed the three-layer design (React → FastAPI → Anthropic API) and recommended keeping two separate backend routes (`/api/analyze` for the simple path and `/api/agent_analyse` for the agentic path) so we could iterate on the agentic path without breaking the working baseline.

**What worked:** Asking for an architecture before asking for code gave us a shared mental model. When later interactions produced unexpected behavior, we could reason about which layer the problem was in.

### Interaction 3 — First working agent

We asked Claude to generate a minimal working agent. It produced `agent.py`: a direct Anthropic API call that prompted the LLM to write Python, extracted the code block, ran it in a subprocess, and returned the output. It worked, but had a fundamental limitation — if the generated code was wrong, there was no way for the model to see the error and self-correct.

**Blocker:** The agent could not recover from its own mistakes.

### Interaction 4 — Upgrading to a ReAct agent

We described the self-correction limitation to Claude and asked for a solution. Claude recommended LlamaIndex's `ReActAgent`, explained the Think → Act → Observe loop, and generated `agent_service.py`. The loop gave the model automatic self-correction with no custom retry logic on our side.

**What worked:** Describing the limitation rather than prescribing a solution ("the agent can't self-correct, what should we do?") allowed Claude to suggest an architectural upgrade we had not considered.

### Interaction 5 — Code interpreter tool

Claude initially wrote a custom executor, then identified LlamaIndex's `CodeInterpreterToolSpec` as a better drop-in with less code and free compatibility with the data science stack. We accepted the suggestion. This introduced a hidden issue that surfaced in Week 3 (no configurable timeout), but at the time it was the right pragmatic call.

### Interaction 6 — Agent returned code instead of running it

After wiring up the ReAct agent, it would write Python in its responses but never execute it. We pasted the raw API response into the chat and asked Claude to diagnose it. Claude identified two root causes: `streaming=True` (the LlamaIndex default) caused the ReAct parser to misread the Anthropic response mid-stream, and the system prompt was too permissive. Fix: set `streaming=False` and rewrite the system prompt to explicitly prohibit the model from writing code outside a tool call.

**Blocker resolution:** Pasting raw API output directly into the conversation was the key. Claude could not diagnose the problem from a description alone — seeing the actual malformed response made the issue obvious.

### Interaction 7 — Streaming the reasoning trace

We wanted the frontend to show the Think / Act / Observe steps live rather than displaying a single large response at the end. We asked Claude to design a streaming endpoint. Claude proposed Server-Sent Events (SSE) and generated the `/api/agent_analyse/stream` endpoint and the corresponding frontend `analyzeStream()` function in `api.js`.

**What worked:** Asking "design a streaming endpoint" rather than "add streaming" prompted Claude to explain the SSE pattern and its trade-offs before writing code, so we understood what was being built.

### Interaction 8 — Reasoning steps were invisible

After deploying the streaming endpoint, the chat window still showed only the final answer. The intermediate steps were printing to the server terminal via `verbose=True` but never reaching the browser. We described the symptom to Claude. Claude rewrote the agent as a manual ReAct loop using the Anthropic SDK directly, capturing each thought and tool call as a structured `steps[]` array, and updated the frontend to render each step as a distinct bubble.

**Blocker resolution:** Describing the symptom ("steps appear in server logs but not in the UI") rather than guessing at a fix led Claude to the right diagnosis immediately.

### Interaction 9 — Reasoning trace was unreadable

After wiring up step rendering, the UI displayed nothing useful. We pasted both the raw API response object and the existing `_parse_react_trace()` function into the conversation and asked Claude to explain the mismatch. Claude identified it immediately: the parser expected old-style verbose text (`Thought: / Action: / Observation:`) but the LlamaIndex agent emitted structured Python event objects. Fix: replaced stdout parsing with the `stream_events()` API and redesigned the data models around typed event objects.

**What worked:** Providing both the input and the code that processes it let Claude spot the mismatch in seconds. Describing it in words would have been far slower.

### Interaction 10 — Chart rendering

We asked Claude to add chart output support. Claude evaluated two options — base64 encoding in the response body vs. saving to disk and returning a URL — and recommended URLs for their small payload and streaming compatibility. It generated the full pipeline: system prompt instructions for saving charts with a `CHART_SAVED:` marker, backend regex extraction, a FastAPI `StaticFiles` mount, and the Vite proxy entry.

**What worked:** Explicitly asking Claude to compare options before implementing forced it to surface the trade-off between approaches, which we later documented in the written report.

### Interaction 11 — Chart URL had garbage appended

The browser was requesting `/charts/abc123.png/n/nHistogram`. We pasted the malformed URL and the regex into the chat. Claude diagnosed the bug: `[^'\s\n]+` matched the two-character literal `\n` escape sequence rather than stopping at it. Fix: replace with `[0-9a-f]+\.png` — anchored to the exact UUID filename pattern.

**What worked:** Sharing the exact malformed output plus the regex that produced it gave Claude everything needed to diagnose and fix the bug in one turn.

### Interaction 12 — UX polish

We asked Claude for targeted UX improvements without specifying what they should be. Claude made three changes: code blocks default to open, tool output with literal `\n` sequences is normalised to real newlines before display, and stderr gets a red label bar so errors are immediately obvious.

**What worked:** Giving Claude latitude to decide *what* to improve (within a boundary — "UX improvements") produced changes we would not have thought to ask for specifically.

---

## Week 2 — Feature Iteration with Claude Code

By Week 2 the codebase was established. We switched from Claude.ai to Claude Code, which operates directly in the terminal and editor and can read, edit, and run files without copy-pasting. This changed the interaction style: less back-and-forth design conversation, more precise targeted edits.

### CSV and Excel file upload

We told Claude Code the goal — attach a CSV before a prompt and have the agent analyse it — and asked it to implement the feature end-to-end. Claude Code added the `POST /api/upload` endpoint, the `uploads/` directory, the paperclip button in the UI, the file badge display, and the `_build_user_msg()` helper that prepends file context to the agent's user message. All in one session.

**What worked:** Claude Code reading the actual files (rather than us pasting code) meant the edits were contextually correct from the first attempt.

### Dynamic package installation and the two-tier library model

The agent was occasionally failing because it generated `import statsmodels` (not installed) or `pip install pandas` (already installed, wasteful). We asked Claude Code to fix both. It identified the root cause — the system prompt's library list was incomplete — and proposed the two-tier model: pre-install the common packages via `requirements.txt` and let the agent install uncommon ones at runtime. Claude Code also fixed several recurring code-generation errors (double-escaped backslash continuations, `os.makedirs` syntax errors, `Series.__format__` type errors) by updating the system prompt rules.

**Blocker resolution:** We described the class of failures ("the agent sometimes tries to install packages that are already there, and sometimes imports packages that aren't installed") and let Claude Code audit the system prompt and requirements file to find all gaps at once.

### `_uuid` module collision

The agent was crashing with `AttributeError: module '_uuid' has no attribute 'uuid4'`. We reported the error message. Claude Code diagnosed it: `import uuid as _uuid` resolved to Python's internal C extension `_uuid` (which has no `uuid4`). Fix: rename to `import uuid` everywhere.

**What worked:** Sharing the exact error message and stack trace let Claude Code find the root cause in one step.

---

## Week 3 — Hardening and Safety with Claude Code

Week 3 focused on reliability, safety, and correctness. Most interactions followed a consistent pattern: we identified a gap (often from the assignment spec), described it to Claude Code, and asked for the minimal fix.

### CSV file persistence across follow-up prompts

We noticed that asking a follow-up question about an uploaded CSV required re-uploading the file. We asked Claude Code to fix this. It identified that the file path was discarded after each turn and added a fallback scan in `submit()` that walks backward through `messages[]` to find the most recently attached file. Users can still override by attaching a new file.

### Discovering the timeout was never enforced

We asked Claude Code to verify that `EXECUTION_TIMEOUT_SECONDS` actually worked. It traced the code path and found that `CodeInterpreterToolSpec` (the LlamaIndex built-in) ran code in its own subprocess with no timeout — the environment variable had no effect. Claude Code replaced the spec entirely with a custom `_code_interpreter` function backed by `subprocess.run(timeout=_EXECUTION_TIMEOUT)`.

**What worked:** Asking "does this feature actually work?" rather than assuming it did. Tracing the code path with a sceptical eye uncovered a silent failure.

### Input validation and harmful-prompt rejection

We asked Claude Code to implement prompt-level input validation. It added a `_BLOCKED_KEYWORDS` list and an `_is_harmful()` helper in `main.py`, applied to all three POST endpoints, with a descriptive HTTP 400 response. We noted that keyword matching is case-sensitive by default; Claude Code fixed it by lowercasing the prompt before checking.

**Design discussion:** We asked Claude whether keyword matching or semantic analysis was better. Claude explained the trade-off — keywords are simple and predictable; semantic analysis is more robust but requires an additional API call and adds latency. We chose keywords and documented the limitation in the written report.

### Descriptive API error messages

We observed that when the API was misconfigured, the frontend showed a generic error with no actionable guidance. We asked Claude Code to add specific error handling. It added catches for `RateLimitError`, `AuthenticationError`, credits-exhausted patterns, context-window overflow, network errors, and max-iterations exceeded — each with a human-readable message surfaced to the frontend via the SSE `error` event.

### Frontend error display was silently broken

After adding the error messages, we tested with a harmful prompt and saw no error displayed in the UI. We shared a screenshot. Claude Code traced the path: the `onError` handler was setting `content` on the message object, but `MessageBubble` ignores `content` when a `result` object is present. Fix: set `result.error` instead of `content`.

**What worked:** Screenshots were faster and more precise than text descriptions for UI bugs. Sharing the screenshot immediately directed Claude Code to the right component.

### Self-correction demo scenario (Scenario D) was broken

We tested the scenario "Fetch AAPL data and calculate the mean of a column called Weekly_Closing_Average" (intended to trigger a self-correction loop on a missing column). The agent was creating the column instead of trying to access it and failing. We described the intended behavior and asked Claude Code to fix it.

Claude Code added Rule 8 to the system prompt: *"If the user asks you to use a specific named column, access it directly. Do NOT create or derive a column to match the requested name. If the column does not exist, a KeyError will be raised — observe it, then self-correct."*

**What worked:** Explaining the *intended* behavior ("we want the agent to fail and self-correct") rather than just describing the bug helped Claude Code understand that the "fix" was to make the agent *less* proactive, not more.

---

## Patterns That Made Us Most Effective

### Show, don't describe
Pasting raw API responses, error messages, stack traces, regex patterns, and screenshots was consistently faster than describing problems in words. Claude can diagnose from evidence; it cannot diagnose from paraphrase.

### Ask "does this work?" before shipping
Several features were nominally wired up but silently broken (the execution timeout, the frontend error display). Asking Claude Code to trace the code path end-to-end caught these before they became bugs in production.

### Design questions before build requests
For architectural decisions (streaming vs. polling, base64 vs. URL for charts, keyword matching vs. semantic safety filters), asking Claude to compare options first produced better outcomes than asking it to implement the first approach that came to mind.

### Describe the *intended* behavior, not just the bug
For the self-correction scenario, describing what we *wanted* the agent to do (fail with a KeyError and recover) was the key to getting the right fix. If we had just said "the agent creates the column when it should not", Claude might have added a check to block column creation globally, which would have broken legitimate analysis tasks.

### Use Claude Code for edits, Claude.ai for design
Claude.ai with a long context window is better for open-ended design conversations where you are reasoning through trade-offs. Claude Code is better for surgical edits to an existing codebase — it reads the actual files, so it cannot make incorrect assumptions about what the code looks like.

### Let Claude suggest the scope
Several times we described a symptom and let Claude decide the scope of the fix. This often produced smaller, more targeted changes than if we had prescribed the approach ourselves. When Claude proposed a larger refactor than necessary, we pushed back and asked for the minimal fix.

---

## Blockers and How We Resolved Them

| Blocker | Root Cause | Resolution |
|---------|-----------|------------|
| Agent returned code instead of running it | `streaming=True` + weak system prompt | Pasted raw API response; Claude diagnosed both issues at once |
| Reasoning trace showed nothing in UI | Parser expected text format; agent emitted Python objects | Shared both raw response and parser code; Claude spotted mismatch immediately |
| Chart URL had garbage appended | Regex over-captured literal `\n` escape sequences | Shared malformed URL + regex; fixed in one turn |
| Execution timeout had no effect | `CodeInterpreterToolSpec` ran its own subprocess | Code path trace with Claude Code revealed the silent bypass |
| Frontend showed no error on API failure | `onError` set `content`; `MessageBubble` ignored it when `result` exists | Screenshot + component trace |
| Agent created missing column instead of failing | System prompt did not prohibit column fabrication | Explained intended behavior; Claude added targeted system prompt rule |
| Agent loaded CSV on unrelated prompts | File context was phrased as a directive, not a condition | Changed `_build_user_msg` wording to conditional hint |
