# Frontend brief — Rakesh (AWS rebuild)

**Hackathon:** Agents for Humans (AWS) · Everyday Agents track
**Deadline:** Sep 14, 5:00pm PDT (5:30am IST Sep 15) — **6 days**
**Your scope:** `client/`, plus deploying it

> **Handover, Sep 8.** Neeraj is unavailable; Rakesh picks up the UI. This brief was
> rewritten for the time actually remaining. The old Sep 3–14 timeline is gone — we are
> six days out, not eleven, and the backend is roughly four days behind its own plan.
>
> Rakesh is now also carrying the three blog posts and the architecture diagram.
> **That is too much for one person. Raise it at the next sync** — the blog posts are
> 0.6 of a 5.6-point scale and must not silently drop.

---

## 0. START HERE — the one thing that does not exist yet

**`AWAITING_CONFIRMATION` has never been built.** Not in this repo, not in the Google
build, not on any branch. Verified on Sep 8:

```
git log --all -S 'AWAITING_CONFIRMATION'   →  one hit: the commit that added it to the contract
```

`client/src/care/types.ts` declares 12 states and does not include it. The frozen v1
contract — the one from the Google hackathon — lists the same 12. The state was invented
on **Sep 7**, after extraction testing showed the model misreads dates and vitals, so
there is nothing to carry over.

Every `confirm` string you will find in `client/src/` lives in `src/renderer/`, the legacy
simulation UI. `ConfirmModal.tsx` there is a generic dialog in a different design system.
It is **not** reusable for this — see §2.3 for what the screen actually needs.

**This is your first and highest-priority piece of work.**

---

## 1. The headline: everything else carries over

The backend is being rebuilt on AWS (Strands Agents, Bedrock, DynamoDB, S3, EventBridge).
**The API surface is deliberately unchanged.** Same endpoints, same Episode object, same
enums, same error shapes. The one addition is the confirmation step.

Your required config change is one line:

```
NEXT_PUBLIC_API_BASE_URL=<AWS endpoint>
```

Because `output: 'export'` bakes env vars in at build time, that needs a **rebuild and
redeploy** — not a runtime config change. Do not discover this on Sep 13.

Keep `NEXT_PUBLIC_USE_MOCKS=true` until the backend is live. Mock mode is your demo-day
safety net; do not break it.

---

## 2. What you actually need to do

### 2.1 Get it running and verify the mocks (Sep 8)

`client/` stays in this repo — the "copy to a fresh repo" plan from Sep 3 is **cancelled**,
it costs a day and buys nothing a judge can see. Run the app against
`client/public/mocks/01`–`09` and confirm every state still renders.

### 2.2 Build the confirmation step — NEW, core scope, do it first

Full spec in `api-contract-v2.md` §4. Three parts:

**a. Teach the app the state.** Add `AWAITING_CONFIRMATION` to the `EpisodeState` union in
`client/src/care/types.ts`, and to `STATE_LABELS`, `STATE_SHORT_LABELS`, `STATE_HINTS` and
`TERMINAL_STATES` in `client/src/care/stateLabels.ts`. UI label: **"Confirm what we read"**.

It is **terminal until acted on** — polling must stop. Nothing happens until the patient
responds. A poller that keeps spinning here is a bug.

**b. Add a mock.** `client/public/mocks/10-awaiting-confirmation.json`, following the shape
of `02-tests-identified.json` plus the `confirmation` object from contract §4.3.

**c. Build the screen:**

- The extracted test list, each row **editable and removable**
- **The prescription image alongside it** — without this the confirmation is meaningless,
  because the patient has nothing to check against. This is not optional.
- An urgency toggle per test (urgent / routine)
- Primary action: **"Confirm and find labs"**
- Secondary: **"I need to re-upload"** → back to upload

Send the **full** list back with `keep` flags, not just the kept ones — the backend records
what the patient rejected.

**Two fields the API returns that you must NOT display:** `date` and `exam_findings`. The
model misreads DD.MM.YY dates (a real 17.03.17 came back as 2014-03-14, and this reproduced
again on Sep 8) and misreads vitals. They are stored for completeness. Showing a wrong blood
pressure in a health app is worse than showing nothing.

`medicines`, `complaint`, `diagnosis` and `patient` may be shown read-only as context. They
are not editable and drive nothing.

> **Note on `confirmation.required`.** Decided Sep 8: it is **false when extraction
> confidence is `high`** — the agent books those without asking. `medium` routes to
> `AWAITING_CONFIRMATION`; `low` or no tests goes to `NEEDS_HUMAN`.
>
> **This does not change your work,** but it does mean not every episode passes through
> your screen. Build it to render whenever the episode is in `AWAITING_CONFIRMATION`, and
> do not assume it always will be.

**Make this screen good.** Design is one of five equally weighted criteria and asks whether
this is a complete product or a technical proof of concept. An agent that says "here's what
I read, confirm before I book" is the most defensible thing in the whole product.

### 2.3 Design polish — worth real marks

Last hackathon Design wasn't a named criterion. **Here it is one of five equally weighted
criteria.**

- **Empty and loading states everywhere.** A blank panel reads as broken.
- **The timeline** — still the hero element. Make agent actions visually distinct from
  patient actions. If a judge looks at one screen, it's this one.
- **The results table and sparklines.** A falling line is instantly legible; make sure it
  reads at video resolution.
- **`NEEDS_HUMAN`** — a graceful, clearly-worded failure state with a working retry.
  This path is live today: the dental prescription (`IMG_2071`) extracts zero tests and
  gates straight to `NEEDS_HUMAN`, so you can test it for real.
- **Consistency pass.** Same spacing, type scale and button styles throughout.

### 2.6 Error panel: warning vs error styling — NEW, Sep 9

`ErrorPanel.tsx` is hardcoded red everywhere. That is wrong for one common case:
a prescription we read perfectly well that simply orders no tests. It stops the
episode, so it lands in `NEEDS_HUMAN` and renders here — but it is a normal
outcome, and alarm red makes a working agent look broken.

The backend now says which it is. `error.severity` is `"warning"` or `"error"`.
**Treat a missing value as `"error"`** — older episodes in DynamoDB predate the field.

| code | severity | when |
|---|---|---|
| `NO_TESTS_FOUND` | `warning` | Read fine, no investigations on the page |
| `PRESCRIPTION_UNREADABLE` | `error` | Handwriting illegible, or the file could not be opened |
| `REPORT_UNREADABLE`, `NO_LABS_FOUND`, `EXTRACTION_FAILED` | `error` | Genuine failures |

**File: `client/src/care/components/ErrorPanel.tsx`.** Five hardcoded values to
make severity-dependent:

| line | now | warning should be |
|---|---|---|
| 24 | `border: '1px solid #f0c8c8'` | amber border, e.g. `#f0dcb4` |
| 25 | `background: 'linear-gradient(165deg, #fffafa 0%, #fff 55%)'` | warm tint, e.g. `#fffdf7` |
| 36 | icon chip `background: '#fdeaea'` | `#fdf4e3` |
| 37 | icon chip `border: '1px solid #f0c0c0'` | `#f0dcb4` |
| 40 | icon `color: '#c83030'` | `#b5761a` |
| 78 | `<MonoButton variant="danger">` | the neutral/primary variant |

`AlertTriangle` (line 44) is right for both — keep it.

**Also: `client/src/care/types.ts`.**

```ts
export type ErrorCode =
  | 'PRESCRIPTION_UNREADABLE'
  | 'NO_TESTS_FOUND'      // add
  // ...existing codes

export interface EpisodeError {
  code: ErrorCode | string
  message: string
  action_hint: string
  retryable: boolean
  severity?: 'warning' | 'error'   // add; absent means 'error'
}
```

**Copy also changed.** The backend no longer puts exception text in `message` —
"Something went wrong while processing this episode: Unsupported file type 'heic'…"
is gone. Messages are now plain sentences a patient can act on, so the panel can
show `message` as the headline without pre-processing it.

**Worth testing:** upload `IMG_2071.jpg` (a dental prescription, no
investigations) against the live API. That is the `warning` path end to end.

---

### 2.4 Delete the legacy MedLifeSim UI

`client/src/renderer/` holds the old simulation UI with a `react-router-dom` shim. **Delete
it.** Judges clone and read this repo; dead code that isn't part of the product weakens the
"coherent product experience" score, and the shim breaks for anyone running it fresh. Put it
on a branch if you want it preserved.

### 2.5 Live demo link

Projects with a live demo score higher on Technical Implementation, and you already produce
a static export. **Firebase Hosting is fine** — nothing requires the frontend on AWS, and
the S3 + CloudFront move is **cut**. Working beats on-brand.

---

## 3. Coverage feature — CUT, do not build

The insurance-coverage extension in `api-contract-v2.md` §5 is **cancelled**, not deferred.
Its own gate required the core cascade running end to end by Sep 10, and it will not be.
The `coverage` field simply never appears and nothing breaks.

---

## 4. Video needs

Max 5 minutes, and Presentation is a full criterion.

- **The app must survive a continuous live run.** No refreshes, no manual nudges. Test the
  full flow start to finish before Sep 13.
- **Readable at video resolution.** Check the timeline and results table at recording size.
  If it needs squinting, it fails on video.

---

## 5. Timeline — rewritten Sep 8

| Date | What |
|---|---|
| **Sep 8** | Get `client/` running, verify mocks 01–09, delete `src/renderer/` |
| **Sep 9** | `AWAITING_CONFIRMATION`: types, labels, mock 10 |
| **Sep 10** | Confirmation screen built against mock 10 |
| **Sep 11** | Point at Shashank's live API, rebuild, redeploy |
| **Sep 12** | Integration fixes · `NEEDS_HUMAN` retry · loading and empty states · rehearse at video resolution |
| **Sep 13** | **Recording day.** No new features. |
| **Sep 14** | Buffer only |

Blog posts and the architecture diagram run alongside this. If something has to give,
**say so at the sync** — do not quietly drop the posts.

---

## 6. Definition of done

- [ ] Deployed, public URL, reachable
- [ ] All 13 states render without crashing (12 + `AWAITING_CONFIRMATION`)
- [ ] Nulls handled — early states are mostly null
- [ ] Confirmation screen: editable tests, prescription image alongside, working confirm
- [ ] Polling stops in `AWAITING_CONFIRMATION`
- [ ] `date` and `exam_findings` NOT displayed anywhere
- [ ] Timeline distinguishes agent from patient actions
- [ ] Results table shows values, ranges, flags, trends
- [ ] Disclaimer visible wherever findings appear
- [ ] `NEEDS_HUMAN` renders with working retry
- [ ] Loading and empty states everywhere
- [ ] `src/renderer/` removed
- [ ] Mock mode still works with no backend
- [ ] Readable at video resolution
- [ ] Survives a full continuous run without intervention

---

## 7. Daily sync

15 minutes, three questions:
1. What is done
2. What is blocked
3. Does the end-to-end path still work

Raise any API contract mismatch at the sync — don't work around it silently. A mismatch
found on Sep 12 costs both of you a day.
