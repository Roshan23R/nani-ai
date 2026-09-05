# Frontend brief — Neeraj (AWS rebuild)

**Hackathon:** Agents for Humans (AWS) · Everyday Agents track
**Deadline:** Sep 14, 5:00pm PDT (5:30am IST Sep 15) — **11 days**
**Your scope:** `client/` in the new repo, plus deploying it

---

## 1. The headline: your work mostly carries over

The backend is being rebuilt on AWS (Strands Agents, Bedrock, DynamoDB, S3, EventBridge). **The API surface is deliberately unchanged.** Same endpoints, same Episode object, same 12 states, same enums, same error shapes.

Your required change is one line:

```
NEXT_PUBLIC_API_BASE_URL=<new AWS endpoint>
```

Because `output: 'export'` bakes env vars in at build time, that needs a rebuild and redeploy — not a runtime config change.

So your 11 days are mostly **not** rebuilding. They're for the four things below.

---

## 2. What you actually need to do

### 2.1 Set up the new repo (Sep 3)
Copy `client/` into the new repo. Deploy something — even a blank page — on day one. Confirm the pipeline works before you need it.

### 2.2 Design polish — this is now worth real marks

Last hackathon, Design wasn't a named criterion. **Here it is one of five equally weighted criteria:** does the project deliver a complete, coherent product experience and not just a technical proof of concept?

That means polish is no longer optional garnish. Specific things worth your time:

- **Empty and loading states everywhere.** A blank panel reads as broken.
- **The timeline** — still the hero element. Make agent actions visually distinct from patient actions. If a judge only looks at one screen, this is it.
- **The results table and sparklines.** A falling line is instantly legible; make sure it reads at video resolution.
- **`NEEDS_HUMAN`** — a graceful, clearly-worded failure state with a working retry. Judges look for this.
- **Consistency pass.** Same spacing, same type scale, same button styles throughout. Incoherence is what separates "product" from "proof of concept."

### 2.3 The legacy MedLifeSim UI — decide and act

`src/renderer/` holds the old simulation UI, kept for internal use, with a `react-router-dom` shim.

**Recommendation: delete it from the new repo.** Reasons:
- Judges will clone and read this repo. Dead code that isn't part of the product reads as clutter and weakens the "coherent product experience" score.
- The shim is a source of confusing breakage for anyone running it fresh.
- It's not part of the submission.

Keep it in the old repo where it belongs. If you want it preserved, put it on a branch.

### 2.4 Live demo link — matters for scoring

The rules say projects with a live demo score higher on Technical Implementation. You already produce a static export, so this is nearly free.

**Firebase Hosting is fine** — it's just static files, and nothing in the rules requires the frontend on AWS. If you have spare time late on, S3 + CloudFront is a slightly better story for an AWS hackathon, but do not spend build days on it. Working beats on-brand.

---

## 3. Coverage feature — DO NOT BUILD YET

There's an optional insurance-coverage extension specced in `api-contract-v2.md` section 4. It is a **stretch goal on Shashank's side**, gated on the core cascade working end to end on AWS by Sep 10.

**Wait for Shashank to confirm it's shipping before you build any UI for it.** If it doesn't get built, the `coverage` field simply never appears and nothing breaks.

If it is confirmed, the display rules that matter are in `api-contract-v2.md` section 5. The one to internalise: **always show the clause reference next to the verdict.** "Clause 4.2" is what proves the agent read the document rather than guessing. It's the most important visual detail in the whole feature.

---

## 4. Video needs — plan for this

The video is max 5 minutes and Presentation is a full criterion. Two things from you:

- **The app must survive a continuous live run.** No refreshes, no manual nudges, no "let me just reload that." Test the full flow start to finish before Sep 13.
- **Readable at video resolution.** Check the timeline and the results table at the size they'll be recorded. If it needs scrolling or squinting, it fails on video.

---

## 5. Timeline

| Date | What |
|---|---|
| Sep 3 | New repo, `client/` copied, blank deploy working |
| Sep 4 | Verify mocks all still render; delete `src/renderer/` |
| Sep 5 | Polish pass: loading and empty states |
| Sep 6 | Polish pass: timeline, results table, consistency |
| Sep 7 | `NEEDS_HUMAN` state and retry flow |
| Sep 8 | Repoint to live AWS API, rebuild, redeploy |
| Sep 9 | Deploy final frontend |
| Sep 10 | Fix integration breaks with Shashank |
| Sep 11 | Coverage UI **only if confirmed**; otherwise buffer |
| Sep 12 | Full end-to-end rehearsal at video resolution |
| Sep 13 | **Recording day.** Help Shashank. No new features. |
| Sep 14 | Buffer only |

---

## 6. Definition of done

- [ ] Deployed, public URL, reachable
- [ ] All 12 states render without crashing
- [ ] Nulls handled — early states are mostly null
- [ ] Timeline distinguishes agent from patient actions
- [ ] Results table shows values, ranges, flags, trends
- [ ] Disclaimer visible wherever findings appear
- [ ] `NEEDS_HUMAN` renders with working retry
- [ ] Loading and empty states everywhere
- [ ] `src/renderer/` removed
- [ ] Mock mode still works with no backend (your demo-day safety net)
- [ ] Readable at video resolution
- [ ] Survives a full continuous run without intervention

---

## 7. Daily sync

15 minutes, three questions:
1. What is done
2. What is blocked
3. Does the end-to-end path still work

Raise any API contract mismatch at the sync — don't work around it silently. A mismatch found on Sep 12 costs both of you a day.
