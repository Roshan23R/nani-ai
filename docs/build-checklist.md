# Build checklist — Nani AI on AWS

**Live working order. Tick as you go.** Drawn Sep 8 2026 · deadline **Sep 14, 5:00pm PDT**.

Strategy and reasoning live in `aws-build-plan.md`. This file is only *what to do next*.
One rule: **do not skip ahead.** The order encodes dependencies, and the spine (Phase 1)
blocks everything after it.

> ### ▶ NEXT UP — step 06, the idempotency claim
> `backend/state/idempotency.py`. The table is live and the machine is done and tested.

---

## Phase 0 · Unblock

- [x] **00a** Bedrock reachable — `scripts/hello_strands.py` returns from Sonnet 4.5
- [x] **00b** Intake agent + gate, verified 4/4 on `IMG_2070`, 0 tests → `NEEDS_HUMAN` on `IMG_2071`
- [x] **00c** `.gitignore` covering `demo-data/`, `*accessKeys*.csv`, `venv/`, `.env*`
- [x] **02** DynamoDB table `nani-ai` — on-demand, `PK`/`SK` strings, TTL on `expires_at`
- [ ] **01** **Make the repo public** — Stage One is pass/fail. MIT licence already committed and detected; only visibility is wrong
- [ ] **03** Credits form — **closes Sep 11, 12:00pm PT.** Rules page and resources page link different forms; submit both
- [ ] **03b** Billing alarm at $25 (you have $50, not $300)
- [ ] **04** Load Places key + Calendar OAuth into Secrets Manager (currently empty)
- [ ] **04b** **Anonymise demo identities** — real patient names came out of both prescriptions. Invented names in every seed record, mock and on-screen string before the repo goes public or anything is recorded

---

## Phase 1 · The spine, stubbed — Sep 8–9

**Goal: one episode walks upload → `CLOSED` locally, with fake labs and fake emails, every
step on the timeline.** Nothing here calls a third-party API. This is the week's hard part.

- [x] **05** `backend/state/machine.py` — 14 states, legal-transition table, `assert_legal()` raises. Confidence routing included. 26 tests green
- [ ] **06** `backend/state/idempotency.py` — atomic claim on `{episode_id}:{test_code}:{attempt}` via `ConditionExpression="attribute_not_exists(PK)"`, with a TTL. Write it *before* anything can send email
- [ ] **07** `backend/tools/store.py` — single-table access: put/get episode, append `timeline[]`, list by patient, read/write result history. Keys exactly as in build plan §3
- [ ] **08** `backend/coordinator.py` — plain-Python driver. Intake real; logistics and diagnostics return canned dicts. Every transition appends a timeline entry. **No LLM decides sequence**
- [ ] **09** `backend/scripts/run_episode.py` — walks the whole cascade on a real prescription and prints the timeline. **When this passes, the hard part is behind you**

---

## Phase 2 · API and the first real render — Sep 9

- [ ] **10** `backend/api/main.py` — FastAPI, plain uvicorn, containerised for App Runner. All eight endpoints. Episode serialises to the frozen v1 shape; diff field-by-field against `client/public/mocks/02-tests-identified.json` before moving on
- [ ] **11** Point the client at localhost — `NEXT_PUBLIC_USE_MOCKS=false`. The 21 components in `client/src/care/` already render every state; this is where wrong fields surface

---

## Phase 3 · Replace the stubs — Sep 9–10

- [ ] **12** `backend/tools/places.py` — nearby labs via Google Places (staying on Google: Amazon Location's India POI coverage for pathology labs is too thin to risk)
- [ ] **13** `backend/tools/ses.py` — booking request email. **SES sandbox: 1/second, 200/day.** Throttle the loop or a four-test prescription throws. Six verified addresses already exist
- [ ] **14** `backend/tools/calendar.py` — Google Calendar slot hold (no AWS equivalent exists)
- [ ] **15** `backend/agents/logistics.py` — Strands `@tool` functions over 12–14, on the fast model. **Claim idempotency inside the tool, before the send**
- [ ] **16** `backend/tools/s3.py` + `backend/scripts/deliver_report.py` — the report inbox, and a way to play the part of the lab so you can rehearse
- [ ] **17** `backend/agents/diagnostics.py` — values and reference ranges **from the report itself**, compared against stored history, then one significance call on the smart model
- [ ] **18** `POST /api/tick` + EventBridge schedule — the second trigger, and what makes this agentic rather than a document reader

---

## Phase 4 · Confirmation step — Sep 10 · runs parallel to Phase 3

- [ ] **19** Backend: `AWAITING_CONFIRMATION`, `POST /api/episodes/{id}/confirm`, and the `confirmation` object (`extracted_tests`, `confirmed_tests`, `edits_made`). Terminal until acted on
- [x] **19b** **Decided Sep 8: yes.** `high` books autonomously, `medium` confirms, `low`/no tests escalates. CLAUDE.md rule 3 rewritten to match; logic in `state/machine.py:route_after_extraction`
- [ ] **20** Frontend (Rakesh): state in `types.ts` + `stateLabels.ts`, mock `10-awaiting-confirmation.json`, then the screen — editable removable rows, urgency toggle, **prescription image alongside**. Never render `date` or `exam_findings`. See `frontend-brief-aws.md` §0 and §2.2

---

## Phase 5 · Deploy — Sep 11

**Ship the boring deploy first, then attempt AgentCore as an upgrade.** A failed AgentCore
run with no fallback live means no demo at all.

- [ ] **21** Container to App Runner. Point the EventBridge schedule at the deployed tick endpoint, not your laptop
- [ ] **22** Frontend rebuild + redeploy with the real `NEXT_PUBLIC_API_BASE_URL` — `output: 'export'` bakes it in at build time
- [ ] **23** AgentCore attempt — **only** with 21 and 22 green, timeboxed to one day, abandoned without regret

---

## Phase 6 · Make it demonstrable — Sep 12

- [ ] **24** Seed a patient profile and prior results so `TRENDS_ANALYZED` has something to compare. A trend with one point is not a trend
- [ ] **25** Walk both paths: happy path end to end, then `IMG_2071` → `NEEDS_HUMAN` → retry
- [ ] **26** **Fire the scheduler twice deliberately** and prove no duplicate email leaves. This is what step 06 exists for
- [ ] **27** README rewrite, architecture diagram, prior-work disclosure verbatim in README *and* Devpost

---

## Phase 7 · Ship — Sep 13–14

- [ ] **28** **Record the video Sep 13**, not the 14th. Max 5 minutes. Must explicitly cover the problem, who it's for, and why it matters
- [ ] **29** Devpost: Everyday Agents track, public repo with MIT in About, AWS Builder ID, live demo link, disclosure
- [ ] **30** Submit Sep 14 morning IST — not at the deadline

---

## Parallel track — Rakesh · do not let this slip

Three posts on builder.aws.com with "Agents for Humans" in the title are **0.6 bonus on a
1–5.6 scale** — over 10% of the range, from someone off the critical path. Cheapest points
available. Rakesh is now also carrying the UI; if something gives, **it must be said out
loud at the sync**, not dropped quietly.

- [ ] **B1** Post 1 — porting an agent stack to Strands · by Sep 10
- [ ] **B2** Post 2 — atomic idempotency on DynamoDB · by Sep 12
- [ ] **B3** Post 3 — asking the patient to confirm · by Sep 13
- [ ] **B4** Architecture diagram (needed by both README and video) · by Sep 12

---

## Cut — decided Sep 8, do not relitigate

| Cut | Why |
|---|---|
| Coverage check | Its own gate required the core running by Sep 10. It won't be |
| S3 + CloudFront frontend | Firebase Hosting is fine for a static export; judges can't tell |
| Fresh `nani-ai-aws` repo | That advice was for Sep 3. Costs a day now, buys nothing visible |
| AgentCore first | Demoted, not cut — it stays a goal, it stops being a dependency |
