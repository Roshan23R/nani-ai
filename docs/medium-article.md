# Agents for Humans: Building an Autonomous Care Episode Agent on AWS

*A practical look at building a long-running healthcare workflow with Strands Agents, Amazon Bedrock, and AWS serverless services.*

*This post was created for the AWS Agents for Humans hackathon, Everyday Agents track.*

Most healthcare software is good at recording what happened. It is much less good at remembering what should happen next.

A patient leaves a doctor's office with a prescription, a list of tests, and a vague promise to follow up when the reports are ready. The difficult part is not any single step. It is the chain of steps spread across different days: reading the prescription, finding a lab, booking the tests, waiting for the report, comparing the results with history, and deciding whether a consultation is necessary.

We built Nani AI to carry that chain forward.

Nani AI is an autonomous care-episode agent built with the Strands Agents SDK and Amazon Bedrock. A patient uploads a prescription, the system identifies the investigations, helps arrange them, waits for a report to arrive, and resumes the episode automatically. It is designed to summarise and flag information, never to diagnose or replace a clinician.

The most important design decision was also the least glamorous: the language model does not control the workflow.

## What it does

A document reader finishes when it returns JSON. A care episode does not finish when the prescription is understood. Nani AI carries the episode forward:

1. It reads the prescription, including handwriting, and extracts the tests ordered.
2. It finds nearby diagnostic labs and reasons about a practical option.
3. It sends a real booking-request email and can create a tentative calendar hold.
4. It waits for the report instead of asking the patient to manage another upload.
5. It extracts values and the reference ranges printed on the report itself.
6. It compares the results with the patient's history and requests follow-up only when a meaningful change is found.

The important part is step four. The system is not just a form that waits for a user to keep pushing buttons. It can pause, observe a later event, and resume the same episode.

## The episode state machine

Our workflow begins with `PRESCRIPTION_RECEIVED` and moves through explicit states:

```text
PRESCRIPTION_RECEIVED -> TESTS_IDENTIFIED -> LABS_SHORTLISTED
-> BOOKING_REQUESTED -> AWAITING_REPORT -> REPORT_RECEIVED
-> TRENDS_ANALYZED -> NORMAL or ANOMALY_FOUND
-> CONSULT_REQUESTED -> CLOSED
```

There are two important pauses in this journey. If the prescription is readable but not completely certain, the system enters `AWAITING_CONFIRMATION` and shows the patient what it understood. If the input is too poor to trust, it enters `NEEDS_HUMAN` instead of inventing an answer.

The other pause is more fundamental: `AWAITING_REPORT`. The system may remain in that state for hours or days. Nothing needs to run continuously. The episode is stored durably and a later event carries it forward.

That distinction changes how we think about an agent. Autonomy is not a model producing a confident answer in ten seconds. It is a system that can make a bounded decision, wait safely, and resume from durable state when the world changes.

## Why the Coordinator Is Ordinary Python

The project uses three Strands specialists:

- An intake specialist reads prescription images and PDFs.
- A logistics specialist finds nearby labs and coordinates booking requests.
- A diagnostics specialist reads reports, compares results with history, and evaluates whether a change matters.

These agents perform judgement. They do not decide the legal state transitions of the episode.

Those transitions live in a deterministic coordinator and a single state machine. The coordinator validates every move, appends an event to the timeline, persists the new episode, and invokes the next specialist only when the current state permits it.

This boundary matters especially in healthcare. A model can be useful for interpreting handwriting or summarising a report, but an unrestricted model should not be able to skip confirmation, send a duplicate booking request, or jump directly from an upload to a consultation.

The model answers questions such as:

- Which investigations appear on this prescription?
- Which nearby lab is the most practical option?
- Is the change between these two reports meaningful enough to flag?

The coordinator answers different questions:

- Is this transition legal?
- Has the patient confirmed the extracted tests?
- Has this side effect already been performed?
- Should the episode wait, retry, escalate, or close?

In short: agents provide judgement, while the application owns control flow.

## Confidence-Gated Autonomy

A healthcare system should not treat every extraction as equally trustworthy. We added a confidence gate after testing against difficult handwritten prescriptions.

The route is deterministic:

| Extraction confidence | Result |
|---|---|
| `high` | Continue toward lab discovery and booking. |
| `medium` | Show the extracted tests and wait for patient confirmation. |
| `low`, or no tests | Escalate to `NEEDS_HUMAN`. |

This is a more useful form of autonomy than either extreme. Always asking for confirmation makes the system slow and abdicates judgement. Never asking for confirmation makes the system overconfident. The confidence gate lets the system act when its input is strong, ask when it is uncertain, and stop when it is unsafe.

There is another important constraint: the agent reads the reference ranges from the report itself. We do not hardcode a universal medical reference table. Laboratories can use different methods and ranges, so the report is the source of truth for that particular result.

The application also stores extracted dates and examination findings without displaying them by default. Handwritten dates and vitals can be misread with surprising confidence. A wrong date or blood pressure shown in a health interface is worse than leaving an uncertain field out of the user-facing summary.

## AWS makes the waiting possible

The AWS implementation is designed around durable state and scheduled resumption. The patient starts an episode through API Gateway. Lambda invokes the application, and the coordinator persists progress in DynamoDB. When the tests are booked, the episode enters `AWAITING_REPORT`.

The main architecture is:

```text
Next.js static export
          |
          v
API Gateway -> Lambda -> deterministic coordinator
                              |
                 +------------+------------+
                 v            v            v
              Intake      Logistics     Diagnostics
                 \            |            /
                  +------ Amazon Bedrock

DynamoDB: episodes, history, profiles, idempotency
S3: uploaded reports and report inbox
EventBridge Scheduler: periodic heartbeat
Secrets Manager: integration credentials
SES: booking and consultation emails
```

There is no process sitting open for days. A report arrives in the S3 inbox. EventBridge Scheduler periodically invokes the heartbeat, which finds waiting episodes and resumes the diagnostics flow. The patient starts the episode; the scheduler carries it forward later. These are two different triggers for the same durable workflow.

DynamoDB stores the episode, the patient's previous results, and the timeline. S3 provides a durable place for reports to arrive. EventBridge Scheduler invokes the heartbeat, which looks for episodes that are ready to progress. AWS Secrets Manager keeps integration credentials out of the repository. Amazon SES handles booking-request and consultation emails.

Google Places and Google Calendar are focused third-party integrations. Places provides the local lab search, while Calendar provides a visible slot hold for the patient. AWS provides the runtime, coordination, persistence, scheduling, storage, and email layer around them.

## The engineering decisions that mattered

Several details made the difference between a model demo and a dependable workflow:

- **The hard part is waiting.** The episode is stored in DynamoDB while it waits. Nothing has to stay alive between the booking and the report.
- **Idempotency comes before side effects.** A DynamoDB conditional write claims a booking before SES sends the email, so a repeated scheduler invocation cannot send the same request twice.
- **Reference ranges come from the report.** The system does not hardcode a universal medical reference table because laboratories can use different methods and ranges.
- **Model routing is deliberate.** The stronger Claude Sonnet model handles prescription extraction and the significance decision. The faster Claude Haiku model handles lower-risk summarisation and lab selection. Haiku is not used for prescription extraction.
- **Booking is honest.** When a lab does not expose a booking API, the system sends a real booking-request email and creates a tentative calendar hold rather than pretending that an appointment was confirmed.
- **Ambiguity escalates.** The system summarises and flags; it does not diagnose. Weak or unreadable input goes to `NEEDS_HUMAN`.

## Idempotency Before Side Effects

A scheduler can fire twice. A client can retry a request. A network timeout can make the caller unsure whether an email was sent.

For that reason, every external side effect is preceded by an idempotency claim in DynamoDB. The claim uses a conditional write with a key such as:

```text
{episode_id}:{test_code}:{attempt}
```

The first invocation creates the claim and is allowed to send the booking request. A second invocation receives a conditional-write failure and skips the email. The operation is safe even when the heartbeat is delivered more than once.

This is a small implementation detail, but it is one of the most important parts of the system. A demo can survive a repeated log line. A patient should not receive two booking requests or two consultation holds because a scheduled function retried.

## Designing for the Patient's View

The frontend is a static Next.js application. It renders the Episode object and its timeline rather than exposing a collection of internal agent traces.

The patient can see:

- What was read from the prescription
- Which tests need confirmation
- Which labs were shortlisted
- Whether a booking request was sent
- Whether the system is waiting for a report
- What values were extracted from the report
- How the new values compare with previous results
- Why a follow-up was or was not requested

The API contract remains stable while the backend changes underneath it. This allows the existing UI and mock episodes to remain useful during the AWS migration. Mock mode also lets us test the complete experience without spending Bedrock credits or sending real email.

The timeline is particularly important. An autonomous system should not feel like a black box that occasionally changes status. Each meaningful action becomes a visible event, so the patient can understand what happened and the team can inspect the same story during a failure.

## What We Learned

The hardest part was not calling a model. It was deciding where the model should stop.

A strong agent system is not necessarily the one with the most freedom. In a long-running workflow, reliability comes from combining flexible judgement with rigid boundaries:

- Use a capable model for ambiguous language and images.
- Keep state transitions in code that can be tested and reviewed.
- Store progress durably before waiting.
- Claim side effects before performing them.
- Escalate ambiguity instead of filling gaps with plausible text.
- Make the timeline explain the work to both the patient and the developer.

The result is a different kind of agent demo. It does not end with a clever answer immediately after the upload. It shows a system that can begin with a prescription, pause when the real world requires patience, and continue days later without losing the thread.

That is the behaviour we want from an everyday agent: not more autonomy for its own sake, but dependable help across the parts of life that do not happen in one request.

## The stack

- Strands Agents SDK for the intake, logistics, and diagnostics specialists
- Amazon Bedrock for multimodal extraction, report analysis, and significance decisions
- AWS Lambda and Amazon API Gateway for the backend API and heartbeat handler
- Amazon DynamoDB for episodes, patient history, profiles, and idempotency claims
- Amazon S3 for uploaded documents and the report inbox
- Amazon EventBridge Scheduler for the autonomous heartbeat
- AWS Secrets Manager for integration credentials
- Amazon SES for booking and consultation emails
- Google Places API and Google Calendar API for focused third-party capabilities


The codebase also includes deterministic stubs, mock episodes, and tests for the state machine and coordinator. That makes it possible to test the complete care journey without requiring a live model call or sending a real email for every run.
