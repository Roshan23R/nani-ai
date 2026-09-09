# Build checklist — Nani AI on AWS

**Live working order. Tick as you go.** Drawn Sep 8 2026 · deadline **Sep 14, 5:00pm PDT**.

Strategy and reasoning live in `aws-build-plan.md`. This file is only *what to do next*.
One rule: **do not skip ahead.** The order encodes dependencies, and the spine (Phase 1)
blocks everything after it.

> ### ▶ NEXT UP — step 22, build and deploy the frontend
> The confirmation screen exists and the backend is live. Nothing has ever been
> built or deployed from `client/` in this repo: no `out/`, no `.firebaserc`.
> The live site is still the Google-era build calling Cloud Run.

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
- [x] **04b** Anonymised: every seeded name is invented, `demo-data/` gitignored

---

## Phase 1 · The spine, stubbed — Sep 8–9

**Goal: one episode walks upload → `CLOSED` locally, with fake labs and fake emails, every
step on the timeline.** Nothing here calls a third-party API. This is the week's hard part.

- [x] **05** `backend/state/machine.py` — 14 states, legal-transition table, `assert_legal()` raises. Confidence routing included. 26 tests green
- [x] **06** `backend/state/idempotency.py` — atomic claim, proven: 4 tests, 2 scheduler fires, exactly 4 emails
- [x] **07** `backend/tools/store.py` — single-table store, floats round-trip as floats, nulls preserved
- [x] **08** `backend/coordinator.py` — dispatch table, one bounded step per call, illegal moves raise
- [x] **09** `backend/scripts/run_episode.py` — full cascade upload → CLOSED, both paths verified

---

## Phase 2 · API and the first real render — Sep 9

- [x] **10** `backend/api/main.py` — 8 endpoints, diffed field-by-field against the frozen mocks
- [x] **11** Client wired to the live API — `api.ts` calls all endpoints and tolerates both the old bare-array and new wrapped collection shapes

---

## Phase 3 · Replace the stubs — Sep 9–10

- [x] **12** `backend/tools/places.py` — Google Places with a canned Kolkata fallback
- [x] **13** `backend/tools/ses.py` — live send verified, 1/sec throttle for the sandbox
- [x] **14** `backend/tools/calendar.py` — OAuth refresh-token flow, no extra SDK
- [x] **15** `backend/agents/logistics.py` — Strands agent with a @tool, structured output for lab choice
- [x] **16** `backend/tools/s3.py` + inbox — autonomous pickup verified in production
- [x] **17** `backend/agents/diagnostics.py` — reads ranges off the report, smart model for significance
- [x] **18** `POST /api/tick` + EventBridge every 2 min — verified advancing a live episode unattended

---

## Phase 4 · Confirmation step — Sep 10 · runs parallel to Phase 3

- [x] **19** `AWAITING_CONFIRMATION` + `/confirm` + the `confirmation` object
- [x] **19b** **Decided Sep 8: yes.** `high` books autonomously, `medium` confirms, `low`/no tests escalates. CLAUDE.md rule 3 rewritten to match; logic in `state/machine.py:route_after_extraction`
- [x] **20** Frontend confirmation step — landed in `a76e18a` (Neeraj): `AWAITING_CONFIRMATION` in types + stateLabels, mock 10, `ConfirmationPanel.tsx`, `confirmEpisode()`

---

## Phase 5 · Deploy — Sep 11

**Ship the boring deploy first, then attempt AgentCore as an upgrade.** A failed AgentCore
run with no fallback live means no demo at all.

- [x] **21** Lambda + API Gateway live at https://sbm1mkp3ql.execute-api.us-east-1.amazonaws.com
- [ ] **22** Frontend rebuild + redeploy with the real `NEXT_PUBLIC_API_BASE_URL` — `output: 'export'` bakes it in at build time
- [ ] **23** AgentCore attempt — **only** with 21 and 22 green, timeboxed to one day, abandoned without regret

---

## Phase 6 · Make it demonstrable — Sep 12

- [x] **24** `backend/scripts/seed_demo.py` — invented names, HB history 12.4 → 11.1 → 9.6
- [ ] **25** Walk both paths: happy path end to end, then `IMG_2071` → `NEEDS_HUMAN` → retry
- [x] **26** Double-fire proven — 4 tests, 2 fires, 4 emails
- [x] **27** README rewritten: architecture, models, setup, disclosure

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
