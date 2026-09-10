# Nani AI

**An autonomous care-episode agent** · Built with the Strands Agents SDK on Amazon Bedrock
Submitted to the AWS **Agents for Humans** hackathon — *Everyday Agents* track

*Like a grandmother who watches over your health — Nani AI keeps track of your care and speaks up only when something's genuinely wrong.*

---

## Prior work disclosure

Nani AI was originally built between **Aug 20–31, 2026** for Google's *All Things Agentic* hackathon, on Google Cloud (ADK, Gemini, Cloud Run, Firestore).

**This submission is a rebuild of the agent layer and infrastructure on AWS.** All agents are reimplemented with the **Strands Agents SDK** on **Amazon Bedrock**. Episode state moves to **DynamoDB**, the lab report inbox to **S3**, the heartbeat to **EventBridge Scheduler**, email to **Amazon SES**, and deployment to **AWS Lambda behind API Gateway**.

The problem framing, the state machine design, and the Next.js frontend carry over from the original.

New in this submission:
- Full Strands multi-agent implementation — three specialists under a deterministic coordinator
- **Atomic idempotency claims** using DynamoDB conditional writes, replacing a check-then-write pattern that had a race window
- **Confidence-gated autonomy** — a new `AWAITING_CONFIRMATION` step. The agent books without asking when its read of the prescription is strong, shows the patient what it read when the read is merely good, and escalates to a human when it is weak
- Reference ranges read from each report rather than a hardcoded table

Original repository: https://github.com/Kali-Decoder/nani-ai

---

## What it does

A patient uploads a doctor's prescription. The agent:

1. Reads it — including handwriting — and extracts the tests ordered, flagging what's urgent
2. Finds nearby diagnostic labs and reasons about the best choice
3. Sends a real booking-request email and holds a calendar slot
4. **Waits** — in production, for days. Nothing is running.
5. Picks the lab report up **on its own** when it lands in a watched inbox
6. Extracts values and the reference ranges printed on the report, and compares against the patient's history
7. Books a follow-up consultation **only if something has meaningfully changed**

The demo is not "can a model read a PDF." It is: **one episode, multiple systems, real waiting, autonomous resumption.**

> **Not medical advice.** The agent summarises and flags; it never diagnoses. Every analysis carries a disclaimer. Unreadable or ambiguous input escalates to a human (`NEEDS_HUMAN`) rather than being guessed at.

---

## How it decides how much to decide

The coordinator is **deterministic**. `backend/state/machine.py` holds one transition
table and `assert_legal()` is the only way through it; an illegal move raises. No LLM
ever chooses a state. Agents decide *content* — which tests were ordered, which lab,
whether a change matters — and the coordinator decides *sequence*.

Autonomy is then gated on how well the agent read the page:

| Extraction confidence | What the agent does |
|---|---|
| `high` | Books the tests without asking |
| `medium` | Shows the patient what it read and waits (`AWAITING_CONFIRMATION`) |
| `low`, or no tests found | Escalates to a human (`NEEDS_HUMAN`), retryable |

That middle row exists because extraction is good but imperfect. Testing against real
handwritten prescriptions found the test list read reliably while dates and vitals were
misread *confidently* — so both are stored and neither is ever displayed.

---

## Architecture

```
  Next.js static export
          │  HTTPS
          ▼
  API Gateway (HTTP API)
          │
      AWS Lambda ─────────────────────► one handler, two callers
          │                             HTTP request, or {"nani_tick": true}
   coordinator.py  ── deterministic state machine
          │
   ┌──────┼───────────────┐
   ▼      ▼               ▼
 intake  logistics    diagnostics        ← Strands agents on Bedrock
          │  │
          │  └─ Google Places · SES · Google Calendar
          │
   ┌──────┴──────┬─────────────┬──────────────────┐
   ▼             ▼             ▼                  ▼
DynamoDB        S3        Secrets Manager   EventBridge Scheduler
(state,      (report                        every 2 min → tick
 history,     inbox)
 idempotency)
```

**Two triggers.** The patient starts an episode; the scheduler carries it forward. The
second one is what makes this an agent rather than a form.

### Models

| Job | Model | Why |
|---|---|---|
| Prescription extraction | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | 4/4 tests on a hard handwritten page, zero fabrications |
| Report reading, significance | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | The one judgement call worth the stronger model |
| Lab selection | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Summarising and choosing, ~90% of calls |

Haiku is never used for extraction: it invents tests that were not on the page.

---

## Running it

```bash
# backend
cd backend
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

# credentials: AWS via `aws configure`, Google keys in backend/.env (gitignored)
cp .env.example .env      # then fill in GOOGLE_PLACES_API_KEY etc.

# one-time AWS setup
./venv/bin/python scripts/seed_demo.py          # demo patients + prior results

# prove the pieces work
./venv/bin/python scripts/hello_strands.py      # Strands reaches Bedrock
./venv/bin/python scripts/run_intake.py ../demo-data/rx.jpg
./venv/bin/python scripts/run_episode.py ../demo-data/rx.jpg --stub   # whole cascade, no cost

# tests
./venv/bin/python -m pytest tests/ -q

# deploy
./venv/bin/python scripts/deploy_lambda.py
./venv/bin/python scripts/setup_schedule.py
```

`--stub` swaps in canned agents: no Bedrock calls, no email, no cost. `NANI_DRY_RUN=1`
builds emails without handing them to SES.

### Frontend

```bash
cd client && npm install && npm run build
```

`output: 'export'` bakes `NEXT_PUBLIC_*` in at build time, so changing the API URL needs
a rebuild and redeploy — it is not a runtime config change.

---

## Testing

### Backend unit tests

```bash
cd backend
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m pytest tests/ -q
```

Covers the deterministic state machine, coordinator routing (including confirmation
confidence gates), and prompt parity.

### Backend smoke scripts

Requires AWS credentials (`aws configure`). Optional Google keys live in `backend/.env`
(see `.env.example`).

```bash
cd backend

# Bedrock reachable via Strands
./venv/bin/python scripts/hello_strands.py

# Intake only (real Bedrock call — costs credits)
./venv/bin/python scripts/run_intake.py ../demo-data/rx.jpg

# Full cascade with stubbed agents — no Bedrock / SES cost
./venv/bin/python scripts/run_episode.py ../demo-data/rx.jpg --stub
```

- `--stub` swaps in canned agents (no model calls, no email).
- `NANI_DRY_RUN=1` builds booking emails without handing them to SES.

API liveness:

```bash
curl https://<api-base>/api/health
# → {"ok": true, "service": "nani-ai"}
```

### Frontend — mock mode (no backend)

Default for local UI work. No AWS required.

```bash
cd client
npm install
cp .env.example .env.local
```

Set in `.env.local`:

```
NEXT_PUBLIC_USE_MOCKS=true
NEXT_PUBLIC_API_BASE_URL=
```

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Manual checklist**

- Landing → launch app → dashboard
- Upload a prescription — mocks advance and pause at `AWAITING_CONFIRMATION`
- Confirm / edit / remove tests, or **I need to re-upload**
- Episode mock cycler (bottom-right when mocks are on) — step all states including
  `NEEDS_HUMAN` and `CLOSED`
- Report upload when awaiting report
- Analytics and episodes list still render

Mock payloads: `client/public/mocks/` (`01`–`10`).

### Frontend — against the live API

```
NEXT_PUBLIC_USE_MOCKS=false
NEXT_PUBLIC_API_BASE_URL=https://<your-api-gateway>
NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID=<optional>
```

Restart `npm run dev`. For static export / Firebase Hosting, **rebuild** after any
`NEXT_PUBLIC_*` change — values bake in at build time.

**End-to-end checklist**

1. `GET /api/health` returns ok
2. Upload prescription → intake
3. Medium confidence → confirmation screen → **Confirm and find labs**
4. Labs shortlisted → booking requested (SES)
5. Upload report (or wait for S3 inbox + EventBridge tick)
6. Trends → anomaly **or** normal → consult / closed
7. Unreadable / no-tests Rx → `NEEDS_HUMAN` → retry

### Production build sanity

```bash
cd client
npm run build   # static site → out/
```

| Layer | How |
|---|---|
| Automated backend | `pytest tests/` |
| Stub cascade | `run_episode.py … --stub` |
| UI only | `NEXT_PUBLIC_USE_MOCKS=true` |
| UI + AWS | mocks off + live `NEXT_PUBLIC_API_BASE_URL` |
| Liveness | `GET /api/health` |

---

## Status

The backend cascade runs end to end on AWS: upload → extract → confirm → labs → booking
emails → **wait** → autonomous report pickup → trend comparison → consult → closed.
The confirmation screen is the remaining frontend work.

---

## Team

Shashank — agents, backend, deployment
Rakesh — UI, content, documentation
Neeraj — frontend (original build)

## License

MIT — see [LICENSE](LICENSE).
