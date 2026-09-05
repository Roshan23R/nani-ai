# Coverage check — design (OPTIONAL extension)

**Status: stretch goal.** Build only if the core cascade runs end to end on AWS by **Sep 10**. If it doesn't, skip this entirely — a working core beats a broken extension.

**Estimated cost:** 3–4 hours once the cascade exists.

---

## 1. What it does

The patient uploads their insurance policy PDF once. From then on, before the agent books any test, it decides **per test** whether that test is payable under *that specific policy* — and cites the clause.

Example output:

> **Serum ferritin** — covered under your OPD benefit (clause 3.7). You pay ₹0.
> **TSH** — not payable. Clause 4.2 excludes outpatient diagnostics. You pay ₹450.
> **CBC** — partly covered. Your remaining OPD limit covers ₹200 of ₹900. You pay ₹700.
>
> **Estimated out of pocket: ₹1,150**

---

## 2. Why it's worth building

**It makes the AWS submission an extension rather than a port.** Creativity & Originality is one of five equally weighted criteria and it's where a rebuild scores worst. This is new capability, not relocated capability.

**The negative answer is the best demo moment available.** An agent that says "this is NOT covered, here is the exact clause, and here's what it'll cost you" proves it read a document rather than hallucinating from general knowledge. A cheerful false "covered" proves nothing.

**It fits the track brief precisely.** Everyday Agents is about home, money, health, errands — working quietly and surfacing a real decision. This is money and health in one step.

**It reuses machinery you already have.** Document reading, structured extraction, a step in the cascade, a decision with three outcomes. No new patterns.

---

## 3. Where it sits in the flow

One new state, between two existing ones:

```
TESTS_IDENTIFIED → COVERAGE_CHECKED → LABS_SHORTLISTED
```

**Skipped entirely when no policy is on file.** The episode goes straight from `TESTS_IDENTIFIED` to `LABS_SHORTLISTED` exactly as it does today. This is important — it means the feature is additive and can't break the core path.

---

## 4. Two-phase design (do it this way)

### Phase 1 — parse the policy once, at upload

Reading a 50-page policy PDF on every test is slow and expensive. Parse it once into a compact rule set and store that.

```
POST /api/patients/{id}/policy  →  parse  →  store rules in DynamoDB
```

Stored shape (`PATIENT#{id}` / `POLICY#{policy_id}`):

```json
{
  "policy_id": "pol_3a9f",
  "insurer": "Example General Insurance",
  "plan_name": "Health Secure Individual",
  "sum_insured": 500000,
  "opd_benefit": { "present": true, "annual_limit": 5000, "used_to_date": 1200 },
  "covered_categories": [
    { "category": "diagnostic_tests", "clause": "3.7",
      "condition": "payable under OPD benefit up to annual limit" }
  ],
  "exclusions": [
    { "clause": "4.2", "summary": "Outpatient diagnostics excluded unless linked to hospitalisation" },
    { "clause": "4.9", "summary": "Consumables and administrative charges not payable" }
  ],
  "waiting_periods": [
    { "clause": "5.1", "condition": "pre-existing diseases", "months": 36 }
  ],
  "parsed_at": "2026-09-11T08:20:00Z"
}
```

### Phase 2 — decide per test, at episode time

The coverage agent gets the rule set plus the test list. That's a small prompt, a fast model, and a cheap call.

**Three outcomes per test, plus one honest fourth:**
- `covered` — payable, clause cited
- `not_covered` — excluded, clause cited
- `partial` — payable up to a sub-limit
- `unknown` — could not determine confidently

`unknown` matters. **Never let the agent guess "covered."** A wrong "covered" costs the patient real money and is exactly the failure mode a judge will probe.

---

## 5. The Indian-policy reality — plan for it

Indian health policies mostly **exclude outpatient lab tests.** Coverage is built around hospitalisation. So with a plain base policy, nearly every answer is "not covered."

Two ways to handle this, both legitimate:

**Option A — lean into it.** The demo line becomes: *"None of Shashank's three tests are payable. Clause 4.2 excludes outpatient diagnostics. He'll pay roughly ₹1,600 — and Nani AI tells him now, before he books, instead of him finding out at the counter."* Honest, useful, and it proves the agent read the document.

**Option B — use a policy with an OPD rider.** Several Indian insurers offer optional OPD or health-checkup benefits covering diagnostics up to a limit. That yields a **mix** — one covered, one excluded, one hitting a sub-limit.

**Recommendation: Option B.** A mix demos considerably better because it shows the agent making *different* calls on *different* line items, which is the whole point. Uniform rejection could be a hardcoded string; a mix can't be.

Rakesh is sourcing a policy — the brief asks specifically for one with an OPD or diagnostic benefit.

---

## 6. Documents

**For testing and the demo:** a real policy wording PDF from a major Indian insurer. These are published publicly on insurer websites (IRDAI requires it). A real 40–60 page document with dense legal language is a genuinely hard extraction problem, and handling it is impressive precisely because it's messy.

**Two cautions:** don't commit the insurer's PDF to the public repo, and don't name the insurer in the video in a way that reads as a claim about their product. "A real policy wording from a major Indian insurer" is the right framing.

**For the repo:** a synthetic 8–10 page policy, fictional insurer, realistic structure, clearly labelled as synthetic. This is what lets judges clone the code and actually run the feature.

**Why both:** you test against something hard and honest, and you ship something reproducible. Reproducibility feeds Technical Implementation.

---

## 7. Safety framing

Same discipline as the medical side, and for the same reason:

- The agent **estimates coverage; it does not adjudicate claims.** An insurer decides.
- Every coverage output carries that disclaimer, visibly.
- Costs are labelled as estimates.
- `unknown` is rendered as uncertainty, never as good news.

Say this in the video. Health *and* money in one feature is exactly where a judge will look for overreach.

---

## 8. Implementation checklist

- [ ] `COVERAGE_CHECKED` added to the state machine, skippable
- [ ] `POST /api/patients/{id}/policy` — upload and parse
- [ ] `GET /api/patients/{id}/policy` — poll parse status
- [ ] Policy rule set stored in DynamoDB
- [ ] Coverage agent (Strands) — decides per test from the rule set
- [ ] `coverage` object populated on the episode
- [ ] `POLICY_UNREADABLE` and `POLICY_NOT_FOUND` error codes
- [ ] `coverage_agent` added as a timeline actor
- [ ] Synthetic policy committed to the repo
- [ ] Real policy tested against, not committed
- [ ] Disclaimer wired into the UI wherever coverage appears
- [ ] Neeraj told it's confirmed **before** he builds UI for it

---

## 9. Decision gate

**Sep 10, end of day.** If the core cascade — prescription → tests → labs → booking → wait → autonomous pickup → trend → consult — is not running end to end on AWS, **do not start this.**

If it is running, this is the highest-value 4 hours available to you.
