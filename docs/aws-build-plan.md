# Nani AI on AWS — build plan

**Hackathon:** Agents for Humans (AWS) · **Everyday Agents** track
**Deadline:** Sep 14, 2026, 5:00pm PDT = **5:30am IST, Sep 15**
**Days available:** 11 (today is Sep 3)
**Team:** Shashank (agents, backend, deploy) · Neeraj (UI, deploy) · Rakesh (content, docs, testing)

**Prior work:** Nani AI was built Aug 20–31, 2026 for Google's All Things Agentic hackathon on Google Cloud (ADK + Gemini + Cloud Run + Firestore). This is a rebuild of the agent layer and infrastructure on AWS. See section 11 for the disclosure requirement — this is not optional.

---

## 1. What changes and what doesn't

### Carries over unchanged
- The problem, the pitch, the care-episode cascade
- The 12-state machine and every state name
- The Episode object contract (plus optional coverage fields — see api-contract)
- The entire `client/` Next.js UI (repoint the API base URL)
- Demo patient profiles, the ESR trend story, mock payloads
- Domain knowledge: reference ranges printed on reports, no lab booking APIs, idempotency design
- Deterministic coordinator owning transitions, LLM specialists doing judgement

### Gets rewritten
| Google | AWS |
|---|---|
| ADK `LlmAgent` + `Runner` | **Strands Agents SDK** |
| Gemini 3.5 Flash / 3.1 Pro via Vertex | **Amazon Bedrock** models |
| Cloud Run | **Bedrock AgentCore Runtime** (see section 4) |
| Firestore | **DynamoDB** |
| Cloud Storage | **S3** |
| Cloud Scheduler | **EventBridge Scheduler** |
| Secret Manager | **AWS Secrets Manager** |
| Gmail API (send) | **Amazon SES** (see section 5) |

### Stays on Google (allowed — third-party APIs are fine)
- **Google Places API** — no AWS equivalent for nearby-lab lookup
- **Google Calendar API** — for the tentative slot hold

The rules explicitly permit third-party SDKs and APIs provided you're authorised to use them. Note both in the README so it's clear they're deliberate, not leftovers.

---

## 2. Strands port mapping

**Verify all API specifics against the quickstart before writing code** — the shapes below are the pattern, not gospel:
- Quickstart: `strandsagents.com/docs/user-guide/quickstart/overview/`
- Examples: `strandsagents.com/docs/examples/`
- **Read properly:** the AWS ML blog "Strands Agents SDK: A Technical Deep Dive into Agent Architectures and Observability." Technical Implementation asks how *skilfully* you use Strands, not just whether you imported it.

### Your three specialists

ADK `LlmAgent` with structured output maps to a Strands `Agent` with structured output. ADK tool-calling maps to Strands `@tool`-decorated functions.

```
backend/agents/
├── intake.py         reads prescription → tests, medicines, urgency
├── logistics.py      tools: find_labs, send_booking_request, hold_calendar_slot
├── diagnostics.py    extracts values + ref ranges, trends, significance
└── strands_setup.py  model config, shared session/state plumbing
```

**Keep `coordinator.py` almost as-is.** It's plain Python driving a state machine — only the calls into the agents change. This is your biggest time saving and also your strongest Technical Implementation story: a deterministic coordinator means an LLM never decides a medical state transition.

### Multi-agent pattern — decide this on day 1

Strands supports several patterns (agents-as-tools, swarm, graph, workflow). Your current design is a **deterministic driver calling specialists**, which is closest to agents-as-tools or a plain orchestrated workflow.

**Recommendation:** keep the deterministic coordinator, express the three specialists as Strands agents, and use Strands' own multi-agent primitive for the logistics agent's internal tool use. Do **not** hand the whole state machine to a swarm — you'd lose the safety property that's currently your best architectural argument.

### Model selection

Run `aws bedrock list-foundation-models --region <your-region>` and pick from what's actually enabled on your account. You need model access granted in the Bedrock console first — **do this on day 1, some models need a request.**

Keep the same routing shape you had:
- **Fast model** — extraction, classification, summary writing (~90% of calls)
- **Stronger model** — the significance decision only

Put the exact model IDs in the README.

---

## 3. Data model (DynamoDB)

Single-table design. One table, `nani-ai`.

| Entity | PK | SK | Notes |
|---|---|---|---|
| Episode | `EPISODE#{episode_id}` | `META` | the full episode object |
| Patient index | `PATIENT#{patient_id}` | `EPISODE#{created_at}#{episode_id}` | for listing episodes |
| Result history | `PATIENT#{patient_id}` | `RESULT#{test_code}#{date}` | trend comparison reads this |
| Idempotency claim | `IDEM#{key}` | `CLAIM` | conditional write |
| Patient profile | `PATIENT#{patient_id}` | `PROFILE` | name, city, dob |
| Policy (optional) | `PATIENT#{patient_id}` | `POLICY#{policy_id}` | parsed coverage rules |

### Idempotency gets *better* on AWS

In Firestore you checked-then-wrote. DynamoDB gives you an atomic claim:

```python
table.put_item(
    Item={"PK": f"IDEM#{key}", "SK": "CLAIM", "episode_id": eid, "claimed_at": now},
    ConditionExpression="attribute_not_exists(PK)",
)
# ConditionalCheckFailedException => already claimed, skip the side effect
```

One atomic operation, no race window. **Call this out in the video and README** — it's a genuine improvement over the original, and it's exactly the kind of detail Technical Implementation rewards.

Set a TTL attribute on idempotency items so they expire automatically.

---

## 4. Deployment — AgentCore vs the alternatives

The rules state AgentCore is a smart architectural choice that will strengthen the Technical Implementation score, but is not required. There's a purpose-built path: "Deploy a Strands Agent to AgentCore Runtime" in the AgentCore starter toolkit.

**Recommendation: AgentCore Runtime.** Reasons:
- It's an explicitly stated scoring lever on an equally weighted criterion
- There's a documented Strands→AgentCore path, so it's not a research project
- It gives you a managed runtime story rather than "I containerised it," which is what most entries will do

**Fallback if AgentCore fights you:** Lambda + API Gateway for the API and the tick handler, or App Runner if you want a long-running container. Decide by **end of Sep 9** — if AgentCore isn't working by then, fall back and don't look back.

**Also required:** a live demo link scores higher on Technical Implementation. Neeraj's static export can stay on Firebase Hosting (that's fine — it's just static files), or move to S3 + CloudFront if you want the whole thing on AWS. Firebase is the pragmatic choice; S3+CloudFront is the better story. Only move it if Neeraj has spare time.

---

## 5. Email — switch to SES, with one warning

Move booking and consult emails from Gmail API to **Amazon SES**. It removes the OAuth refresh-token fragility that nearly broke your last demo, and it's AWS-native so it strengthens the "uses AWS properly" story.

**The catch: SES starts in sandbox mode.** In sandbox you can only send *to* verified email addresses. For a demo that's fine — verify your own and Neeraj's addresses and use those as the "lab" and "doctor" recipients. Production access requires a support request that can take a day or more.

**Do the verification on day 1.** If you need production access, request it day 1 too.

Keep Google Calendar for the slot hold — there's no AWS equivalent and it's a real, visible API call. That means you still need one Google OAuth credential, but only for Calendar, which is a much smaller surface than before.

---

## 6. Architecture

```
client (Next.js, static)
        │
        ▼
  API (AgentCore Runtime / Lambda + API Gateway)
        │
   coordinator.py  ── deterministic 12-state machine
        │
   ┌────┴────┬──────────────┐
   ▼         ▼              ▼
 intake   logistics    diagnostics      ← Strands agents on Bedrock
            │  │
            │  └─ tools: Places · SES · Calendar
            │
   ┌────────┴───────────────────────┐
   ▼           ▼          ▼         ▼
DynamoDB      S3      Secrets   EventBridge
(state,    (report   Manager    Scheduler
 history,   inbox)              (heartbeat →
 idem)                           POST /api/tick)
```

Two triggers, same as before: the patient starts an episode, the scheduler carries it forward. That's what makes this agentic rather than a document reader — keep it prominent in the diagram.

---

## 7. The coverage check (EXTRA — build only if ahead)

Treated as a stretch goal, not core scope. Full design in `coverage-check-design.md`.

One line summary: the patient uploads their insurance policy PDF once; before booking, the agent decides per test whether it's payable under *that* policy and cites the clause.

**Decision gate: if the core cascade isn't running end to end on AWS by Sep 10, skip this entirely.** A working core beats a broken extension.

---

## 8. Repo and licensing — do today

Your current repo has **no LICENSE file**. AWS requires MIT or Apache, and the rules say the license must be detectable and visible at the top of the repository page (in the About section). Without it you risk failing Stage One, which is pass/fail.

```bash
cd /path/to/nani-ai
curl -sL https://raw.githubusercontent.com/licenses/license-templates/master/templates/mit.txt -o LICENSE
# or just paste the MIT text and fill in year + name
git add LICENSE && git commit -m "Add MIT license" && git push
```

Then check the repo's **About** panel on GitHub shows "MIT license". If it doesn't, the file name or format is wrong.

**Repo strategy:** use a **new repo** (`nani-ai-aws` or similar), not the existing one. Reasons: the AWS submission needs its own clean history and README, the Google submission stays intact for that hackathon's judging period (which runs to Oct), and a fresh repo makes the "built during the submission period" story cleaner. Copy `client/` across.

---

## 9. Timeline

| Date | Shashank | Neeraj | Rakesh |
|---|---|---|---|
| **Sep 3** | AWS account, Bedrock model access, SES verify, credits form, LICENSE, new repo | Copy `client/` to new repo, deploy blank | Read docs, set up AWS Builder ID |
| Sep 4 | Strands hello-world, port **intake** agent | UI unchanged — verify mocks still work | Draft blog post 1 (the port decision) |
| Sep 5 | Port **logistics** (Places, SES, Calendar tools) | Coverage UI mock (if in scope) | Source a real policy PDF |
| Sep 6 | Port **diagnostics** (extract, trend, significance) | Polish, accessibility pass | Architecture diagram v1 |
| Sep 7 | DynamoDB store + coordinator wiring | — | Blog post 1 published |
| Sep 8 | S3 inbox, EventBridge, idempotency | Repoint to live API | README rewrite |
| Sep 9 | **AgentCore deploy — or fall back to Lambda** | Deploy frontend | Test as a fresh user |
| Sep 10 | End-to-end on AWS. **Core must work today.** | Fix integration breaks | Blog post 2 |
| Sep 11 | Coverage check if ahead · **credits form closes 12pm PT** | — | Architecture diagram final |
| Sep 12 | Buffer, polish, failure paths | Buffer | Blog post 3 |
| **Sep 13** | **RECORD VIDEO** | Help with video | Upload, Devpost draft |
| Sep 14 | Buffer. **Submit by 2pm IST.** | — | Final checks |

**Record on Sep 13, not the 14th.** Same rule as last time, same reason.

---

## 10. Pre-flight checklist

### Accounts and access (Sep 3)
- [ ] AWS account created
- [ ] AWS Builder ID created (**required field on the submission**)
- [ ] Bedrock model access requested/granted in the console
- [ ] `aws bedrock list-foundation-models` returns the models you plan to use
- [ ] SES: sender identity verified, recipient addresses verified
- [ ] SES production access requested (if needed)
- [ ] Credits form submitted — **note the two forms differ between the rules and resources pages; the resources one is `forms.gle/Ssr8zLw4afKg114M7`. Ask in Discussions or submit both. Closes Sep 11, 12pm PT**
- [ ] Devpost registered for this hackathon, team formed
- [ ] Billing alert set (you have $50, not $300 — set it at $25)

### Repo (Sep 3)
- [ ] New repo created, **public**
- [ ] **LICENSE file (MIT or Apache) committed and showing in About**
- [ ] `client/` copied across
- [ ] `.gitignore` covers `.env*`, credentials, `demo-data/`
- [ ] Neeraj and Rakesh added as collaborators

### Build
- [ ] Strands installed, hello-world agent running
- [ ] Bedrock reachable from local
- [ ] DynamoDB table created
- [ ] S3 bucket created for the report inbox
- [ ] Secrets in AWS Secrets Manager (Places key, Calendar OAuth)
- [ ] EventBridge Scheduler rule pointed at the tick endpoint

---

## 11. Disclosure — required, not optional

The rules say participants may use frameworks and libraries freely but **must disclose any other pre-existing code or work incorporated into the Project.**

Your Google submission is public on Devpost and findable. Disclose plainly, in both the README and the Devpost description:

> **Prior work disclosure.** Nani AI was originally built between Aug 20–31, 2026 for Google's All Things Agentic hackathon on Google Cloud (ADK, Gemini, Cloud Run, Firestore). This submission is a rebuild of the agent layer and infrastructure on AWS: all agents are reimplemented with the Strands Agents SDK on Amazon Bedrock, state moves to DynamoDB, the report inbox to S3, the heartbeat to EventBridge Scheduler, and email to SES. The problem framing, state machine design, and Next.js frontend carry over. New in this submission: [list what's genuinely new — the Strands multi-agent implementation, the atomic DynamoDB idempotency claim, AgentCore deployment, and the coverage check if built].

Two reasons to lead with this rather than bury it:
1. It's a rules requirement and non-disclosure is a disqualification risk
2. Judges who spot it themselves will read it far less charitably than judges you told

**One honest caveat:** Creativity & Originality is one of five equally weighted criteria. A rebuild will score lower there than a fresh idea, however well disclosed. The counter is to make the *new* parts substantial — the Strands architecture, the idempotency improvement, AgentCore, and ideally the coverage check.

---

## 12. Submission checklist

- [ ] Track: **Everyday Agents**
- [ ] Text description — what it does, **who it's for**, how it works
- [ ] Public repo URL, with LICENSE visible in About
- [ ] README with full setup instructions
- [ ] Architecture diagram
- [ ] Video, **max 5 minutes**, public on YouTube or Vimeo
- [ ] Video pitch explicitly covers: **(1) the problem (2) who it's for (3) why it matters**
- [ ] AWS Builder ID
- [ ] Live demo link (scores higher)
- [ ] Prior-work disclosure in README and description
- [ ] Bonus: **3 blog posts on builder.aws.com**, "Agents for Humans" in the title, published before the deadline
- [ ] Submitted before Sep 14, 5:00pm PDT

---

## 13. Scoring — five equally weighted criteria

| Criterion | What earns it here |
|---|---|
| Technical Implementation | Skilful Strands use, AgentCore deploy, live demo, non-trivial code |
| Design | Complete product experience, not a proof of concept. Your UI is already strong. |
| Potential Impact | Specific real audience, credible problem, solution demonstrably addresses it |
| Creativity & Originality | **Your weakest — needs the new parts to be substantial** |
| Presentation | Video shows it working end to end; pitch is clear and easy to follow |

Plus up to **0.6 bonus** from blog posts. Final scores run 1 to 5.6, so 0.6 is over 10% of the range. **Three posts at 0.2 each is the cheapest score available — do not skip this.**

---

## 14. Biggest risks

1. **Treating this as a port.** It scores as one. Make the new work real.
2. **AgentCore rabbit hole.** Hard cutoff Sep 9; fall back to Lambda without regret.
3. **SES sandbox discovered late.** Verify addresses on day 1.
4. **Missing LICENSE.** Stage One is pass/fail. Do it today.
5. **Blog posts left to Sep 13.** They're 10% of the range and they need publishing time.
