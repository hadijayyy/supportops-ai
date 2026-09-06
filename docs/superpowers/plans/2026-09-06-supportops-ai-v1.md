# SupportOps AI V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployable NovaCart support agent that uses evidence, typed tools, deterministic safety gates, human escalation, and reproducible evaluation to resolve real workflows.

**Architecture:** A modular monolith separates domain rules, operational tools, policy retrieval, orchestration, observability, and API delivery. A Next.js console consumes FastAPI endpoints; SQLite provides a zero-config demo while the repository includes a PostgreSQL/pgvector production path.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/SQLite, LangGraph-compatible explicit state graph, deterministic TF-IDF retrieval with optional embeddings, Next.js, TypeScript, pytest, Docker, GitHub Actions.

**Spec:** `docs/PRD.md`

## Global Constraints

- Use only synthetic NovaCart data: at least 750 customers and 3,000 orders.
- Financial actions require deterministic authorization and idempotency.
- Retrieved text is untrusted and cannot alter instructions.
- Never expose chain-of-thought; traces contain only observable steps and sanitized outputs.
- Evaluation metrics must be produced from executed cases, never hard-coded.
- Keep a modular monolith; no Kubernetes or unnecessary microservices.

---

### Task 1: Foundation and seeded operational data

**Files:** `backend/supportops/config.py`, `backend/supportops/db.py`, `backend/supportops/models.py`, `backend/supportops/seed.py`, `backend/tests/test_seed.py`

**Interfaces:** Produces `Database`, `seed_database(db)`, and typed domain records consumed by every later task.

- [ ] Write a failing test asserting counts of customers, orders, shipments, policies, and deterministic demo records.
- [ ] Run `pytest backend/tests/test_seed.py -q` and confirm the missing modules fail.
- [ ] Implement schema creation and deterministic Faker-free generation of 800 customers and 3,200 orders plus linked records.
- [ ] Re-run the seed test and confirm all count and foreign-key assertions pass.
- [ ] Commit foundation changes.

### Task 2: Deterministic business rules and typed tools

**Files:** `backend/supportops/rules.py`, `backend/supportops/tools.py`, `backend/tests/test_rules_tools.py`

**Interfaces:** Produces `ToolRegistry.execute(name, args) -> ToolResult`, refund eligibility/calculation, cancellation, ticket, and escalation operations.

- [ ] Write failing tests for eligible refund, threshold escalation, duplicate prevention, unknown order, and invalid arguments.
- [ ] Run the focused tests and confirm failures.
- [ ] Implement Pydantic tool inputs, structured outputs, transactions, idempotency keys, and deterministic authorization.
- [ ] Re-run tests and confirm tool mutations persist exactly once.
- [ ] Commit tools and rules.

### Task 3: Policy retrieval with attributable evidence

**Files:** `backend/supportops/rag.py`, `backend/data/policies/*.md`, `backend/tests/test_rag.py`

**Interfaces:** Produces `PolicyRetriever.search(query, category, k) -> list[PolicyEvidence]` with document ID, title, version, effective date, excerpt, and score.

- [ ] Write failing retrieval and citation tests for returns, damaged items, shipping, lost packages, cancellations, and prompt-injection content.
- [ ] Run the focused retrieval tests.
- [ ] Implement chunking, normalized token scoring, metadata filtering, stable ranking, and evidence preservation.
- [ ] Verify Recall@3 against the policy fixture queries.
- [ ] Commit policy and retrieval changes.

### Task 4: Explicit agent workflow and safety gates

**Files:** `backend/supportops/agent.py`, `backend/supportops/schemas.py`, `backend/tests/test_agent.py`

**Interfaces:** Produces `SupportAgent.run(AgentRequest) -> AgentResult` and serializable state containing intent, confidence, customer/order context, evidence, tool events, risks, authorization, escalation, response, and usage.

- [ ] Write failing end-to-end tests for all five required demos.
- [ ] Run focused agent tests and capture failures.
- [ ] Implement intent routing, identity/order resolution, conditional retrieval, tool sequence, policy/risk validation, safe action execution, and handoff generation.
- [ ] Add prompt-injection detection and bounded tool retries without revealing private reasoning.
- [ ] Re-run the demo tests and confirm grounded resolution or escalation.
- [ ] Commit workflow changes.

### Task 5: API and observability

**Files:** `backend/supportops/api.py`, `backend/supportops/observability.py`, `backend/tests/test_api.py`

**Interfaces:** Produces `/health`, `/customers/demo`, `/agent/run`, `/runs/{id}`, `/evaluations/latest`, and `/architecture` JSON endpoints.

- [ ] Write failing API contract tests.
- [ ] Run focused API tests.
- [ ] Implement dependency-injected app state, structured run logging, secret/PII sanitization, latency, token, and estimated-cost accounting.
- [ ] Re-run API tests and validate persisted run records.
- [ ] Commit API changes.

### Task 6: Reproducible benchmark suite

**Files:** `backend/evals/cases.json`, `backend/evals/run.py`, `backend/evals/metrics.py`, `backend/tests/test_evals.py`

**Interfaces:** Produces `python -m evals.run` and `backend/data/evaluation-results.json` from at least 150 executed cases.

- [ ] Write failing benchmark-schema and metric-calculation tests.
- [ ] Generate balanced deterministic cases with expected intent, tools, policy, outcome, and escalation.
- [ ] Execute every case against `SupportAgent`, calculate required metrics and percentiles, and persist aggregate plus per-case results.
- [ ] Re-run to prove reproducibility and ensure the dashboard reads only generated output.
- [ ] Commit evaluation suite and actual result artifact.

### Task 7: Recruiter-facing operations console

**Files:** `frontend/app/**`, `frontend/components/**`, `frontend/lib/**`, `frontend/package.json`

**Interfaces:** Consumes the API contracts from Task 5 and renders demos, conversation, context, evidence, tool activity, sanitized trace, evaluation, and architecture.

- [ ] Implement a typed API client and demo fallback fixture generated from real backend responses.
- [ ] Build a responsive light-mode support console with concise operational copy and one-click demo scenarios.
- [ ] Build evaluation and architecture views using actual API data; keep visualization density purposeful.
- [ ] Run lint/typecheck/build and verify desktop/mobile layouts.
- [ ] Commit frontend changes.

### Task 8: Packaging, CI, documentation, and final QA

**Files:** `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `README.md`, `.env.example`, `Makefile`, `docs/architecture.md`

**Interfaces:** Produces repeatable local/deployed builds and recruiter documentation.

- [ ] Add multi-stage containers, health checks, environment contracts, and CI commands.
- [ ] Document agent justification, architecture, RAG, tool safety, evaluation methodology/results, setup, deployment, and limitations.
- [ ] Run backend tests, evaluation, frontend checks/build, container config validation, and five demo smoke tests.
- [ ] Fix all high-impact failures, record verified commands, and package the repository.
- [ ] Commit the completed project and prepare deployment handoff.
