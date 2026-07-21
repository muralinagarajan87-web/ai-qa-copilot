# AI QA Copilot

An autonomous, agentic QA platform: upload a PRD, an LLM-driven agent pipeline generates traceable manual test cases, a human reviews and approves them, and a second agent turns the approved cases into a real, runnable Playwright automation suite (Page Object Model, ESLint-enforced standards, `tsc`-checked). Built to explore agentic workflow design, autonomous decision-making, and enterprise QA process automation end-to-end — not a toy chatbot wrapper.

Everything runs on a config-driven orchestrator: agents are registered by name in YAML, the transition table in `configuration/workflow.yaml` decides what runs next, and no agent class is ever imported directly by the engine. Adding a new agent is a YAML entry plus a module, not a change to orchestration code.

## Why this exists

Built as a hands-on deep dive into what "AI-augmented QA leadership" actually looks like in practice: not just "use ChatGPT to write test cases," but a real pipeline with requirement traceability, versioned artifacts, an audit trail, and mechanically-enforced code standards — the kind of system a QA org could actually trust and extend.

## Architecture

```
PRD upload
   │
   ▼
Test Case Generator Agent  ──▶  requirement extraction, then scenario-driven
   │                            test case decomposition (depth scales with
   │                            requirement type: validation rules get deep
   │                            coverage, UI behavior gets minimal coverage)
   ▼
Human review / approval  ◀──  full requirement-traceability + PRD gap analysis
   │
   ▼
Automation Agent  ──▶  groups approved test cases by module, generates one
   │                   Page Object + one Playwright spec per module, with
   │                   step-level test.step() wrapping for readable reports
   ▼
ESLint + tsc gate  ──▶  mechanically enforced: no XPath, no hard waits,
                        every test asserts something, POM is mandatory
```

**Orchestrator** (`backend/app/orchestrator/engine.py`) walks a transition table (`configuration/workflow.yaml`) and holds zero business logic — it doesn't know what a "test case" or a "hard wait" is. It asks the **Agent Registry** (`configuration/agents.yaml`) for an agent by name, asks the agent to build its own input from a shared `WorkflowContext`, executes it, validates the result, and persists the output as a versioned artifact.

**Artifacts are filesystem-derived, not double-recorded.** Every agent output is saved to `artifacts/runs/<run_id>/<kind>/v<n>.json`; a run's revision history and requirement-traceability matrix are computed on read from those versions, not maintained as a separate log that could drift out of sync.

**LLM access is a swappable provider**, not a hardcoded client. Every agent depends on an `LLMProvider` protocol (`generate()` / `embed()`); which model answers is entirely a `configuration/models.yaml` edit. Ollama (fully local, zero cost), Groq (fast hosted inference), and Claude are all implemented behind the same interface.

## Agents

| Agent | Status | What it does |
|---|---|---|
| **Test Case Generator** | Built | Two-stage: extracts numbered requirements from a PRD, then generates test cases per requirement. Decomposition depth is driven by requirement type (a validation rule gets a 6+ test-case floor; a UI-behavior requirement gets one). Flags PRD gaps (zero-coverage requirements) instead of fabricating scope. |
| **Automation Agent** | Built | Converts approved test cases into a real Playwright + TypeScript project: one Page Object and one spec file per module, Page Object Model enforced, `test.step()`-wrapped for step-level reporting. Output is checked with real ESLint + `tsc`, not just prompted-and-trusted. |
| **Reviewer Agent** | Planned | Will close the loop: reviews generated automation against org coding standards, and the Automation Agent regenerates against its feedback (bounded revision loop, capped at 3 attempts before escalating to a human). |

## Real-site grounding

Generated automation targets [saucedemo.com](https://www.saucedemo.com/), a public Playwright practice site — not a fictional app. The PRD in `docs/samples/sample-prd-saucedemo.md` was written from real inspection of the live DOM (actual `data-test` attributes, actual error copy, actual redirect URLs), so the generated Playwright suite in `playwright/` is a real, currently-runnable test suite, not illustrative sample code.

## Stack

- **Backend**: FastAPI, Pydantic, SQLite (workflow run + artifact metadata index)
- **Agents/LLM**: Python, with Ollama / Groq / Claude behind one provider interface
- **Automation output**: Playwright + TypeScript, ESLint (`eslint-plugin-playwright`), `tsc`
- **Orchestration**: config-driven state machine (no framework — a transition table + an agent registry)

## Running it

```bash
# Backend
uv sync
cp .env.example .env   # fill in GROQ_API_KEY and/or ANTHROPIC_API_KEY as needed
uvicorn backend.app.main:app --reload

# Generated Playwright suite
cd playwright
npm install
npx playwright install chromium
npx playwright test
```

`configuration/models.yaml` controls which LLM provider agents use — Ollama needs nothing beyond a local `ollama serve` and the referenced models pulled; Groq/Claude need the matching API key in `.env`.

## What's deliberately not built yet

- **Reviewer Agent** — the closing piece of the review→regenerate loop (see table above).
- **GitHub PR integration** (`services/git_service.py`) — interface is defined, implementation is a stub. The goal is a webhook triggering this same orchestrator on PR events, not a re-hosted Claude Skill.
- **Frontend** — the system is currently API-first (FastAPI + WebSocket event stream); a review UI is a natural next layer on top of the existing `/workflows` API.
