# AI Data Analyst — AI-Powered Data Analysis Web Application

> CISC 520 Final Project | Week 1 Prototype

An agentic AI system that lets users perform data analysis through natural language. Users describe what they want — *"Fetch Apple stock prices for the last 100 days and plot a chart"* — and the agent generates Python code, executes it, interprets the results, and presents findings in a clean chat interface.

---

## 🚀 Live Demo

**[https://ai-data-analyst-xi.vercel.app/](https://ai-data-analyst-xi.vercel.app/)**

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (Frontend)                 │
│   React chat UI · Code renderer · Chart.js plots    │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP POST /api/analyze
┌───────────────────────▼─────────────────────────────┐
│                 FastAPI Backend                      │
│   Prompt builder → Anthropic API → Code parser      │
│   → Python executor (subprocess + timeout)          │
│   → Result interpreter → Structured JSON response   │
└───────────────────────┬─────────────────────────────┘
                        │ HTTPS
              ┌─────────▼──────────┐
              │   Anthropic API    │
              │  claude-sonnet-4   │
              └────────────────────┘
```

**Agentic pattern implemented:** Multi-step reasoning (plan → generate code → execute → interpret) with self-correction on execution errors and iterative refinement via conversation history.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Clone & configure

```bash
git clone https://github.com/oshevchuk27/ai-data-analyst.git
cd ai-data-analyst
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Example Prompts

| Scenario | Prompt |
|----------|--------|
| Stock analysis (Scenario A) | `Fetch the last 100 days of Apple (AAPL) stock closing prices. Plot a line chart with dates on the x-axis. Then calculate and display: mean, median, standard deviation, min, and max price.` |
| Dataset analysis (Scenario B) | `Generate a sample sales dataset with 100 rows and columns: date, product, region, units_sold, and revenue. Show me the first 5 rows, data types for each column, any missing values, and plot a histogram of the revenue column.` |
| Statistical comparison (Scenario C) | `Compare the monthly returns of Tesla (TSLA) and Microsoft (MSFT) over the past year. Show both on the same chart and run a t-test to see if the mean returns are significantly different.` |
| Self-correction (Scenario D) | `Fetch AAPL stock data for the last 30 days and calculate the mean of a column called Weekly_Closing_Average then plot it.` *(agent hits a KeyError, auto-corrects, and retries)* |
| Crypto portfolio analysis (Scenario E) | `Fetch the last 6 months of Bitcoin (BTC-USD) and Ethereum (ETH-USD) prices. Compute the 7-day and 30-day rolling correlation. Plot price history, rolling correlation, and a scatter plot of daily returns with a regression line. Print whether BTC and ETH are highly correlated and what that means for portfolio diversification.` |
| Follow-up / iterative refinement | `Now calculate a 30-day rolling Value at Risk (VaR) at 95% confidence level for each stock and compute the maximum drawdown.` *(references prior analysis — tests conversation memory)* |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Chart.js |
| Backend | Python 3.13, FastAPI, Uvicorn |
| LLM | Anthropic Claude (claude-sonnet-4-20250514) |
| Code execution | Python `subprocess` with 60s timeout |
| Data libraries | pandas, numpy, matplotlib, yfinance, scipy, seaborn |

---

## Project Structure

```
ai-data-analyst/
├── README.md
├── .env.example
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── ChatWindow.jsx
│       │   ├── MessageBubble.jsx
│       │   ├── CodeBlock.jsx
│       │   └── ChartOutput.jsx
│       └── api.js
├── backend/
│   ├── requirements.txt
│   ├── main.py          ← FastAPI app + routes
│   ├── agent.py         ← LLM orchestration + system prompt
│   ├── executor.py      ← Python code execution sandbox
│   ├── models.py        ← Pydantic request/response models
│   └── Procfile         ← Railway deployment config
└── docs/
    └── architecture.md
```

---

## Deployment

The app is deployed using **Railway** (backend) and **Vercel** (frontend). Both platforms are connected to this GitHub repository and **automatically redeploy on every push to `main`** — no manual deployment steps required.

| Service | Platform | URL |
|---------|----------|-----|
| Frontend (React + Vite) | Vercel | https://ai-data-analyst-xi.vercel.app/ |
| Backend (FastAPI) | Railway | https://ai-data-analyst-production.up.railway.app |

### Deploying your own instance

1. Fork this repository
2. Connect Railway to your fork, set root directory to `backend`, and add environment variables (`ANTHROPIC_API_KEY`, `ALLOWED_ORIGINS`, `EXECUTION_TIMEOUT_SECONDS`)
3. Connect Vercel to your fork, set root directory to `frontend`, and add `VITE_API_URL` pointing to your Railway URL
4. Push to `main` — both services deploy automatically

---

## Known Limitations (Week 1 Prototype)

- **No true sandbox isolation** — code execution runs in a Python subprocess, not a fully isolated Docker container. A Docker-based sandbox (e.g. E2B or a custom container) is planned for Week 2 for improved security
- **No CSV file upload** — Scenario B currently uses agent-generated sample datasets instead of user-uploaded CSV files. File upload support is planned for Week 2
- **Self-correction reliability** — the agent sometimes anticipates missing columns or files and corrects proactively within a single code block, rather than producing a visible runtime error followed by a retry. A more robust error-trigger-and-retry loop is planned
- **Static library allowlist** — the code executor only allows libraries listed in `requirements.txt`. If the LLM generates code using a library not pre-installed (e.g. `scikit-learn`, `statsmodels`), the execution fails. Dynamic dependency installation based on user prompts is planned for Week 2
- **Output display order is fixed** — the UI always renders code → stdout → chart → summary regardless of the order the user specified in their prompt. Dynamic ordering based on prompt intent is a planned enhancement
- **No authentication or rate limiting** — the API endpoints are publicly accessible with no user authentication or per-user rate limiting
- **No persistent conversation history** — conversation context is stored in browser memory only and is lost on page refresh or tab close. Database-backed persistence is planned for Week 2
- **Matplotlib figure capture depends on server environment** — requires `MPLBACKEND=Agg` environment variable to be set on the server; missing this causes charts to not render in the deployed version
- **yfinance network timeouts** — fetching live stock data can exceed the execution timeout on slow network conditions; the timeout has been set to 60 seconds to mitigate this

---

## AI Usage Documentation

As required by the course, the following documents all AI tool usage in this project.

### Tools used
- **Claude.ai (Anthropic)** — used exclusively throughout the project

### How Claude.ai was used

| Area | Usage |
|------|-------|
| Full-stack code generation | Generated all backend files (`main.py`, `agent.py`, `executor.py`, `models.py`) and all frontend components (`App.jsx`, `ChatWindow.jsx`, `MessageBubble.jsx`, `CodeBlock.jsx`, `ChartOutput.jsx`, `api.js`) from scratch |
| System prompt engineering | Designed and iterated on the LLM system prompt for the data analysis agent, including output format constraints and self-correction instructions |
| Deployment configuration | Generated `Procfile`, `.env.example`, CI workflow (`ci.yml`), and guided the full Railway + Vercel deployment process step by step |
| Debugging & troubleshooting | Diagnosed and resolved CORS errors, Railway build failures (`Railpack` errors, Python version issues), matplotlib rendering issues in production, and Git conflicts |
| Architecture design | Designed the agentic pipeline architecture (prompt → LLM → code → execute → self-correct → interpret) and the overall project structure |
| Test generation | Generated all unit tests in `tests/test_executor.py` and `tests/test_api.py` |
| Documentation | Generated this README, `docs/architecture.md`, and inline code comments |
| Demo scenario design | Designed all 5 demo scenario prompts and follow-up prompts for iterative refinement testing |

### Which parts were AI-assisted
All code in this repository was generated with Claude.ai assistance. The students directed the architecture decisions, reviewed all generated code, debugged issues interactively with Claude, and validated the application end-to-end through manual testing.