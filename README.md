# Data Agent — Autonomous Pandas Code Generation with Self-Correction

An agent that answers natural-language questions about tabular data by planning a solution, writing pandas code, executing it, and automatically correcting itself when the code fails — built end-to-end with a FastAPI backend and a lightweight web frontend.

## How it works

1. **Plan** — given a question and a preview of the dataframe, the LLM (Groq, `llama-3.3-70b-versatile`) writes a short step-by-step plan before touching any code.
2. **Generate code** — based on its own plan, the LLM writes pandas code that stores its final answer in a variable called `result`.
3. **Safety check** — generated code is scanned for dangerous patterns (file access, system calls, imports beyond pandas) before execution.
4. **Execute** — the code runs in a restricted namespace containing only `df` and `pandas`.
5. **Validate** — the result is checked to confirm it's a single clean value (not a Series, DataFrame, tuple, dict, or `None`).
6. **Self-correct** — if execution fails, or the result fails validation, the error is fed back to the LLM along with its previous code, and it retries (up to 4 attempts).

This loop — plan, act, observe, correct — is the same reasoning pattern behind agentic AI frameworks generally (often called ReAct: Reasoning + Acting), implemented here from first principles rather than through a heavier framework, to understand exactly what's happening at each step.

## Stack

- **LLM**: Groq API (`llama-3.3-70b-versatile`)
- **Backend**: FastAPI + Pydantic (request validation), Uvicorn (server)
- **Data**: pandas
- **Frontend**: plain HTML/CSS/JavaScript (no framework) calling the API via `fetch`
- **Secrets**: `.env` + `python-dotenv`, excluded from version control via `.gitignore`

## Running it locally

```bash
git clone <repo-url>
cd data-agent
python -m venv venv
source venv/bin/activate  # or venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
```

Create a `.env` file:
```
GROQ_API_KEY=your_key_here
```

Run the server:
```bash
uvicorn api:app --reload
```

Visit `http://127.0.0.1:8000/` and ask a question. Interactive API docs are available at `http://127.0.0.1:8000/docs`.

Run the evaluation suite:
```bash
python evaluate.py
```

## Evaluation results

Tested against a 10-question set spanning simple lookups, multi-step aggregations, date/time-based grouping, and one deliberately hard multi-condition question, with all expected values independently verified via direct pandas computation (not manual arithmetic).

Across two evaluation runs:

| Metric | Run 1 | Run 2 |
|---|---|---|
| Accuracy | 80%* | 100% |
| Crashes (unrecovered) | 0/10 | 0/10 |
| Avg. attempts per question | 1.0 | 1.3 |
| Avg. response time | 0.67s | 0.57s |

\* Run 1's two "failures" were later found to be an evaluation bug, not agent errors — the agent correctly identified March as the highest-spending month but returned it as a bare month number (`3`) rather than year-month format (`2024-03`); the comparison logic was fixed to recognize this equivalence.

**Notable finding:** the same question can require a different number of attempts across separate runs, since the LLM's code generation is non-deterministic — for example, remembering to convert a date column to datetime type before grouping by it sometimes happens on the first attempt and sometimes requires a self-correction round. This is expected behavior in LLM-based systems, not a defect.

## Known limitations

- **Self-correction can regress on its own fixes.** On a sufficiently complex question requiring multiple chained corrections, the model occasionally re-introduces a bug it had already fixed earlier in the same retry sequence, since each retry regenerates the full solution rather than patching a specific line. A repeat-error detector was added to flag and escalate exact repeated errors, but it only catches identical error text — conceptually similar but differently-worded errors slip through.
- **The code safety check is a text-based blocklist, not a true sandbox.** It catches obvious risks (file access, system calls, unauthorized imports) but is not a guarantee against a sufficiently adversarial prompt. One real false positive was found and fixed during development (`pd.eval()`, a legitimate pandas method, was being blocked because it contains the substring `eval(`). A more robust approach would parse code into an AST and check actual function calls rather than text patterns.
- **No validation that a successful result matches the question's intent**, only that it's a single clean value. A result can pass all checks while still answering a subtly different question than the one asked, if the model's plan drifts from its own stated steps.
- **`exec()`-based execution**, even with a restricted namespace and pre-execution safety scan, is not appropriate for a fully public-facing deployment without additional sandboxing (e.g., a separate restricted process or container) — noted here rather than overstated as production-ready.

## What this project demonstrates

- Agentic design: planning before acting, tool use (code execution), and self-correction based on observed failures
- Prompt engineering for structured, parseable LLM output
- Honest evaluation methodology, including catching and fixing bugs in the evaluation harness itself, not just the system under test
- A full-stack implementation: LLM integration → backend API → request validation → frontend, with security considerations addressed at the execution layer
