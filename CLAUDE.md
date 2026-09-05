# Nani AI — project context

Autonomous care-episode agent. Built with the **Strands Agents SDK** on **Amazon Bedrock** for the AWS "Agents for Humans" hackathon, Everyday Agents track. Deadline Sep 14 2026, 5pm PDT.

## What it does

A patient uploads a doctor's prescription. The agent identifies and prioritises the tests ordered, finds nearby diagnostic labs, sends real booking-request emails and calendar holds, then **waits** — possibly days. When a lab report lands in a watched S3 inbox, a scheduled heartbeat picks it up autonomously, extracts values and reference ranges, compares against the patient's history, and books a follow-up consultation **only if something meaningfully changed**.

The point is not document extraction. It is one episode carried forward across days and systems, deciding at each step whether to act.

## Non-negotiable architecture rules

1. **The coordinator is deterministic.** `backend/coordinator.py` owns the 12-state machine in plain Python. An LLM must never decide a state transition. This is the project's core safety property and its strongest technical argument — do not refactor it into a swarm or hand transitions to an agent.
2. **Agents do judgement, not control flow.** The three Strands specialists (intake, logistics, diagnostics) extract, reason and decide *content*. The coordinator decides *sequence*.
3. **Idempotency before side effects.** Every booking claims `{episode_id}:{test_code}:{attempt}` in DynamoDB with `ConditionExpression="attribute_not_exists(PK)"` **before** the email sends. The scheduler can and will fire twice.
4. **Every step appends to `episode.timeline[]`.** The timeline is what the UI renders and what the demo shows. No silent state changes.
5. **Reference ranges come from the report itself.** Indian lab reports print them. Never hardcode a reference database.
6. **Ambiguity escalates, never guesses.** Unreadable input goes to `NEEDS_HUMAN`. Medical and coverage outputs summarise and flag; they never diagnose or adjudicate.

## State machine

```
PRESCRIPTION_RECEIVED → TESTS_IDENTIFIED → [COVERAGE_CHECKED] → LABS_SHORTLISTED
  → BOOKING_REQUESTED → AWAITING_REPORT → REPORT_RECEIVED → TRENDS_ANALYZED
  → ANOMALY_FOUND | NORMAL → CONSULT_REQUESTED → CLOSED
```

`NEEDS_HUMAN` is reachable from any live state and is retryable.
`COVERAGE_CHECKED` is optional and skipped when no policy is on file.

## Stack

| Concern | Service |
|---|---|
| Agents | Strands Agents SDK |
| Models | Amazon Bedrock (fast model for extraction, stronger for the significance call only) |
| Runtime | Bedrock AgentCore Runtime (fallback: Lambda + API Gateway) |
| State, history, idempotency | DynamoDB, single table `nani-ai` |
| Report inbox | S3 |
| Heartbeat | EventBridge Scheduler → `POST /api/tick` |
| Secrets | AWS Secrets Manager |
| Email | Amazon SES |
| Nearby labs | Google Places API (third party — no AWS equivalent) |
| Slot holds | Google Calendar API (third party) |
| Frontend | Next.js static export |

## Repo layout

```
backend/
  agents/        intake · logistics · diagnostics (Strands) + strands_setup.py
  coordinator.py deterministic 12-state driver
  state/         state machine + idempotency
  tools/         dynamo store · places · ses · calendar · s3
  api/main.py    the endpoints the UI calls
  scripts/       seeding, extraction proofs, report delivery
  tests/
client/          Next.js UI, mock-first
docs/            planning docs (see below)
```

## Docs — read on demand, not by default

| File | When to read it |
|---|---|
| `docs/aws-build-plan.md` | Architecture, Strands port mapping, timeline, checklists. **Start here for any backend work.** |
| `docs/api-contract-v2.md` | Before touching any endpoint or the Episode shape |
| `client/api-contract.md` | The frozen v1 Episode object — source of truth |
| `docs/coverage-check-design.md` | Only if working on the optional coverage feature |
| `docs/frontend-brief-neeraj-aws.md` | Only for frontend work |

## Conventions

- Python, `venv` per directory, `pip freeze > requirements.txt` after adding deps
- The API contract is **frozen**. Changing a field name breaks the frontend — raise it, don't just do it.
- Never commit `.env*`, credentials, or anything in `demo-data/`
- The repo is **public**. Assume everything committed is scraped.
- Prefer editing existing files over creating new ones
- Tests live in `backend/tests/`, run with `pytest`

## Things that will bite

- **SES starts in sandbox mode** — only sends to verified addresses
- **Bedrock model access must be requested** in the console before models are callable
- **$50 of credits, not $300.** Fast model for everything except the single significance call.
- The app must stay live and testable until **Oct 8** (judging period), not just until submission
- `client` uses `output: 'export'`, so `NEXT_PUBLIC_*` vars bake in at build time — changing one needs a rebuild and redeploy

## Prior work

Nani AI was originally built Aug 20–31 2026 on Google Cloud (ADK, Gemini, Cloud Run, Firestore) for Google's All Things Agentic hackathon. This repo is a rebuild of the agent layer and infrastructure on AWS. The prior-work disclosure in the README is a **rules requirement** — do not remove it.
