# Nani AI

**An autonomous care-episode agent** · Built with the Strands Agents SDK on Amazon Bedrock
Submitted to the AWS **Agents for Humans** hackathon — *Everyday Agents* track

*Like a grandmother who watches over your health — Nani AI keeps track of your care and speaks up only when something's genuinely wrong.*

---

## Prior work disclosure

Nani AI was originally built between **Aug 20–31, 2026** for Google's *All Things Agentic* hackathon, on Google Cloud (ADK, Gemini, Cloud Run, Firestore).

**This submission is a rebuild of the agent layer and infrastructure on AWS.** All agents are reimplemented with the **Strands Agents SDK** on **Amazon Bedrock**. Episode state moves to **DynamoDB**, the lab report inbox to **S3**, the heartbeat to **EventBridge Scheduler**, email to **Amazon SES**, and deployment to **Bedrock AgentCore Runtime**.

The problem framing, the 12-state machine design, and the Next.js frontend carry over from the original.

New in this submission:
- Full Strands multi-agent implementation (three specialists under a deterministic coordinator)
- Atomic idempotency claims using DynamoDB conditional writes, replacing a check-then-write pattern with a race window
- AgentCore Runtime deployment
- *(if built)* Insurance coverage checking — reads the patient's actual policy document and decides per test whether it's payable, citing the clause

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

## Status

🚧 **Build in progress.** Full setup instructions, architecture diagram, and demo links land before submission.

---

## Team

Shashank — agents, backend, deployment
Neeraj — UI, frontend deployment
Rakesh — content, documentation, testing

## License

MIT — see [LICENSE](LICENSE).
