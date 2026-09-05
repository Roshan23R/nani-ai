# Content brief — Rakesh

**Hackathon:** Agents for Humans (AWS) · Everyday Agents track
**Deadline:** Sep 14, 5:00pm PDT (5:30am IST Sep 15)
**Your scope:** blog posts, architecture diagram, README, document sourcing, testing

You're not writing agent code. What follows is worth more to the score than another pair of hands on the backend, and none of it needs Shashank or Neeraj to unblock you.

---

## 1. Your biggest single contribution: the blog posts

**This is worth up to 0.6 points on a scale that runs 1 to 5.6.** That's over 10% of the total range, and it's the cheapest score available in the entire hackathon.

### The rules
- Published publicly on **builder.aws.com**
- **"Agents for Humans" in the title**
- Covers your journey building and implementing AWS for this hackathon
- **0.2 points each, maximum 0.6** — so **three posts**
- Must be published before the Sep 14 deadline
- (The rules were updated Aug 12 to *remove* the `#AgentsforHumans` hashtag requirement — you just need the phrase in the title)

### Three posts that write themselves

**Post 1 — "Agents for Humans: Porting a Care Agent from ADK to Strands"**
Nani AI existed on Google's ADK. We rebuilt the agent layer on Strands. What mapped cleanly, what didn't, what we'd do differently. This is genuinely useful content — very few people have done this port, and AWS's own audience would want to read it. Target Sep 7.

**Post 2 — "Agents for Humans: Why an LLM Should Never Decide a Medical State Transition"**
The deterministic-coordinator pattern. Three Strands agents do judgement; plain Python owns the 12-state machine. Why that matters in healthcare, and how atomic DynamoDB conditional writes stop a double-fired scheduler from double-booking a lab test. This is the strongest technical story the project has. Target Sep 10.

**Post 3 — "Agents for Humans: The Hard Part Is the Waiting"**
Most agent demos finish in ten seconds. A real care episode takes days. How the agent survives with nothing running — S3 inbox, EventBridge heartbeat, state in DynamoDB — and picks up a lab report on its own. Target Sep 12.

### How to write them well
- Read a few existing posts on builder.aws.com first and match the house style
- Include real code snippets, not pseudocode — ask Shashank for the actual files
- Include the architecture diagram
- Be honest about what didn't work. Posts that admit friction read as real and are more useful.
- 800–1,500 words each is plenty

**Publish as you go. Do not leave all three to Sep 12.** Posts need to be live before the deadline and platforms can be slow.

---

## 2. Architecture diagram

A stated submission requirement, and it feeds the Technical Implementation and Presentation scores. It also goes in all three blog posts and the video.

**What it must show:**
- The client (Next.js, static)
- The API layer (AgentCore Runtime, or Lambda + API Gateway if we fall back)
- The deterministic coordinator and the 12-state machine
- Three Strands agents: intake, logistics, diagnostics
- Bedrock behind them
- DynamoDB, S3, Secrets Manager, EventBridge Scheduler
- The two triggers: **the patient starts an episode, the scheduler carries it forward**
- Third-party: Google Places, Google Calendar, Amazon SES

**The one thing not to get wrong:** the two triggers. That's the whole reason this is an agent and not a document reader. Make the scheduler path visually obvious, not a footnote.

Tools: draw.io, Excalidraw, or Mermaid. Whatever you're fastest in. **Export as PNG or SVG and commit it to the repo** — don't leave it in a cloud tool behind a login.

v1 by Sep 6 (blog post 1 needs it), final by Sep 11.

---

## 3. README

Judges will read this. It's often the only thing they read besides the video.

Take the existing Nani AI README as your base — it's strong — and change:

- **All Google references → AWS.** Strands, Bedrock, DynamoDB, S3, EventBridge, SES.
- **A requirements table** mapping each AWS requirement to where it's satisfied in the code. The old README had one of these for Google's requirements; it worked well.
- **Setup instructions that actually work from scratch.** Clone, install, configure, run. Test them yourself on a clean machine — this is section 5 of your job.
- **The prior-work disclosure**, verbatim from `aws-build-plan.md` section 11. This is a rules requirement. Near the top, not buried.
- Live demo link and the AWS Builder ID.

---

## 4. Source a real insurance policy PDF

For the optional coverage feature. Even if it doesn't get built, this costs you an hour and unblocks Shashank if it does.

**What to find:** Indian insurers publish full policy wordings as PDFs on their own sites (IRDAI requires it). Star Health, HDFC Ergo, Niva Bupa, ICICI Lombard. You want one with:
- A proper numbered exclusions section
- Ideally an **OPD or diagnostic benefit** — that gives a mix of covered/not-covered/partial, which demos far better than uniform rejection

**Rules:** don't commit the insurer's PDF to the public repo (it's their copyrighted document) and don't name the insurer in the video in a way that looks like a claim about their product. "A real policy wording from a major Indian insurer" is the right framing.

Also write a short **synthetic** policy (8–10 pages, fictional insurer, realistic structure) that *can* live in the repo, so judges cloning the code can run the feature. Label it clearly as synthetic.

---

## 5. Test as a fresh user — genuinely valuable

You have something Shashank and Neeraj don't: you haven't built it, so you don't know what it's supposed to do.

**Around Sep 9–10:**
- Clone the repo on your own machine and follow the README exactly. Every place you get stuck is a place a judge gets stuck.
- Use the deployed app as a new user. Try things that shouldn't work — upload a photo of a cat, a blank PDF, a prescription with no tests on it.
- Check every one of the 12 states renders.
- File what you find as GitHub issues, not WhatsApp messages.

This directly protects Design and Technical Implementation.

---

## 6. Devpost submission draft

Around Sep 12, draft the Devpost submission text so Shashank isn't writing it at 1am on the 14th.

**The pitch must explicitly answer three things** — the rules name them:
1. **The problem** you're solving
2. **Who it's for**
3. **Why it matters**

Don't be clever about this. Write three clearly separated paragraphs, one per question. Judges are checking they're there.

---

## 7. Your timeline

| Date | What |
|---|---|
| Sep 3 | AWS Builder ID created. Read the build plan and the Strands docs. |
| Sep 4 | Draft blog post 1 |
| Sep 5 | Source the real policy PDF; write the synthetic one |
| Sep 6 | Architecture diagram v1 |
| Sep 7 | **Blog post 1 published** |
| Sep 8 | README rewrite |
| Sep 9 | Fresh-user testing, file issues |
| Sep 10 | **Blog post 2 published** |
| Sep 11 | Architecture diagram final |
| Sep 12 | **Blog post 3 published.** Devpost draft. |
| Sep 13 | Video upload, Devpost submission prepared |
| Sep 14 | Final checks. Submit by 2pm IST. |

---

## 8. Definition of done

- [ ] AWS Builder ID created and passed to Shashank
- [ ] **3 blog posts live on builder.aws.com, "Agents for Humans" in each title**
- [ ] Architecture diagram committed to the repo as PNG or SVG
- [ ] README rewritten, setup instructions tested on a clean machine
- [ ] Prior-work disclosure in place near the top
- [ ] Real policy PDF sourced (not committed); synthetic policy written (committed)
- [ ] Fresh-user test done, issues filed
- [ ] Devpost draft written, all three pitch questions answered explicitly
- [ ] Video uploaded public to YouTube
