# SupportOps AI — PRD V1

SupportOps AI is a portfolio-grade Applied AI customer-support agent for the fictional e-commerce company NovaCart. It must understand requests, retrieve versioned policy evidence, query real operational data, execute typed tools, pass deterministic authorization gates, resolve low-risk cases, and escalate unsafe cases with a structured handoff.

## Product boundary

The product is not a generic chatbot, PDF Q&A demo, notebook, prompt showcase, or fake dashboard. The core claim is: **the AI safely resolves support workflows, not merely answers questions.**

## Required system

- Synthetic NovaCart dataset: 750+ customers, 3,000+ orders, shipments, payments, refunds, tickets, policies, and 150+ evaluation cases.
- Explicit structured agent state and multi-step orchestration.
- Policy RAG with document metadata and traceable citations.
- Typed operational tools backed by application state.
- Deterministic authorization for financial actions and duplicate prevention.
- Human escalation for high-risk, unresolved, conflicting, low-confidence, or failing cases.
- Reproducible evaluation with real execution metrics, latency, token, and cost accounting.
- B2B support console, sanitized resolution trace, evaluation dashboard, and architecture view.
- FastAPI/Pydantic backend, Next.js/TypeScript frontend, tests, Docker, CI, and deployment documentation.

## Required demos

1. Order status lookup.
2. Damaged-item refund through RAG, validation, and safe execution.
3. $600 refund escalated above threshold.
4. Prompt-injection attempt rejected by deterministic rules.
5. Late-package investigation with lost-package classification and conditional refund.

## Definition of done

A recruiter can select a demo identity, send a request, inspect evidence and real tool calls, observe safe resolution or escalation, inspect the sanitized trace and actual evaluation metrics, review the architecture, and inspect working code. No important behavior, metric, tool result, database result, or trace is fabricated.
