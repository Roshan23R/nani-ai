# Nani AI

**An autonomous care-episode agent built with the Strands Agents SDK and Amazon Bedrock.**

Nani AI keeps track of a patient's care journey and speaks up when something genuinely needs attention.

> **Not medical advice.** Nani AI summarises medical information and flags changes. It does not diagnose. Ambiguous or unreadable input is escalated to a human.

## What It Does

A patient uploads a doctor's prescription. Nani AI:

1. Extracts the ordered tests, including handwritten prescriptions.
2. Flags urgent tests.
3. Finds and evaluates nearby diagnostic labs.
4. Sends a booking request and holds a calendar slot.
5. Waits for the lab report to arrive.
6. Detects and processes new reports automatically.
7. Extracts results and report-specific reference ranges.
8. Compares results with the patient's history.
9. Books a follow-up consultation only when results have meaningfully changed.

The system is designed around a complete care episode: intake, coordination, waiting, report processing, trend analysis, and follow-up.

## Confidence-Gated Autonomy

The coordinator is deterministic. `backend/state/machine.py` contains the transition table, and `assert_legal()` validates every state change. LLMs determine content, while the coordinator controls sequence.

Prescription extraction confidence determines the next action:

| Confidence | Action |
|---|---|
| `high` | Book the requested tests automatically |
| `medium` | Show the extracted tests and wait in `AWAITING_CONFIRMATION` |
| `low`, or no tests found | Escalate to `NEEDS_HUMAN` |

The system never guesses when a prescription or report is unclear.

## Architecture

```text
Next.js static export
        |
        | HTTPS
        v
API Gateway HTTP API
        |
        v
AWS Lambda
        |
        v
Deterministic coordinator
        |
        +-- Intake agent
        +-- Logistics agent
        +-- Diagnostics agent
                 |
                 +-- Amazon Bedrock
                 +-- Google Places
                 +-- Google Calendar
                 +-- Amazon SES

DynamoDB              Episode state, history, idempotency
Amazon S3             Lab report inbox
AWS Secrets Manager   Credentials and secrets
EventBridge Scheduler Periodic episode checks
```

The system has two triggers:

- A patient starts an episode through the API.
- EventBridge Scheduler periodically invokes the Lambda to resume waiting episodes.

## Models

| Job | Model |
|---|---|
| Prescription extraction | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Report reading and significance analysis | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Lab selection | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |

Haiku is used for summarisation and lab selection. Prescription extraction uses Sonnet.

## Setup

### Backend

```bash
cd backend

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cp .env.example .env
```

Configure AWS credentials with:

```bash
aws configure
```

Add the required Google API keys and other settings to `backend/.env`.

Seed demo data:

```bash
./venv/bin/python scripts/seed_demo.py
```

### Frontend

```bash
cd client
npm install
cp .env.example .env.local
```

For local mock mode:

```env
NEXT_PUBLIC_USE_MOCKS=true
NEXT_PUBLIC_API_BASE_URL=
```

Start the frontend:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Running the Backend

Test Strands and Bedrock connectivity:

```bash
cd backend
./venv/bin/python scripts/hello_strands.py
```

Run prescription intake:

```bash
./venv/bin/python scripts/run_intake.py ../demo-data/rx.jpg
```

Run the complete cascade without model calls or email delivery:

```bash
./venv/bin/python scripts/run_episode.py ../demo-data/rx.jpg --stub
```

`--stub` uses canned agent responses. Set `NANI_DRY_RUN=1` to build booking emails without sending them through SES.

## Testing

Run backend tests:

```bash
cd backend
./venv/bin/python -m pytest tests/ -q
```

The tests cover:

- Deterministic state transitions
- Coordinator routing
- Confidence-gated confirmation
- Prompt consistency
- Episode progression

Build the frontend:

```bash
cd client
npm run build
```

The frontend uses a static export. Changes to `NEXT_PUBLIC_*` variables require a new build.

## Live API Configuration

```env
NEXT_PUBLIC_USE_MOCKS=false
NEXT_PUBLIC_API_BASE_URL=https://<your-api-gateway>
NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID=<optional>
```

Check API health:

```bash
curl https://<api-base>/api/health
```

Expected response:

```json
{
  "ok": true,
  "service": "nani-ai"
}
```

## Deployment

Deploy the Lambda:

```bash
cd backend
./venv/bin/python scripts/deploy_lambda.py
```

Configure the scheduler:

```bash
./venv/bin/python scripts/setup_schedule.py
```

## Demo Flow

1. Upload a prescription.
2. Review or confirm the extracted tests.
3. Select a diagnostic lab.
4. Send a booking request.
5. Upload a report or wait for automatic report detection.
6. Review trends and flagged changes.
7. Book a follow-up consultation when needed.
8. Close the care episode when no further action is required.

## Status

The backend supports the complete care-episode flow:

```text
Prescription
    -> Extraction
    -> Confirmation
    -> Lab selection
    -> Booking request
    -> Report waiting
    -> Report processing
    -> Trend comparison
    -> Follow-up or closure
```

## Team

- Shashank: Agents, backend, and deployment
- Rakesh: UI, content, and documentation
- Neeraj: Frontend

## License

MIT. See [LICENSE](LICENSE).
