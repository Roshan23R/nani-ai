# Nani AI — project context

Autonomous care-episode agent. Built with the **Strands Agents SDK** on **Amazon Bedrock** for the AWS "Agents for Humans" hackathon, Everyday Agents track. Deadline Sep 14 2026, 5pm PDT.

## What it does

A patient uploads a doctor's prescription. The agent identifies the tests ordered, **asks the patient to confirm what it read**, finds nearby diagnostic labs, sends real booking-request emails and calendar holds, then **waits** — possibly days. When a lab report lands in a watched S3 inbox, a scheduled heartbeat picks it up autonomously, extracts values and reference ranges, compares against the patient's history, and books a follow-up consultation **only if something meaningfully changed**.

The point is not document extraction. It is one episode carried forward across days and systems, deciding at each step whether to act.

## Non-negotiable architecture rules

1. **The coordinator is deterministic.** `backend/coordinator.py` owns the state machine in plain Python. An LLM must never decide a state transition. This is the project's core safety property and its strongest technical argument — do not refactor it into a swarm or hand transitions to an agent.
2. **Agents do judgement, not control flow.** The Strands specialists extract, reason and decide *content*. The coordinator decides *sequence*.
3. **Autonomy is gated on extraction confidence.** `high` → book without asking. `medium` → `AWAITING_CONFIRMATION`, show what was read and wait. `low` or no tests → `NEEDS_HUMAN`. Decided Sep 8, replacing a blanket always-confirm rule: refusing to act on a good read regardless of how good it was is not judgement, it is abdication. The rule lives in `state/machine.py:route_after_extraction`, is deterministic, and is tested.
4. **Idempotency before side effects.** Every booking claims `{episode_id}:{test_code}:{attempt}` in DynamoDB with `ConditionExpression="attribute_not_exists(PK)"` **before** the email sends. The scheduler can and will fire twice.
5. **Every step appends to `episode.timeline[]`.** The timeline is what the UI renders and what the demo shows. No silent state changes.
6. **Reference ranges come from the report itself.** Indian lab reports print them. Never hardcode a reference database.
7. **Ambiguity escalates, never guesses.** Unreadable input goes to `NEEDS_HUMAN`. Medical and coverage outputs summarise and flag; they never diagnose or adjudicate.

## State machine

```
PRESCRIPTION_RECEIVED → TESTS_IDENTIFIED ─┬─ high ──────────────────┐
                                          ├─ medium → AWAITING_CONFIRMATION ─┤
                                          └─ low / no tests → NEEDS_HUMAN    │
                                                                             ▼
  [COVERAGE_CHECKED] → LABS_SHORTLISTED → BOOKING_REQUESTED → AWAITING_REPORT
  → REPORT_RECEIVED → TRENDS_ANALYZED → ANOMALY_FOUND | NORMAL
  → CONSULT_REQUESTED → CLOSED
```

The table lives in `backend/state/machine.py`. It is the only place transitions are
defined, `assert_legal()` is the single choke point, and an illegal move **raises** —
a state machine you can bypass is a diagram, not a safety property.

- `NEEDS_HUMAN` is reachable from any live state and is retryable back into any of them.
- `AWAITING_CONFIRMATION` stops the UI poll but is **not** final. Nothing proceeds until `POST /api/episodes/{id}/confirm`; `→ PRESCRIPTION_RECEIVED` is the "I need to re-upload" path.
- `COVERAGE_CHECKED` is **cut** for this build. It stays wired in the table so enabling it later is a coordinator change, not a machine change — but nothing routes to it today.
- `NORMAL` and `CLOSED` both stop polling; the frontend already treats `NORMAL` as terminal.

## Extraction findings — tested Sep 7 against 3 real handwritten prescriptions

**These were expensive to learn. Do not re-litigate them.**

- **Sonnet 4.5 for extraction and the significance decision.** 4 of 4 tests correct on a hard handwritten prescription, zero fabrications.
- **Haiku 4.5 for summary writing and lab selection only.** It invents tests (LFT, RFT that weren't on the page) and misreads names. **Never use it for extraction.**
- **Nova Pro is disqualified** — it missed an MRI, the most important investigation on the page.
- **The prompt must NOT contain a list of common investigations framed as a reference.** Models treat such a list as a *menu* and fill gaps from it. Frame any list as recognition-only, with an explicit "this is not a menu" instruction. This single change took Sonnet from 3/4-with-a-fabrication to 4/4-clean.
- **`date` and `exam_findings` are extracted but unreliable.** The model asserted `2014-03-14` for a prescription clearly dated 17.03.17, and read a BP of 140/80 as PR 110/80 — both confidently, without flagging. Store them, never display them. Use the upload timestamp for anything user-facing.
- **Exam findings are not medicines.** SLR, OLE, ROM, BP, PR, SpO2, rhonchi, "no neurology" — these get misfiled into `medicines` unless the prompt calls them out explicitly.
- **Gate:** `confidence == "low"` or empty `tests` → `NEEDS_HUMAN`. Never proceed on a weak extraction. This gate caught Haiku fabricating an entire coherent cardiac case (aspirin, statin, beta blocker, lipid profile, ECG) from an illegible prescription about back pain.

**The working prompt lives in `backend/scripts/test_extraction.py`. Reuse it verbatim in the intake agent.** It is the product of four tuning rounds against real documents.

## Stack

| Concern | Service |
|---|---|
| Agents | Strands Agents SDK |
| Models | Amazon Bedrock — see config below |
| Runtime | Bedrock AgentCore Runtime (fallback: Lambda + API Gateway) |
| State, history, idempotency | DynamoDB, single table `nani-ai` |
| Report inbox | S3 |
| Heartbeat | EventBridge Scheduler → `POST /api/tick` |
| Secrets | AWS Secrets Manager |
| Email | Amazon SES |
| Nearby labs | Google Places API (third party — no AWS equivalent) |
| Slot holds | Google Calendar API (third party) |
| Frontend | Next.js static export |

## Config

```
AWS_REGION=us-east-1
BEDROCK_MODEL_SMART=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_MODEL_FAST=us.anthropic.claude-haiku-4-5-20251001-v1:0
```

- Bedrock is called through the **Converse API**. Images go as `{"image": {"format": "jpeg", "source": {"bytes": raw}}}`, PDFs as `{"document": {...}}` with an alphanumeric name.
- Models wrap JSON in markdown fences despite instructions — **always strip fences defensively before parsing.**
- `temperature=0` for all extraction calls.
- **SES is in sandbox: 1 email/second, 200/day.** If the logistics agent sends booking requests for several tests, throttle them or you'll hit a rate error.

## Repo layout

```
backend/
  agents/        intake · logistics · diagnostics (Strands) + strands_setup.py
  coordinator.py deterministic state machine driver
  state/         state machine + idempotency
  tools/         dynamo store · places · ses · calendar · s3
  api/main.py    the endpoints the UI calls
  scripts/       test_extraction.py, seeding, report delivery
  tests/
client/          Next.js UI, mock-first
docs/            planning docs (see below)
demo-data/       real prescriptions — gitignored, never commit
```

## Docs — read on demand, not by default

| File | When to read it |
|---|---|
| `docs/aws-build-plan.md` | Architecture, Strands port mapping, timeline, checklists. **Start here for any backend work.** |
| `docs/api-contract-v2.md` | Before touching any endpoint or the Episode shape. Section 4 is the confirmation step. |
| `client/api-contract.md` | The frozen v1 Episode object — source of truth |
| `docs/coverage-check-design.md` | Only if working on the optional coverage feature |
| `docs/frontend-brief-aws.md` | Only for frontend work. Rakesh owns the UI as of Sep 8 |
| `docs/build-checklist.md` | The live step-by-step build order. **Check this before picking up work.** |

## Conventions

- Python, `venv` per directory, `pip freeze > requirements.txt` after adding deps
- The API contract is **frozen**. Changing a field name breaks the frontend — raise it, don't just do it.
- Never commit `.env*`, credentials, or anything in `demo-data/`. Real prescriptions with real patient names are in there.
- The repo is **public**. Assume everything committed is scraped.
- Prefer editing existing files over creating new ones
- Tests in `backend/tests/`, run with `pytest`

## Build order — the rule that protects the project

Do not build agents one at a time to completion. Build the whole path badly first: intake → logistics → diagnostics → coordinator → infra. Stubs everywhere. **Ugliest possible end-to-end run by Sep 10**, then improve.

Three excellent components that don't talk to each other score zero.

## Things that will bite

- **$50 of credits, not $300.** Haiku for everything except extraction and the single significance call per episode.
- The app must stay live and testable until **Oct 8** (judging period), not just until submission. Do not tear down after recording.
- `client` uses `output: 'export'`, so `NEXT_PUBLIC_*` vars bake in at build time — changing one needs a rebuild and redeploy.
- Record the demo video **Sep 13**, not the 14th. Max 5 minutes.

## Prior work

Nani AI was originally built Aug 20–31 2026 on Google Cloud (ADK, Gemini, Cloud Run, Firestore) for Google's All Things Agentic hackathon. This repo is a rebuild of the agent layer and infrastructure on AWS. The prior-work disclosure in the README is a **rules requirement** — do not remove it.
